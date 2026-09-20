#!/usr/bin/env python3
"""Hash-bound release evidence, separate from free-form writing.

  template WORK --body 正文_3分钟版.md > /tmp/release-template.json
  check WORK                         read .发布证据.json; never publish anything

Exit 0 = ready for owner confirmation, 1 = known defect/stale evidence,
2 = input/tool error, 3 = PROVISIONAL (required evidence unavailable).
Attestations are reviewer claims, NOT authentication or proof of an independent
agent, listening, copyright permission, platform approval or publication.
"""
from __future__ import annotations
import argparse
from datetime import datetime
import json
import math
from pathlib import Path
import re
import subprocess
from fuben_engine import inspect_path, load_policy, sha256

REVIEW_KINDS = ('facts', 'story', 'account_policy', 'media')


def local(work, name):
    if not isinstance(name, str) or not name:
        raise ValueError('evidence path missing')
    path = (work / name).resolve()
    if not path.is_relative_to(work.resolve()):
        raise ValueError('evidence path escapes work directory')
    return path


def inputs(work, body):
    result = {body: sha256(local(work, body))}
    for name in ('设定.md', '.fuben.json'):
        if (work / name).is_file():
            result[name] = sha256(work / name)
    return result


def probe_media(path):
    try:
        proc = subprocess.run(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(path)],
                              capture_output=True, text=True, timeout=30)
    except FileNotFoundError as exc:
        raise ValueError('ffprobe 不可用，媒体未实测；不能把文字估时作为替代') from exc
    if proc.returncode != 0:
        raise ValueError('ffprobe failed: ' + proc.stderr[-500:])
    data = json.loads(proc.stdout)
    duration = float(data.get('format', {}).get('duration', 0))
    types = {s.get('codec_type') for s in data.get('streams', [])}
    if not math.isfinite(duration) or duration <= 0 or not {'audio', 'video'} <= types:
        raise ValueError('口播成片需可解析的正时长、音轨和视频轨')
    return {'duration_seconds': duration, 'stream_types': sorted(types), 'measurement': 'ffprobe',
            'listened_or_viewed_by_tool': False}


def template(work, body='正文.md'):
    return {'schema_version': 1, 'body': body, 'inputs_sha256': inputs(work, body),
            'profile': 'short' if '3分钟' in body else 'full', 'constraints': {},
            'reviews': {key: {'status': 'UNVERIFIED', 'reviewer': '', 'mode': 'solo', 'reviewed_at': '',
                               'reviewed_inputs_sha256': inputs(work, body),
                               'reviewed_media_sha256': None,
                               'evidence': {'path': '审核报告.md', 'sha256': ''}} for key in REVIEW_KINDS},
            'media': {'path': '', 'sha256': ''}, 'owner_publication_authorized': False}


def check(work, *, manifest_name='.发布证据.json', probe=probe_media):
    work = Path(work).resolve()
    result = {'schema_version': 1, 'scope': 'release_evidence_only', 'issues': [], 'checked': [],
              'published': False, 'automatic_publication': False, 'attestation_identity_verified': False}

    def issue(severity, code, message):
        result['issues'].append({'severity': severity, 'code': code, 'message': message})

    path = local(work, manifest_name)
    manifest = None
    body = '正文.md'
    if not path.exists():
        issue('MISSING', 'RELEASE_EVIDENCE_ABSENT', '缺少可选发布阶段的 .发布证据.json；不影响起草，但不能宣称可发布')
    else:
        try:
            manifest = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(manifest, dict) or manifest.get('schema_version') != 1:
                raise ValueError('unsupported release evidence schema')
            body = manifest['body']
            local(work, body)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            issue('ERROR', 'RELEASE_SCHEMA_ERROR', str(exc))
            manifest = None
    profile = manifest.get('profile', 'full') if manifest else 'full'
    mechanical = inspect_path(local(work, body), profile=profile)
    result['mechanical'] = mechanical
    for item in mechanical['findings']:
        if item['severity'] in ('ERROR', 'BLOCK'):
            issue(item['severity'], item['rule_id'], item['message'])
    if manifest:
        try:
            current = inputs(work, body)
            if manifest.get('inputs_sha256') != current:
                issue('BLOCK', 'STALE_INPUT_EVIDENCE', '正文/设定/profile 已变，旧审核失效；对当前版本重审，不只刷新哈希')
            else:
                result['checked'].append('body_and_optional_brief_hashes')
            reviews = manifest.get('reviews')
            if not isinstance(reviews, dict):
                raise ValueError('reviews must be an object')
            for kind in REVIEW_KINDS:
                review = reviews.get(kind)
                if not isinstance(review, dict) or review.get('status') == 'UNVERIFIED':
                    issue('MISSING', 'REVIEW_' + kind.upper(), kind + ' 尚未获得具名审核证据')
                    continue
                status = review.get('status')
                if status in ('BLOCK', 'FIX'):
                    issue('BLOCK', 'REVIEW_' + status, kind + ' 审核要求修订')
                    continue
                if status != 'APPROVED':
                    raise ValueError('unknown review status for ' + kind)
                if review.get('reviewed_inputs_sha256') != current:
                    issue('BLOCK', 'STALE_REVIEW_BINDING', kind + ' 签署仍绑定旧正文/设定，不能只刷新发布清单哈希')
                if kind == 'media' and review.get('reviewed_media_sha256') != manifest.get('media', {}).get('sha256'):
                    issue('BLOCK', 'STALE_MEDIA_REVIEW', '成片变了，听感/字幕审核没有同步重做')
                if not isinstance(review.get('reviewer'), str) or not review['reviewer'].strip():
                    raise ValueError('approved review needs reviewer identity')
                if review.get('mode') not in ('solo', 'independent'):
                    raise ValueError('review mode must disclose solo or independent')
                stamp = datetime.fromisoformat(review.get('reviewed_at', '').replace('Z', '+00:00'))
                if stamp.utcoffset() is None:
                    raise ValueError('review timestamp needs timezone')
                evidence = review.get('evidence', {})
                file = local(work, evidence.get('path'))
                if not file.is_file() or file.stat().st_size == 0:
                    issue('MISSING', 'REVIEW_FILE_MISSING', kind + ' 审核依据不存在或为空')
                elif sha256(file) != evidence.get('sha256'):
                    issue('BLOCK', 'STALE_REVIEW_FILE', kind + ' 审核依据哈希失效')
                else:
                    result['checked'].append('reviewer_attestation:' + kind + ':' + review['mode'])
            media = manifest.get('media', {})
            if not isinstance(media, dict):
                raise ValueError('media must be an object')
            if not media.get('path'):
                issue('MISSING', 'MEDIA_MISSING', '没有实际成片；未进行时长/音轨验证，更未完成听感或字幕 QA')
            else:
                media_path = local(work, media['path'])
                if not media_path.is_file():
                    issue('MISSING', 'MEDIA_FILE_MISSING', '成片文件不存在')
                elif sha256(media_path) != media.get('sha256'):
                    issue('BLOCK', 'STALE_MEDIA', '成片与审核绑定的媒体版本不一致')
                else:
                    result['media_probe'] = probe(media_path)
                    result['checked'].append('media_metadata_not_listening')
                    constraints = manifest.get('constraints', {})
                    if not isinstance(constraints, dict) or set(constraints) - {'max_duration_seconds'}:
                        raise ValueError('unsupported release constraints')
                    maximum = constraints.get('max_duration_seconds')
                    if maximum is not None:
                        if type(maximum) not in (int, float) or not math.isfinite(maximum) or maximum <= 0:
                            raise ValueError('max_duration_seconds must be positive')
                        if result['media_probe']['duration_seconds'] > maximum:
                            issue('BLOCK', 'EXPLICIT_DURATION_LIMIT', '成片超过用户明确的时长上限；不是按通用90秒模板裁切')
            if manifest.get('owner_publication_authorized') is not True:
                issue('MISSING', 'OWNER_AUTHORIZATION_MISSING', '尚无账号主明确发布授权；工具不会代发')
        except (OSError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired) as exc:
            issue('ERROR', 'EVIDENCE_OR_MEDIA_ERROR', str(exc))
    severities = {x['severity'] for x in result['issues']}
    result['status'] = ('ERROR' if 'ERROR' in severities else 'BLOCKED' if 'BLOCK' in severities
                        else 'PROVISIONAL' if 'MISSING' in severities else 'READY_FOR_OWNER_CONFIRMATION')
    result['exit_code'] = {'ERROR': 2, 'BLOCKED': 1, 'PROVISIONAL': 3, 'READY_FOR_OWNER_CONFIRMATION': 0}[result['status']]
    result['note'] = '哈希仅防止旧版证据误用，不认证签字人，也不证明观看/独立审核发生；最终发布由账号主决定。'
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['template', 'check'])
    parser.add_argument('work', type=Path)
    parser.add_argument('--body', default='正文.md')
    parser.add_argument('--manifest', default='.发布证据.json')
    args = parser.parse_args(argv)
    try:
        result = template(args.work.resolve(), args.body) if args.command == 'template' else check(args.work, manifest_name=args.manifest)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result.get('exit_code', 0)
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({'status': 'ERROR', 'error': str(exc)}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
