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
- v9 花光的底气：`## 花光的底气` 表 ≥2 行 + 锚点命中；正文信念句（还会中/下一期/再中）≥2 处
- v10 底气引擎：信念句 ≥3 处（每个花钱阶段至少一处）；`## 加注阶梯` ≥3 行且金额逐级变大 + 锚点命中；
  小奖是燃料（写「五块十块中过不少、大的没有」），不许写「一次都没中过」
- v8 钱的去向定稿：**补欠+场面 ≥70%**、**补欠 ≥4 笔**（旅游 / 想买没买的 / 请自己的朋友）、
  **借出 = 0 笔**（亲戚借钱只写拒绝现场）；新增 `## 忘本（拒绝与筛选）` 表 ≥3 行 + 锚点命中正文
- v7 转场：跨度题必须写 `## 转场表`（压缩段 → 回位句 → 正文锚点），回位句必须命中正文
- v7 习惯漂移加严：至少一行要「新做法里的数字 > 旧做法」（号码换 + 买得更多）
"""
from __future__ import annotations

import os
import re
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

NEG_HEAD = re.compile(r"(?:不|没|无|别|勿|非|莫|未)[^\n]{0,3}$")
NEG_LINE = re.compile(r"禁止|不得|不许|不写|不是|避免|反事实|防错|不出现|不人格化|不强行")

def count_positively(pattern: "re.Pattern", text: str) -> int:
    """v5.1 否定窗口：与 fuben_consistency._locked_game 同构——「不写到账神话」
    这类反事实清单行不得计入兑现/习惯题触发数（75 号踩坑：否定句 ×4 误开钱的去向门）。"""
    n = 0
    for m in pattern.finditer(text):
        line_start = text.rfind("\n", 0, m.start()) + 1
        line_end = text.find("\n", m.start())
        line = text[line_start:line_end if line_end != -1 else len(text)]
        ctx = text[max(0, m.start() - 6):m.start()]
        if NEG_LINE.search(line) or NEG_HEAD.search(ctx):
            continue
        n += 1
    return n


if os.path.join(ROOT, "scripts") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
from fuben_consistency import read, section  # noqa: E402

HAN = lambda text: len(re.findall(r"[\u4e00-\u9fff]", text))
CN_DIGITS = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def _cn_value(token: str) -> int:
    if token in CN_DIGITS:
        return CN_DIGITS[token]
    # R18 修：支持 百/千 位（「二百」原实现只认十位、误返回 2；78 号习惯漂移踩坑）
    m = re.fullmatch(r"([零一二两三四五六七八九]?)([百千])([零一二两三四五六七八九]?)", token)
    if m:
        base = CN_DIGITS.get(m.group(1), 1) if m.group(1) else 1
        unit = 100 if m.group(2) == "百" else 1000
        tail = CN_DIGITS.get(m.group(3), 0) if m.group(3) else 0
        return base * unit + tail
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

    money = max([amount(m) for m in re.findall(r"(\d+|[零一二两三四五六七八九十百千]+)\s*(?:元|块)", text)] or [0])
    notes = max([amount(m) for m in re.findall(r"(\d+|[零一二两三四五六七八九十百千]+)\s*注", text)] or [0])
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
                "who": cells[6] if len(cells) >= 7 else None,
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

    # ---------- R21 在场腿（语料解剖：≥+5 节点 78% 在场者≥2；峰值独享＝观众判「不爽」的机械指纹） ----------
    # 爽点表第 7 列「在场」为版本开关：老表无该列 → WARN 报告制（不追改）；新稿登记了列 → 硬核。
    # 「无」＝作者自报私享爽点：≥+5 封顶 +4（回血/独处节点落结尾判词可以，报 +5+ 不行）。
    HOOK = re.compile(r"钩子|前置|开场")
    if any(r.get("who") is not None for r in rows):
        STOP = {"你", "它", "自己", "别人", "你们", "我们"}
        hi_rows = [r for r in valid if r["mood"] >= 5 and not HOOK.search(r["type"] or "")]
        solo, orphan = [], []
        for r in hi_rows:
            who_raw = re.sub(r"（.*?）", "", (r.get("who") or "").strip())
            names = [t for t in re.split(r"[、，,/;；]", who_raw) if len(t) >= 2 and t not in STOP]
            if who_raw in {"", "无", "—", "-"} or not names:
                solo.append(f"{r['event'][:12]}←{who_raw or '未登'}")
                continue
            idx = (r.get("line") or 1) - 1
            window = " ".join(lines[max(0, idx - 10): idx + 11])
            if not any(n in window for n in names):
                orphan.append(f"{r['event'][:12]}←{names[0]}")
        show("无独享高爽点(在场≠无)", not solo, "私享节点≥+5：" + "、".join(solo[:3]) if solo else "")
        show("见证人落锚点±10行", not orphan, "登记了名字但场面里没人：" + "；".join(orphan[:3]) if orphan else "")
    else:
        print("WARN 在场列未登记                    （R21 新规：新稿 ≥+5 爽点须第7列写见证人；老稿豁免）")

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
    MONEY_KINDS = ("给自己人", "被骗", "补欠", "场面", "借出", "亏", "花")
    SAD_END = re.compile(r"报案|报警|跑路|卷走|办公室空|空壳|假合同|被骗|骗走|要不回来")
    # v9：花光的底气——他敢花，是因为他信还会再中（不是抽象上瘾，也不是被骗）。
    BELIEF = re.compile(r"还会中|还能中|再中一次|下一期|下期|再中一回")
    HABIT = re.compile(r"每天一张|天天|每天买|守号|日复一日|每天都要")

    def parse_money(block: str):
        rows = []
        for line in block.splitlines():
            if not line.startswith("|") or re.match(r"^\|\s*:?-", line):
                continue
            cells = [c.strip().strip("*").strip() for c in line.strip("|").split("|")]
            if len(cells) < 4 or re.fullmatch(r"[笔序]\s*数?|序号|#|合计", cells[0]):
                continue
            # 类别只认第 3 列，避免「他人反应」里出现「给朋友」被误判成类别。
            kind = cells[2] if len(cells) > 2 and cells[2] in MONEY_KINDS else None
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

    if count_positively(FULFILL, setting) >= 4:
        base = section(setting, "花光的底气", "底气")
        show("花光的底气表存在", bool(base), "兑现/暴富题必须写「## 花光的底气」：他的底气（一句话）/ 依据 / 正文锚点")
        if base:
            brows = []
            for line in base.splitlines():
                if not line.startswith("|") or re.match(r"^\|\s*:?-", line):
                    continue
                cells = [c.strip().strip("*").strip() for c in line.strip("|").split("|")]
                if len(cells) < 3 or any("底气" in c or c in {"依据", "正文锚点", "他的底气"} for c in cells):
                    continue
                brows.append(cells[-1])
            show("底气表≥2行", len(brows) >= 2, f"{len(brows)} 行")
            miss_b = [a for a in brows if a and a not in text]
            show("底气锚点命中正文", not miss_b, "缺失:" + "、".join(m[:12] for m in miss_b[:3]))
        belief = [line for line in lines if BELIEF.search(line)]
        show("正文底气≥3处", len(belief) >= 3, f"{len(belief)} 处：" + " / ".join(line[:14] for line in belief[:4]))
        ladder = section(setting, "加注阶梯")
        show("加注阶梯表存在", bool(ladder), "兑现/暴富题必须写「## 加注阶梯」：阶段 / 日期区间 / 注数 / 每天花多少 / 正文锚点")
        if ladder:
            lrows = []
            for line in ladder.splitlines():
                if not line.startswith("|") or re.match(r"^\|\s*:?-", line):
                    continue
                cells = [c.strip().strip("*").strip() for c in line.strip("|").split("|")]
                if len(cells) < 4 or any(c in {"阶段", "日期区间", "注数", "每天花多少", "正文锚点"} for c in cells):
                    continue
                money = max([int(m) if m.isdigit() else _cn_value(m) for m in re.findall(r"(\d+|[零一二两三四五六七八九十]+)\s*(?:元|块)", " ".join(cells))] or [0])
                lrows.append({"anchor": cells[-1], "money": money})
            show("加注阶梯≥3行", len(lrows) >= 3, f"{len(lrows)} 行（每天花：{[r['money'] for r in lrows]}）")
            grew = len(lrows) >= 3 and all(b["money"] > a["money"] for a, b in zip(lrows, lrows[1:]))
            show("加注逐级变大", grew, " → ".join(f"{r['money']}元" for r in lrows))
            miss_l = [r["anchor"] for r in lrows if r["anchor"] and r["anchor"] not in text]
            show("阶梯锚点命中正文", not miss_l, "缺失:" + "、".join(m[:12] for m in miss_l[:3]))
        wang = section(setting, "忘本")
        show("忘本（拒绝与筛选）表", bool(wang), "兑现/暴富题必须写「## 忘本（拒绝与筛选）」：谁来 / 怎么开口 / 你怎么拒 / 他后来 / 正文锚点")
        if wang:
            wrows = []
            for line in wang.splitlines():
                if not line.startswith("|") or re.match(r"^\|\s*:?-", line):
                    continue
                cells = [c.strip().strip("*").strip() for c in line.strip("|").split("|")]
                if len(cells) < 4 or any(c in {"谁来", "怎么开口", "你怎么拒", "他后来", "正文锚点"} for c in cells):
                    continue
                wrows.append(cells[-1])
            show("忘本表≥3行", len(wrows) >= 3, f"{len(wrows)} 行")
            miss_w = [a for a in wrows if a and a not in text]
            show("拒借锚点命中正文", not miss_w, "缺失:" + "、".join(m[:12] for m in miss_w[:3]))
        flow = section(setting, "钱的去向表", "钱的去向", "去向表")
        show("钱的去向表存在", bool(flow), "兑现/暴富题必须写「## 钱的去向表」：笔数 / 金额 / 类别 / 他人反应 / 正文锚点")
        if flow:
            money = parse_money(flow)
            show("去向表≥8笔", len(money) >= 8, f"{len(money)} 笔（类别：补欠 / 场面 / 给自己人 / 借出 / 亏 / 被骗）")
            kinds = Counter(r["kind"] for r in money)
            if money:
                total_pen = len(money)
                care = (kinds["补欠"] + kinds["场面"]) / total_pen
                show("补欠+场面≥70%", care >= 0.7, f"补欠{kinds['补欠']}+场面{kinds['场面']}={kinds['补欠'] + kinds['场面']}/{total_pen}（{care:.0%}）")
                show("补欠≥4笔", kinds["补欠"] >= 4, f"补欠 {kinds['补欠']} 笔（旅游 / 想买没买的 / 请自己的朋友）")
                show("借出=0笔", kinds["借出"] == 0, f"借出 {kinds['借出']} 笔（钱不能是借完的；亲戚借钱只写拒绝现场）")
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
    if count_positively(HABIT, setting) >= 3:
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
