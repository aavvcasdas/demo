#!/usr/bin/env python3
"""人生副本质地/颗粒度门禁 · 校准器（2026-09-19）。

为什么存在：check_fuben_texture.py 的阈值（感官≥6、价格≥12、品牌≥4、字数≥2800）从未对
39 篇原稿做过校准——实测只有约 36% 的原稿能过「感官≥6」，闸门失准且孤儿（未接入流水线），
对 66–72 成稿静默失败 100%。本脚本把「对 39 篇原稿的实测分布」变成阈值唯一来源：

1. 测量 分篇/*.txt（39 篇爆款原稿）与 作品/66–72（已知失败批次）的全量指标；
2. 输出每篇指标表与分位数，打印「拟采用阈值」下的通过率复核；
3. 把阈值落盘 scripts/fuben_texture_thresholds.json（每个阈值带样本来源字段）；
4. 验收双标准（来自任务书）：39 篇原稿通过率 ≥80% 且 66–72 全部低于阈值。
   复合判定：硬指标失败 ≥2 项判 FAIL（单点漂移容错：非钱题价格数天然为 0、民俗题品牌数天然为 0）。

用法：python3 scripts/fuben_calibrate_texture.py        # 重测 + 重写 thresholds JSON
"""
import glob
import json
import os
import re
import statistics as st
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WL = json.load(open(os.path.join(ROOT, "scripts", "fuben_wordlists.json"), encoding="utf-8"))["lists"]
SENS = WL["sens"]["pattern"]
BRAND = WL["brand"]["pattern"]
MEME = WL["meme"]["pattern"]
HAN_PRICE = WL["han_price"]["pattern"]

OPENER = re.compile(r"人生副本|副本")
HIT = re.compile(SENS + r"|℃|\d")  # 落地=感官词或任意阿拉伯数字（早上7点/5点闹钟都算数字落地；「度」单字会误伤制度/态度，剔除）


def content_lines(path):
    t = open(path, encoding="utf-8", errors="ignore").read()
    return [l for l in t.split("\n") if l.strip() and not l.lstrip().startswith("#")]


def measure(path):
    lines = content_lines(path)
    txt = re.sub(r"\s", "", "".join(lines))
    n = len(txt)
    digits = len(re.findall(r"\d+", txt))
    hanp = len(re.findall(HAN_PRICE, txt))
    price = len(re.findall(r"\d+(?:\.\d+)?\s*(?:块|元|万|毛)", txt))
    # 开篇落地（重定义）：跳过开场白行（含「副本」的头部 ≤3 行），其后 10 行内须有感官/温度/金额/数字
    body = list(lines)
    skipped = 0
    while body and OPENER.search(body[0]) and skipped < 3:
        body.pop(0)
        skipped += 1
    opener_hit = bool(HIT.search("".join(body[:10])))
    dlg = sum(1 for l in lines if re.search(r"(你说|他说|她说|说 |问 |喊 |：)", l)) / max(len(lines), 1) * 100
    return {
        "n": n,
        "sens": round(len(re.findall(SENS, txt)) / max(n, 1) * 1000, 1),
        "digits": digits,
        "dpk": round(digits / max(n, 1) * 1000, 1),
        "ratio": round(digits / (digits + hanp), 2) if digits + hanp else 0.0,
        "price": price,
        "brand": len(set(re.findall(BRAND, txt))),
        "dlg": round(dlg, 1),
        "meme": len(re.findall(MEME, txt)),
        "opener": opener_hit,
    }


# 拟采用阈值（每项在落盘 JSON 里都带样本来源；calibrate 还会按实测打印复核）
TH = {
    "word_count": {"min": 2200, "max": 4200},
    "sens_per_kk": {"min": 1.8},
    "digits_total": {"min": 8},
    "digit_density_per_kk": {"min": 3.5},
    "arabic_ratio": {"min": 0.5},
    "price_count": {"min": 1},
    "brand_count": {"min": 1},
    "dialogue_pct": {"max": 3.0},
    "meme_count": {"max": 0},
    "opener_hit": {"required": True},
}


def failures(m, for_original=False):
    """返回这篇稿失败的硬指标名列表；失败 ≥2 项 → 复合 FAIL。
    for_original=True 时跳过「热梗」：29 号原稿自带当期热梗（第55行）且成爆款——热梗=0 是【成 稿政策】（写完即过期），不是爆款基因的测量；对原稿校准时不计入，对成稿门禁时计入。"""
    f = []
    if not (TH["word_count"]["min"] <= m["n"] <= TH["word_count"]["max"]):
        f.append("字数")
    if m["sens"] < TH["sens_per_kk"]["min"]:
        f.append("感官")
    if m["digits"] < TH["digits_total"]["min"]:
        f.append("数字总数")
    if m["dpk"] < TH["digit_density_per_kk"]["min"]:
        f.append("数字密度")
    if m["ratio"] < TH["arabic_ratio"]["min"]:
        f.append("阿拉伯化率")
    if m["price"] < TH["price_count"]["min"]:
        f.append("价格")
    if m["brand"] < TH["brand_count"]["min"]:
        f.append("品牌")
    if m["dlg"] > TH["dialogue_pct"]["max"]:
        f.append("对话行%")
    if not for_original and m["meme"] > TH["meme_count"]["max"]:
        f.append("热梗")
    if TH["opener_hit"]["required"] and not m["opener"]:
        f.append("开篇落地")
    return f


def pct(vals, q):
    vals = sorted(vals)
    return vals[min(len(vals) - 1, int(len(vals) * q))]


def main():
    orig = []
    for f in sorted(glob.glob(os.path.join(ROOT, "分篇", "*.txt"))):
        orig.append((os.path.basename(f), measure(f)))
    drafts = []
    # 验收集＝66–72 已知失败批次（含 72 变体）；71 号已按同方重写为合规稿（PR C 实验件），
    # 从失败验收集移入观察集并按「应 PASS」复核——重写稿若被拦＝阈值过紧，同样报警。
    acc, obs, redo = [], [], []
    for f in sorted(glob.glob(os.path.join(ROOT, "作品", "6*_*/正文.md")) + glob.glob(os.path.join(ROOT, "作品", "7*_*/正文.md"))):
        rel = os.path.relpath(f, ROOT)
        if "作品/71_" in rel:
            redo.append((rel, measure(f)))
        elif re.search(r"作品/(6[6-9]|7[0-2])_", rel):
            acc.append((rel, measure(f)))
        else:
            obs.append((rel, measure(f)))
    drafts = acc

    print("=== 39 篇原稿指标与命中（≥2 项失败=FAIL） ===")
    opass = 0
    for name, m in orig:
        f = failures(m, for_original=True)
        opass += len(f) < 2
        print(f"{'OK ' if len(f)<2 else 'BAD'} {name[:24]:26} n={m['n']:>5} sens={m['sens']:>4} digits={m['digits']:>3} dpk={m['dpk']:>5} ratio={m['ratio']:>4} price={m['price']:>2} brand={m['brand']:>2} dlg={m['dlg']:>4} opener={int(m['opener'])}"
              + (f"  ← {','.join(f)}" if f else ""))
    print(f"\n原稿复合通过率: {opass}/{len(orig)} = {opass/len(orig)*100:.1f}%（验收线 ≥80%）")

    print("\n=== 66–72 成稿（已知失败批次，应全部 FAIL） ===")
    dfail = 0
    for name, m in drafts:
        f = failures(m)
        dfail += len(f) >= 2
        print(f"{'FAIL' if len(f)>=2 else 'pass!?'} {name[:44]:46} n={m['n']:>5} sens={m['sens']:>4} digits={m['digits']:>3} ratio={m['ratio']:>4} dlg={m['dlg']:>4}  ← {','.join(f)}")
    print(f"\n验收集（66–72）拦截率: {dfail}/{len(drafts)}")
    rpass = 0
    for name, m in redo:
        f = failures(m)
        rpass += len(f) < 2
        print(f"重做合规件 {'PASS' if len(f)<2 else 'FAIL!?'} {name[:44]:44} ← {','.join(f) if f else '全绿'}")
    if obs:
        print("\n=== 60–65 观察集（不进验收判定） ===")
        for name, m in obs:
            f = failures(m)
            print(f"{'FAIL' if len(f)>=2 else 'PASS'} {name[:44]:46} ← {','.join(f) if f else '全绿'}")

    print("\n=== 分位数（阈值样本来源） ===")
    for k in ["n", "sens", "digits", "dpk", "price", "brand", "dlg"]:
        vals = [m[k] for _, m in orig]
        print(f"{k:7} min={min(vals):>6} p10={pct(vals,.1):>6} p20={pct(vals,.2):>6} median={st.median(vals):>7} max={max(vals):>7}")
    nonzero = sorted(m["ratio"] for _, m in orig if m["digits"] > 0)
    print(f"ratio  非零最低={nonzero[0]:.2f} median={st.median([m['ratio'] for _,m in orig]):.2f}")

    out = {
        "version": "2026-09-19",
        "source": "分篇/*.txt 39 篇 ASR 原稿 + 作品/66–72 成稿实测（本脚本可复跑重生成）",
        "acceptance": "39 篇原稿复合通过率 ≥80%（单篇硬指标失败 <2 项）且 66–72 已知失败批次（71 已重写除外）全部 ≥2 项失败；71 号重写件应 PASS（被拦＝阈值过紧）",
        "thresholds": TH,
        "样本来源": {
            "word_count": "39 篇 p10=2375、median=2999、max=4479 → 硬边界 [2200,4200]、目标带 [2400,3600]",
            "sens_per_kk": "p10=1.8、p20=2.4、median=4.2 → 下限取 p10 的 1.8（旧阈值 6.0 失准：仅 36% 原稿能过）",
            "digits_total": "p10=11、median=30 → 下限 8",
            "digit_density_per_kk": "p10=3.7、p20=4.1、median=10.0 → 下限 3.5",
            "arabic_ratio": "原稿非零最低 0.67、median≈0.9；66–71 成稿=0.00（汉字漂移） → 下限 0.5",
            "price_count": "p20=1、median=4；非钱题天然 0 → 计入复合容错而非单独 FAIL",
            "brand_count": "p20=1、median=1；民俗/校园题天然 0 → 同上",
            "dialogue_pct": "39 篇 max=2.0%、median=0%；成稿实测 6.7–13.3% → 上限 3.0",
            "opener_hit": "跳过开场白行后前 10 行须有感官词或阿拉伯数字（旧定义把固定开场白当正文且不认裸数字，39 篇仅 5 篇过）",
        },
    }
    with open(os.path.join(ROOT, "scripts", "fuben_texture_thresholds.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print("\nthresholds 已落盘 scripts/fuben_texture_thresholds.json")
    ok = opass / len(orig) >= 0.8 and dfail == len(drafts) and (not redo or rpass == len(redo))
    print("验收双标准:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
