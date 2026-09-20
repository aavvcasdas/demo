#!/usr/bin/env python3
"""R21 语料解剖复算器：解析 拆文库/*/情节节点.md 全量节点表，复算
《作品/_R21_爽点解剖_78验尸.md》引用的全部统计。只读，不改任何文件。

基线口径＝R20/R21 审判台同款 44 个单副本（00 合集容器豁免；R20 后入库的
40–45、47 等篇不计入——`--all` 可把全部目录算进来，数字会变大，属预期）。
运行：python3 scripts/corpus_node_scan.py [--all]
"""
import glob, os, re, statistics, sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = {f"{i:02d}" for i in range(1, 40)} | {"28b", "46", "48a", "48b", "48c"}
NODE = re.compile(r"^N(\d+)\s+\*\*(.+?)\*\*\s*[:：]?\s*(.*)$")
TYPE = re.compile(r"类型\{([^}]*)\}")
MOOD = re.compile(r"情绪\{[^}]*\}\{([^}]*)\}")  # 复合弧线如「+3→-6」取终点＝节点情绪值（首扫同口径）
WHO = re.compile(r"涉及\{([^}]*)\}")

def parse(path):
    lines = open(path, encoding="utf-8").read().splitlines()
    nodes = []
    for i, line in enumerate(lines):
        m = NODE.match(line.strip())
        if not m:
            continue
        g = MOOD.search(line)
        vals = re.findall(r"[+-]?\d+", g.group(1)) if g else []
        rec = {"n": "N" + m.group(1), "ev": m.group(2),
               "val": int(vals[-1]) if vals else None,
               "type": (TYPE.search(line).group(1) if TYPE.search(line) else ""),
               "who": (WHO.search(line).group(1) if WHO.search(line) else ""), "q": ""}
        for j in range(i + 1, min(i + 6, len(lines))):
            s = lines[j].strip()
            if s.startswith(">"):
                rec["q"] = s[1:].strip()
                break
            if NODE.match(s):
                break
        nodes.append(rec)
    return nodes

def nwho(w):
    w = re.sub(r"（.*?）|\(.*?\)", "", w or "")
    return [t for t in re.split(r"[、，,/;；和与及+＋]", w) if t]

def main():
    want_all = "--all" in sys.argv
    files = [f for f in sorted(glob.glob(os.path.join(ROOT, "拆文库", "*", "情节节点.md")))
             if want_all or os.path.basename(os.path.dirname(f)).split("_")[0] in BASELINE]
    all_n, peaks = [], []
    for f in files:
        ns = parse(f)
        for n in ns:
            n["id"] = os.path.basename(os.path.dirname(f))
        all_n += ns
        vs = [n["val"] for n in ns if n["val"] is not None]
        if vs:
            peaks.append((os.path.basename(os.path.dirname(f)), max(vs)))
    hi = [n for n in all_n if n["val"] is not None and n["val"] >= 5]
    tr = [n for n in all_n if n["val"] is not None and n["val"] <= -6]
    body = re.compile(r"抖|僵|愣|站起|坐下|瘫|哭|喊|叫|嗓|咽|手|眼|腿|背|呼吸|汗|拍桌|点头|摇头|安静|鸦雀|炸|哗")
    num = re.compile(r"\d|万|亿|千|百|十")
    set_ = re.compile(r"到账|结算|判|宣布|念|刷|签字|盖章|付清|还|给|递|报|表扬|批|入账|过账|落定|收")
    def pc(a, b): return f"{len(a)}/{b} = {len(a)/b:.0%}"
    print(f"篇数 {len(files)}  全节点 {len(all_n)}  有情绪值 {sum(1 for n in all_n if n['val'] is not None)}")
    print(f"≥+5 高爽 {len(hi)}  ≤−6 深谷 {len(tr)}  谷:峰 {len(tr)/max(1,len(hi)):.1f}:1")
    print("高爽在场≥2:", pc([n for n in hi if len(nwho(n['who'])) >= 2], len(hi)))
    print("高爽在场≤1人:", pc([n for n in hi if len(nwho(n['who'])) <= 1], len(hi)))
    print("高爽身体刻度:", pc([n for n in hi if body.search(n['q'] + n['ev'])], len(hi)))
    print("高爽带数字:", pc([n for n in hi if num.search(n['q'] + n['ev'])], len(hi)))
    print("高爽结算词:", pc([n for n in hi if set_.search(n['q'] + n['ev'])], len(hi)))
    print("谷在场≥1:", pc([n for n in tr if nwho(n['who'])], len(tr)))
    print("谷带数字:", pc([n for n in tr if num.search(n['q'] + n['ev'])], len(tr)))
    print("高爽类型:", Counter(n["type"] or "—" for n in hi).most_common(9))
    print("单篇峰值中位:", statistics.median(v for _, v in peaks),
          " 峰值≥5:", sum(1 for _, v in peaks if v >= 5), f"/{len(peaks)}",
          " 峰值≥6:", sum(1 for _, v in peaks if v >= 6))
    solo = [n for n in hi if set(nwho(n["who"])) <= {"你", "我", "自"}]
    print("在场仅『你/我/自』的高爽:", pc(solo, len(hi)), "类型:", Counter(n["type"] or "—" for n in solo).most_common())

if __name__ == "__main__":
    main()
