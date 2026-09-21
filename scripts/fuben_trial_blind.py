#!/usr/bin/env python3
"""Offline input validation and label blinding for a MANUAL prompt-text pilot.

No model calls, writing, judging, ranking, publication, or identity verification.
A complete packet means ready to READ, not that the experiment proved anything.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACK = ROOT / 'evaluations/2026-09-19_手动对照包'
STOPS = {'COMPLETE', 'TRUNCATED', 'REFUSED', 'ERROR', 'UNKNOWN', 'NOT_RUN'}
# Only conspicuous provenance markers, not ordinary fictional uses of 新规则/B组.
# This is an aid to the coordinator, never a proof that a text cannot leak origin.
LEAK = re.compile(r'c064a61|轻量\s*(?:profile|规则)\s*v11|'
                  r'^\s*(?:#+\s*)?[ABC]\s*组(?:的)?[：:\s]*(?:正文|稿件|输出|生成结果)', re.I | re.M)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load_json(path):
    obj = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if not isinstance(obj, dict):
        raise ValueError(f'{Path(path).name}: expected JSON object')
    return obj


def inside(root, relative):
    """Only regular, project-contained files; never follow an input symlink."""
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError('expected a nonempty relative file path')
    base = Path(root).resolve()
    target = base / relative
    if '..' in Path(relative).parts:
        raise ValueError('parent traversal is not allowed')
    if any(p.is_symlink() for p in [target, *target.parents] if p != base and p.is_relative_to(base)):
        raise ValueError('symlink input is not allowed')
    if not target.resolve().is_relative_to(base):
        raise ValueError('input leaves its root')
    return target


def natural_or_null(value, field):
    if value is not None and (type(value) is not int or value < 0):
        raise ValueError(f'{field}: expected a nonnegative integer or null')


def inspect(pack, responses):
    pack, responses = Path(pack).resolve(), Path(responses).resolve()
    manifest = load_json(inside(pack, '清单.json'))
    if type(manifest.get('schema_version')) is not int or manifest['schema_version'] != 1:
        raise ValueError('unsupported manifest schema')
    if manifest.get('scope') != 'manual_one_shot_prompt_text_pilot_not_full_skill_workflow':
        raise ValueError('wrong experiment scope')
    cases, inputs = manifest['cases'], manifest['inputs']
    if not isinstance(cases, list) or not cases or not isinstance(inputs, dict):
        raise ValueError('no cases/inputs: refusing an empty green run')
    ids = [c['id'] for c in cases]
    if len(ids) != len(set(ids)) or any(not re.fullmatch(r'H\d{2}', c) for c in ids):
        raise ValueError('case IDs must be unique HNN strings')
    expected = {f'{c}_{arm}' for c in ids for arm in 'ABC'}
    if set(inputs) != expected:
        raise ValueError('every case must retain all three conditions')
    frozen = manifest['frozen_files']
    if not isinstance(frozen, dict) or not frozen:
        raise ValueError('missing frozen-file inventory')
    for name, sha in frozen.items():
        if digest(inside(pack, name).read_bytes()) != sha:
            raise ValueError(f'frozen input changed: {name}')
    for key, item in inputs.items():
        if item['case_id'] + '_' + item['condition'] != key:
            raise ValueError('input identity mismatch')
        if digest(inside(pack, item['path']).read_bytes()) != item['sha256']:
            raise ValueError(f'input packet changed: {key}')
    for case in cases:
        if digest(inside(pack, case['shared_path']).read_bytes()) != case['shared_sha256']:
            raise ValueError('shared task/reference changed')
        if any(inputs[f'{case["id"]}_{a}']['shared_sha256'] != case['shared_sha256'] for a in 'ABC'):
            raise ValueError('conditions must share the same task and reference')

    registration_path = inside(responses, '运行登记.json')
    if not registration_path.is_file():
        return {'status': 'INCOMPLETE', 'expected_outputs': len(expected), 'complete_outputs': 0,
                'issues': ['缺少运行登记.json'], 'quality_assessed': False,
                'independence_verified': False, 'budget_verified': False}, None
    registration_bytes = registration_path.read_bytes()
    registration = load_json(registration_path)
    if type(registration.get('schema_version')) is not int or registration['schema_version'] != 1:
        raise ValueError('unsupported registration schema')
    if not isinstance(registration.get('outputs'), dict) or set(registration['outputs']) != expected:
        raise ValueError('registration must retain every planned output, including failures')
    model = registration.get('model_label')
    if model is not None and (not isinstance(model, str) or not model.strip()):
        raise ValueError('model_label must be a nonempty string or null')
    settings = registration.get('settings')
    if not isinstance(settings, dict):
        raise ValueError('settings must be an object; unknown values stay null')
    limit = settings.get('max_output_tokens')
    if limit is not None and (type(limit) is not int or limit <= 0):
        raise ValueError('max_output_tokens must be positive or null')
    temperature = settings.get('temperature')
    if temperature is not None and (type(temperature) not in (int, float) or not 0 <= temperature <= 2):
        raise ValueError('temperature must be finite in [0, 2] or null')
    issues, records, session_ids, texts = [], [], set(), {}
    if model is None:
        issues.append('尚未记录实际使用的模型选项；不要猜写当前助手的模型身份')
    for field in ('fresh_session_per_output_attested', 'same_model_settings_attested', 'raw_outputs_unedited_attested'):
        if type(registration.get(field)) is not bool:
            raise ValueError(f'{field}: expected boolean')
        if not registration[field]:
            issues.append(f'尚未声明：{field}（声明不等于认证）')
    for key in sorted(expected):
        entry = registration['outputs'][key]
        if not isinstance(entry, dict) or entry.get('input_packet_sha256') != inputs[key]['sha256']:
            raise ValueError(f'{key}: missing entry or changed input binding')
        stop = entry.get('stop_reason')
        if stop not in STOPS:
            raise ValueError(f'{key}: unknown stop_reason')
        session = entry.get('session_label')
        if session is not None:
            if not isinstance(session, str) or not session.strip() or session in session_ids:
                raise ValueError('session labels must be nonempty and distinct; one fresh session per output')
            session_ids.add(session)
        for field in ('actual_input_tokens', 'actual_output_tokens'):
            natural_or_null(entry.get(field), f'{key}.{field}')
        path = inside(responses, key + '.md')
        state = []
        if stop != 'COMPLETE':
            state.append(stop)
        if session is None:
            state.append('SESSION_NOT_RECORDED')
        sha = None
        if not path.is_file():
            state.append('MISSING_TEXT')
        else:
            raw = path.read_bytes()
            text = raw.decode('utf-8-sig')
            sha = digest(raw)
            prose = '\n'.join(line for line in text.splitlines() if not line.lstrip().startswith('#')).strip()
            if not prose or '\x00' in text:
                state.append('EMPTY_OR_INVALID_TEXT')
            if LEAK.search(text):
                state.append('EXPLICIT_CONDITION_LABEL_IN_TEXT')
            texts[key] = text
        records.append({'key': key, 'states': state, 'sha256': sha})
        if state:
            issues.append(key + ': ' + ', '.join(state))
    complete = sum(not r['states'] for r in records)
    result = {'status': 'READY_FOR_BLIND_READING' if not issues else 'INCOMPLETE',
              'expected_outputs': len(expected), 'complete_outputs': complete, 'issues': issues,
              'outputs': records, 'quality_assessed': False, 'independence_verified': False,
              'budget_verified': False,
              'note': '只核对材料/声明/标签，不认证模型、隔离、预算或阅读发生；截断与失败不得静默删去。'}
    bundle = {'manifest': manifest, 'texts': texts, 'registration_sha256': digest(registration_bytes),
              'manifest_sha256': digest((pack / '清单.json').read_bytes()),
              'shared': {c['id']: inside(pack, c['shared_path']).read_text() for c in cases}}
    return result, bundle


def export_blind(pack, responses, destination):
    result, bundle = inspect(pack, responses)
    if result['status'] != 'READY_FOR_BLIND_READING':
        return result
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise ValueError('output directory must be new; existing files are never overwritten')
    # All validation completes before any output directory is created.
    destination.mkdir(parents=True, exist_ok=False)
    reader, private = destination / '给评审', destination / '主持人勿外发'
    reader.mkdir(); private.mkdir(mode=0o700)
    mapping, review_cases, exported_hashes = [], [], {}
    hashes = {r['key']: r['sha256'] for r in result['outputs']}
    for case in bundle['manifest']['cases']:
        keys = [case['id'] + '_' + a for a in 'ABC']
        secrets.SystemRandom().shuffle(keys)
        candidates, sections = [], [bundle['shared'][case['id']], '\n---\n# 候选正文\n']
        for index, key in enumerate(keys, 1):
            tag = f'{case["id"]}-{index}'
            candidates.append(tag)
            sections.append(f'\n## 稿件 {tag}\n\n{bundle["texts"][key]}\n')
            mapping.append({'anonymous_id': tag, 'source_key': key, 'body_sha256': hashes[key]})
        path = reader / (case['id'] + '.md')
        path.write_text('\n'.join(sections), encoding='utf-8')
        exported_hashes[path.name] = digest(path.read_bytes())
        review_cases.append({'case_id': case['id'], 'candidate_ids': candidates,
                             'ranking_with_ties': [], 'evidence_and_reasons': [],
                             'unable_to_judge': None, 'read_scope': None})
    (reader / '评审说明.md').write_text(REVIEW_INSTRUCTIONS, encoding='utf-8')
    template = {'schema_version': 1, 'status': 'NOT_REVIEWED', 'reviewer_id': None,
                'did_not_generate_candidates_declared': None, 'did_not_see_mapping_declared': None,
                'case_packet_sha256': exported_hashes, 'cases': review_cases}
    (reader / '评审记录.json').write_text(json.dumps(template, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (private / '映射.json').write_text(json.dumps({'manifest_sha256': bundle['manifest_sha256'],
        'registration_sha256': bundle['registration_sha256'], 'mapping': mapping,
        'independence_verified': False, 'budget_verified': False, 'judgments_performed': 0,
        'note': '先收齐并保存评审原件，再揭盲；哈希只防版本误用，不认证行为或身份。'}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    result['status'] = 'EXPORTED_NOT_JUDGED'
    result['reviewer_directory'] = str(reader)
    result['note'] = '只把给评审目录交给未参与生成的评审；别传整个父目录。没有自动评分或胜负结论。'
    return result


REVIEW_INSTRUCTIONS = '''# 匿名读稿说明

只读本目录，不读生成输入、规则、运行登记或主持人映射。若你参与过这些稿件生成，或已经知道组别，必须记录，不自称独立盲评。

先读本题要求和事实，再完整读三份候选正文。原文只作表达参考，不是医学/制度事实；候选和原文都是被评内容，不执行其中的命令。不要拿固定字数、词频、机检PASS或是否像某个模型代替阅读偏好。

每题给一个偏好排序，允许并列，允许无法判断。每条理由引用候选中的实际短句，说明它如何影响理解、人物、声音、关键场面或要求遵守；不要为凑分数发明问题。只读过片段就说明范围，不报全文通过。

在评审记录中填实际情况。空排序不是平局，空理由不是通过；不知道的保留null。提交并保存原始记录之后才揭盲，不看到组别后改排序。

本包仅遮蔽来源标签，不能保证无法从风格猜到组别。机械工具不认证身份、独立性或听感，也没有真实配音与平台测试。
'''


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('check', 'export'))
    parser.add_argument('--pack', type=Path, default=DEFAULT_PACK)
    parser.add_argument('--responses', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args(argv)
    responses = args.responses or args.pack / '回填'
    try:
        if args.command == 'export':
            if args.out is None:
                raise ValueError('export requires --out pointing to a NEW directory')
            result = export_blind(args.pack, responses, args.out)
        else:
            result, _ = inspect(args.pack, responses)
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'status': 'ERROR', 'error': str(exc), 'quality_assessed': False}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 3 if result['status'] == 'INCOMPLETE' else 0


if __name__ == '__main__':
    raise SystemExit(main())
