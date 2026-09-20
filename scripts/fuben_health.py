#!/usr/bin/env python3
"""Dynamic whole-library coverage; success is not a literary or release verdict."""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import re
from fuben_engine import ROOT, inspect_path, sha256


def discover_works(root=ROOT):
    """Include missing bodies as errors; never silently skip numeric work directories."""
    return sorted(p for p in (root / '作品').iterdir() if p.is_dir() and re.match(r'^\d', p.name))


def inspect_collection(*, corpus=False, variants=True, root=ROOT):
    if corpus:
        from fuben_corpus import discover
        items = [(p, 'reference', 'anthology' if p.parents[1].name.startswith('00_') else 'individual') for p in discover(root)]
        excluded = [str(p.relative_to(root)) for p in (root / '拆文库').glob('*/原文/*')
                    if p.is_file() and not re.match(r'^\d', p.parents[1].name)]
    else:
        items = []
        excluded = []
        for directory in discover_works(root):
            items.append((directory / '正文.md', 'full', 'work'))
            if variants:
                items.extend((p, 'short', 'variant') for p in sorted(directory.glob('正文_*.md')))
            excluded.extend(str(p.relative_to(root)) + '（制作单内嵌脚本；未当作独立正文或音频检测）'
                            for p in sorted(directory.glob('切条*/制作单.md')))
    if not items:
        raise ValueError('No inputs: refusing an empty green run')
    before = {str(p): sha256(p) for p, _, _ in items if p.is_file()}
    rows = []
    for path, profile, kind in items:
        result = inspect_path(path, profile=profile)
        rows.append({'source': str(path.relative_to(root)), 'kind': kind, 'result': result})
    after = {str(p): sha256(p) for p, _, _ in items if p.is_file()}
    if after != before:
        raise ValueError('Inputs changed during health check')
    return {'schema_version': 2, 'scope': 'corpus' if corpus else 'works', 'input_hashes_unchanged': True,
            'coverage': dict(Counter(kind for _, _, kind in items)),
            'status_counts': dict(Counter(row['result']['status'] for row in rows)),
            'errors': sum(row['result']['status'] == 'ERROR' for row in rows),
            'blocks': sum(row['result']['status'] == 'FAIL' for row in rows),
            'excluded_or_unassessed': excluded, 'rows': rows,
            'interpretation': 'No software finding is a claim of literary quality, completed human review, TTS listening or publication readiness.'}


def markdown(report):
    lines = [f"# 人生副本全库检查 · {report['scope']}", '', '> 机械通过 ≠ 文笔更好 ≠ 已精读 ≠ 可发布。缺证据保留未验证，不补造表格。', '',
             '| 输入 | 分类 | 机械状态 | BLOCK | REVIEW |', '|---|---|---|---:|---:|']
    for row in report['rows']:
        counts = Counter(f['severity'] for f in row['result']['findings'])
        lines.append(f"| {row['source']} | {row['kind']} | {row['result']['status']} | {counts['BLOCK']} | {counts['REVIEW']} |")
    lines.extend(['', '覆盖：`' + json.dumps(report['coverage'], ensure_ascii=False) + '`', '', '## 不适用 / 未评估'])
    lines.extend('- ' + x for x in report['excluded_or_unassessed'])
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', action='store_true')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    try:
        report = inspect_collection(corpus=args.corpus)
    except (OSError, ValueError) as exc:
        print('ERROR: ' + str(exc))
        return 2
    output = json.dumps(report, ensure_ascii=False, indent=2) + '\n' if args.json else markdown(report)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding='utf-8')
        print(args.output)
        print(json.dumps({'coverage': report['coverage'], 'statuses': report['status_counts']}, ensure_ascii=False))
    else:
        print(output)
    return 2 if report['errors'] else 1 if report['blocks'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
