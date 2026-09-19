#!/usr/bin/env python3
"""体检模式（R17 偷师 shuohao-skills 的体检模式 + zenstory 的四档结论）。

用法
  python3 scripts/fuben_health.py             # 全库体检：对 作品/*/ 跑全部机械闸，出单页报告
  python3 scripts/fuben_health.py --corpus    # 语料反向体检：拿拆文库大师稿跑正文闸

哲学（两家 3566★/2059★ 仓验证过的路线）：
  - shuohao-skills：模型自评容易自圆其说，脚本检查不会 → 体检全部确定性脚本跑，零模型额度；
  - chaosinu7 铁律：自动质检查不出内容缺陷 → 体检报告不是免检牌，脊柱层仍走 fuben-review 人工项；
  - zenstory：关键输入不足时给 PROVISIONAL，不硬判 → 无设定.md 的作品只跑文本检查并如实标注。

语料反向体检的裁决尺（R13b 处决 6 条伪阈值用的同一把）：
  大师稿成批过不了的正文闸 = 把单稿体质当全员义务 = 多余硬约束嫌疑；
  账号主明令类闸（品牌红线等）豁免于语料检验，永远保留。
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKS = os.path.join(ROOT, "作品")
LIB = os.path.join(ROOT, "拆文库")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from fuben_consistency import content_lines  # noqa: E402
from fuben_loop import (  # noqa: E402
    HAN, INNER, VERDICT, LYRIC_END, _TIME_ALONE, _stamp_report, _timeline_info, dialogue_units,
)
from fuben_density import density  # noqa: E402

PHYS = re.compile(r"手|耳朵|后背|喉咙|胃|膝盖|呼吸|汗|发麻|发烫|发凉|嗡|味道|声音|灯|门|窗|风|雨|凉|热|空调|冷气|响|湿|烫|烟味|太阳|水壶")
YEAR_LEDGER = re.compile(r"^第\s*[一二三四五六七八九十\d]+\s*个?年")
BRANDS = re.compile(r"资生堂|Mac|MAC|空军一号|AJ|耐克|阿迪|苹果|iPhone|华为|小米|星巴克|瑞幸|喜茶|优衣库|ZARA")

# 正文文本闸清单：name -> (判定函数, 类别)。类别：风格=须过语料检验；账号=账号主明令，豁免。
def text_checks(body: str) -> dict:
    lines = content_lines(body)
    n = HAN(body)
    out = {}

    out["字数2200–3600"] = (2200 <= n <= 3600, f"{n} 字")
    out["行数220–420"] = (220 <= len(lines) <= 420, f"{len(lines)} 行")
    out["单行>24字≤2"] = (sum(1 for l in lines if HAN(l) > 24) <= 2, f"{sum(1 for l in lines if HAN(l) > 24)} 行超长")

    h, a, o, ex = _stamp_report(lines)
    alone_head = [l for l in lines[:16] if _TIME_ALONE.match(l.strip())]
    alone_mid = [l for l in lines[5:16] if _TIME_ALONE.match(l.strip())]
    out["开头不堆时戳"] = (
        h <= 1 and a <= 2 and o <= max(6, int(len(lines) * 0.035)) and len(alone_head) <= 1 and not alone_mid,
        f"时戳开头{h} 整行{a} 例:{' | '.join(ex[:2])}",
    )

    inner = [l for l in lines if INNER.search(l)]
    out["主角内心≤6"] = (len(inner) <= 6, f"{len(inner)} 处：{' / '.join(l[:12] for l in inner[:3])}")
    verdict = [l for l in lines if VERDICT.search(l)]
    out["叙述者不替观众判决"] = (not verdict, f"{len(verdict)} 处")

    speech = dialogue_units(lines)
    limit = max(8, int(len(lines) * 0.04))
    out["对白稀缺≤max(8,4%)"] = (len(speech) <= limit, f"{len(speech)}/{limit}")
    ack = [(no, l) for no, l in speech if re.search(r"(?:说|回|回答)\s+(?:好|行|嗯|哦|是|知道|好的|没事|没有)\s*$", l)]
    out["无空回应"] = (not ack, f"{len(ack)} 处")

    values, backwards = _timeline_info(body)
    out["时间顺序不倒退"] = (not backwards, str(backwards[:1]))
    out["年份锚点≤12"] = (len(set(values)) <= 12, f"{len(set(values))} 个")

    ledger = [i + 1 for i, l in enumerate(lines) if YEAR_LEDGER.match(l)]
    consec = any(ledger[i + 1] - ledger[i] == 1 for i in range(len(ledger) - 1))
    out["跨度不用年表罗列"] = (len(ledger) <= 2 and not consec, f"{len(ledger)} 行第N年开头")

    tail = lines[-6:]
    out["收束不抒情"] = (not any(LYRIC_END.search(l) for l in tail[:-1]), " / ".join(tail[-2:])[:40])
    out["末句≤25字"] = (HAN(tail[-1]) <= 25, tail[-1][:24])

    brands = BRANDS.findall(body)
    out["无不必要品牌"] = (not brands, str(set(brands)) if brands else "")

    gaps = [s + 1 for s in range(0, len(lines), 45) if not any(PHYS.search(l) for l in lines[s:s + 45])]
    out["每45行环境/身体"] = (not gaps, f"空窗起行 {gaps}")

    t, dn, d = density(body)
    out["数字密度≤25"] = (d <= 25.0, f"{d}/千字")
    return out


# R17b 降级三闸：报告制不计 FAIL（与 fuben_loop 对齐）
DOWNGRADED = {"字数2200–3600", "行数220–420", "每45行环境/身体"}


CORPUS_STYLE_CHECKS = [
    "字数2200–3600", "行数220–420", "单行>24字≤2", "开头不堆时戳", "主角内心≤6",
    "叙述者不替观众判决", "对白稀缺≤max(8,4%)", "无空回应", "时间顺序不倒退", "年份锚点≤12",
    "跨度不用年表罗列", "收束不抒情", "末句≤25字", "每45行环境/身体", "数字密度≤25",
]
ACCOUNT_POLICY = {"无不必要品牌"}  # 账号主 R2 去品牌红线：豁免语料检验


def corpus_mode() -> int:
    files = []
    for d in sorted(os.listdir(LIB)):
        if not d[0].isdigit() or d.startswith("00"):
            continue
        p = os.path.join(LIB, d, "原文", "原文.txt")
        if os.path.exists(p):
            files.append((d, p))
    print(f"# 语料反向体检：{len(files)} 篇大师稿 × 正文文本闸\n")
    viol = {k: [] for k in CORPUS_STYLE_CHECKS + list(ACCOUNT_POLICY)}
    for name, p in files:
        body = open(p, encoding="utf-8").read()
        res = text_checks(body)
        for k, (ok, info) in res.items():
            if not ok:
                viol[k].append(name.split("_", 1)[-1][:12])
    print(f"{'检查':<22}{'违例':>6}  违例作品")
    for k in CORPUS_STYLE_CHECKS + list(ACCOUNT_POLICY):
        flag = "（账号红线·豁免）" if k in ACCOUNT_POLICY else ("（R17b已降级报告制）" if k in DOWNGRADED else "")
        print(f"{k:<22}{len(viol[k]):>4}/{len(files)}  {'、'.join(viol[k][:6])}{'…' if len(viol[k]) > 6 else ''} {flag}")
    print("\n裁决尺：风格类违例率 ≥30% = 多余硬约束嫌疑（R13b 伪阈值同款）；≤10% = 大师稿默认操作，保留。")
    return 0


def works_mode() -> int:
    rows = []
    for d in sorted(os.listdir(WORKS)):
        dirp = os.path.join(WORKS, d)
        if not os.path.isdir(dirp) or not os.path.exists(os.path.join(dirp, "正文.md")):
            continue
        body = open(os.path.join(dirp, "正文.md"), encoding="utf-8").read()
        t, n, dens = density(body)
        secs = n / 6.4
        has_setting = os.path.exists(os.path.join(dirp, "设定.md"))
        if has_setting:
            r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "fuben_run.py"), dirp],
                               capture_output=True, text=True)
            gate = "PASS" if "全部机械闸 PASS" in r.stdout else "FAIL"
            fails = [l.strip()[4:].split("  ")[0] for l in r.stdout.splitlines() if l.strip().startswith("BAD")]
            s = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "fuben_scene_check.py"), dirp],
                               capture_output=True, text=True)
            raw = s.stdout.strip()
            scene = "0漂移" if raw.startswith("OK") else raw.split("：")[-1].strip()
            if gate == "PASS":
                verdict = "APPROVE" if scene == "0漂移" else "APPROVE_WITH_NOTES（场面表老件豁免）"
            else:
                verdict = "REVISE"
        else:
            res = text_checks(body)
            fails = [k for k, (ok, _) in res.items() if not ok and k not in DOWNGRADED]
            gate = f"文本闸 {len(fails)} FAIL" if fails else "文本闸 PASS"
            scene = "—"
            verdict = "PROVISIONAL（无设定.md，仅文本闸）"
        rows.append((d, n, dens, secs, gate, scene, verdict, fails))
    lines = [f"# 全库体检报告（fuben_health v1 · {date.today()}）", "",
             "> 体检模式：只报告不拦截（shuohao 体检模式 + zenstory 四档结论）。机械闸全绿≠成片没病",
             "> （chaosinu7 铁律：自动质检查不出内容缺陷）；脊柱层（状态三问等）仍走 fuben-review 人工项。",
             "> 已发布作品的 FAIL = 发布后体检改进点，入档不追改（R13 边界）。", "",
             "| 作品 | 字数 | 密度 | 估时 | 机械闸 | 场面表 | 结论 |", "|---|---|---|---|---|---|---|"]
    for d, n, dens, secs, gate, scene, verdict, fails in rows:
        lines.append(f"| {d} | {n} | {dens} | {int(secs)//60}:{int(secs)%60:02d} | {gate} | {scene} | {verdict} |")
    detail = [d for d, *_ , f in rows if f]
    if detail:
        lines += ["", "## FAIL 明细", ""]
        for d, n, dens, secs, gate, scene, verdict, fails in rows:
            if fails:
                lines.append(f"- **{d}**：{'、'.join(fails[:6])}")
    out = os.path.join(WORKS, "_体检报告_全库.md")
    open(out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\n已写入 {out}")
    return 0


if __name__ == "__main__":
    sys.exit(corpus_mode() if "--corpus" in sys.argv else works_mode())
