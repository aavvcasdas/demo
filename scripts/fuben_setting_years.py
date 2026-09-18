#!/usr/bin/env python3
"""设定卡散文层 × 事实锁/正文 年份交叉对账（fuben-review v3.1 新增门）。

只查一件事：设定.md 散文/表格里「具体物件 + 年份」的主张，必须能同时被
①事实锁同词年份、②正文该词全部出现处的邻近年份锚、③全篇最晚年（终止式表述）
解释。否则就是 58b(217/218)、73(主线「二手单反从2015」vs 事实锁「2021年购入」)
这类「同一张卡两个出身」。机械 facts 闸只扫事实锁表格 vs 正文，散文层裸奔——补这层。

物件词 = 物件台账首格的完整中文段 + 尾两/三字（汉语中心词在右：烫金喜糖盒→糖盒）。
主张 = 含词且含年份的设定行；表格行只看词所在同一单元格；跳过事实锁、
L0/参考/变更等引用节、http 行、箭头年份链（「2015→2017」是锚点列表非出身主张）。
退出码：0 一致；1 有冲突；2 用法/缺文件。
"""
from __future__ import annotations
import os, re, sys

SKIP_HEAD = re.compile(r"L0|核查|拆书|参考|借用|变更|评判|来源")
YR = re.compile(r"(?<!\d)(20\d\d)年")
BARE = re.compile(r"(?<!\d)20\d\d(?![\d%\-]|\-\d)")
CHAIN = re.compile(r"20\d\d年?(?=[\-—~→]\s*20\d\d)|(?<=[\-—~→]\s)20\d\d年?")

def load(p):
    try:
        return open(p, encoding="utf-8").read()
    except OSError:
        return ""

def content_lines(t):
    return [l.strip() for l in t.splitlines() if l.strip() and not l.strip().startswith("#")]

def nearest_year_above(lines, idx, back=40):
    for j in range(idx, max(-1, idx - back), -1):
        m = re.match(r"^\D{0,8}(20\d\d)年", lines[j])
        if m:
            return int(m.group(1))
    return None

def years_in(text):
    return {int(m) for m in YR.findall(text)} | {int(m) for m in BARE.findall(CHAIN.sub(" ", text))}

def main():
    if len(sys.argv) != 2:
        print("用法: python3 scripts/fuben_setting_years.py 作品/NN_xxx/")
        return 2
    d = sys.argv[1].rstrip("/")
    setting, body = load(os.path.join(d, "设定.md")), load(os.path.join(d, "正文.md"))
    if not setting or not body:
        print("缺少 设定.md 或 正文.md"); return 2
    blines = content_lines(body)
    body_years = {int(m) for m in re.findall(r"(?<!\d)(20\d\d)年", body)}
    if not body_years:
        print("OK  正文无年份锚（单日/短时段题），散文层对账跳过"); return 0
    slines = setting.splitlines()
    heads, buf, head = [], "", []
    for l in slines:
        if l.strip().startswith("#"):
            head = l.strip("# ")
        heads.append(head)
    # 物件词
    words, cur = set(), ""
    for i, l in enumerate(slines):
        if l.strip().startswith("#"):
            cur = l.strip("# ")
        if "物件台账" in cur and re.match(r"^\|\s*[^|:\-]", l):
            cell = l.strip("|").split("|")[0]
            m = re.match(r"\s*\**([\u4e00-\u9fff]{2,6})", cell)
            if m:
                w = m.group(1)
                words |= {w, w[-3:], w[-2:]}
    words = {w for w in words if len(w) >= 2 and w not in {"字段", "已锁", "规则", "结果", "禁止", "物件"}}
    # 事实锁合法年份（按词）
    lock_years = {}
    for i, l in enumerate(slines):
        if "事实锁" in heads[i]:
            ys = years_in(l)
            for w in words:
                if w in l:
                    lock_years.setdefault(w, set()).update(ys)
    bad = 0
    reported = set()
    for word in sorted(words, key=len, reverse=True):
        occ = [i for i, l in enumerate(blines) if word in l]
        if not occ:
            continue
        legal = {max(body_years)}
        for i in occ:
            y = nearest_year_above(blines, i)
            if y:
                legal.add(y)
            for j in (i - 1, i, i + 1):
                if 0 <= j < len(blines):
                    legal.update(int(x) for x in YR.findall(blines[j]))
        legal |= lock_years.get(word, set())
        for i, l in enumerate(slines, 1):
            if SKIP_HEAD.search(heads[i - 1]) or "事实锁" in heads[i - 1] or "http" in l or word not in l:
                continue
            if l.strip().startswith("|"):
                cells = [c for c in l.strip("|").split("|") if word in c]
                claim = set()
                for c in cells:
                    claim |= years_in(c)
            else:
                claim = set()
                for m in re.finditer(re.escape(word), l):
                    lo, hi = max(0, m.start() - 14), min(len(l), m.end() + 14)
                    claim |= years_in(l[lo:hi])
                if word in ("三张", "两面", "背面照", "面照"):  # 泛用尾词只认全句一次物件的场景，跳过
                    pass
            for y in sorted(claim - legal):
                if (i, y) in reported:
                    continue
                reported.add((i, y))
                print(f"BAD 设定L{i} [{heads[i-1]}]: 「{word}」主张 {y}年；正文该物件邻接锚 {sorted(legal)}（事实锁/正文）对不上")
                bad += 1
    print("SETTING-YEARS:", "PASS" if not bad else f"FAIL {bad} → 改设定散文口径；不许动正文凑数")
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main())
