#!/usr/bin/env python3
"""人生副本的事实锁、时间线和状态台账检查。

这个检查器只做可复核的硬约束，不试图用正则判断文笔好坏：
- 设定卡必须先锁定题材规则、频率、单位、对象和禁写项；
- 正文中的关键数字、玩法和开奖/结果表述不能越过事实锁；
- 显式年份与精确日期不能倒退，票数与日期若都给出则必须能对账；
- 每个八拍都要能从状态台账找到「触发 → 动作 → 状态变化」。
"""
from __future__ import annotations

import datetime as _dt
import os
import re
import sys
from typing import Dict, Iterable, List, Optional, Tuple

SEVERITY = {"S1": 0, "S2": 1, "S3": 2}
NEGATION = re.compile(r"(?:没有|没|未|不再|不因|不是|不能|禁止|无|从不|并不|也不|不靠|不写|不出现|不会|未曾|不)")


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
    for match in re.finditer(pattern, line):
        if not NEGATION.search(line[max(0, match.start() - 8):match.start()]):
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


def facts_from(setting: str) -> Dict[str, object]:
    lock = section(setting, "事实锁", "事实账", "事实底座")
    l0 = section(setting, "L0 事实核查", "事实核查表")
    source = lock or l0
    all_text = source + "\n" + setting
    facts: Dict[str, object] = {"lock": bool(lock), "source": source}
    if re.search(r"福彩\s*3D|福彩3D", all_text):
        facts["game"] = "福彩3D"
    elif re.search(r"双色球", all_text):
        facts["game"] = "双色球"
    if re.search(r"(?:每注|每张|每票)[^\n]{0,16}(?:2\s*元|2\s*块|两元|两块)", source):
        facts["unit_cost"] = 2
    if re.search(r"每天一张|每日一张|每天只买一张|一张新", source):
        facts["frequency"] = "daily_one"
    fixed = re.search(r"(?:固定|同一组|守号)[^\n]{0,24}(?<!\d)(\d{3})(?!\d)", source)
    if fixed:
        facts["fixed_number"] = fixed.group(1)
    prize = re.search(r"(?:奖金|中奖金额|固定奖金)[^\n]{0,20}?(\d+(?:\.\d+)?)\s*元", source)
    if prize:
        facts["prize"] = prize.group(1)
    facts["no_omen"] = bool(re.search(r"不写.*(?:预感|感觉)|随机|官方结果|不能靠.*(?:感觉|预感)", source))
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


def check_directory(directory: str) -> List[Tuple[str, str, str]]:
    directory = directory.rstrip("/")
    setting = read(os.path.join(directory, "设定.md"))
    body = read(os.path.join(directory, "正文.md"))
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
        _issue(issues, "S1", "NO_FACT_LOCK", "设定.md 没有「## 事实锁」；L0 事实核查表不能代替可执行的硬事实账")
    ledger = section(setting, "因果", "状态台账", "状态变化", "转场台账")
    if not ledger:
        _issue(issues, "S1", "NO_STATE_LEDGER", "设定.md 没有「## 因果/状态台账」；无法核对每拍的触发、动作和状态变化")

    body_lines = content_lines(body)
    setting_lines = content_lines(setting)
    combined = "\n".join(body_lines)
    full = setting + "\n" + body

    # 规则/彩票的高风险越界。只有在事实锁明确选择了相关规则时才启用。
    if facts.get("game") == "福彩3D":
        bad_game = [(i + 1, l) for i, l in enumerate(body_lines) if _has_positive(l, r"红球|蓝球|六个红球|一个蓝球|双色球")]
        if bad_game:
            _issue(issues, "S1", "GAME_MIX", "事实锁是福彩3D，但正文出现双色球的红球/蓝球结构：" + "; ".join(f"L{n} {line[:24]}" for n, line in bad_game[:3]))
    if facts.get("unit_cost") == 2:
        unit_patterns = r"(?:每天|每日|一张|每注|每票).{0,12}(?:10\s*元|十元|10\s*块|十块|20\s*元|两万|四万|八万|五注|一百倍|两百倍|加倍|倍投|重仓)"
        bad_unit = [(i + 1, l) for i, l in enumerate(body_lines) if _has_positive(l, unit_patterns)]
        if bad_unit:
            _issue(issues, "S1", "UNIT_DRIFT", "事实锁要求单张/单注2元，正文却升级了金额、注数或倍数：" + "; ".join(f"L{n} {line[:28]}" for n, line in bad_unit[:5]))
        # 也检查设定卡自己的数字反向表，防止事实锁和大纲互相打架。
        card_bad = [(i + 1, l) for i, l in enumerate(setting_lines) if _has_positive(l, r"(?:每天|每张|单注).{0,14}(?:10\s*元|十元|十块|20\s*元|两万|四万|八万|倍投|重仓)")]
        if card_bad:
            _issue(issues, "S1", "CARD_UNIT_DRIFT", "设定卡同时写了2元硬事实和金额升级：" + "; ".join(f"L{n} {line[:28]}" for n, line in card_bad[:4]))
    if facts.get("frequency") == "daily_one":
        multi = [(i + 1, l) for i, l in enumerate(body_lines) if _has_positive(l, r"(?:每天|每日).{0,14}(?:第二张|多买|五注|多注|加倍|倍投|十元|十块)")]
        if multi:
            _issue(issues, "S1", "FREQUENCY_DRIFT", "事实锁是每天一张新票，正文出现同日追加/多注/金额改变：" + "; ".join(f"L{n} {line[:28]}" for n, line in multi[:5]))
    if facts.get("fixed_number"):
        changed = [(i + 1, l) for i, l in enumerate(body_lines) if _has_positive(l, r"(?:换号|改号|号码改|号码换|改了号码)")]
        if changed:
            _issue(issues, "S2", "NUMBER_DRIFT", "事实锁要求固定号码，但正文出现换号动作：" + "; ".join(f"L{n} {line[:28]}" for n, line in changed[:3]))
    if facts.get("no_omen"):
        omen = r"有感觉|预感|快了|会中的|天选|它还会|认出了你|号码有了脾气|三等奖是信号"
        bad_omen = [(i + 1, l) for i, l in enumerate(body_lines) if _has_positive(l, omen)]
        if bad_omen:
            _issue(issues, "S1", "OMEN_DRIFT", "事实锁禁止玄学预感/号码意志，正文出现：" + "; ".join(f"L{n} {line[:30]}" for n, line in bad_omen[:5]))
        if not re.search(r"官方(?:开奖|结果|公告)|开奖结果", combined):
            _issue(issues, "S2", "NO_OFFICIAL_CHECK", "中奖线没有明确写官方开奖结果/公告与票面核对")

    # 年份/精确日期不能倒退。重复同一年允许，倒退不允许。
    ys = event_years(combined)
    backwards = []
    last = None
    for year, _, raw in ys:
        if last is not None and year < last:
            backwards.append((last, year, raw))
        last = max(last or year, year)
    if backwards:
        _issue(issues, "S1", "YEAR_BACKTRACK", "正文时间线倒退：" + "; ".join(f"{a}→{b}({raw})" for a, b, raw in backwards[:3]))
    # 已知旧稿的典型硬矛盾也要显式报出，而不是只报「缺事实锁」。
    if re.search(r"守了?\s*7年|七年", setting) and re.search(r"八年里|八年", combined):
        _issue(issues, "S1", "DURATION_CONFLICT", "设定写七年，正文又写八年；必须统一期限与票数")
    ds = iso_dates(combined)
    date_back = []
    prev = None
    for date, _, raw in ds:
        if prev and date < prev:
            date_back.append((prev.isoformat(), date.isoformat(), raw))
        prev = max(prev or date, date)
    if date_back:
        _issue(issues, "S1", "DATE_BACKTRACK", "精确日期倒退：" + "; ".join(f"{a}→{b}({raw})" for a, b, raw in date_back[:3]))

    ticket_matches = [int(value) for value in re.findall(r"第\s*(\d+)张", combined)]
    ticket_date = facts.get("ticket_date")
    if ticket_matches and ticket_date:
        expected_no, date_text = ticket_date
        if expected_no not in ticket_matches:
            _issue(issues, "S1", "TICKET_NO_MISMATCH", f"正文没有事实锁校验日期对应的第{expected_no}张（出现了 {ticket_matches[:6]}）")
        try:
            target = _dt.date.fromisoformat(date_text)
            starts = facts.get("exact_dates") or []
            if starts:
                start = _dt.date.fromisoformat(starts[0])
                calculated = (target - start).days + 1
                if calculated != expected_no:
                    _issue(issues, "S1", "DATE_COUNT_MISMATCH", f"从{start}每天一张到{target}应是第{calculated}张，不是事实锁写的第{expected_no}张")
        except ValueError:
            _issue(issues, "S2", "BAD_DATE_LOCK", f"事实锁日期无法解析：{date_text}")

    # 状态台账不是装饰：至少要有「触发/因为/第二天」和可见状态词。
    if ledger:
        has_trigger = bool(re.search(r"触发|因为|所以|因此|当天|第二天|之后|仍然|决定", ledger))
        has_change = bool(re.search(r"状态|余额|数量|持有|从.{0,12}到|增加|减少|停止|开始", ledger))
        if not has_trigger or not has_change:
            _issue(issues, "S2", "WEAK_STATE_LEDGER", "因果/状态台账缺少触发词或状态变化字段")

    return issues


def print_report(directory: str) -> int:
    issues = check_directory(directory)
    if not issues:
        print("CONSISTENCY: PASS")
        return 0
    for severity, code, message in sorted(issues, key=lambda x: SEVERITY.get(x[0], 9)):
        print(f"{severity} {code}: {message}")
    print(f"CONSISTENCY: FAIL {len(issues)}")
    return 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("用法: python3 scripts/fuben_consistency.py 作品/NN_xxx/")
    raise SystemExit(print_report(sys.argv[1]))
