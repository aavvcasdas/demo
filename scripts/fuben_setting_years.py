#!/usr/bin/env python3
"""设定卡散文层 × 正文 交叉对账（fuben-review v3.1；v2 增「计数主张」层，二轮会审指令3）。

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


CN_DIG = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
CN_UNIT = {"十": 10, "百": 100, "千": 1000}

def cn2int(tok: str):
    """一千一百七十六→1176；四千三百二十万→43200000；省略式：一千二→1200、四万五→45000。
    纯数字串按逐位念法解析（一八八→188，75 正文口播惯例）。仅认 ≥100。"""
    core = tok[:-1] if tok.endswith("字") else tok
    if not core:
        return None
    if all(c in CN_DIG for c in core):
        if len(core) < 3:
            return None
        v = int("".join(str(CN_DIG[c]) for c in core))
        return v if v >= 100 else None
    if any(c not in CN_DIG and c not in CN_UNIT and c != "万" for c in core):
        return None
    total, sec, cur = 0, 0, 0
    seen = False
    last_unit = 0
    for ch in core:
        if ch in CN_DIG:
            cur = CN_DIG[ch]; seen = True
        elif ch in CN_UNIT:
            sec += (cur if cur else (1 if ch == "十" else 0)) * CN_UNIT[ch]
            cur = 0; seen = True; last_unit = CN_UNIT[ch]
        else:  # 万
            sec += cur
            total += (sec if sec else 1) * 10000
            sec = 0; cur = 0; seen = True; last_unit = 10000
    if cur and last_unit and len(core) >= 2 and core[-1] in CN_DIG and core[-2] in CN_UNIT or (cur and len(core) >= 2 and core[-1] in CN_DIG and core[-2] == "万"):
        cur = cur * (last_unit // 10) if last_unit else cur  # 一千二→2×百；四万五→5×千；三万六千二→2×百
    total += sec + cur
    return total if seen and total >= 100 else None

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

def main():
    if len(sys.argv) != 2:
        print("用法: python3 scripts/fuben_setting_years.py 作品/NN_xxx/")
        return 2
    d = sys.argv[1].rstrip("/")
    setting, body = load(os.path.join(d, "设定.md")), load(os.path.join(d, "正文.md"))
    if not setting or not body:
        print("缺少 设定.md 或 正文.md"); return 2
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
    for i2, l2 in enumerate(slines_all):
        pass
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

if __name__ == "__main__":
    sys.exit(main())
