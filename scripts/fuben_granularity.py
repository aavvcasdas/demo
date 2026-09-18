#!/usr/bin/env python3
"""人生副本颗粒度传感器（L2.9 · 新增 2026-09-19）：**只测正文，不测声明表**。

整条流水线（facts/hype/draft/review/lint/AI 味）测的是事实、结构、禁忌模式；fuben_hype 只验证
「设定里声明的爽点锚点命中正文」——纸面爽点防住了，真爽没有。没有一道闸回答：正文是否真的
落在能看见、能摸到、能数的细节上。这恰是 39 篇爆款基因第 1 条（数字判词/具名消费/感官落地），
也是 66–72 成稿发布哑火的技术层根因：唯一测对层的旧质地闸是孤儿、失准且静默失败 100%。

本传感器的四项（全部硬门，阈值样本来源见 scripts/fuben_texture_thresholds.json）：
  1. 阿拉伯数字总数 ≥ 8（39 篇 p10=11、median=30；66–71 成稿=0——全写汉字＝数字基因漂移）
  2. 数字密度 ≥ 3.5/千字（p10=3.7、p20=4.1、median=10.0）
  3. 阿拉伯化率 ≥ 0.5＝阿拉伯数字/(阿拉伯+汉字金额数字)（原稿非零最低 0.67、median 0.96；
     66–71 成稿 0.00、72 主版 0.28）
  4. 对话行占比 ≤ 3%（39 篇 max=2.0%、median=0%；成稿 6.7–13.3%）
另报 advisory：价格数/品牌数/感官密度（单点容错在 L2.8 质地闸里做，此处不重复判 FAIL）。

验收双标准（2026-09-19 校准器实测）：39 篇原稿通过率 92.3% ≥80%；66–72 中 8/9 稿被本闸拦截，
72_重生成基线数字基因未漂移（lottery 稿保留了阿拉伯数字）属正常放行，其质地由 L2.8 拦截——
双闸并集覆盖 9/9 稿。

用法: python3 scripts/fuben_granularity.py 作品/xx/正文.md
退出码: PASS 0 / FAIL 1。
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TH = json.load(open(os.path.join(ROOT, "scripts", "fuben_texture_thresholds.json"), encoding="utf-8"))["thresholds"]
WL = json.load(open(os.path.join(ROOT, "scripts", "fuben_wordlists.json"), encoding="utf-8"))["lists"]
HAN_PRICE = WL["han_price"]["pattern"]
MEME = WL["meme"]["pattern"]


def evaluate(path):
    t = open(path, encoding="utf-8", errors="ignore").read()
    lines = [l for l in t.split("\n") if l.strip() and not l.lstrip().startswith("#")]
    txt = re.sub(r"\s", "", "".join(lines))
    n = len(txt)
    digits = len(re.findall(r"\d+", txt))
    dpk = digits / max(n, 1) * 1000
    hanp = len(re.findall(HAN_PRICE, txt))
    ratio = digits / (digits + hanp) if digits + hanp else 0.0
    dlg = sum(1 for l in lines if re.search(r"(你说|他说|她说|说 |问 |喊 |：)", l)) / max(len(lines), 1) * 100
    meme = len(re.findall(MEME, txt))
    rows = [
        ("阿拉伯数字", digits, digits >= TH["digits_total"]["min"], f"≥{TH['digits_total']['min']}"),
        ("数字密度/千字", round(dpk, 1), dpk >= TH["digit_density_per_kk"]["min"], f"≥{TH['digit_density_per_kk']['min']}"),
        ("阿拉伯化率", round(ratio, 2), ratio >= TH["arabic_ratio"]["min"], f"≥{TH['arabic_ratio']['min']}"),
        ("对话行%", round(dlg, 1), dlg <= TH["dialogue_pct"]["max"], f"≤{TH['dialogue_pct']['max']}"),
        ("热梗(政策)", meme, meme <= TH["meme_count"]["max"], "=0"),
    ]
    advice = [
        ("价格数", len(re.findall(r"\d+(?:\.\d+)?\s*(?:块|元|万|毛)", txt)), f"参考 p20={1} median=4"),
        ("感官/千字", round(len(re.findall(WL["sens"]["pattern"], txt)) / max(n, 1) * 1000, 1), f"参考 p10=1.8 median=4.2"),
    ]
    bad = sum(1 for _, _, ok, _ in rows if not ok)
    return bad, rows, advice


def check(path):
    bad, rows, advice = evaluate(path)
    print(os.path.relpath(path, ROOT) if os.path.isabs(path) else path)
    for k, v, ok, th in rows:
        print(f"{'OK ' if ok else 'BAD'} {k:14} {v}  (门槛 {th})")
    for k, v, th in advice:
        print(f"INFO {k:14} {v}  ({th})")
    print("RESULT:", "PASS" if not bad else f"FAIL {bad}项")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(min(1, sum(check(p) for p in sys.argv[1:])))
