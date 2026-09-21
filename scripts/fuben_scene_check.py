#!/usr/bin/env python3
"""Optional local-span scene evidence. Global word presence is not local consistency.

Optional 场面证据.json:
  {"schema_version":1,"body_sha256":"...","scenes":[
    {"name":"饭桌","start_line":8,"end_line":20,"quotes":["原文"],"props":["碗"]}]}
No evidence supplied => NOT_ASSESSED, not 'scene QA passed'. Lines are physical
1-based body-file lines. This tool checks literal spans, not scene interpretation.
"""
import argparse
import json
from pathlib import Path
import re
from fuben_engine import inspect_path, finding, finish, emit


def norm(text):
    return re.sub(r'[^一-鿿0-9A-Za-z]', '', text)


def inspect_scenes(work):
    work = Path(work)
    report = inspect_path(work, run_style=False, components={'metrics'})
    report['scene_status'] = 'NOT_ASSESSED'
    if not report['mechanical_pass']:
        return report
    evidence_path = work / '场面证据.json'
    if not evidence_path.exists():
        report['findings'].append(finding('SCENE_NOT_ASSESSED', 'NOTE', 'evidence',
            '未提供可选的逐场行范围证据；不以全篇搜到几个词冒充局部一致，不要求为了创作补表。'))
        return finish(report)
    try:
        data = json.loads(evidence_path.read_text(encoding='utf-8'))
        if data.get('schema_version') != 1 or not isinstance(data.get('scenes'), list) or not data['scenes']:
            raise ValueError('场面证据需 schema_version=1 和非空 scenes')
        if data.get('body_sha256') != report['inputs']['body_sha256']:
            report['findings'].append(finding('STALE_SCENE_EVIDENCE', 'BLOCK', 'evidence', '场面证据不是当前正文版本'))
            return finish(report)
        lines = (work / '正文.md').read_text(encoding='utf-8-sig').splitlines()
        for scene in data['scenes']:
            start, end = scene.get('start_line'), scene.get('end_line')
            if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines):
                raise ValueError('场面起止行不合法')
            local = norm('\n'.join(lines[start - 1:end]))
            count = 0
            for key in ('quotes', 'props'):
                entries = scene.get(key, [])
                if not isinstance(entries, list):
                    raise ValueError('quotes/props 必须是数组')
                for value in entries:
                    if not isinstance(value, str) or not norm(value):
                        raise ValueError('场面证据不可为空')
                    count += 1
                    if norm(value) not in local:
                        report['findings'].append(finding('SCENE_SPAN_MISS', 'REVIEW', 'facts',
                            f"{scene.get('name', '未命名场面')} 的 {value!r} 不在 L{start}–{end}；需要上下文核对，不自动改写",
                            file=work / '正文.md', line=start))
            if count == 0:
                raise ValueError('不能用空场面证据获得 0/0 通过')
        report['scene_status'] = 'LITERAL_SPANS_CHECKED_NOT_SEMANTIC_APPROVAL'
        report['checked'].append('hash_bound_local_scene_spans')
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        report['findings'].append(finding('SCENE_EVIDENCE_ERROR', 'ERROR', 'evidence', str(exc), file=evidence_path))
    return finish(report)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    return emit(inspect_scenes(args.path), json_output=args.json, label='SCENE-LITERAL')


if __name__ == '__main__':
    raise SystemExit(main())
