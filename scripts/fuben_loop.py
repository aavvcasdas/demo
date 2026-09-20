#!/usr/bin/env python3
"""Compatibility entry point for the lightweight fuben workflow.

  design <brief-file>        check supplied brief readability, not quota tables
  draft|facts <body-or-dir>  shared mechanical checks
  review <body-or-dir>       review candidates; never automatic editorial approval
  record <new-data-args>     schema-validated snapshots (see fuben_data.py)
  report                    read validated snapshots; show quarantined legacy data

No generate→quota→rewrite-until-green loop. An editorial iteration fixes the most
important evidenced problems; subjective disagreement goes back to the author.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
from fuben_engine import char_count as HAN, inspect_path, emit, finding, finish, sha256


def design(path):
    target = Path(path)
    report = {'schema_version': 2, 'profile': 'draft', 'target': str(path), 'findings': [],
              'tools': [], 'inputs': {}, 'checked': [], 'unverified': ['brief interpretation', 'all story/release checks']}
    try:
        text = target.read_text(encoding='utf-8-sig')
        if not text.strip():
            report['findings'].append(finding('EMPTY_BRIEF', 'BLOCK', 'input', '指定的 brief 文件为空', file=path))
        else:
            report['inputs']['brief_sha256'] = sha256(target)
            report['checked'].append('supplied_brief_is_readable_nonempty')
            report['findings'].append(finding('NO_CREATIVE_QUOTAS', 'NOTE', 'style',
                                             '不要求八拍、爽点表、呼应数或感官配额；理解用户请求后即可起稿。'))
    except (OSError, UnicodeError) as exc:
        report['findings'].append(finding('BRIEF_READ_ERROR', 'ERROR', 'input', str(exc), file=path))
    return finish(report)


def features(directory):
    report = inspect_path(directory, run_style=False, components={'metrics'})
    if not report['mechanical_pass']:
        raise ValueError('cannot extract features from invalid text')
    return {'metric_schema_version': 2, **report['metrics']}


def review(path):
    report = inspect_path(path)
    # Keywords, table presence and 0/0 callback recovery cannot attest to a review.
    report['review_status'] = 'PROVISIONAL'
    report['findings'].append(finding('EDITORIAL_NOT_ATTESTED', 'NOTE', 'evidence',
                                     '只生成审核候选，没有确认精读或三方会审；完整审核按 fuben-review，发布按哈希证据验收。'))
    return finish(report)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in ('record', 'report'):
        from fuben_data import main as data_main
        if argv[0] == 'record' and len(argv) > 1 and not argv[1].startswith('-'):
            print('ERROR: 旧 record NN 点赞 [播放] 缺版本/时间/来源，已禁用以防继续写坏 CSV。\n'
                  '使用 python3 scripts/fuben_data.py record --input snapshot.json；先运行 template 查看结构。', file=sys.stderr)
            return 2
        return data_main(argv)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['design', 'draft', 'facts', 'consistency', 'review'])
    parser.add_argument('path')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    if args.command == 'design':
        report = design(args.path)
    elif args.command == 'review':
        report = review(args.path)
    else:
        report = inspect_path(args.path, components={'facts', 'setting'} if args.command in ('facts', 'consistency') else None)
    return emit(report, json_output=args.json, label='MECHANICAL-' + args.command.upper())


if __name__ == '__main__':
    raise SystemExit(main())
