#!/usr/bin/env python3
"""人生副本口播稿质地体检（L2.8 · 校准版 2026-09-19）。

契约位置（修复孤儿问题）：scripts/fuben_run.py 第 L2.8 步 ＋ skills/fuben-review Phase 0 清单；
配方依据：人生副本实录.md v11 §0.1 执行顺序 / §3 正文规则 / §4.1 机械验收（旧 docstring 引用的
「第十四节」不存在，已修正）。

与旧版的差异：
- 阈值不再写死在脚本里：全部来自 分篇/*.txt 39 篇原稿实测分布（scripts/fuben_texture_thresholds.json，
  由 scripts/fuben_calibrate_texture.py 生成，每项带样本来源；校准则：39 篇原稿复合通过率 ≥80%
  且 66–72 全部低于阈值）。
- 词表外置 scripts/fuben_wordlists.json（热点词按月随扫榜复核，CHANGELOG 记录）。
- 复合判定：硬指标失败 ≥2 项判 FAIL（单点漂移容错——非钱题价格数天然 0、民俗题品牌数天然 0，
  39 篇实测也有 6 篇单点缺口；66–72 成稿实测系统性失败 4–8 项）。
- 「热梗=0」是成稿政策、不是爆款基因（29 号原稿自带当期热梗）；成稿门禁照常硬拦。
- 开篇落地重定义：跳过开场白行后前 10 行须有感官词或阿拉伯数字（旧定义把固定开场白当正文，
  原稿通过率仅 5/39，是本闸失准的最大来源）。

用法: python3 scripts/check_fuben_texture.py 作品/xx/正文.md [--mode comedy]
退出码: 全 PASS 0；任一文件 FAIL 1。
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TH = json.load(open(os.path.join(ROOT, "scripts", "fuben_texture_thresholds.json"), encoding="utf-8"))["thresholds"]
WL = json.load(open(os.path.join(ROOT, "scripts", "fuben_wordlists.json"), encoding="utf-8"))["lists"]
SENS = WL["sens"]["pattern"]
BRAND = WL["brand"]["pattern"]
MEME = WL["meme"]["pattern"]
HAN_PRICE = WL["han_price"]["pattern"]
OPENER = re.compile(r"人生副本|副本")
HIT = re.compile(SENS + r"|℃|\d")

COMEDY_NODE = re.compile(r"\d|规定|表格|Excel|公告|举报|以为|其实|居然|一模一样|默认|流程|条例|评分|投票|截图|收到")


def evaluate(path):
    """返回 (bad_count, rows)。rows = [(指标, 值, 是否通过, 阈值)]。复合：bad≥2 → FAIL。"""
    t = open(path, encoding="utf-8", errors="ignore").read()
    lines = [l for l in t.split("\n") if l.strip() and not l.lstrip().startswith("#")]
    txt = re.sub(r"\s", "", "".join(lines))
    n = len(txt)
    digits = len(re.findall(r"\d+", txt))
    row = []
    row.append(("字数", n, TH["word_count"]["min"] <= n <= TH["word_count"]["max"], f"{TH['word_count']['min']}–{TH['word_count']['max']}"))
    row.append(("感官/千字", round(len(re.findall(SENS, txt)) / max(n, 1) * 1000, 1),
                len(re.findall(SENS, txt)) / max(n, 1) * 1000 >= TH["sens_per_kk"]["min"], f"≥{TH['sens_per_kk']['min']}"))
    row.append(("阿拉伯数字", digits, digits >= TH["digits_total"]["min"], f"≥{TH['digits_total']['min']}"))
    hanp = len(re.findall(HAN_PRICE, txt))
    ratio = digits / (digits + hanp) if digits + hanp else 0.0
    row.append(("阿拉伯化率", round(ratio, 2), ratio >= TH["arabic_ratio"]["min"], f"≥{TH['arabic_ratio']['min']}"))
    price = len(re.findall(r"\d+(?:\.\d+)?\s*(?:块|元|万|毛)", txt))
    row.append(("价格数", price, price >= TH["price_count"]["min"], f"≥{TH['price_count']['min']}"))
    brand = len(set(re.findall(BRAND, txt)))
    row.append(("品牌数", brand, brand >= TH["brand_count"]["min"], f"≥{TH['brand_count']['min']}"))
    dlg = sum(1 for l in lines if re.search(r"(你说|他说|她说|说 |问 |喊 |：)", l)) / max(len(lines), 1) * 100
    row.append(("对话行%", round(dlg, 1), dlg <= TH["dialogue_pct"]["max"], f"≤{TH['dialogue_pct']['max']}"))
    meme = len(re.findall(MEME, txt))
    row.append(("热梗(政策)", meme, meme <= TH["meme_count"]["max"], "=0"))
    body = list(lines)
    skip = 0
    while body and OPENER.search(body[0]) and skip < 3:
        body.pop(0)
        skip += 1
    opener = bool(HIT.search("".join(body[:10])))
    row.append(("开篇落地", "是" if opener else "否", opener, "开场白后10行有感官/数字"))
    bad = sum(1 for _, _, ok, _ in row if not ok)
    return bad, row


def check(path):
    bad, row = evaluate(path)
    print(os.path.relpath(path, ROOT) if os.path.isabs(path) else path)
    for k, v, ok, th in row:
        print(f"{'OK ' if ok else 'BAD'} {k:12} {v}  (门槛 {th})")
    verdict = bad < 2
    print(f"硬指标失败 {bad} 项（≥2 判 FAIL）")
    print("RESULT:", "PASS" if verdict else f"FAIL")
    return 0 if verdict else 1


def check_comedy(path):
    t = open(path, encoding="utf-8", errors="ignore").read()
    lines = [l for l in t.split("\n") if l.strip() and not l.lstrip().startswith("#")]
    txt = re.sub(r"\s", "", "".join(lines))
    n = len(txt)
    meme = len(re.findall(MEME, txt))
    nodes = sum(1 for l in lines if COMEDY_NODE.search(l))
    rows = [("字数", n, 2100 <= n <= 3900, "2100–3900"),
            ("制度/数字行占比(advisory)", round(nodes / max(n, 1) * 1000, 1), True, "参考: 32=3.3 39=11 29=7.6"),
            ("热梗(政策)", meme, meme == 0, "=0")]
    bad = 0
    for k, v, ok, th in rows:
        print(f"{'OK ' if ok else 'BAD'} {k:10} {v}  (门槛 {th})")
        bad += not ok
    print("RESULT:", "PASS" if not bad else f"FAIL {bad}项")
    return bad


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a not in ("--mode", "comedy")]
    if "comedy" in sys.argv:
        sys.exit(min(1, sum(check_comedy(p) for p in args)))
    sys.exit(min(1, sum(check(p) for p in args)))
