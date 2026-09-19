#!/usr/bin/env python3
"""人生副本的设计、事实、成稿与复核门禁。

用法
  python3 scripts/fuben_loop.py design 作品/NN_xxx/设定.md
  python3 scripts/fuben_loop.py facts  作品/NN_xxx/
  python3 scripts/fuben_loop.py draft  作品/NN_xxx/
  python3 scripts/fuben_loop.py review 作品/NN_xxx/
  python3 scripts/fuben_loop.py record NN 点赞 [播放] [备注]
  python3 scripts/fuben_loop.py report

本文件刻意不把「300 行」「八拍」「台词行数」当成质量本身。它们只能是格式提醒；
事实锁、因果台账、时间线和对象指代才是 BLOCK 条件。
"""
from __future__ import annotations

import csv
import glob
import json
import os
import re
import statistics as st
import sys
from typing import Iterable, List, Sequence, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKS = os.path.join(ROOT, "作品")
LIB = os.path.join(ROOT, "拆文库")
DATA = os.path.join(WORKS, "_数据.csv")

# 允许 scripts/ 作为模块目录，也允许用户直接从仓库根运行本文件。
if os.path.join(ROOT, "scripts") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
from fuben_consistency import check_directory, content_lines, section, years  # noqa: E402

HAN = lambda text: len(re.findall(r"[\u4e00-\u9fff]", text))


def read(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except FileNotFoundError:
        return ""


def lib_titles() -> List[str]:
    return [os.path.basename(d).split("_", 1)[-1] for d in glob.glob(os.path.join(LIB, "[0-9]*"))]


def table_rows(text: str, heading_terms: Sequence[str]) -> List[str]:
    block = section(text, *heading_terms)
    return [line for line in block.splitlines() if re.match(r"^\|", line) and not re.match(r"^\|\s*:?-", line)]


def dialogue_units(lines: Sequence[str]) -> List[Tuple[int, str]]:
    """Count actual speech markers, not every occurrence of the character「说」.

    「说出、说完、说到、据说、听说」是叙述动词，不算对白；带空格的
    `陈哲说 你还买不买`、`你问 多少钱` 才算。无引号短台词仍由人工在
    `对白预算` 中登记，避免把口播换行误判成对白。
    """
    speech = re.compile(r"(?:^|\s)(?:你|他|她|母亲|爸爸|妈妈|老板娘|陈哲|老周|主管|同事|同学|室友|门卫|前台|客户|小伙|辅导员|财务|大老板)?(?:说|问|回|喊|回答|提醒|告诉|嘀咕|开口)[：:]?\s+(?!出|完|着|到|明|清|起|来|过|的是|出来)")
    result: List[Tuple[int, str]] = []
    for index, line in enumerate(lines):
        if re.search(r"^[「『\"]|[」』\"]$", line) or speech.search(line):
            # 标题中的「」不在正文 lines 中；短行「今天」不应被算作对白。
            if not re.search(r"(?:说|问|回|喊|回答|提醒|告诉|嘀咕|开口)|^[「『\"]", line):
                continue
            result.append((index + 1, line))
    return result


def _need(bad: List[str], label: str, ok: bool, why: str = "") -> None:
    print(("OK  " if ok else "BAD ") + label + ("" if ok else "  ← " + why))
    if not ok:
        bad.append(label)


# ---------- L1 设计门禁 ----------
def design(path: str) -> int:
    setting = read(path)
    if not setting:
        print("BAD 设定.md  ← 文件不存在或为空")
        return 1
    bad: List[str] = []
    core = section(setting, "主线")
    fact_lock = section(setting, "事实锁", "事实账", "事实底座")
    ledger = section(setting, "因果", "状态台账", "状态变化", "转场台账")
    structure = section(setting, "结构验收", "可读性验收")
    travel = section(setting, "呼应")
    imported = section(setting, "拆书情节移植", "情节移植", "参考")

    _need(bad, "事实锁存在", bool(fact_lock), "先写 ## 事实锁，不得只写散落的 L0 资料")
    if fact_lock:
        for label, pattern in [
            ("规则/玩法", r"玩法|规则|制度|题材事实"),
            ("频率/次数", r"频率|每天|每周|每月|次数"),
            ("单价/金额", r"单价|价格|金额|成本|奖金|工资"),
            ("对象/号码", r"对象|号码|物件|人物|地点"),
            ("结果/判定", r"结果|判定|中奖|结局|验收"),
            ("禁止越界", r"禁止|不写|不得|不能|反事实"),
        ]:
            _need(bad, f"事实锁·{label}", bool(re.search(pattern, fact_lock, re.I)), "事实锁必须可供正文逐项对账")
    _need(bad, "因果/状态台账存在", bool(ledger), "写每拍的触发、动作、状态前/后、下一步")
    if ledger:
        ledger_rows = [r for r in ledger.splitlines() if re.match(r"^\|", r) and not re.match(r"^\|\s*:?-", r)]
        _need(bad, "状态台账≥5条", len(ledger_rows) >= 6, f"当前 {len(ledger_rows)} 行（含表头）")
        _need(bad, "台账有触发与状态变化", bool(re.search(r"触发|因为|所以|当天|第二天", ledger)) and bool(re.search(r"前|后|状态|余额|数量|停止|开始", ledger)), "因果链不能只列年份")

    _need(bad, "主线四字段", bool(core) and all(re.search(k, core) for k in ("设定", "核心行动", "悬念", "一句话")), "主线必须回答谁、一直做什么、等什么、最后变成什么")
    _need(bad, "参考来源已标", bool(re.search(r"拆文库/|对标|参考|借用|来源", setting)), "至少写一个实际读取过的拆文库案例，不得只写手法名")
    # 不再要求「八拍」这种形式。路线图有两条合法路径：
    #   ① 情绪节拍表（首选）：位置 / 情绪值 / 事件 / 状态前后；
    #   ② 旧版八拍表（兼容旧稿）。
    # 无论哪条，都必须有 ≥8 行，且 ≥6 行写清情绪值、峰值/谷底或状态动作。
    beats = section(setting, "情绪节拍", "节拍表", "爽点节拍", "八拍")
    beat_rows = [line for line in beats.splitlines() if re.match(r"^\|\s*[0-9一二三四五六七八九十]+\s*\|", line)]
    _need(bad, "节拍表≥8行", len(beat_rows) >= 8, "写情绪节拍表：位置 / 情绪值 / 事件 / 状态前后；八拍不是必填形式")
    marked = [line for line in beat_rows if re.search(r"[+-]\s*\d|推进|受阻|揭示|改变|停止|核对|峰值|谷底", line)]
    _need(bad, "每节有情绪或状态", len(marked) >= 6, "至少六节写清情绪值、峰值/谷底或状态变化，不能只写年份")
    hype = section(setting, "爽点表")
    _need(bad, "爽点表≥6行", len([line for line in hype.splitlines() if re.match(r"^\|\s*\d+\s*\|", line)]) >= 6, "爽点是硬要求：位置 / 情绪值 / 事件 / 类型 / 正文锚点，缺了就写不出爽点稿")
    _need(bad, "贯穿物件/人物台账", bool(re.search(r"物件台账|物证台账|人物台账|贯穿物件", setting)), "首次出现、再次碰到、回收动作要有名字")
    _need(bad, "呼应表≥5对", len(re.findall(r"^\|\s*\d+\s*\|", travel, re.M)) >= 5, "每一对都要有前置和后半回收")
    _need(bad, "对白预算已锁", bool(re.search(r"对白预算|对白上限|对白只保留", setting)), "写总行数/场景上限/允许保留的功能")
    _need(bad, "开头路线已锁", bool(re.search(r"线性|开头不倒叙|倒叙合法|结果前置", setting)), "默认从第一件事开始；若倒叙必须标回到哪一天")
    if structure:
        _need(bad, "一遍读懂测试", bool(re.search(r"一遍读懂|初中生|第一屏|首屏", structure)), "验收写谁/物件/时间/结果是否明确")
        _need(bad, "因果测试", bool(re.search(r"因果|触发|状态", structure)), "验收每个转场是否能回答为什么现在发生")
        _need(bad, "数字/事实测试", bool(re.search(r"数字|事实|对账|守恒", structure)), "验收金额、频率、数量、日期")
    else:
        _need(bad, "结构验收节存在", False, "加 ## 结构验收：首屏、时间线、因果、称呼、事实、对白")

    # 有反派才要求报应/反杀；沉沦或日常题不强行制造社死。
    no_antagonist = bool(re.search(r"反派设计[:：]\s*(?:不适用|无)|对手[:：]\s*(?:无|系统规则)|没有会说话的反派|不强行写反杀", setting))
    if no_antagonist:
        _need(bad, "无对手题写明不用反杀", bool(re.search(r"不安排|不人格化|不强行|结果核对|行为后果", setting)), "沉沦/规则题用结果、核对和状态改变收束")
    else:
        _need(bad, "对手与升级触发", bool(re.search(r"对手[:：]|对手首恶|升级触发", setting)), "人物题须明确谁做了什么、何时改变")
        _need(bad, "报应/反转对应表", len(re.findall(r"^\|\s*\d+\s*\|", section(setting, "报应表", "反转表"), re.M)) >= 3, "人物题才要求一一对应，不能把规则题硬套成反杀")

    # 事实锁与设定卡先做一次轻量冲突检查。
    positive_lock_lines = [line for line in fact_lock.splitlines() if not re.search(r"禁止|不写|不得|不能|不出现|反事实", line)]
    positive_lock = "\n".join(positive_lock_lines)
    if re.search(r"每(?:张|注|票)[^\n]{0,16}(?:2\s*元|2\s*块|两元|两块)", positive_lock) and re.search(r"(?:每天|每张|单注).{0,14}(?:10\s*元|十元|十块|倍投|重仓)", positive_lock):
        _need(bad, "事实锁内部无金额冲突", False, "同一稿不能同时锁2元单张和每天10元/倍投")
    else:
        _need(bad, "事实锁内部无金额冲突", True)

    # L0 仍然需要来源，但不再让「有链接」掩盖事实锁不存在。
    l0 = section(setting, "L0 事实核查", "事实核查表")
    sources = len(re.findall(r"https?://", l0 or fact_lock))
    _need(bad, "事实来源≥2", sources >= 2, f"当前 {sources} 个链接")

    title = re.search(r"#\s*\d+\s*[·・]\s*([^（(\n]+)", setting)
    if title:
        key = title.group(1).strip()
        hits = [x for x in lib_titles() if any(word in x for word in re.findall(r"[\u4e00-\u9fff]{2,}", key)[:3])]
        _need(bad, "同题差异已说明", bool(re.search(r"同题|换视角|差异|不借", setting)) or not hits, f"拆文库已有 {hits[:3]}，说明你借了什么、避开什么")

    print("\nDESIGN:", "PASS" if not bad else f"FAIL {len(bad)} → 先改设定.md，再写正文")
    return len(bad)


# ---------- L2 facts + draft ----------
def facts(directory: str) -> int:
    issues = check_directory(directory)
    if not issues:
        print("FACTS: PASS")
        return 0
    for severity, code, message in issues:
        print(f"BAD {severity} {code}: {message}")
    print(f"FACTS: FAIL {len(issues)}")
    return len(issues)


# ---- v6.1 反流水账：时戳不得充当分段器（75 教训：开头「X点+你Y」钟面账）----
_TIME_HEAD = re.compile(
    r"^(凌晨|清晨|早上|上午|中午|下午|晚上|夜里|半夜|傍晚"
    r"|[0-9]{1,2}[:：][0-9]{1,2}"
    r"|[0-9零一二两三四五六七八九十]{1,3}点"
    r"|[0-9]{1,2}月[0-9]{1,2}[号日]?)")
_TIME_ALONE = re.compile(
    r"^(凌晨|清晨|早上|上午|中午|下午|晚上|夜里|半夜|傍晚)?[0-9零〇一二两三四五六七八九十]{1,4}[:：点][0-9零〇一二两三四五六七八九十]{0,4}$")

def _stamp_report(lines: List[str]) -> Tuple[int, int, int, List[str]]:
    """(前16行时戳开头数, 整行时戳数, 全篇时戳开头数, 违规行样例)"""
    head = [l for l in lines[:16] if _TIME_HEAD.match(l)]
    alone = [l for l in lines if _TIME_HEAD.match(l) and _TIME_ALONE.match(l.strip())]
    openn = [l for l in lines if _TIME_HEAD.match(l)]
    return len(head), len(alone), len(openn), [l[:16] for l in (head + alone)[:4]]

INNER = re.compile(r"^(你觉得|你以为|你认为|你知道|你明白|你终于|你意识到|你心里|你感到|你想)")
VERDICT = re.compile(r"(被孤立|被排挤|疏远了你|没人再|再也没有人|所有人都|大家都不|众叛亲离|自食其果|报应)")
LYRIC_END = re.compile(r"(是不是也|也许|或许|大概|你在想|不知道.*吗|吧$|呢$)")


def _timeline_info(body: str) -> Tuple[List[int], List[Tuple[int, int, str]]]:
    found = years(body)
    values = [year for year, _, _ in found]
    backwards: List[Tuple[int, int, str]] = []
    last = None
    for year, _, raw in found:
        if last is not None and year < last:
            backwards.append((last, year, raw))
        last = max(last or year, year)
    return values, backwards


def draft(directory: str) -> int:
    directory = directory.rstrip("/")
    body = read(os.path.join(directory, "正文.md"))
    setting = read(os.path.join(directory, "设定.md"))
    lines = content_lines(body)
    n = HAN(body)
    bad: List[str] = []

    def need(label: str, ok: bool, info: str = ""):
        print(("OK  " if ok else "BAD ") + f"{label:24} {info}")
        if not ok:
            bad.append(label)

    def warn(label: str, ok: bool, info: str = ""):
        # R17b 语料反向体检降级：报告制不拦截（字数/行数/环境45行 三项，大师稿违例 18–25%）。
        print(("OK  " if ok else "WARN") + f" {label:22} {info}")

    warn("字数·交付格式", 2200 <= n <= 3600, f"{n}（R17b 报告制：目标随发布形态声明，不拦截）")
    warn("行数·交付格式", 220 <= len(lines) <= 420, f"{len(lines)} 行（R17b 报告制）")
    long_lines = [line for line in lines if HAN(line) > 24]
    need("单行不过长", len(long_lines) <= 2, f"{len(long_lines)} 行 >24字")

    # 事实是硬闸；设计/正文都必须经同一份检查器。
    fact_issues = check_directory(directory)
    for severity, code, message in fact_issues:
        print(f"BAD {severity} {code}: {message}")
    if fact_issues:
        bad.append("事实/时间线一致性")

    # 首屏：不以未解释的未来结果开头；线性稿要在前12行交代具体时间/对象。
    # R20 语料反审（2026-09-19）：旧版此闸 29/44 篇 10w+ 原文被误杀（01「15岁那年冬天/
    # 你还是县一中的初三学生」被拦）——词表代理判不了「交代是否清楚」。改报告制（WARN），
    # 首屏质量归 fuben-review「首屏显微镜+钩子评分」人审；词表扩容仅作信息，不作判定。
    # 「未来结果前置」的线性检查保留硬（0.1/09 事故层）。
    first = "".join(lines[:12])
    linear = bool(re.search(r"线性|开头不倒叙", setting))
    future_open = bool(re.search(r"^(最后|多年后|七年后|两年后|中奖后|清零后)", "\n".join(lines[:3])))
    has_time_or_start = bool(re.search(r"\d{4}年|\d{1,2}月|[一二三四五六七八九十]+年|[一二三四五六七八九十]+月|第一天|第二天|小时|早晨|晚上|上午|下午|中午|傍晚|凌晨|清晨|岁|\d+点|[一二三四五六七八九十]+点|\.?\d{1,2}:\d{2}", first))
    named_object = bool(re.search(r"票|账|盒|号码|母亲|妈妈|老板娘|同事|主管|铁盒|手机|学校|公司|本子|电脑|文件夹|档案|简历|收据|截图|药|房|车|学生|同学|一中|中学|大学|店|摊|馆|宿舍|寝|车间|工地|村|镇|县|站|铺|机|被|床|门|桌", first))
    warn("首屏时间/对象(报告制)", has_time_or_start and named_object, first[:48])
    need("线性稿不深倒叙", not (linear and future_open), "前3行先写现在/未来结果再倒回，改成第一天或明确回到哪一年")

    # v6.2 反流水账+钩子豁免（二轮会审指令4）：前5行允许且仅允许1处独立钟面行（冷开场合法）；
    # 第6–16行不得出现整行时戳；时戳开头行≤max(6,3.5%)。首屏闸的时间词由嵌句满足。
    # R20 语料反审：「整行时戳全篇≤2」被 11《印度婆罗门》（一日编年体，钟点即题材）原文违例——
    # 「时间只在是信息时保留」机器不可判，整行计数改报告制；占比线保留（75 病灶 6.6%>3.5% 仍可拦）。
    _h, _a, _o, _ex = _stamp_report(lines)
    _alone_head = [l for l in lines[:16] if _TIME_ALONE.match(l.strip())]
    _alone_mid = [l for l in lines[5:16] if _TIME_ALONE.match(l.strip())]
    need("开头不堆时戳", _h <= 1 and not _alone_mid and _o <= max(6, int(len(lines) * 0.035)),
         "前16行时间开头 %d（独立钟面仅许第1–5行1处）、时戳开头行 %d/%d｜例：%s" % (_h, _o, len(lines), " | ".join(_ex)))
    warn("整行时戳计数(报告制)", _a <= 2, "全篇整行时戳 %d｜一日编年/病程钟点题合法（11 先例），流水账交人审" % _a)

    # R20 语料反审：「你以为X」是拆文库标准的错位引入钩（02/04 判词结构「你以为…其实…」），
    # 不计入内心闸；「你觉得/你感到」等惰性直报仍拦（3.9 红线：情绪翻译成动作）。
    inner = [line for line in lines if re.search(r"^(你觉得|你认为|你知道|你明白|你终于|你意识到|你心里|你感到|你想)", line)]
    need("主角内心≤6", len(inner) <= 6, " / ".join(line[:14] for line in inner[:5]))
    # R20 语料反审：旧判决词表把「围观对位」（所有人都看着你）与「行为事实」（再也没有人回应你）
    # 当宣判误杀，6/44 原文违例且全部为合法机制（01/17/37 等）。判决闸只拦「旁白宣布因果清算」；
    # 围观/疏远类场面词改报告制，交人审区分「写行为」与「下判词」。
    verdict = [line for line in lines if re.search(r"(自食其果|活该|罪有应得|报应|恶有恶报|天道好轮回|你堕落了|这就是命|这就是报应|这就是结局)", line)]
    need("叙述者不替观众判决", not verdict, " / ".join(line[:18] for line in verdict[:3]))
    scene_judge = [line for line in lines if VERDICT.search(line) and not re.search(r"(自食其果|活该|罪有应得|报应|恶有恶报|天道好轮回|你堕落了|这就是命)", line)]
    warn("围观/疏远判决词(报告制)", not scene_judge, " / ".join(line[:16] for line in scene_judge[:3]) or "无")

    speech = dialogue_units(lines)
    # 人生副本是旁白稿，直接对白默认≤8个功能单位且≤4%；静态记载仍可写进设定。
    speech_limit = max(8, int(len(lines) * 0.04))
    need("对白稀缺", len(speech) <= speech_limit, f"{len(speech)} / {speech_limit}：" + " | ".join(line[:14] for _, line in speech[:5]))
    ack = [(line_no, line) for line_no, line in speech if re.search(r"(?:说|回|回答)\s+(?:好|行|嗯|哦|是|知道|好的|没事|没有)\s*$", line)]
    need("无空回应", not ack, " / ".join(f"L{no} {line}" for no, line in ack[:4]))

    values, backwards = _timeline_info(body)
    unique_years = len(set(values))
    need("时间顺序不倒退", not backwards, str(backwards[:2]))
    need("时间锚点不过载", unique_years <= 12, f"{unique_years} 个年份锚点")

    # v6 跨度检查：长期题不许写成「第一年…第二年…」的年表。
    # 观众反馈「第 1 年到第 7 年跳转生硬」的机械特征就是这一串编号行——
    # 压时间要靠「同一动作重复 + 细节漂移」，不是按年列条目（拆文库 01/05 时间操控）。
    YEAR_LEDGER = re.compile(r"^第\s*[一二三四五六七八九十\d]+\s*个?年")
    ledger_lines = [i + 1 for i, line in enumerate(lines) if YEAR_LEDGER.match(line)]
    consecutive = any(ledger_lines[i + 1] - ledger_lines[i] == 1 for i in range(len(ledger_lines) - 1))
    need(
        "跨度不用年表罗列",
        len(ledger_lines) <= 2 and not consecutive,
        f"{len(ledger_lines)} 行以「第N年」开头{'（含连续）' if consecutive else ''}："
        + " / ".join(lines[i - 1][:14] for i in ledger_lines[:4]),
    )

    # 以设定里的主线关键词做覆盖提醒；没有关键词则以核心行动的显性名词为后备。
    key_match = re.search(r"主线关键词[:：]\s*([^\n]+)", setting)
    if key_match:
        keywords = [k for k in re.split(r"[/、,，\s]+", key_match.group(1)) if k]
    else:
        core = section(setting, "主线")
        keywords = [k for k in re.findall(r"[\u4e00-\u9fff]{2,4}", core) if k not in {"核心行动", "一句话主线", "悬念问句"}][:6]
    if keywords:
        hits = []
        for part in range(8):
            chunk = "".join(lines[part * len(lines) // 8:(part + 1) * len(lines) // 8])
            hits.append(any(word in chunk for word in keywords))
        need("主线贯穿≥5/8段", sum(hits) >= 5, f"{sum(hits)}/8 {keywords}")
    else:
        need("主线关键词可追", False, "设定.md 主线加入「主线关键词」或可复述的核心行动")

    # 末段必须是动作/状态，不用抽象鸡汤收口。
    tail = lines[-6:]
    need("收束不抒情", not any(LYRIC_END.search(line) for line in tail[:-1]), " / ".join(tail[-3:])[:80])
    need("末句≤25字", HAN(tail[-1]) <= 25, tail[-1][:32])
    # R20 语料反审：10/44 原文含品牌且全部是剧情主体（15 卖肾换的就是 iPhone、23 分期买的 Mac、
    # 01 的 Xiaomi 手机、05 的 AJ）——「品牌≠装饰」机器不可判。改报告制（与 R13b 删除 texture
    # 品牌行同判）；去品牌红线由 fuben-review 人审执行（64 豆包→那个AI 先例：人审抓得出，闸抓不对）。
    from collections import Counter as _C
    brands = _C(re.findall(r"资生堂|Mac|MAC|空军一号|AJ|耐克|阿迪|苹果|iPhone|华为|小米|星巴克|瑞幸|喜茶|优衣库|ZARA", body))
    warn("品牌出现(报告制)", not brands, f"{dict(brands)}｜主体道具(事实锁登记/出现≥3次)→放行；装饰→删")

    # 环境/身体只做低强度防流水账提醒：不为达标硬塞感官。
    phys = re.compile(r"手|耳朵|后背|喉咙|胃|膝盖|呼吸|汗|发麻|发烫|发凉|嗡|味道|声音|灯|门|窗|风|雨|凉|热|空调|冷气|响|湿|烫|烟味|太阳|水壶")
    gaps = [start + 1 for start in range(0, len(lines), 45) if not any(phys.search(line) for line in lines[start:start + 45])]
    warn("每45行环境/身体", not gaps, f"空窗起行 {gaps}（R17b 词表代理降级：语料 11/44 违例，报告不拦截）")

    print("\nDRAFT:", "PASS" if not bad else f"FAIL {len(bad)}")
    return len(bad)


# ---------- L2.5 人工对照提醒 ----------
def review(directory: str) -> int:
    directory = directory.rstrip("/")
    body = read(os.path.join(directory, "正文.md"))
    setting = read(os.path.join(directory, "设定.md"))
    lines = content_lines(body)
    N = len(lines)
    bad = 0

    def show(label: str, value: object, ok: bool):
        nonlocal bad
        print(("OK  " if ok else "BAD ") + f"{label:24} {value}")
        if not ok:
            bad += 1

    for severity, code, message in check_directory(directory):
        print(f"BAD {severity} {code}: {message}")
        bad += 1

    # 每个转场都必须能在正文找到触发词；不是把年月标题排成一列。
    transition_words = len(re.findall(r"因为|所以|因此|当天|第二天|那天之后|于是|仍然|决定|直到", body))
    year_count = len(set(year for year, _, _ in years(body)))
    show("转场有因果词", transition_words >= max(3, min(8, year_count)), f"{transition_words} 个触发词 / {year_count} 个年份")

    travel = section(setting, "呼应")
    pairs = re.findall(r"^\|\s*\d+\s*\|([^|]+)\|([^|]+)\|", travel, re.M)
    tail = "".join(lines[int(N * 0.40):]) if N else ""
    recovered = 0
    for setup, payoff in pairs:
        words = [word for word in re.findall(r"\d{2,4}|[\u4e00-\u9fff]{2,3}", payoff) if word not in {"没有", "一个", "你的", "她的", "仍然", "结果", "第一", "第"}]
        if any(word in tail for word in words[:10]):
            recovered += 1
    required = max(3, (len(pairs) * 7 + 9) // 10) if pairs else 0
    show("呼应后半有回收", f"{recovered}/{len(pairs)}", recovered >= required)

    no_antagonist = bool(re.search(r"反派设计[:：]\s*(?:不适用|无)|对手[:：]\s*(?:无|系统规则)|没有会说话的反派|不强行写反杀", setting))
    if no_antagonist:
        show("不强制反杀现场", True, "规则/习惯题改看结果核对与状态改变")
        show("结尾有状态动作", bool(re.search(r"停止|放回|关掉|合上|走向|留下|只剩|不再", "".join(lines[-8:]))), "".join(lines[-4:])[:70])
    else:
        show("人物题有反转现场", bool(re.search(r"反杀|对质|面试|审判|报应", setting)) and bool(re.search(r"问|停|收回|转身", body)), "需人工核对落点")

    show("结局没有越过事实锁", not any(code in {"GAME_MIX", "UNIT_DRIFT", "FREQUENCY_DRIFT", "NUMBER_DRIFT", "OMEN_DRIFT", "TICKET_NO_MISMATCH", "DATE_COUNT_MISMATCH"} for _, code, _ in check_directory(directory)), "金额/日期/号码/规则")
    print("\nREVIEW:", "PASS" if bad == 0 else f"FAIL {bad} → 先改对应拍，再做三方审核")
    return bad


# ---------- L3 数据回流 ----------
def features(directory: str):
    body = read(os.path.join(directory, "正文.md"))
    setting = read(os.path.join(directory, "设定.md"))
    lines = content_lines(body)
    if not lines:
        return None
    tail = "".join(lines[-6:])
    return dict(
        字数=HAN(body),
        呼应对=len(re.findall(r"^\|\s*\d+\s*\|", section(setting, "呼应"), re.M)),
        内心句=sum(bool(INNER.search(line)) for line in lines),
        宣判句=sum(bool(VERDICT.search(line)) for line in lines),
        台词单位=len(dialogue_units(lines)),
        抒情收束=int(bool(LYRIC_END.search(tail))),
        年份锚点=len(set(year for year, _, _ in years(body))),
        价格数=len(re.findall(r"\d+(?:\.\d+)?\s*(?:块|元|万)", body)),
        因果词=len(re.findall(r"因为|所以|因此|于是|第二天|当天|仍然", body)),
    )


def record(args: Sequence[str]) -> None:
    if len(args) < 2:
        raise SystemExit("record 用法: record NN 点赞 [播放] [备注]")
    nid, likes = args[0], int(args[1])
    plays = int(args[2]) if len(args) > 2 and args[2].isdigit() else ""
    note = " ".join(args[3:]) if len(args) > 3 else ""
    directory = next((x for x in glob.glob(os.path.join(WORKS, f"{nid}_*")) if os.path.isdir(x)), None)
    if not directory:
        raise SystemExit(f"找不到 作品/{nid}_*")
    feat = features(directory) or {}
    new = not os.path.exists(DATA)
    with open(DATA, "a", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        if new:
            writer.writerow(["id", "目录", "点赞", "播放", "备注"] + list(feat))
        writer.writerow([nid, os.path.basename(directory), likes, plays, note] + list(feat.values()))
    print("已记录 →", DATA)
    print(json.dumps(feat, ensure_ascii=False))


def report() -> None:
    if not os.path.exists(DATA):
        raise SystemExit("还没有数据：先 record")
    rows = list(csv.DictReader(open(DATA, encoding="utf-8")))
    if len(rows) < 4:
        print(f"仅 {len(rows)} 条，归因不稳；先列出：")
    keys = [key for key in rows[0] if key not in ("id", "目录", "点赞", "播放", "备注")]
    print(f"{'篇':6}{'点赞':>6}  " + " ".join(f"{key:>7}" for key in keys))
    for row in rows:
        print(f"{row['id']:6}{row['点赞']:>6}  " + " ".join(f"{row[key]:>7}" for key in keys))
    if len(rows) >= 4:
        likes = [float(row["点赞"]) for row in rows]
        median = st.median(likes)
        print("\n特征 × 点赞（只有方向稳定才升级 skill）")
        for key in keys:
            try:
                high = [float(row[key]) for row in rows if float(row["点赞"]) > median]
                low = [float(row[key]) for row in rows if float(row["点赞"]) <= median]
                if high and low:
                    print(f"  {key:8} 高组 {st.mean(high):7.1f}  低组 {st.mean(low):7.1f}  差 {st.mean(high)-st.mean(low):+7.1f}")
            except ValueError:
                pass
        print("\n处置：机械门禁解决一致性与可读性；发布数据只改 advisory，不拿小样本替代事实门禁。")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    command, args = sys.argv[1], sys.argv[2:]
    if command == "design":
        raise SystemExit(design(args[0]))
    if command in {"facts", "consistency"}:
        raise SystemExit(facts(args[0]))
    if command == "draft":
        raise SystemExit(draft(args[0]))
    if command == "review":
        raise SystemExit(review(args[0]))
    if command == "record":
        record(args)
    elif command == "report":
        report()
    else:
        raise SystemExit(__doc__)
