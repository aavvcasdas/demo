#!/usr/bin/env python3
"""场面表反抽对账（advisory 工具，非闸——遵 R9 冻结令，不进 fuben_run）。

用法：python3 scripts/fuben_scene_check.py <作品目录>
读 设定.md 的「## 场面表」，对每行：
  - 转述引语列：剥「X说：/母：」前缀，按 ，、（）→ 切段，≥4 字段须能在正文（去标点归一化）中找到；
  - 可拍器物列：顿号切分，≥2 字词条须在正文可找到。
出处：公司 v10.3 待办#2 点名「表里每个引语/器物必须 grep 得到」，方法有效；
76 自审用此法又抓到 9 行漂移（见 76 审核报告 R11 节）。做成脚本而非闸：
单稿教训不升格为机械闸（R9 C2），但每次交审必跑（fuben-review 人工层条目）。
"""
import re, sys, pathlib


def norm(s: str) -> str:
    return re.sub(r"[^一-鿿0-9A-Za-z]", "", s)


def check(work: pathlib.Path) -> int:
    text = norm((work / "正文.md").read_text(encoding="utf-8"))
    setting = (work / "设定.md").read_text(encoding="utf-8")
    m = re.search(r"##\s*场面表", setting)
    if not m:
        print(f"SKIP {work.name}：设定.md 无「场面表」（老件按 3.3 豁免，见 SKILL 备案制）")
        return 0
    body = setting[m.end():]
    nxt = re.search(r"^##\s", body, re.M)
    if nxt:
        body = body[:nxt.start()]
    rows = [ln for ln in body.splitlines() if ln.strip().startswith("|")]
    rows = rows[1:] if rows and "场面" in rows[0] else rows
    bad = 0
    for ln in rows:
        cols = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cols) < 6:
            continue
        name, quote, props = cols[0][:14], cols[4], cols[5]
        for frag in re.split(r"[，、。；→（）\"]", re.sub(r"^[^：]{0,3}：", "", quote)):
            f = norm(frag)
            if len(f) >= 4 and f not in text:
                print(f"MISS 行「{name}」引语片段无正文出处：{frag}")
                bad += 1
        for item in re.split(r"[、，;；]", props):
            p = norm(item)
            if len(p) >= 2 and p not in text:
                print(f"MISS 行「{name}」器物无正文出处：{item}")
                bad += 1
    print(f"{'FAIL' if bad else 'OK  '} {work.name}：场面表 {len(rows)} 行，漂移 {bad} 处")
    return 0  # advisory：恒 0 退出，不改任何闸的语义


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(check(pathlib.Path(sys.argv[1])))
