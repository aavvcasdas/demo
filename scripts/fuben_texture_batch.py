#!/usr/bin/env python3
"""存量作品质地/颗粒度体检批跑（观察用；CI 中 continue-on-error，输出供数据复盘）。

用法: python3 scripts/fuben_texture_batch.py
"""
import glob
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import check_fuben_texture as tex  # noqa: E402
import fuben_granularity as gran  # noqa: E402

rows = []
for f in sorted(glob.glob(os.path.join(ROOT, "作品", "*_", "正文.md")) + glob.glob(os.path.join(ROOT, "作品", "[0-9]*_*/正文.md"))):
    rel = os.path.relpath(f, ROOT)
    try:
        tb, _ = tex.evaluate(f)
        gb, _, _ = gran.evaluate(f)
        rows.append((rel, tb, gb))
    except FileNotFoundError:
        continue

print(f"{'作品':52} 质地(L2.8) 颗粒度(L2.9)")
tp = gp = 0
for rel, tb, gb in rows:
    t = "PASS" if tb < 2 else f"FAIL({tb})"
    g = "PASS" if gb == 0 else f"FAIL({gb})"
    tp += tb < 2
    gp += gb == 0
    print(f"{rel:52} {t:>9} {g:>10}")
print(f"\n质地 PASS {tp}/{len(rows)} ｜ 颗粒度 PASS {gp}/{len(rows)}（此表是观察面，不是门禁；门禁见 fuben_run L2.8/L2.9 与 作品/_ci_闸门.txt）")
sys.exit(0)
