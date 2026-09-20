#!/usr/bin/env python3
"""Fuben mechanical checks. PASS is not editorial or publication approval.

python3 scripts/fuben_run.py 作品/NN_xxx/ --json
python3 scripts/fuben_run.py 作品/NN_xxx/正文_3m.md --profile short
Publication evidence is checked separately by fuben_release.py.
"""
from fuben_engine import cli

if __name__ == '__main__':
    raise SystemExit(cli(label='MECHANICAL'))
