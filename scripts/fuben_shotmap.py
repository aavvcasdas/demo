#!/usr/bin/env python3
"""Estimated spoken duration / anchor positions; never actual TTS alignment.

python3 scripts/fuben_shotmap.py 作品/NN_xxx/ --cps 6.4 --anchor '某句原文'
No platform-distribution or completion prediction is made from a speed estimate.
"""
import argparse
import json
import math
import os
from pathlib import Path
from fuben_engine import char_count, load_policy


def positive(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError('cps 必须是正有限数')
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths', nargs='+')
    parser.add_argument('--cps', type=positive, default=os.environ.get('FUBEN_CPS', str(load_policy()['estimated_chars_per_second'])))
    parser.add_argument('--anchor', action='append', default=[])
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    rows = []
    for name in args.paths:
        path = Path(name)
        if path.is_dir():
            path /= '正文.md'
        try:
            text = path.read_text(encoding='utf-8-sig')
            n = char_count(text)
            if n == 0:
                raise ValueError('empty prose')
            anchors = []
            for anchor in args.anchor:
                if not anchor:
                    raise ValueError('empty anchor')
                positions = []
                offset = text.find(anchor)
                while offset != -1:
                    positions.append(round(char_count(text[:offset]) / args.cps, 2))
                    offset = text.find(anchor, offset + 1)
                anchors.append({'literal': anchor, 'estimated_seconds': positions,
                                'state': 'ESTIMATED' if positions else 'NOT_FOUND'})
            rows.append({'path': str(path), 'state': 'ESTIMATED', 'characters': n, 'cps': args.cps,
                         'estimated_duration_seconds': round(n / args.cps, 2), 'anchors': anchors,
                         'note': '没有生成/聆听音频；不含停顿、英文和数字实际念法，不等于前15秒已兑现。'})
        except (OSError, ValueError) as exc:
            rows.append({'path': str(path), 'state': 'ERROR', 'error': str(exc)})
    print(json.dumps(rows, ensure_ascii=False, indent=2) if args.json else '\n'.join(str(row) for row in rows))
    return 2 if any(row['state'] == 'ERROR' for row in rows) else 0


if __name__ == '__main__':
    raise SystemExit(main())
