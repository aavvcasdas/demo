#!/usr/bin/env python3
"""对账口径 · 数字/千字 唯一权威尺（R9 会审：口径漂移的制度性修复）。

口径（打印在每行输出末尾；一切汇报必须引用本脚本，禁止手搓正则自报）：
  分母 = 正文去标点汉字数（去 ，。、？！：；「」"" 与空白，含数字与字母）
  分子 = 数字 token：①每段连续阿拉伯数字（含小数）计 1；
        ②阿拉伯钟面「H:MM / H点MM」的分钟段再计 1；
        ③每段连续中文数词（≥2字，字符集 一二两三四五六七八九十百千万零〇）计 1；
        ④中文钟面「N点N」的点位段再计 1。
  同尺锚点（拆文库原文，2026-09-19）：13≈9.0 / 01≈10.8 / 05≈17.7 / 06≈19.0 / 04≈28.0
  带：非钱题 advisory ≤25；钱题 ≤30；语料非钱带 9–19。
用法：python3 scripts/fuben_density.py 作品/NN_xxx/正文.md ... 或 --all
"""
import re, sys, glob, os

CN1 = "一二两三四五六七八九十百千万零〇"
CAL = {"13": 9.0, "01": 10.8, "05": 17.7, "06": 19.0, "04": 28.0}

def density(text: str):
    lines = [l for l in text.split("\n") if l.strip() and not l.startswith("#")]
    body = "".join(lines)
    n = len(re.sub(r"[，。、？！：；「」\"'\s]", "", body))
    if n == 0:
        return 0, 0, 0.0
    t = len(re.findall(r"\d+(?:\.\d+)?", body))
    t += len(re.findall(r"\d+[点:：]\d+", body))
    t += len(re.findall(r"[%s]{2,}" % CN1, body))
    t += len(re.findall(r"[%s]+点[%s]+" % (CN1, CN1), body))
    return t, n, round(t / n * 1000, 1)

def main():
    args = sys.argv[1:]
    if args == ["--all"]:
        args = sorted(glob.glob("作品/*/正文.md"))
    print("# 对账口径 fuben_density v1（口径见脚本 docstring）")
    bad = 0
    for p in args:
        if os.path.isdir(p):
            p = os.path.join(p, "正文.md")
        t, n, d = density(open(p, encoding="utf-8").read())
        spath = os.path.join(os.path.dirname(p), "设定.md")
        head = open(spath, encoding="utf-8").read() if os.path.exists(spath) else ""
        money = bool(re.search(r"##\s*钱的去向|花光的底气|##\s*钱题", head))  # 钱题=设定含专用账节
        lim = 30 if money else 25
        mark = "OK " if d <= lim else "OVER"
        bad += d > lim
        print("%s %-38s %5.1f/千字（%d tok / %d 字）带 ≤%d%s" % (mark, p, d, t, n, lim, "（钱题）" if money else ""))
    return 0 if not bad else 1

if __name__ == "__main__":
    sys.exit(main())
