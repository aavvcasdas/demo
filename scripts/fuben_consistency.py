#!/usr/bin/env python3
"""Optional fact-lock diagnostics; narrative inference is REVIEW, not a fact verdict.

No mandatory design/ledger fields. Explicit date/count arithmetic is checked only
when the author actually locks a daily frequency. Nonlinear time is allowed.
CLI and aggregate runner share fuben_policy.json dispositions.
"""
from __future__ import annotations

import datetime as _dt
import os
import re
import sys
from typing import Dict, Iterable, List, Optional, Tuple

SEVERITY = {"S1": 0, "S2": 1, "S3": 2}
NEGATION = re.compile(r"(?:没有|没|未|不再|不因|不是|不能|禁止|无|从不|并不|也不|不靠|不写|不出现|不会|未曾|不)")
# v7：事实锁若声明「中奖后」的号码与注数漂移（换号、由一注变多注），
# 带漂移标记的行不再算金额/频率越界——否则观众要的「天天买但换号、买得更多」会被误判。
DRIFT_MARK = re.compile(r"中奖后|中奖以后|中奖之后|改成|改买|改选|换号|换一组|换七个|后来|不再|一次买|加注|加到|注数|五注|十注|五十注|十五注|一天三十|一天五十|一天一百")


def read(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except FileNotFoundError:
        return ""


def content_lines(text: str) -> List[str]:
    return [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]


def section(text: str, *names: str) -> str:
    """Return the first markdown section whose heading contains one of names."""
    headings = list(re.finditer(r"^##+\s+([^\n]+)\n", text, re.M))
    for match in headings:
        title = match.group(1)
        if any(name in title for name in names):
            end = next((n.start() for n in headings if n.start() > match.start()), len(text))
            return text[match.end():end]
    return ""


def _has_positive(line: str, pattern: str) -> bool:
    """命中即算越界，除非命中片段本身或紧邻前文已经否定它。

    「单注 2 元，不倍投」这类句子以前会被判成金额漂移，因为否定词写在
    命中片段里面；现在把 match 文本一并纳入否定窗口。
    """
    for match in re.finditer(pattern, line):
        window = line[max(0, match.start() - 8):match.start()] + match.group(0)
        if not NEGATION.search(window):
            return True
    return False


def _cn_year(value: str) -> Optional[int]:
    value = value.replace("〇", "零").replace("○", "零")
    if re.fullmatch(r"[零一二三四五六七八九]{4}", value):
        return int("".join(str("零一二三四五六七八九".index(c)) for c in value))
    return None


def years(text: str) -> List[Tuple[int, int, str]]:
    found: List[Tuple[int, int, str]] = []
    for m in re.finditer(r"(?<!\d)(20\d{2})年", text):
        found.append((int(m.group(1)), m.start(), m.group(0)))
    for m in re.finditer(r"(?<![零一二三四五六七八九〇○])([零一二三四五六七八九〇○]{4})年", text):
        year = _cn_year(m.group(1))
        if year:
            found.append((year, m.start(), m.group(0)))
    return sorted(found, key=lambda x: x[1])


def iso_dates(text: str) -> List[Tuple[_dt.date, int, str]]:
    found: List[Tuple[_dt.date, int, str]] = []
    for m in re.finditer(r"(?<!\d)(20\d{2})[-年](\d{1,2})[-月](\d{1,2})日?", text):
        try:
            found.append((_dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))), m.start(), m.group(0)))
        except ValueError:
            pass
    return sorted(found, key=lambda x: x[1])


def event_years(text: str) -> List[Tuple[int, int, str]]:
    """只取以年份/日期开头的事件锚点，跳过末段「从2017年开始」的回顾。"""
    found: List[Tuple[int, int, str]] = []
    offset = 0
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            offset += len(raw_line) + 1
            continue
        if re.match(r"^(?:20\d{2}|[零一二三四五六七八九〇○]{4})年", line):
            match = re.match(r"^(20\d{2}|[零一二三四五六七八九〇○]{4})年", line)
            if match:
                raw = match.group(1)
                value = int(raw) if raw.isdigit() else _cn_year(raw)
                if value:
                    found.append((value, offset, match.group(0)))
        offset += len(raw_line) + 1
    return found


def _locked_game(source: str, all_text: str) -> Optional[str]:
    """先看事实锁自己写的「规则/玩法」格，再看没有被否定的正文描述。

    旧写法只要全文出现「福彩3D」四个字就把玩法判成 3D，连「不是福彩3D」
    这种反事实清单也会被当成事实，于是把双色球稿误判成玩法混用。
    """
    for line in source.splitlines():
        if "|" not in line or not re.search(r"规则|玩法|彩种", line):
            continue
        if re.search(r"福彩\s*3D", line):
            return "福彩3D"
        if re.search(r"双色球", line):
            return "双色球"
    positive = "\n".join(
        line for line in all_text.splitlines()
        if not re.search(r"禁止|不写|不得|不能|不出现|反事实|不是|不借|不把", line)
    )
    if re.search(r"福彩\s*3D", positive):
        return "福彩3D"
    if re.search(r"双色球", positive):
        return "双色球"
    return None


def facts_from(setting: str) -> Dict[str, object]:
    lock = section(setting, "事实锁", "事实账", "事实底座")
    l0 = section(setting, "L0 事实核查", "事实核查表")
    source = lock or l0
    all_text = source + "\n" + setting
    facts: Dict[str, object] = {"lock": bool(lock), "source": source}
    facts["game"] = _locked_game(source, all_text)
    if re.search(r"(?:每注|每张|每票)[^\n]{0,16}(?:2\s*元|2\s*块|两元|两块)", source):
        facts["unit_cost"] = 2
    if any(_has_positive(line, r"每天一张|每日一张|每天只买一张") for line in source.splitlines()):
        facts["frequency"] = "daily_one"
    fixed = re.search(r"(?:固定|同一组|守号)[^\n]{0,24}(?<!\d)(\d{3})(?!\d)", source)
    if fixed:
        facts["fixed_number"] = fixed.group(1)
    prize = re.search(r"(?:奖金|中奖金额|固定奖金)[^\n]{0,20}?(\d+(?:\.\d+)?)\s*元", source)
    if prize:
        facts["prize"] = prize.group(1)
    facts["no_omen"] = bool(re.search(r"不写.*(?:预感|感觉)|随机|官方结果|不能靠.*(?:感觉|预感)", source))
    facts["post_win_change"] = bool(
        re.search(r"中奖(?:后|以后|之后)[^\n]{0,120}?(?:五注|十注|五十注|多注|加注|加到|改买|换号|换一组|号码变多|十元|10\s*元|30\s*元|100\s*元)", source)
    )
    facts["one_ticket_only"] = bool(re.search(r"不(?:因|因为).{0,10}(?:追加|第二张|多买)|一张.*不变|不出现.*(?:加倍|多注)", source))
    # 允许在事实锁中写「起始日期：2019-09-17 / 第2557张日期：2026-09-16」。
    exact = re.findall(r"(?:起始日期|开始日期|第一张日期|第一张)\s*[：:]\s*(20\d{2}-\d{1,2}-\d{1,2})", source)
    if exact:
        facts["exact_dates"] = exact
    count = re.search(r"(?:第\s*)(\d+)张\s*[：:]\s*(20\d{2}-\d{1,2}-\d{1,2})", source)
    if not count:
        count = re.search(r"(?:第\s*)(\d+)张[^\n]{0,20}?(20\d{2}-\d{1,2}-\d{1,2})", source)
    if count:
        facts["ticket_date"] = (int(count.group(1)), count.group(2))
    return facts


def _issue(issues: List[Tuple[str, str, str]], sev: str, code: str, message: str) -> None:
    issues.append((sev, code, message))


def check_text(setting: str, body: str) -> List[Tuple[str, str, str]]:
    issues: List[Tuple[str, str, str]] = []
    if not setting:
        _issue(issues, "S1", "MISSING_SETTING", "缺少设定.md")
        return issues
    if not body:
        _issue(issues, "S1", "MISSING_BODY", "缺少正文.md")
        return issues

    facts = facts_from(setting)
    lock = section(setting, "事实锁", "事实账", "事实底座")
    if not lock:
        _issue(issues, "S1", "NO_FACT_LOCK", "未提供事实锁；无法进行锁定值对账，不等于事实错误")
    ledger = section(setting, "因果", "状态台账", "状态变化", "转场台账")
    if not ledger:
        _issue(issues, "S1", "NO_STATE_LEDGER", "未提供可选状态台账；因果关系需按正文语义复核，不要求补表")

    body_records = [(i, line.strip()) for i, line in enumerate(body.splitlines(), 1)
                    if line.strip() and not line.lstrip().startswith("#")]
    setting_records = [(i, line.strip()) for i, line in enumerate(setting.splitlines(), 1)
                       if line.strip() and not line.lstrip().startswith("#")]
    body_lines = [line for _, line in body_records]
    setting_lines = [line for _, line in setting_records]
    combined = "\n".join(body_lines)
    full = setting + "\n" + body

    # 规则/彩票的高风险越界。只有在事实锁明确选择了相关规则时才启用。
    if facts.get("game") == "福彩3D":
        bad_game = [(i, l) for i, l in body_records if _has_positive(l, r"红球|蓝球|六个红球|一个蓝球|双色球")]
        if bad_game:
            _issue(issues, "S1", "GAME_MIX", "事实锁是福彩3D，但正文出现双色球的红球/蓝球结构：" + "; ".join(f"L{n} {line[:24]}" for n, line in bad_game[:3]))
    allow_drift = bool(facts.get("post_win_change"))

    def _drift_ok(line: str) -> bool:
        return allow_drift and bool(DRIFT_MARK.search(line))

    if facts.get("unit_cost") == 2:
        unit_patterns = r"(?:每天|每日|一张|每注|每票).{0,12}(?:10\s*元|十元|10\s*块|十块|20\s*元|两万|四万|八万|五注|一百倍|两百倍|加倍|倍投|重仓)"
        bad_unit = [(i, l) for i, l in body_records if _has_positive(l, unit_patterns) and not _drift_ok(l)]
        if bad_unit:
            _issue(issues, "S1", "UNIT_DRIFT", "事实锁要求单张/单注2元，正文却升级了金额、注数或倍数：" + "; ".join(f"L{n} {line[:28]}" for n, line in bad_unit[:5]))
        # 也检查设定卡自己的数字反向表，防止事实锁和大纲互相打架。
        card_bad = [
            (i, l)
            for i, l in setting_records
            if _has_positive(l, r"(?:每天|每张|单注).{0,14}(?:10\s*元|十元|十块|20\s*元|两万|四万|八万|倍投|重仓)") and not _drift_ok(l)
        ]
        if card_bad:
            _issue(issues, "S1", "CARD_UNIT_DRIFT", "设定卡同时写了2元硬事实和金额升级：" + "; ".join(f"L{n} {line[:28]}" for n, line in card_bad[:4]))
    if facts.get("frequency") == "daily_one":
        multi = [
            (i, l)
            for i, l in body_records
            if _has_positive(l, r"(?:每天|每日).{0,14}(?:第二张|多买|五注|多注|加倍|倍投|十元|十块)") and not _drift_ok(l)
        ]
        if multi:
            _issue(issues, "S1", "FREQUENCY_DRIFT", "事实锁是每天一张新票，正文出现同日追加/多注/金额改变：" + "; ".join(f"L{n} {line[:28]}" for n, line in multi[:5]))
    if facts.get("fixed_number"):
        changed = [
            (i, l)
            for i, l in body_records
            if _has_positive(l, r"(?:换号|改号|号码改|号码换|改了号码)") and not _drift_ok(l)
        ]
        if changed:
            _issue(issues, "S2", "NUMBER_DRIFT", "事实锁要求固定号码，但正文出现换号动作：" + "; ".join(f"L{n} {line[:28]}" for n, line in changed[:3]))
    if facts.get("no_omen"):
        omen = r"有感觉|预感|快了|会中的|天选|它还会|认出了你|号码有了脾气|三等奖是信号"
        bad_omen = [(i, l) for i, l in body_records if _has_positive(l, omen)]
        if bad_omen:
            _issue(issues, "S1", "OMEN_DRIFT", "事实锁禁止玄学预感/号码意志，正文出现：" + "; ".join(f"L{n} {line[:30]}" for n, line in bad_omen[:5]))
        if not re.search(r"官方(?:开奖|结果|公告)|开奖结果", combined):
            _issue(issues, "S2", "NO_OFFICIAL_CHECK", "中奖线没有明确写官方开奖结果/公告与票面核对")

    # 倒序只提示上下文复核；允许倒叙、回忆、多对象时间线。
    ys = event_years(combined)
    backwards = []
    last = None
    for year, _, raw in ys:
        if last is not None and year < last:
            backwards.append((last, year, raw))
        last = max(last or year, year)
    if backwards:
        _issue(issues, "S1", "YEAR_BACKTRACK", "检测到倒序时间锚（可能是倒叙，需上下文确认）：" + "; ".join(f"{a}→{b}({raw})" for a, b, raw in backwards[:3]))
    # 已知旧稿的典型硬矛盾也要显式报出，而不是只报「缺事实锁」。
    if re.search(r"守了?\s*7年|七年", setting) and re.search(r"八年里|八年", combined):
        _issue(issues, "S1", "DURATION_CONFLICT", "出现七年/八年表述；确认是否同一对象与统计区间，不要求强行统一")
    ds = iso_dates(combined)
    date_back = []
    prev = None
    for date, _, raw in ds:
        if prev and date < prev:
            date_back.append((prev.isoformat(), date.isoformat(), raw))
        prev = max(prev or date, date)
    if date_back:
        _issue(issues, "S1", "DATE_BACKTRACK", "检测到倒序日期（不自动视为错误）：" + "; ".join(f"{a}→{b}({raw})" for a, b, raw in date_back[:3]))

    ticket_matches = [int(value) for value in re.findall(r"第\s*(\d+)张", combined)]
    ticket_date = facts.get("ticket_date")
    if ticket_date:
        expected_no, date_text = ticket_date
        if ticket_matches and expected_no not in ticket_matches:
            _issue(issues, "S1", "TICKET_NO_MISMATCH", f"正文没有事实锁校验日期对应的第{expected_no}张（出现了 {ticket_matches[:6]}）")
        try:
            target = _dt.date(*map(int, date_text.split("-")))
            starts = facts.get("exact_dates") or []
            if starts and facts.get("frequency") == "daily_one":
                start = _dt.date(*map(int, starts[0].split("-")))
                calculated = (target - start).days + 1
                if calculated != expected_no:
                    _issue(issues, "S1", "DATE_COUNT_MISMATCH", f"从{start}每天一张到{target}应是第{calculated}张，不是事实锁写的第{expected_no}张")
        except ValueError:
            _issue(issues, "S2", "BAD_DATE_LOCK", f"事实锁日期无法解析：{date_text}")

    # 旧台账仅作诊断；关键词不等于已理解因果。
    if ledger:
        has_trigger = bool(re.search(r"触发|因为|所以|因此|当天|第二天|之后|仍然|决定", ledger))
        has_change = bool(re.search(r"状态|余额|数量|持有|从.{0,12}到|增加|减少|停止|开始", ledger))
        if not has_trigger or not has_change:
            _issue(issues, "S2", "WEAK_STATE_LEDGER", "因果/状态台账缺少触发词或状态变化字段")

    return issues


def check_directory(directory: str) -> List[Tuple[str, str, str]]:
    return check_text(read(os.path.join(directory, "设定.md")), read(os.path.join(directory, "正文.md")))


def print_report(directory: str) -> int:
    from fuben_engine import inspect_path, emit
    report = inspect_path(directory, run_style=False, components={"facts"})
    return emit(report, label="CONSISTENCY")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("用法: python3 scripts/fuben_consistency.py 作品/NN_xxx/")
    raise SystemExit(print_report(sys.argv[1]))
