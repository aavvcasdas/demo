#!/usr/bin/env python3
"""Descriptive rhythm information. No emotion-score / location / spending quotas.

Self-labelled emotions are annotations, not audience measurements. Read the story
before deciding whether its promises, scenes and ending work. Absence of a mood
spreadsheet is not a writing error.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import re
from fuben_engine import inspect_path, emit, finding, finish
from fuben_numbers import numeric


def _cn_value(token):
    """Compatibility API; invalid numbers are None, never a guessed leading digit."""
    return numeric(token, colloquial=True)


def scale_signature(text):
    def maximum(unit):
        values = [_cn_value(x) for x in re.findall(r'(\d+(?:\.\d+)?[万亿]?|[零一二两三四五六七八九十百千万亿]+)\s*(?:' + unit + ')', text)]
        return max([x for x in values if x is not None] or [0])
    return maximum('元|块'), maximum('注')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    report = inspect_path(args.path, run_style=False, components={'metrics'})
    report['findings'].append(finding('RHYTHM_NOT_MACHINE_JUDGED', 'NOTE', 'style',
                                     '不按情绪分数、节点数、固定百分比判好看；无爽点表也可创作。'))
    return emit(finish(report), json_output=args.json, label='RHYTHM-DESCRIPTIVE')


if __name__ == '__main__':
    raise SystemExit(main())
