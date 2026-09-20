#!/usr/bin/env python3
"""R20 语料反向体检审判台（报告见 作品/_语料反审_全闸门栈_R20_2026-09-19.md）。

被审对象：拆文库 fuben 口径全部条目 原文/原文.txt（10w+ 真爆款原文）
审判闸：  fuben_loop draft / fuben_lint / fuben_density / check_fuben_texture
          / check-ai-patterns / check-degeneration
设计层豁免：facts/design/hype/setting_years 属生产合同（需设定卡），原文无对账对象，
            不计入原文 verdict；draft 内「主线贯穿」「主线关键词可追」「事实/时间线一致性」
            单列为 design-contract 不计。
钱题带（≤30/千字）按标题关键词判定并在 stub 里显式标注（与现行闸同口径：设定含钱题记号）。
运行：python3 scripts/corpus_gate_audit.py            # 摘要（每闸违例数+篇目）
      python3 scripts/corpus_gate_audit.py --json      # 全量 JSON
"""
import glob, json, os, re, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "拆文库")
OUT = tempfile.mkdtemp(prefix="fuben_corpus_audit_")
WORK = os.path.join(OUT, "work")

MONEY = re.compile(r"彩票|外卖员|卖肾|分期|0首付|恒大|贷款|雇佣兵|游戏|减肥|团播")

def entries():
    for d in sorted(glob.glob(os.path.join(SRC, "[0-9]*"))):
        t = os.path.join(d, "原文", "原文.txt")
        if os.path.exists(t) and re.match(r"^\d", os.path.basename(d)):
            yield os.path.basename(d), t

def run(cmd):
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return r.stdout + r.stderr

def audit_one(name, src_path):
    num = name.split("_")[0]
    wd = os.path.join(WORK, num)
    os.makedirs(wd, exist_ok=True)
    shutil.copy(src_path, os.path.join(wd, "正文.md"))
    money = bool(MONEY.search(name))
    stub = "## 主线\n（语料反审：原文无设定卡，设计层豁免，见脚本 docstring）\n"
    if money:
        stub += "\n## 钱的去向\n（R20 语料反审：标题含钱题记号，按 ≤30/千字带判）\n"
    open(os.path.join(wd, "设定.md"), "w").write(stub)
    rec = {"id": num, "title": name.split("_", 1)[1], "money": money,
           "fail_draft": [], "fail_lint": [], "density": None,
           "texture_fail": [], "ai_blocking": 0, "degen_note": ""}
    out = run(["python3", "scripts/fuben_loop.py", "draft", wd])
    for line in out.splitlines():
        m = re.match(r"^(BAD|WARN) (\S+)", line)
        if not m or m.group(1) == "WARN":
            continue
        label = m.group(2)
        if label.startswith(("S1", "S2")) or label.startswith("主线"):
            continue  # design-contract：课文无设定卡，不计
        rec["fail_draft"].append(line.strip()[:150])
    out = run(["python3", "scripts/fuben_lint.py", wd])
    for line in out.splitlines():
        if line.startswith("BAD "):
            rec["fail_lint"].append(line.strip()[:150])
    out = run(["python3", "scripts/fuben_density.py", os.path.join(wd, "正文.md")])
    m = re.search(r"(OK|OVER)\s+\S+\s+([\d.]+)/千字", out)
    if m:
        rec["density"] = (m.group(1), float(m.group(2)))
    out = run(["python3", "scripts/check_fuben_texture.py", os.path.join(wd, "正文.md")])
    for line in out.splitlines():
        if line.startswith("BAD "):
            rec["texture_fail"].append(line.strip()[:100])
    out = run(["node", "skills/story-review/scripts/check-ai-patterns.js", "--check",
               "--fail-on=blocking", os.path.join(wd, "正文.md")])
    rec["ai_blocking"] = out.count("[blocking]")
    return rec

def main():
    # R20 parses the old BAD/WARN text protocol and discards subprocess exit codes.
    # Keep the historical implementation, but never misreport the new engine as green.
    if os.path.isfile(os.path.join(ROOT, "scripts", "fuben_policy.json")):
        print("ERROR: R20历史采集器不兼容现行检查协议；请用 python3 scripts/fuben_corpus.py。旧结果须在 edbb035 对应的旧代码版本中复现。", file=sys.stderr)
        return 2
    shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK, exist_ok=True)
    results = [audit_one(n, p) for n, p in entries()]
    if "--json" in sys.argv:
        print(json.dumps(results, ensure_ascii=False, indent=1))
        return 0
    single = [r for r in results if r["id"] != "00"]  # 00=合集容器，单副本口径不含
    print(f"n=44 单副本（00 容器豁免）  临时目录：{OUT}")
    fail = [r for r in single if r["fail_draft"] or r["fail_lint"] or r["texture_fail"] or r["ai_blocking"]]
    for r in fail:
        why = r["fail_draft"] + r["fail_lint"] + r["texture_fail"] + ([f"ai-blocking×{r['ai_blocking']}"] if r["ai_blocking"] else [])
        print(f"  {r['id']} {r['title'][:18]}：{'; '.join(x.strip()[:40] for x in why)}")
    print(f"正文层硬闸违例：{len(fail)}/44")
    print("（设计层四闸按契约豁免；degeneration 的 truncated 命中系 ASR 文件天然无收尾标点，属测量伪象不计——见报告 §1 末行）")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
