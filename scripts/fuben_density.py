#!/usr/bin/env python3
"""Descriptive number-token density, not a quality or publication gate.

Denominator uses the repository's established punctuation-stripped convention;
headers are excluded. Tokens and this estimate are not semantic numbers or speech
measurements. No universal upper/lower band; the same quantity may be repeated for
a legitimate narrative reason. Do not modify prose to make this statistic green.
"""
import re, sys, glob, os

CN1 = "一二两三四五六七八九十百千万零〇"
CAL = {"13": 9.0, "01": 10.8, "05": 17.7, "06": 19.0, "04": 28.0}

def density(text: str):
    lines = [l for l in text.split("\n") if l.strip() and not l.lstrip().startswith("#")]
    body = "".join(lines)
    n = len(re.sub(r"[，。、？！：；「」\"'\s]", "", body))
    if n == 0:
        return 0, 0, 0.0
    t = len(re.findall(r"\d+(?:\.\d+)?", body))
    t += len(re.findall(r"\d+[点:：]\d+", body))
    t += len(re.findall(r"[%s]{2,}" % CN1, body))
    t += len(re.findall(r"[%s]+点[%s]+" % (CN1, CN1), body))
    return t, n, round(t / n * 1000, 1)

def main(argv=None):
    import argparse
    import json
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths', nargs='*')
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    paths = [Path(p) for p in args.paths]
    if args.all:
        paths += sorted((Path(__file__).resolve().parents[1] / '作品').glob('*/正文.md'))
    if not paths:
        parser.error('至少提供一个正文文件或 --all')
    rows = []
    errors = 0
    for path in paths:
        path = path / '正文.md' if path.is_dir() else path
        try:
            text = path.read_text(encoding='utf-8-sig')
            if not text.strip():
                raise ValueError('empty body')
            t, n, d = density(text)
            rows.append(dict(path=str(path), status='DESCRIPTIVE', tokens=t, characters=n, density_per1000=d))
        except (OSError, ValueError) as exc:
            errors += 1
            rows.append(dict(path=str(path), status='ERROR', error=str(exc)))
    print(json.dumps(rows, ensure_ascii=False, indent=2) if args.json else '\n'.join(str(x) for x in rows))
    return 2 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
