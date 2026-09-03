#!/usr/bin/env python3
"""
把「剧本人生」系列的合集字幕文稿（uploads/8月16日.txt）按「今天体验的人生副本是…」开场白
切成独立短篇，去掉片尾导流广告，输出到 分篇/ 目录，并生成 分篇/索引.md。

用法：python3 scripts/split_episodes.py
"""
import re
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "uploads" / "8月16日.txt"
OUT = ROOT / "分篇"

# 开场白正则：每一篇都以这句话起头（ASR 断行不稳定，允许尾部带半截标题）
OPENER = re.compile(r"^(今天你要体验的人生|今天带你体验的人生|每天体验一种人生副本|今天体验的人生副本.*)$")

# 片尾导流广告（原样整行匹配即删除）
AD_LINES = {
    "喜欢体验人生的兄弟们别错过", "超多人生副本", "各种各样的人生都在抖音精选",
    "各种各样的人生", "都在抖音精选", "搜索剧本人生", "主页里全是我制作的优质精选内容",
    "沉浸式体验人生", "认准抖音精选",
}

# 人工核对后的标题表：序号 -> (文件名用标题, 原始开场白里的标题, 备注)
TITLES = {
    1:  ("无辣不欢的一生", "无辣不欢的一生", ""),
    2:  ("外卖员的一生", "外卖员的一生（第1-8集）", "系列剧压缩稿，含 8 集小标题"),
    3:  ("雇佣兵的一生", "雇佣兵的一生（第1-8集）", "系列剧压缩稿"),
    4:  ("中10亿彩票的人生", "中10亿彩票的人生（第1-8集）", "系列剧压缩稿，篇幅最短"),
    5:  None,  # 「外卖员的一生」重复上传版本（与第 2 篇相似度 99.8%），归档到 _重复/
    6:  ("县城精神小伙的沉沦之路", "县城精神小伙的沉沦之路", ""),
    7:  ("职高生毕业后的残酷现实", "职高生毕业后面临的残酷现实", ""),
    8:  ("精神小妹纹身找不到工作去做团播", "精神小妹技校毕业因为纹身找不到工作去做团播的人生", ""),
    9:  ("印度贫民窟高温下的人生", "在印度贫民窟经历高温的人生", ""),
    10: ("贷款买恒大房0首付哪吒车老婆开中药奶茶店", "贷款买恒大房子、0首付买哪吒电车、老婆偷开中药奶茶店、爸妈被骗买保健品的人生", ""),
    11: ("一辈子不结婚的人生", "一辈子不结婚的人生", ""),
    12: ("印度婆罗门高温下的生活", "印度婆罗门在高温下的生活", "与第 9 篇构成阶层对照组"),
    13: ("世界上只剩下你一个人", "世界上只剩下你一个人", ""),
    14: ("高中死装努力姐", "高中死装努力姐", ""),
    15: ("江浙沪顶级独生女的人生", "江浙沪顶级独生女的人生", ""),
    16: ("卖肾买iPhone4的人生", "卖肾买 iPhone4 的人生", ""),
    17: ("你有一个县城刀枪炮的父亲", "你有一个现成刀枪炮的父亲", "ASR 疑误：「现成」按正文语境应为「县城」"),
    18: ("外耗型人格的人生", "外号型人格的人生", "ASR 误写：正文明示「与其内耗自己不如外耗别人」，应为「外耗型人格」"),
    19: ("极度性压抑的男大学生", "极度性压抑的男大学生", ""),
    20: ("矮个子男生的人生", "矮个子男生的人生", ""),
    21: ("男生又挫又丑的人生", "男生又挫又丑的人生", ""),
    22: ("大学生意外接触PG电子游戏", "大学生意外接触 PG 电子游戏的人生", ""),
    23: ("先天性聋哑人的人生", "先天性聋哑人的人生", ""),
    24: ("买什么都喜欢分期的大学生", "买什么都喜欢分期的大学生", ""),
    25: ("没有公主命却有公主病的女生", "没有公主命却有公主病的女生", ""),
    26: ("减肥圈传来噩耗", "减肥圈传来噩耗", ""),
    27: ("你娶了大你10岁的邻家姐姐", "你娶了大你 10 岁的邻家姐姐", ""),
    28: ("对军训教官一见钟情的女大学生", "对军训教官一见钟情的女大学生", ""),
    29: ("你有一个长得不好看但很爱你的女朋友", "你有一个长得不好看但是很爱你的女朋友", "篇幅最长（约 6300 字）"),
    30: ("愤怒的普通人", "愤怒的普通人", ""),
    31: ("喜欢小众的小众哥", "喜欢小众的小众哥", ""),
    32: ("卖完游戏账号又找回的找回哥", "卖完游戏账号又找回的找回哥", ""),
    33: ("你有一个打呼噜跟水牛叫一样的室友", "你有一个打呼噜跟水牛叫一样的室友", ""),
    34: ("先婚后爱的人生", "先婚后爱的人生", ""),
    35: ("朋友眼中的人生赢家", "朋友眼中的人生赢家", "篇幅最短（约 1250 字）"),
    36: ("你有一个高壮男的男朋友", "你有一个高壮男的男朋友", ""),
    37: ("误入色途一事无成后幡然醒悟", "误入色途一事无成后幡然醒悟的人生", ""),
    38: ("班级里那个没有边界感的女生", "班级里那个没有边界感的女生", ""),
    39: ("小时候去浏览器玩游戏意外发现新世界的男生", "小时候去浏览器玩游戏意外发现新世界的男生", ""),
}


def main() -> None:
    lines = SRC.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
    starts = [i for i, l in enumerate(lines) if OPENER.match(l.strip())]
    assert len(starts) == 39, f"期望 39 个开场白，实际 {len(starts)}"
    bounds = [(s, (starts[k + 1] if k + 1 < len(starts) else len(lines))) for k, s in enumerate(starts)]

    OUT.mkdir(exist_ok=True)
    (OUT / "_重复").mkdir(exist_ok=True)
    index_rows, meta = [], []
    out_no = 0
    for k, (s, e) in enumerate(bounds, start=1):
        body = [l.rstrip() for l in lines[s:e]]
        while body and not body[-1].strip():
            body.pop()
        # 去掉片尾广告块
        stripped_ad = False
        while body and body[-1].strip() in AD_LINES:
            body.pop()
            stripped_ad = True
        body = [l for l in body if l.strip()]
        text = "\n".join(body)
        chars = len(text.replace("\n", ""))

        if TITLES[k] is None:
            path = OUT / "_重复" / "02b_外卖员的一生_重复版本.txt"
            path.write_text(text + "\n", encoding="utf-8")
            index_rows.append(f"| — | 外卖员的一生（重复版本） | `_重复/02b_外卖员的一生_重复版本.txt` | {chars} | 与第 02 篇为同一片，仅断行/错别字不同（相似度 99.8%），不单独拆 |")
            continue

        out_no += 1
        fname_title, display_title, note = TITLES[k]
        fname = f"{out_no:02d}_{fname_title}.txt"
        header = (
            f"# {display_title}\n"
            f"# 来源：剧本人生 合集《8月16日》第 {k} 段（源文件第 {s + 1}-{e} 行）\n"
            f"# 正文字数：{chars}{'  | 已去除片尾导流广告' if stripped_ad else ''}\n\n"
        )
        (OUT / fname).write_text(header + text + "\n", encoding="utf-8")
        index_rows.append(f"| {out_no:02d} | {display_title} | `{fname}` | {chars} | {note} |")
        meta.append({"no": out_no, "title": display_title, "file": fname, "chars": chars,
                     "src_lines": [s + 1, e], "ad_stripped": stripped_ad, "note": note})

    total = sum(m["chars"] for m in meta)
    index_md = [
        "# 《剧本人生》合集分篇索引",
        "",
        f"源文件：`uploads/8月16日.txt`（ASR 字幕稿，共 {len(lines)} 行）",
        f"切分依据：每篇固定开场白「今天体验的人生副本是……」；共识别 39 段，去重后 **{out_no} 篇独立短篇**，合计约 {total} 字。",
        "所有分篇均保留原始逐行字幕格式，仅删除 4 处片尾导流广告（「喜欢体验人生的兄弟们别错过……认准抖音精选」）。",
        "",
        "| 序号 | 标题 | 文件 | 字数 | 备注 |",
        "|---|---|---|---|---|",
        *index_rows,
        "",
        "> 拆书产出见 `拆文库/{序号}_{标题}/`（拆文报告.md · 情节节点.md · 写作手法.md · _meta.json）。",
    ]
    (OUT / "索引.md").write_text("\n".join(index_md) + "\n", encoding="utf-8")
    (OUT / "_index.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"输出 {out_no} 篇 + 1 篇重复归档，合计 {total} 字 → {OUT}")


if __name__ == "__main__":
    main()
