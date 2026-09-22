#!/usr/bin/env python3
"""Optional setting/prose claim diagnostics, never a proof of a contradiction.

A number absent from prose may be background information; nearby years may concern
different objects. Findings require contextual review. Raw source text is not edited.
"""
from __future__ import annotations
import os, re, sys

SKIP_HEAD = re.compile(r"L0|核查|拆书|参考|借用|变更|评判|来源|实体台账|题眼锚|故事合同")
YR = re.compile(r"(?<!\d)(20\d\d)年")
BARE = re.compile(r"(?<!\d)20\d\d(?![\d%\-]|\-\d)")
CHAIN = re.compile(r"20\d\d年?(?=[\-—~→]\s*20\d\d)|(?<=[\-—~→]\s)20\d\d年?")

# —— v3 口播字数主张层（连续性锁 D1）：不依赖引号的「N字」主张 ——
# 「人生就两字 练完再耍」这类口播主张没有引号，老的两条引文规则管不到。
# 声明一个数 → 实测一个数 → 比对：去标点后数汉字，对不上就是纯文本错误。
PAT_CHAR_CLAIM = re.compile(
    r"(?P<pre>人生就|总结成|总结|回复了?|回了?|回的|说了?|说的|写了?|写的|答了?|念了?|备注了?|备注|蹦出|甩出|闪出|闪过|跟了?|补了?|就是|就)"
    r"(?P<n>[一二两三四五六七八九十百零〇\d]+|仨|俩)\s*个?\s*字"
)
# 主张后面跟的不是被数的内容，而是叙述继续：跳过，不判。
CLAIM_FUNC_HEADS = {"说完", "之后", "以后", "的时候", "的话", "以来", "以前", "完了", "后来", "接着", "然后", "跟着", "早已", "已经"}
# 「的/了」开头永远不是引文（「只会说四个字 的人」是描述不是主张）。
CLAIM_HARD_LEAD = re.compile(r"^[的了]")
# 代词/副词开头可能是引文（「我信一次」），只在长度对不上主张时才当叙述跳过。
CLAIM_FUNC_LEAD = re.compile(r"^[他她你我它就都又也才还但而且不没再便却仍那这]")
# 「人生就两字，就是耍起」：数的是“耍起”，系词不算内容。
CLAIM_COPULA = re.compile(r"^(就是|算是|叫做|叫|才是|是)")
CLAIM_SEPARATORS = " \t，、：:；;—…"
CLAIM_SENTENCE_END = "。！？!?"
CLAIM_MAX_N = 30


def _claim_number(token: str):
    """两/仨/俩/十二/9 → int；解析不了返回 None。"""
    if token in ("仨",):
        return 3
    if token in ("俩",):
        return 2
    from fuben_numbers import numeric
    value = numeric(token, colloquial=True)
    if value is None or value != int(value):
        return None
    return int(value)


def _han_runs(text: str, start: int, need: int):
    """从 start 起收集汉字段（跨轻分隔符），直到累计 ≥ need 个汉字或遇到硬边界。

    硬边界：句末标点、空行、非汉字非分隔字符。轻分隔符：空格、顿逗号、单个换行。
    「回了九个字 / 人生就两字 / 练完再耍」要拼两段才数得齐。
    """
    runs, i, total = [], start, 0
    while i < len(text) and len(runs) < 4:
        ch = text[i]
        if ch == "\n":
            if text.startswith("\n\n", i):
                break  # 空行 = 段界
            i += 1
            continue
        if ch in CLAIM_SEPARATORS or ch == "\r":
            i += 1
            continue
        if ch in CLAIM_SENTENCE_END:
            break
        j = i
        while j < len(text) and "\u4e00" <= text[j] <= "\u9fff":
            j += 1
        if j == i:
            break
        runs.append(text[i:j])
        total += j - i
        i = j
        if total >= need:
            break
    return runs


# 续段以代词/指示/副词开头 → 是叙述不是引文，停止拼接（「别谢了/她收到」只数「别谢了」）。
CLAIM_CONT_LEAD = re.compile(r"^[的他她你我它就都又也才还但而且不没再便却仍那这]")


def _effective_phrase(runs, claimed):
    """返回 (计数用段列表, 边界是否确定)。

    去掉开头的纯系词段，剥首段系词，累计到 ≥ claimed 为止；
    续段以代词/叙述词开头就停。补缺补过头的（弃/像一张嘴）边界不确定，
    交 REVIEW 人核，不硬判 BLOCK。
    """
    items = list(runs)
    while items and not CLAIM_COPULA.sub("", items[0]):
        items.pop(0)
    if not items:
        return [], True
    items[0] = CLAIM_COPULA.sub("", items[0])
    out, total = [], 0
    for idx, run in enumerate(items):
        if idx > 0 and CLAIM_CONT_LEAD.match(run):
            break
        out.append(run)
        total += len(run)
        if total >= claimed:
            break
    if not out:
        return [], True
    deterministic = True
    if len(out) >= 2:
        before = sum(len(r) for r in out[:-1])
        if before < claimed and len(out[-1]) > claimed - before and total != claimed:
            deterministic = False  # 补缺补进了下一段叙述，边界不明
    return out, deterministic


def spoken_char_claims(text: str):
    """返回 [(claim, claimed, actual, phrase, line_no, certain)]。

    certain=False 时（语境自称误算等）降为 REVIEW 交人核。
    声明一个数 → 实测一个数 → 比对；只审「主张后紧跟内容」的形态，
    后接叙述（代词/副词/序数开头）不判，避免把没亮出的引文误杀。
    """
    out = []
    fallible = re.compile(r"误算|算错|错算|错写|故意写错|故意说错|谎称|误以为|错误示例")
    ordinal = re.compile(r"^第[一二两三四五六七八九十]")
    for m in PAT_CHAR_CLAIM.finditer(text):
        if m.group("pre") == "就" and not re.search(r"(?:^|[\s，。：；！？])就$", text[:m.start()]):
            continue  # 「就」必须是独立小句开头，避免吞掉词中字
        line_head = text.rfind("\n", 0, m.start()) + 1
        if text[line_head:].lstrip().startswith("|"):
            continue  # 表格行里的「N字」是描述字段，不是口播主张
        claimed = _claim_number(m.group("n"))
        if claimed is None or claimed < 1 or claimed > CLAIM_MAX_N:
            continue
        if text[:m.start()].rstrip().endswith("第"):
            continue  # 「第5个字」是定位，不是长度主张
        line_no = text.count("\n", 0, m.start()) + 1
        line_end = text.find("\n", m.end())
        line = text[line_head: line_end if line_end != -1 else len(text)]
        fallible_hit = bool(fallible.search(line))
        # 找主张后面的内容起点：最多跨一个空行（两个换行）
        i, newlines = m.end(), 0
        while i < len(text):
            ch = text[i]
            if ch == "\n":
                newlines += 1
                if newlines > 2:
                    break
                i += 1
                continue
            if ch in CLAIM_SEPARATORS or ch == "\r":
                i += 1
                continue
            break
        if newlines > 2 or i >= len(text) or text[i] in CLAIM_SENTENCE_END:
            continue  # 隔太远或后面没有内容，无法实测，不判
        if text[i] in "“「\"'‘":
            continue  # 引号内容交给 QUOTED_CHARACTER_COUNT
        runs = _han_runs(text, i, claimed + 3)
        if not runs:
            continue
        items, deterministic = _effective_phrase(runs, claimed)
        if not items:
            continue
        phrase = "".join(items)
        actual = len(re.findall(r"[\u4e00-\u9fff]", phrase))
        first = CLAIM_COPULA.sub("", runs[0])
        if runs[0] in CLAIM_FUNC_HEADS or ordinal.match(first) or CLAIM_HARD_LEAD.match(first):
            continue  # 后面是叙述/描述字段，不是引文
        if CLAIM_FUNC_LEAD.match(first) and abs(actual - claimed) > 2:
            continue  # 代词/副词开头且长度对不上主张：更像叙述，不判
        certain = deterministic and not fallible_hit and bool(re.fullmatch(r"[\u4e00-\u9fff]+", phrase))
        if actual != claimed:
            out.append((m.group(0), claimed, actual, phrase, line_no, certain))
    return out




CN_DIG = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
CN_UNIT = {"十": 10, "百": 100, "千": 1000}

def cn2int(tok: str):
    from fuben_numbers import numeric
    value = numeric(tok.removesuffix("字"), colloquial=True)
    return value if value is not None and value >= 100 else None

def _cn_tokens(text):
    return re.findall(r"[零〇一二两三四五六七八九十百千万]{2,}(?:万[零〇一二两三四五六七八九十百千]{0,8})?", text)

MUL = {"万": 10000, "亿": 100000000}

def arabic_with_unit(text: str):
    """阿拉伯数（千分位整体）+ 紧跟的 万/亿 合并；返回 int 集合。"""
    out = set()
    for m in re.finditer(r"(?<![\d.,])(\d{1,3}(?:,\d{3})+|\d{3,})(?![\d.%])\s*([万亿])?", text):
        v = int(m.group(1).replace(",", ""))
        if m.group(2):
            v *= MUL[m.group(2)]
        if v >= 100:
            out.add(v)
    return out

def body_numbers(body: str):
    """正文数字集合：阿拉伯（含万/亿）∪ 中文位值/省略/逐位念数词。"""
    nums = arabic_with_unit(body)
    for tok in _cn_tokens(body):
        v = cn2int(tok)
        if v: nums.add(v)
    return nums

def setting_claims(setting_lines, heads):
    """设定散文层主张数字（≥100，年份除外——年份有专门对账层）。"""
    out = []
    for i, l in enumerate(setting_lines, 1):
        h = heads[i - 1]
        if SKIP_HEAD.search(h) or re.search(r"事实锁|爽点表|基本信息|去向|八拍|字数|摘要|验收", h):
            continue
        if re.search(r"http|÷|×|≈|=|%|−|\*\*密度|核算|成稿|字数|千字|快照|来源", l):
            continue
        for m in re.finditer(r"(?<![\d.,])(\d{1,3}(?:,\d{3})+|\d{3,})(?![\d.%])\s*([万亿])?", l):
            v = int(m.group(1).replace(",", ""))
            if m.group(2):
                v *= MUL[m.group(2)]
            if v < 100 or (1900 <= v <= 2100 and re.match(r"20\d\d$", m.group(1)) and not m.group(2)):
                continue
            out.append((i, h, v, l[max(0, m.start() - 12):m.end() + 10].strip()))
        for m in re.finditer(r"[零〇一二两三四五六七八九十百千万]{2,}(?:万[零〇一二两三四五六七八九十百千]{0,8})?", l):
            v = cn2int(m.group(0))
            if v:
                out.append((i, heads[i - 1], v, l[max(0, m.start() - 12):m.end() + 8].strip()))
    return out

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

def _diagnose(setting: str, body: str):
    blines = content_lines(body)
    # —— v2 计数主张层（与年份无关，恒跑）：散文层 ≥100 的主张数字必须在正文有出处
    slines_all = setting.splitlines()
    heads_all = []
    cur_h = ""
    for l in slines_all:
        if l.strip().startswith("#"):
            cur_h = l.strip("# ")
        heads_all.append(cur_h)
    bnums = body_numbers(body)
    approx = {v // (10 ** max(0, len(str(v)) - 2)) * (10 ** max(0, len(str(v)) - 2)) for v in bnums}  # 12437→12000
    # 合法集扩展：事实锁表内的数字（含来源列算式）算有出处——派生总额合法
    for i, l in enumerate(slines_all):
        if "事实锁" in heads_all[i]:
            bnums |= arabic_with_unit(l)
            for tok in _cn_tokens(l):
                v = cn2int(tok)
                if v: bnums.add(v)
    nbad = 0
    seen_rep = set()
    for i, h, v, ctx in setting_claims(slines_all, heads_all):
        if v in bnums or (i, v) in seen_rep:
            continue
        vk = str(v).rstrip("0")
        if re.search(r"多|余|约|上下|来块|来张|来人", ctx) and any(b > v and len(str(b)) == len(str(v)) and str(b).startswith(vk) for b in bnums):
            continue  # 约数口径：正文有更精确的同位数同前缀数（一万两千多张←12437）
        if 1990 <= v <= 2100 and "年" in ctx:
            continue  # 年份主张交给下层年份对账
        seen_rep.add((i, v))
        print(f"BAD 设定L{i} [{h}]: 数字主张 {v:,} 在正文找不到出处（含中文数词式）——「{ctx[:34]}」")
        nbad += 1
    body_years = {int(m) for m in re.findall(r"(?<!\d)(20\d\d)年", body)}
    if not body_years:
        print("SETTING-PROSE:", "PASS" if not nbad else f"FAIL {nbad} → 改设定散文口径；不许动正文凑数")
        return 1 if nbad else 0
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
    bad += nbad
    print("SETTING-PROSE:", "PASS" if not bad else f"FAIL {bad} → 年份/计数任一失守即红；改设定散文口径，不许动正文凑数")
    return 1 if bad else 0

def check_text(setting: str, body: str):
    import contextlib
    import io
    if not setting:
        return []
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        _diagnose(setting, body)
    # Capture the old exploratory algorithm only; do not expose its misleading PASS.
    return [line.removeprefix("BAD ") + "；待核对对象/语境，不能据此改正文凑数"
            for line in output.getvalue().splitlines() if line.startswith("BAD ")]


def main():
    import argparse
    from fuben_engine import inspect_path, emit
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    return emit(inspect_path(args.path, run_style=False, components={"setting"}),
                json_output=args.json, label="SETTING-PROSE")


if __name__ == "__main__":
    raise SystemExit(main())
