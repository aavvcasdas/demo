#!/usr/bin/env python3
"""人生副本波形签名 + 反 Goodhart 相似度报警（L3.0 · 新增 2026-09-19）。

Goodhart 诅咒的现场：66/67/70/71 四稿把 v5/v6 门禁做成配额后，波形签名逐位相同——
开场结果前置三段式、峰值一律 +8@34–47%、谷底一律 −6、间距 6–7%、结尾锚点一律 100% 器物判词。
门禁全绿，稿子同质化死亡。本脚本把每篇的波形压成签名落 JSON，连续三篇同签名 → BLOCK。

签名六维（数值维从 `## 爽点表` 锚点在正文中的实测位置计算，与 fuben_hype 同算法）：
  opening_class   开场结构（`## 波形签名` 声明优先；缺省推断：爽点表首行类型含 钩子/前置/开场 → 结果前置开场，否则 冷开场）
  peak_value      峰值情绪值（收敛值：+8）
  peak_band       峰值位置桶 A<25 B 25–33 C 34–47 D>47（C=已收敛带）
  first_big_band  首个大事件位置桶 A≤27 B 28–32 C>32（A=已收敛带；大事件判定与 hype 相同：情绪值≥+5 或类型含 对质/兑现/翻车/社死/承认/面试/爆点/峰值/反转/结账，钩子除外）
  valley_value    谷底情绪值（收敛值：−6）
  ending_device   收束装置（`## 波形签名` 声明优先；缺省推断：末节点类型含 器物/道具 → 器物判词，锚点含数字 → 数字判词，否则 其他）

BLOCK 规则（人生副本实录 v11 §4.3）：候选与上一条签名在 [opening, peak_value, peak_band,
first_big_band, ending_device] 五维中 ≥3 维相同，且上一条与再上一条也 ≥3 维相同 → 第三篇不许再同签名。

用法：
  python3 scripts/fuben_waveform.py --check 作品/NN_xxx/          # 门禁判定（fuben_run L3.0 调用）
  python3 scripts/fuben_waveform.py --record 作品/NN_xxx/ [变体名]  # 判定 + 追加进 作品/_波形.jsonl
  python3 scripts/fuben_waveform.py --scan 作品/*_*/                # 只打印签名表与连环报警，不写文件
退出码：BLOCK 1 / PASS（含打断链提示）0。
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from fuben_consistency import read, section  # noqa: E402
from fuben_hype import parse_rows, HAN  # noqa: E402

JSONL = os.path.join(ROOT, "作品", "_波形.jsonl")
BIG = re.compile(r"对质|兑现|翻车|社死|承认|面试|爆点|峰值|反转|结账")
HOOK = re.compile(r"钩子|前置|开场")
DIMS = ["opening_class", "peak_value", "peak_band", "first_big_band", "ending_device"]


def peak_band(pos):
    return "A" if pos < 25 else "B" if pos <= 33 else "C" if pos <= 47 else "D"


def big_band(pos):
    return "A" if pos <= 27 else "B" if pos <= 32 else "C"


def compute(directory):
    setting = read(os.path.join(directory, "设定.md"))
    body = read(os.path.join(directory, "正文.md"))
    if not setting or not body:
        return None, "缺 设定.md 或 正文.md"
    rows = parse_rows(section(setting, "爽点表"))
    if not rows:
        return None, "爽点表为空或不可解析"
    lines = [l.strip() for l in body.splitlines() if l.strip() and not l.lstrip().startswith("#")]
    total = max(HAN("".join(lines)), 1)
    cumulative, running = [], 0
    for line in lines:
        running += HAN(line)
        cumulative.append(running)
    for row in rows:
        row["actual"] = None
        for i, line in enumerate(lines):
            if row["anchor"] and row["anchor"] in line:
                row["actual"] = cumulative[min(i + 1, len(cumulative) - 1)] / total * 100
                break
    valid = [r for r in rows if r["actual"] is not None]
    if len(valid) < 3:
        return None, "可定位锚点 <3，无法构造签名（先过 hype）"

    sig_block = section(setting, "波形签名")
    declared = dict(re.findall(r"^\s*[-|]?\s*(开场结构|收束装置)\s*[:：|]\s*([^|\n]+)", sig_block, re.M))
    ordered = sorted(valid, key=lambda r: r["actual"])
    peak = max(valid, key=lambda r: r["mood"])
    trough = min(valid, key=lambda r: r["mood"])
    bigs = [r for r in valid if not HOOK.search(r["type"]) and (r["mood"] >= 5 or BIG.search(r["type"]))]
    first_big_pos = min(bigs, key=lambda r: r["actual"])["actual"] if bigs else None
    last = ordered[-1]

    opening = (declared.get("开场结构") or "").strip()
    if not opening:
        opening = "结果前置开场" if HOOK.search(valid[0]["type"]) else "冷开场"
    ending = (declared.get("收束装置") or "").strip()
    if not ending:
        ending = ("器物判词" if re.search(r"器物|道具", last["type"]) else
                  "数字判词" if re.search(r"\d", last["anchor"]) else "其他收束")

    return {
        "episode": os.path.basename(directory.rstrip("/")),
        "nodes": len(valid),
        "opening_class": opening,
        "peak_value": peak["mood"],
        "peak_pos": round(peak["actual"], 1),
        "peak_band": peak_band(peak["actual"]),
        "first_big_pos": round(first_big_pos, 1) if first_big_pos is not None else None,
        "first_big_band": big_band(first_big_pos) if first_big_pos is not None else "—",
        "valley_value": trough["mood"],
        "ending_device": ending,
        "end_pos": round(last["actual"], 1),
        "density_千字": round(len(valid) / (total / 1000), 1),
    }, None


def load_records():
    if not os.path.exists(JSONL):
        return []
    out = []
    for line in open(JSONL, encoding="utf-8"):
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def same_dims(a, b):
    return sum(1 for d in DIMS if a.get(d) == b.get(d))


def verdict(cand, records):
    """返回 (exit_code, message_lines)。"""
    msgs = []
    sig_line = (f"签名: 开场={cand['opening_class']} 峰值={cand['peak_value']:+d}@{cand['peak_pos']}%"
                f"({cand['peak_band']}) 首大={cand['first_big_pos']}%({cand['first_big_band']})"
                f" 谷底={cand['valley_value']:+d} 收束={cand['ending_device']} 节点={cand['nodes']}")
    msgs.append(sig_line)
    prev = [r for r in records if r.get("episode") != cand.get("episode")]
    if len(prev) >= 1:
        a = same_dims(cand, prev[-1])
        diff = [d for d in DIMS if cand.get(d) != prev[-1].get(d)]
        msgs.append(f"vs 上一篇({prev[-1]['episode']}): {a}/5 维相同；差异维: {','.join(diff) if diff else '无'}")
        if len(prev) >= 2 and a >= 3 and same_dims(prev[-1], prev[-2]) >= 3:
            msgs.append(f"BLOCK: 连续三篇同签名（{prev[-2]['episode']} / {prev[-1]['episode']} / 候选 ≥3 维相同）——"
                        "人生副本实录 v11 §4.3：第四篇必须换骨架")
            return 1, msgs
        if a >= 3:
            msgs.append("警戒: 与上一篇 ≥3 维相同，下一篇若再同即 BLOCK；本稿放行")
        elif len(diff) >= 2:
            msgs.append("打断链: 与上一篇差异 ≥2 维，收敛链已打断")
    else:
        msgs.append("曲线库无历史记录，本稿为首条签名")
    return 0, msgs


def main():
    args = sys.argv[1:]
    mode = next((a for a in args if a in ("--check", "--record", "--scan")), None)
    targets = [a for a in args if not a.startswith("--") and a != "comedy"]
    if mode == "--scan":
        records = load_records()[:]
        print(f"{'作品':44} 开场 峰值 首大 谷底 收束 同前")
        prev2 = None
        prev1 = None
        for d in targets:
            for directory in sorted(glob.glob(d)):
                directory = directory.rstrip("/")
                if not os.path.isdir(directory):
                    continue
                sig, err = compute(directory)
                if err:
                    print(f"{os.path.basename(directory):44} 跳过: {err}")
                    continue
                a = same_dims(sig, prev1) if prev1 else 0
                mark = " ⚠︎连环" if (prev1 and prev2 and a >= 3 and same_dims(prev1, prev2) >= 3) else ""
                print(f"{os.path.basename(directory):44} {sig['opening_class'][:6]} {sig['peak_value']:+d}@{sig['peak_pos']}%({sig['peak_band']})"
                      f" {sig['first_big_pos']}%({sig['first_big_band']}) {sig['valley_value']:+d} {sig['ending_device'][:6]} {a}/5{mark}")
                prev2, prev1 = prev1, sig
        return 0
    if mode not in ("--check", "--record") or not targets:
        print(__doc__)
        return 2
    rc = 0
    for t in targets:
        directory = t.rstrip("/")
        sig, err = compute(directory)
        if err:
            print(f"WAVEFORM: FAIL {directory} ← {err}")
            rc = 1
            continue
        records = load_records()
        code, msgs = verdict(sig, records)
        print(f"== {os.path.basename(directory)} ==")
        print("\n".join(msgs))
        if mode == "--record" and code == 0:
            sig["variant"] = sys.argv[-1] if targets[-1] != sys.argv[-1] else ""
            import datetime
            sig["date"] = datetime.date.today().isoformat()
            records = [r for r in records if not (r.get("episode") == sig["episode"] and r.get("variant") == sig.get("variant"))]
            with open(JSONL, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(sig, ensure_ascii=False) + "\n")
            print(f"已追加 作品/_波形.jsonl")
        rc = rc or code
    return rc


if __name__ == "__main__":
    sys.exit(main())
