#!/usr/bin/env python3
"""秒级节奏图（R9-A2）：把爽点表「位置%」翻译成「第几秒」。
时长=去标点字数÷语速（默认 4.8 字/秒，口播经验值；D0 真实数据到位后用 --cps 换实测倍率）。
用法：python3 scripts/fuben_shotmap.py 作品/NN_xxx/ [更长的稿]"""
import re, sys, os

def main():
    cps=float(os.environ.get("FUBEN_CPS","4.8"))
    for a in sys.argv[1:]:
        if a=="--cps":
            continue
        d=a
        body=open(os.path.join(d,"正文.md"),encoding="utf-8").read()
        n=len(re.sub(r"[，。、？！：；「」\"'\s]","",body))
        dur=n/cps
        verdict="OK  冷启动带≤90s" if dur<=90 else f"OVER 冷启动带（D0实测：全长TTS 375–497s 的完播proxy仅4–6%，算法不给二级池）→ 切条≤60s 或 3 分钟精选版"
        print(f"## {d}  去标点 {n} 字 ÷ {cps} 字/秒 ≈ **{dur:.0f} 秒（{dur/60:.1f} 分）**  [{verdict}]")
        sp=os.path.join(d,"设定.md")
        if os.path.exists(sp):
            t=open(sp,encoding="utf-8").read()
            seg=t.split("## 爽点表")
            if len(seg)>1:
                rows=re.findall(r"^\| (\d+) \| (\d+)% \| ([+\-]\d+) \| (.*?) \|",seg[1].split("##")[0],re.M)
                print("| 秒 | % | 情绪 | 事件 |")
                print("|---|---|---|---|")
                for o,pc,mo,ev in rows:
                    print("| %3.0fs | %3s%% | %s | %s |"%(dur*int(pc)/100,pc,mo,ev.strip()[:38]))
        print()
main()
