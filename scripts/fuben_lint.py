#!/usr/bin/env python3
"""L2.6 可读性 lint。

这里的「对白」按说话单元计算，不再把「说出、听说、没有说话」当成对白；
指代检查也只在同一窗口有多个可能人物时报警，避免为了机械绿灯把所有她/他改成生硬全名。
用法: python3 scripts/fuben_lint.py 作品/NN_xxx/ [--fix-list]
"""
from __future__ import annotations

import os
import re
import sys
from typing import List, Sequence, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.join(ROOT, "scripts") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
from fuben_consistency import content_lines  # noqa: E402
from fuben_loop import dialogue_units  # noqa: E402


directory = sys.argv[1].rstrip("/")
body_path = os.path.join(directory, "正文.md")
setting_path = os.path.join(directory, "设定.md")
try:
    with open(body_path, encoding="utf-8") as fh:
        lines = content_lines(fh.read())
    with open(setting_path, encoding="utf-8") as fh:
        setting = fh.read()
except FileNotFoundError as exc:
    raise SystemExit(f"缺少文件: {exc.filename}")

N = len(lines)
bad = 0


def show(label: str, ok: bool, value: str):
    global bad
    print(("OK  " if ok else "BAD ") + f"{label:24} {value}")
    if not ok:
        bad += 1


# 1. 对白：直接标记 + 引号；不以「说」字出现次数冒充对白。
speech = dialogue_units(lines)
limit = max(8, int(N * 0.04))
show("对白单位≤8且≤4%", len(speech) <= limit, f"{len(speech)}/{limit}: " + " | ".join(line[:16] for _, line in speech[:5]))
acks = [(no, line) for no, line in speech if re.search(r"(?:说|回|回答)\s+(?:好|行|嗯|哦|是|知道|好的|没事|没有)\s*$", line)]
show("空回应=0", not acks, " / ".join(f"L{no} {line}" for no, line in acks[:4]))

# 2. 指代：人物身份来自正文明确称呼和设定卡；同一性别的候选同时出现时必须重报身份。
PERSON_TERMS = {
    "母亲", "妈妈", "你妈", "爸爸", "你爸", "老板娘", "陈哲", "老周", "老头", "表弟", "主管", "同事", "同学", "室友", "小陈", "大老板", "门卫", "前台", "客户", "小伙", "辅导员", "财务", "工作人员", "陈老师", "导师", "她妈", "他妈", "买车的人", "老板", "母亲的同事",
}
for term in re.findall(r"[\u4e00-\u9fff]{2,8}", setting):
    if term in {"事实核查表", "状态台账", "结构验收", "核心行动", "主线关键词"}:
        continue
    if re.search(r"(?:母亲|妈妈|老板娘|陈哲|主管|同事|人物|角色|对手|旁人).{0,8}" + re.escape(term), setting):
        PERSON_TERMS.add(term)

FEMALE = {"母亲", "妈妈", "你妈", "老板娘", "她妈", "辅导员", "财务", "前台", "同事"}
MALE = {"爸爸", "你爸", "陈哲", "老周", "老头", "表弟", "主管", "同学", "室友", "小陈", "大老板", "门卫", "客户", "小伙", "陈老师", "导师", "买车的人", "老板"}

def candidates(index: int, group: set) -> List[str]:
    """取最近一个明确人物行；只有同一行/相邻动作同时有两人时才判模糊。"""
    found: List[str] = []
    for previous in reversed(lines[max(0, index - 8):index + 1]):
        current = [term for term in group if term in previous]
        # 「大老板」同时包含「老板」，不能当成两个候选；只保留更长的那个。
        current = [term for term in current if not any(other != term and term in other for other in current)]
        if current:
            for term in current:
                if term not in found:
                    found.append(term)
            # 最近一行有唯一身份就足够；有两人则保留两人报警。
            if len(current) == 1:
                return found
            return found
    return found

ambiguous: List[Tuple[int, str, List[str]]] = []
for index, line in enumerate(lines):
    pronouns = re.findall(r"(?<![她他])([她他])(?!们)", line)
    if not pronouns:
        continue
    for pronoun in pronouns:
        group = FEMALE if pronoun == "她" else MALE
        possible = candidates(index, group)
        # 当前行已经点名/带身份，不是模糊指代；窗口只剩一个人也足够清楚。
        if len(possible) >= 2:
            ambiguous.append((index + 1, line, possible[:4]))

show("同指代候选≤1", len(ambiguous) <= max(2, int(N * 0.01)), f"{len(ambiguous)}处: " + " | ".join(f"L{n} {line[:14]}←{who}" for n, line, who in ambiguous[:5]))

# 3. 初中生测试术语。
jargon = [line for line in lines if re.search(r"评优|综测|推免|经手人|申报|编号|绩点|学分|德育分|OA|KPI|对齐|复盘|赋能|抓手|闭环", line)]
show("陌生术语≤1", len(jargon) <= 1, " / ".join(line[:18] for line in jargon[:4]))

# 4. 人物/物件称呼的首屏检查。
first = "".join(lines[:12])
show("首屏没有悬空他物", not bool(re.search(r"^(他|她|这个|那件|那张|那个)", "\n".join(lines[:4]))), first[:45])

# 5. 每45行至少有一次环境/身体；这是防流水账提醒，不要求每行硬塞感官。
physical = re.compile(r"手|耳朵|后背|喉咙|胃|膝盖|呼吸|汗|发麻|发烫|发凉|嗡|味道|声音|灯|门|窗|风|雨|凉|热|空调|冷气|响|湿|烫|烟味|太阳|水壶|药盒|桌面")
gaps = [start + 1 for start in range(0, N, 45) if not any(physical.search(line) for line in lines[start:start + 45])]
show("每45行有环境/身体", not gaps, f"空窗起行 {gaps}")

# 6. 过渡和空泛句只提示，不把符合用户事实的短稿逼成模板。
filler = [line for line in lines if re.search(r"命运的齿轮|时间在不知不觉中推移|周围的空气开始变得稀薄", line)]
show("模板过渡句≤1", len(filler) <= 1, " / ".join(filler[:3]))

print("\nLINT:", "PASS" if not bad else f"FAIL {bad}")
if "--fix-list" in sys.argv:
    print("\n== 修改清单 ==")
    for no, line in speech:
        print(f"L{no} 对白 → 改成动作/转述，仅保留改变行动的一句: {line[:28]}")
    for no, line, who in ambiguous:
        print(f"L{no} 指代 → 换成身份/名字（候选 {who}）: {line[:28]}")
    for no, line in enumerate(jargon, 1):
        print(f"术语 {no} → 换成普通话: {line[:28]}")
sys.exit(bad)
