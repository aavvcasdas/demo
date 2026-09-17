#!/usr/bin/env python3
"""人生副本·爽点与节奏门禁（L1.8）。

v3 的事实闸证明了「没有事实错误」不等于「好看」：新 72 的事实全绿，但全篇
只有一个正向事件，2510 字里没有任何爽点，观众看不到情绪翻转。

本检查器只做一件事：把 39 篇拆文里测出来的「爽点密度与位置」变成可复核的硬指标。
设定.md 必须提供 `## 爽点表`，每行写明：

    | 序 | 位置 | 情绪值 | 爽点/情绪事件 | 类型 | 正文锚点 |

门禁项（全部来自拆文库实测区间）：
- 节点密度 ≥ 4.0 个/千字（39 篇样本实测 5.1–16.7，最低 5.1）
- 正向爽点（情绪值 ≥ +3）绝对数 ≥ 2（01=6，04=2，13=5，15=3，21=2）
- 第一个正向爽点出现在 ≤22%（01 在 6%，04 在 13% 就给数字钩）
- 峰值：爽/加冕题 ≥+5 且落 25%–48%；沉沦/代价题可 ≥+3 且落 15%–55%
- ≥2 个情绪值 ≥ +5 的大爽点；≥1 个情绪值 ≤ -6 的谷底
- 相邻爽点实际间距 ≤ 全文 30%（超过就是「年表区」，观众会划走）
- 结尾锚点落在 ≥85%，且最后 12 行里要有一个数字或器物判词
- v5 快推结构：首个大事件（≥+5 或 对质/兑现/翻车）≤ 32%，其后仍要有 ≥4 个情绪节点，
  >50% 处已有 ≥3 个节点；相邻节点间距 ≤ 22%（不许把对质留到 75%）
- v6 钱的去向（兑现/暴富题）：`## 钱的去向表` ≥6 笔；类别只有 花/给/亏/被骗；
  **花+给 ≥60%**，**被骗 ≤1 笔**（被骗不是归零主因）；锚点命中正文；钱账误差 0；
  正文「憋屈结算词」（报案/跑路/卷走/办公室空了…）≤2 处
- v6 习惯漂移（习惯/成瘾题）：`## 习惯漂移` ≥2 行，旧做法 → 新做法 → 他的说法 → 正文锚点，
  锚点必须命中正文（习惯原样运行、内容换掉；不许写成「他戒了」）
- v7 钱的去向重排：类别改为 补欠 / 场面 / 给自己人 / 借出 / 亏 / 被骗；表 ≥8 笔，
  **补欠+场面 ≥50%**、**借出 ≤20%**（钱不是借完的）、被骗 ≤1、亏 ≤15%；账仍要平
- v7 转场：跨度题必须写 `## 转场表`（压缩段 → 回位句 → 正文锚点），回位句必须命中正文
- v7 习惯漂移加严：至少一行要「新做法里的数字 > 旧做法」（号码换 + 买得更多）
"""
from __future__ import annotations

import os
import re
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.join(ROOT, "scripts") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
from fuben_consistency import read, section  # noqa: E402

HAN = lambda text: len(re.findall(r"[\u4e00-\u9fff]", text))
CN_DIGITS = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def _cn_value(token: str) -> int:
    if token in CN_DIGITS:
        return CN_DIGITS[token]
    if "十" in token:
        head, _, tail = token.partition("十")
        tens = CN_DIGITS.get(head, 1) if head else 1
        ones = CN_DIGITS.get(tail, 0) if tail else 0
        return tens * 10 + ones
    return CN_DIGITS.get(token[0], 0)


def scale_signature(text: str):
    """取「金额（元/块）」与「注数」两组规模指标，用于核对习惯漂移是否买了更多。"""
    def amount(token: str) -> int:
        return int(token) if token.isdigit() else _cn_value(token)

    money = max([amount(m) for m in re.findall(r"(\d+|[零一二两三四五六七八九十]+)\s*(?:元|块)", text)] or [0])
    notes = max([amount(m) for m in re.findall(r"(\d+|[零一二两三四五六七八九十]+)\s*注", text)] or [0])
    return money, notes
RITUAL = re.compile(r"铁盒|账本|账|药盒|药单|票|凳子|柜台|短信|手机|照片|抽屉|钥匙|门|碗|面|盒子|卡|收据|兑奖单|沙发|车|文件夹|档案|本子|课件")


def parse_rows(block: str):
    rows = []
    for line in block.splitlines():
        if not line.startswith("|") or re.match(r"^\|\s*:?-", line):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 6 or cells[0] in {"序", "序号", "#"}:
            continue
        if not re.fullmatch(r"\d+", cells[0]):
            continue
        pos = re.search(r"(\d+)", cells[1])
        mood = re.search(r"([+-]?\d+)", cells[2].replace("＋", "+").replace("－", "-"))
        if not pos or not mood:
            continue
        rows.append(
            {
                "no": int(cells[0]),
                "pos": int(pos.group(1)),
                "mood": int(mood.group(1)),
                "event": cells[3],
                "type": cells[4],
                "anchor": cells[5],
            }
        )
    return rows


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("用法: python3 scripts/fuben_hype.py 作品/NN_xxx/")
    directory = sys.argv[1].rstrip("/")
    setting = read(os.path.join(directory, "设定.md"))
    body = read(os.path.join(directory, "正文.md"))
    if not setting or not body:
        print("HYPE: FAIL 缺少 设定.md 或 正文.md")
        return 1

    lines = [line.strip() for line in body.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    text = "\n".join(lines)
    total = HAN(text)
    if total <= 0:
        print("HYPE: FAIL 正文没有可统计内容")
        return 1

    block = section(setting, "爽点表")
    bad = []

    def show(label: str, ok: bool, info: str = ""):
        print(("OK  " if ok else "BAD ") + f"{label:26} {info}")
        if not ok:
            bad.append(label)

    if not block:
        show("爽点表存在", False, "设定.md 必须有「## 爽点表」：位置 / 情绪值 / 事件 / 类型 / 正文锚点")
        print("\nHYPE: FAIL → 先补爽点表，再改正文；没有爽点表的稿子一律不进正文流程。")
        return 1

    rows = parse_rows(block)
    show("爽点表可解析", len(rows) >= 6, f"{len(rows)} 行")

    # 计算每个锚点在正文中的真实位置（按汉字累计）。
    cumulative = []
    running = 0
    for number, line in enumerate(lines, 1):
        running += HAN(line)
        cumulative.append((number, running))
    actual = []
    for row in rows:
        anchor = row["anchor"]
        found = None
        for number, line in enumerate(lines):
            if anchor and anchor in line:
                found = (number, cumulative[number][1] if number < len(cumulative) else total)
                break
        row["actual"] = (found[1] / total * 100) if found else None
        row["line"] = found[0] + 1 if found else None
        actual.append(row)

    missing = [r["anchor"] for r in actual if r["actual"] is None]
    dup = {r["anchor"] for r in actual if [x["anchor"] for x in actual].count(r["anchor"]) > 1}
    show("锚点全部命中且唯一", not missing and not dup, "缺失:" + ",".join(missing[:3]) + (" 重复:" + ",".join(list(dup)[:3]) if dup else ""))

    valid = [r for r in actual if r["actual"] is not None]
    if len(valid) < 6:
        print("\nHYPE: FAIL → 锚点必须能在正文里定位，先补齐锚点。")
        return 1

    density = len(valid) / (total / 1000)
    show("节点密度≥4.0/千字", density >= 4.0, f"{density:.1f}/千字（{len(valid)}节点/{total}字）")

    positive = [r for r in valid if r["mood"] >= 3]
    # 39 篇样本里正向爽点（≥+3）绝对数：01=6、04=2、13=5、15=3、21=2。
    # 沉沦/代价题天然少正向（15=0.7/千字），所以这里卡绝对数，不卡每千字比例。
    show("正向爽点≥2个(≥+3)", len(positive) >= 2, f"{len(positive)} 个：{'、'.join(r['event'][:10] for r in positive[:5])}")

    if positive:
        first = min(positive, key=lambda r: r["actual"])
        show("首个爽点≤22%", first["actual"] <= 22, f"{first['actual']:.0f}% {first['event'][:18]}")
    else:
        show("首个爽点≤22%", False, "没有任何情绪值≥+3的爽点")

    peak = max(valid, key=lambda r: r["mood"])
    trough_first = bool(re.search(r"沉沦|代价|实录|忏悔", setting))
    peak_ok = (peak["mood"] >= 3 and 15 <= peak["actual"] <= 55) if trough_first else (peak["mood"] >= 5 and 25 <= peak["actual"] <= 48)
    show("峰值位置与强度", peak_ok, f"{peak['mood']:+d} @ {peak['actual']:.0f}%（{'沉沦/代价题' if trough_first else '爽/加冕题'}）")
    big = len([r for r in valid if r["mood"] >= 5])
    show("大爽点≥2个(≥+5)", big >= 2 or (trough_first and big >= 1), f"{big} 个")
    show("谷底≥1个(≤-6)", len([r for r in valid if r["mood"] <= -6]) >= 1, f"{[r['mood'] for r in valid if r['mood'] <= -6]}")

    ordered = sorted(valid, key=lambda r: r["actual"])
    gaps = [(b["actual"] - a["actual"], a, b) for a, b in zip(ordered, ordered[1:])]
    worst = max(gaps, key=lambda g: g[0]) if gaps else (0, None, None)
    show("无>22%情绪死区", worst[0] <= 22, f"最大间距 {worst[0]:.0f}%（{worst[1]['event'][:12]} → {worst[2]['event'][:12]}）" if gaps else "")

    # v5 快推结构：主线大事件必须 ≤32%，之后还要有 ≥4 个节点。
    # 钩子（结果前置/开场画面）不算大事件——它只是把结论先扔出来，不等于剧情启动。
    BIG = re.compile(r"对质|兑现|翻车|社死|承认|面试|爆点|峰值|反转|结账")
    HOOK = re.compile(r"钩子|前置|开场")
    bigs = [r for r in valid if not HOOK.search(r["type"]) and (r["mood"] >= 5 or BIG.search(r["type"]))]
    if bigs:
        first_big = min(bigs, key=lambda r: r["actual"])
        show("首个大事件≤32%", first_big["actual"] <= 32, f"{first_big['actual']:.0f}% [{first_big['type']}] {first_big['event'][:16]}")
        after = [r for r in valid if r["actual"] > first_big["actual"] + 1]
        show("爆点之后≥4节点", len(after) >= 4, f"{len(after)} 个（{after[0]['event'][:10] if after else '—'} …）")
    else:
        show("首个大事件≤32%", False, "爽点表里没有任何对质/兑现/≥+5 的大事件")
        show("爆点之后≥4节点", False, "没有大事件就无法谈后半")
    second_half = [r for r in valid if r["actual"] > 50]
    show("后半(>50%)≥3节点", len(second_half) >= 3, f"{len(second_half)} 个：{'、'.join(r['event'][:8] for r in second_half[:4])}")
    show("结尾锚点≥85%", ordered[-1]["actual"] >= 85, f"{ordered[-1]['actual']:.0f}% {ordered[-1]['event'][:18]}")

    # ---------- v6：钱的去向（兑现/暴富题） ----------
    FULFILL = re.compile(r"中奖|奖金|到账|彩票|拆迁|遗产|继承|暴富|分红|赔款")
    MONEY_KINDS = ("给自己人", "被骗", "补欠", "场面", "借出", "亏")
    SAD_END = re.compile(r"报案|报警|跑路|卷走|办公室空|空壳|假合同|被骗|骗走|要不回来")
    HABIT = re.compile(r"每天一张|天天|每天买|守号|日复一日|每天都要")

    def parse_money(block: str):
        rows = []
        for line in block.splitlines():
            if not line.startswith("|") or re.match(r"^\|\s*:?-", line):
                continue
            cells = [c.strip().strip("*").strip() for c in line.strip("|").split("|")]
            if len(cells) < 4 or re.fullmatch(r"[笔序]\s*数?|序号|#|合计", cells[0]):
                continue
            kind = next((k for k in MONEY_KINDS if any(c == k or c.startswith(k) for c in cells)), None)
            if not kind:
                continue
            rows.append({"kind": kind, "cells": cells, "anchor": cells[-1]})
        return rows

    def parse_drift(block: str):
        rows = []
        for line in block.splitlines():
            if not line.startswith("|") or re.match(r"^\|\s*:?-", line):
                continue
            cells = [c.strip().strip("*").strip() for c in line.strip("|").split("|")]
            if len(cells) < 4 or re.fullmatch(r"序|序号|#|维度|项目", cells[0]):
                continue
            if any(c in {"旧做法", "新做法", "他的说法", "正文锚点", "类别", "他人反应", "金额"} for c in cells):
                continue
            if not any(cells):
                continue
            rows.append({"anchor": cells[-1], "cells": cells})
        return rows

    if len(FULFILL.findall(setting)) >= 4:
        flow = section(setting, "钱的去向表", "钱的去向", "去向表")
        show("钱的去向表存在", bool(flow), "兑现/暴富题必须写「## 钱的去向表」：笔数 / 金额 / 类别 / 他人反应 / 正文锚点")
        if flow:
            money = parse_money(flow)
            show("去向表≥8笔", len(money) >= 8, f"{len(money)} 笔（类别：补欠 / 场面 / 给自己人 / 借出 / 亏 / 被骗）")
            kinds = Counter(r["kind"] for r in money)
            if money:
                total_pen = len(money)
                care = (kinds["补欠"] + kinds["场面"]) / total_pen
                show("补欠+场面≥50%", care >= 0.5, f"补欠{kinds['补欠']}+场面{kinds['场面']}={kinds['补欠'] + kinds['场面']}/{total_pen}（{care:.0%}）")
                show("借出≤20%", kinds["借出"] / total_pen <= 0.2, f"借出 {kinds['借出']}/{total_pen}（{kinds['借出'] / total_pen:.0%}）")
                show("被骗≤1笔", kinds["被骗"] <= 1, f"{kinds['被骗']} 笔（被骗不能是归零主因）")
                show("亏≤15%", kinds["亏"] / total_pen <= 0.15, f"亏 {kinds['亏']}/{total_pen}")
                missing = [r["anchor"] for r in money if r["anchor"] and r["anchor"] not in text]
                show("去向锚点命中正文", not missing, "缺失:" + "、".join(m[:12] for m in missing[:3]))
            account = re.search(
                r"到账\s*([\d,]+)\s*\+\s*[^+\n]*?([\d,]+)\s*[-−]\s*[^=\n]*?([\d,]+)\s*=\s*[^=\n]*?([\d,]+)",
                flow,
            )
            if account:
                cash = [int(x.replace(",", "")) for x in account.groups()]
                show("钱账误差0", cash[0] + cash[1] - cash[2] == cash[3], f"{cash[0]}+{cash[1]}-{cash[2]}={cash[0] + cash[1] - cash[2]}，表内余额 {cash[3]}")
            else:
                show("钱账误差0", False, "去向表下必须有「到账 X + 变卖 Y − 去向 Z = 余额 W」一行")
            sad = [line for line in lines if SAD_END.search(line)]
            show("憋屈结算≤2处", len(sad) <= 2, f"{len(sad)} 处：" + " / ".join(line[:14] for line in sad[:3]))
    else:
        print("---- 非兑现/暴富题，跳过「钱的去向」门")

    # ---------- v7：转场表（压缩段回位句） ----------
    if "跨度图" in setting:
        trans = section(setting, "转场表")
        show("转场表存在", bool(trans), "长期跨度题必须写「## 转场表」：压缩段 → 回位句 → 正文锚点")
        if trans:
            trows = []
            for line in trans.splitlines():
                if not line.startswith("|") or re.match(r"^\|\s*:?-", line):
                    continue
                cells = [c.strip().strip("*").strip() for c in line.strip("|").split("|")]
                if len(cells) < 3 or any(c in {"压缩段", "回位句", "正文锚点"} for c in cells):
                    continue
                trows.append(cells[-1])
            show("转场表≥2行", len(trows) >= 2, f"{len(trows)} 行")
            miss_t = [a for a in trows if a and a not in text]
            show("回位句命中正文", not miss_t, "缺失:" + "、".join(m[:12] for m in miss_t[:3]))
    else:
        print("---- 非长期跨度题，跳过「转场表」门")

    # ---------- v6：习惯漂移（习惯/成瘾题） ----------
    if len(HABIT.findall(setting)) >= 3:
        drift_block = section(setting, "习惯漂移")
        show("习惯漂移表存在", bool(drift_block), "习惯/成瘾题必须写「## 习惯漂移」：旧做法 → 新做法 → 他的说法 → 正文锚点")
        if drift_block:
            drift_rows = parse_drift(drift_block)
            show("习惯漂移≥2行", len(drift_rows) >= 2, f"{len(drift_rows)} 行")
            miss = [r["anchor"] for r in drift_rows if r["anchor"] and r["anchor"] not in text]
            show("漂移锚点命中正文", not miss, "缺失:" + "、".join(m[:12] for m in miss[:3]))
            # v7：规模必须变（新做法 > 旧做法），只换号码不算漂移。
            grew = []
            for row in drift_rows:
                cells = row.get("cells", [])
                if len(cells) < 2:
                    continue
                old_scale, new_scale = scale_signature(cells[0]), scale_signature(cells[1])
                if (old_scale[0] and new_scale[0] > old_scale[0]) or (old_scale[1] and new_scale[1] > old_scale[1]):
                    grew.append((f"金额{old_scale[0]}→{new_scale[0]}", f"注数{old_scale[1]}→{new_scale[1]}"))
            show("漂移含规模变大", bool(grew), f"{grew[:2]}（旧做法数字 → 新做法数字）")
    else:
        print("---- 非习惯/成瘾题，跳过「习惯漂移」门")

    drift = [r for r in valid if abs(r["actual"] - r["pos"]) > 8]
    show("声明位置与正文一致", not drift, " / ".join(f"#{r['no']} 声明{r['pos']}% 实际{r['actual']:.0f}%" for r in drift[:4]))

    tail = "".join(lines[-12:])
    show("结尾有数字/器物判词", bool(re.search(r"\d|[零一二三四五六七八九十百千万]", tail)) and bool(RITUAL.search(tail)), tail[-24:])

    if bad:
        print(f"\nHYPE: FAIL {len(bad)} → 对照 拆文库 的情绪曲线补爽点：先补位置，再改正文。")
        return len(bad)
    print("\nHYPE: PASS 爽点密度与位置符合拆文库实测区间。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
