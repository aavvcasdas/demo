#!/usr/bin/env python3
"""人生副本·爽点与节奏门禁（L1.8）。

v3 的事实闸证明了「没有事实错误」不等于「好看」：新 72 的事实全绿，但全篇
只有一个正向事件，2510 字里没有任何爽点，观众看不到情绪翻转。

本检查器只做一件事：把 39 篇拆文里测出来的「爽点密度与位置」变成可复核的硬指标。
设定.md 必须提供 `## 爽点表`，每行写明：

    | 序 | 位置 | 情绪值 | 爽点/情绪事件 | 类型 | 正文锚点 |

门禁项（全部来自拆文库实测区间）：
- 节点密度 ≥ 4.0 个/千字（39 篇样本实测 5.1–16.7，最低 5.1）
- 正向爽点（情绪值 ≥ +3）绝对数 ≥ 2（01=6，04=2，13=5，15=3，21=2）
- 第一个正向爽点出现在 ≤22%（01 在 6%，04 在 13% 就给数字钩）
- 峰值：爽/加冕题 ≥+5 且落 25%–48%；沉沦/代价题可 ≥+3 且落 15%–55%
- ≥2 个情绪值 ≥ +5 的大爽点；≥1 个情绪值 ≤ -6 的谷底
- 相邻爽点实际间距 ≤ 全文 30%（超过就是「年表区」，观众会划走）
- 结尾锚点落在 ≥85%，且最后 12 行里要有一个数字或器物判词
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.join(ROOT, "scripts") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
from fuben_consistency import read, section  # noqa: E402

HAN = lambda text: len(re.findall(r"[\u4e00-\u9fff]", text))
RITUAL = re.compile(r"铁盒|账本|药盒|药单|票|凳子|柜台|短信|手机|照片|抽屉|钥匙|门|碗|面|盒子|卡|收据|兑奖单|沙发|车")


def parse_rows(block: str):
    rows = []
    for line in block.splitlines():
        if not line.startswith("|") or re.match(r"^\|\s*:?-", line):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 6 or cells[0] in {"序", "序号", "#"}:
            continue
        if not re.fullmatch(r"\d+", cells[0]):
            continue
        pos = re.search(r"(\d+)", cells[1])
        mood = re.search(r"([+-]?\d+)", cells[2].replace("＋", "+").replace("－", "-"))
        if not pos or not mood:
            continue
        rows.append(
            {
                "no": int(cells[0]),
                "pos": int(pos.group(1)),
                "mood": int(mood.group(1)),
                "event": cells[3],
                "type": cells[4],
                "anchor": cells[5],
            }
        )
    return rows


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("用法: python3 scripts/fuben_hype.py 作品/NN_xxx/")
    directory = sys.argv[1].rstrip("/")
    setting = read(os.path.join(directory, "设定.md"))
    body = read(os.path.join(directory, "正文.md"))
    if not setting or not body:
        print("HYPE: FAIL 缺少 设定.md 或 正文.md")
        return 1

    lines = [line.strip() for line in body.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    text = "\n".join(lines)
    total = HAN(text)
    if total <= 0:
        print("HYPE: FAIL 正文没有可统计内容")
        return 1

    block = section(setting, "爽点表")
    bad = []

    def show(label: str, ok: bool, info: str = ""):
        print(("OK  " if ok else "BAD ") + f"{label:26} {info}")
        if not ok:
            bad.append(label)

    if not block:
        show("爽点表存在", False, "设定.md 必须有「## 爽点表」：位置 / 情绪值 / 事件 / 类型 / 正文锚点")
        print("\nHYPE: FAIL → 先补爽点表，再改正文；没有爽点表的稿子一律不进正文流程。")
        return 1

    rows = parse_rows(block)
    show("爽点表可解析", len(rows) >= 6, f"{len(rows)} 行")

    # 计算每个锚点在正文中的真实位置（按汉字累计）。
    cumulative = []
    running = 0
    for number, line in enumerate(lines, 1):
        running += HAN(line)
        cumulative.append((number, running))
    actual = []
    for row in rows:
        anchor = row["anchor"]
        found = None
        for number, line in enumerate(lines):
            if anchor and anchor in line:
                found = (number, cumulative[number][1] if number < len(cumulative) else total)
                break
        row["actual"] = (found[1] / total * 100) if found else None
        row["line"] = found[0] + 1 if found else None
        actual.append(row)

    missing = [r["anchor"] for r in actual if r["actual"] is None]
    dup = {r["anchor"] for r in actual if [x["anchor"] for x in actual].count(r["anchor"]) > 1}
    show("锚点全部命中且唯一", not missing and not dup, "缺失:" + ",".join(missing[:3]) + (" 重复:" + ",".join(list(dup)[:3]) if dup else ""))

    valid = [r for r in actual if r["actual"] is not None]
    if len(valid) < 6:
        print("\nHYPE: FAIL → 锚点必须能在正文里定位，先补齐锚点。")
        return 1

    density = len(valid) / (total / 1000)
    show("节点密度≥4.0/千字", density >= 4.0, f"{density:.1f}/千字（{len(valid)}节点/{total}字）")

    positive = [r for r in valid if r["mood"] >= 3]
    # 39 篇样本里正向爽点（≥+3）绝对数：01=6、04=2、13=5、15=3、21=2。
    # 沉沦/代价题天然少正向（15=0.7/千字），所以这里卡绝对数，不卡每千字比例。
    show("正向爽点≥2个(≥+3)", len(positive) >= 2, f"{len(positive)} 个：{'、'.join(r['event'][:10] for r in positive[:5])}")

    if positive:
        first = min(positive, key=lambda r: r["actual"])
        show("首个爽点≤22%", first["actual"] <= 22, f"{first['actual']:.0f}% {first['event'][:18]}")
    else:
        show("首个爽点≤22%", False, "没有任何情绪值≥+3的爽点")

    peak = max(valid, key=lambda r: r["mood"])
    trough_first = bool(re.search(r"沉沦|代价|实录|忏悔", setting))
    peak_ok = (peak["mood"] >= 3 and 15 <= peak["actual"] <= 55) if trough_first else (peak["mood"] >= 5 and 25 <= peak["actual"] <= 48)
    show("峰值位置与强度", peak_ok, f"{peak['mood']:+d} @ {peak['actual']:.0f}%（{'沉沦/代价题' if trough_first else '爽/加冕题'}）")
    big = len([r for r in valid if r["mood"] >= 5])
    show("大爽点≥2个(≥+5)", big >= 2 or (trough_first and big >= 1), f"{big} 个")
    show("谷底≥1个(≤-6)", len([r for r in valid if r["mood"] <= -6]) >= 1, f"{[r['mood'] for r in valid if r['mood'] <= -6]}")

    ordered = sorted(valid, key=lambda r: r["actual"])
    gaps = [(b["actual"] - a["actual"], a, b) for a, b in zip(ordered, ordered[1:])]
    worst = max(gaps, key=lambda g: g[0]) if gaps else (0, None, None)
    show("无>30%情绪死区", worst[0] <= 30, f"最大间距 {worst[0]:.0f}%（{worst[1]['event'][:12]} → {worst[2]['event'][:12]}）" if gaps else "")
    show("结尾锚点≥85%", ordered[-1]["actual"] >= 85, f"{ordered[-1]['actual']:.0f}% {ordered[-1]['event'][:18]}")

    drift = [r for r in valid if abs(r["actual"] - r["pos"]) > 8]
    show("声明位置与正文一致", not drift, " / ".join(f"#{r['no']} 声明{r['pos']}% 实际{r['actual']:.0f}%" for r in drift[:4]))

    tail = "".join(lines[-12:])
    show("结尾有数字/器物判词", bool(re.search(r"\d|[零一二三四五六七八九十百千万]", tail)) and bool(RITUAL.search(tail)), tail[-24:])

    if bad:
        print(f"\nHYPE: FAIL {len(bad)} → 对照 拆文库 的情绪曲线补爽点：先补位置，再改正文。")
        return len(bad)
    print("\nHYPE: PASS 爽点密度与位置符合拆文库实测区间。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
