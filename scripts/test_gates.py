#!/usr/bin/env python3
"""门禁自测（还 P2「python 门禁脚本自身零测试」的债）。

覆盖两类刚踩过的坑：
  T1 fuben_hype 否定窗口：反事实清单里的「不写中奖/禁止奖金」不得触发兑现题门；
     肯定句 ≥4 处必须触发。
  T2 fuben_setting_years 散文层对账：设定主线与事实锁年份打架必须红；
     口径一致必须绿。
运行：python3 scripts/test_gates.py        （离线，秒级）
可选：python3 scripts/test_gates.py --works（全库七闸回归，较慢）
"""
import os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MIN_BODY = """今天体验的人生副本是
测试用的一条人
你每天守着一台机器
2021年 你花一千二买了台二手单反
卖家叮嘱别摔
你把光圈拧到5.6
那天你按了快门很多次
晚上你把它收回柜子
柜门的灯灭了
第二天你又拆开机器擦镜头
手心全是汗
"""

SIX_ROWS = """## 爽点表

| 序 | 位置 | 情绪值 | 事件 | 类型 | 锚点 |
|---|---|---|---|---|---|
| 1 | 2% | +7 | 钩子 | 钩子 | 测试用的一条人 |
| 2 | 20% | +5 | 买机器 | 兑现 | 买了台二手单反 |
| 3 | 35% | -6 | 拧光圈 | 规矩 | 你把光圈拧到5.6 |
| 4 | 55% | +8 | 收柜子 | 收束 | 把它收回柜子 |
| 5 | 75% | -7 | 灯灭 | 谷底 | 柜门的灯灭了 |
| 6 | 95% | +3 | 擦镜头 | 器物 | 手心全是汗 |

"""

ANTI_NEG = """## 反事实防错清单

- 不写中奖叙事
- 禁止出现奖金数字
- 不提到账截图
- 这不是彩票故事
- 不写拆迁款
- 遗产一分没有
"""

ANTI_POS = """## 兑现事实

- 他中奖了
- 奖金五十万
- 到账短信亮起来
- 他在彩票站排队
- 拆迁款到账了
- 遗产全给了弟弟
"""

def make_work(tmp, name, body, setting):
    d = os.path.join(tmp, name)
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "正文.md"), "w", encoding="utf-8").write(body)
    open(os.path.join(d, "设定.md"), "w", encoding="utf-8").write(setting)
    return d

def run(cmd):
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr

def t_negation(tmp):
    d1 = make_work(tmp, "作品甲", MIN_BODY, "# 73 · 测试\n\n" + SIX_ROWS + ANTI_NEG)
    _, out1 = run(["python3", "scripts/fuben_hype.py", d1])
    ok1 = "非兑现/暴富题，跳过" in out1
    d2 = make_work(tmp, "作品乙", MIN_BODY, "# 73 · 测试\n\n" + SIX_ROWS + ANTI_POS)
    _, out2 = run(["python3", "scripts/fuben_hype.py", d2])
    ok2 = "非兑现/暴富题，跳过" not in out2 and "钱的去向" in out2
    return ok1 and ok2, f"否定句不开门={ok1} 肯定句开门={ok2}"


def t_stamp(tmp):
    bad = "今天体验的人生副本是\n测试流水账\n凌晨三点十一\n你删了一段\n二百字\n六点四十 闹钟响\n你打开文档\n一行\n再一行\n你继续做事\n把本子合上\n笔停了\n灯灭了\n手冷了\n你又坐下\n纸还有\n你写下字\n墨淡了\n窗外亮\n你把纸收好\n"
    good = "今天体验的人生副本是\n测试嵌句\n你删了一段\n时间是凌晨三点十一\n二百字\n闹钟响在第一声\n你打开文档\n一行\n再一行\n你继续做事\n把本子合上\n笔停了\n灯灭了\n手冷了\n你又坐下\n纸还有\n你写下字\n墨淡了\n窗外亮\n你把纸收好\n"
    st = "# 76 · 测试\n\n- 开头路线：线性\n"
    d1 = make_work(tmp, "作品戊", bad, st)
    _, out1 = run(["python3", "scripts/fuben_loop.py", "draft", d1])
    ok1 = "BAD 开头不堆时戳" in out1
    d2 = make_work(tmp, "作品己", good, st)
    _, out2 = run(["python3", "scripts/fuben_loop.py", "draft", d2])
    ok2 = "OK  开头不堆时戳" in out2
    return ok1 and ok2, f"钟面账被抓={ok1} 时戳嵌句放行={ok2}"


def t_numclaim(tmp):
    body = "今天体验的人生副本是\n测试计数\n手册统计页写着 218次\n成功218次 失败0次\n你看着那行数字\n把手机放下\n灯灭了\n第二天还在\n218 没变\n你笑了一下\n把本子合上\n笔停了\n"
    fake = "# 76 · 测试\n\n## 主线\n\n- 设定：手册统计成功 219 次失败 0 次。\n\n## 事实锁\n\n| 字段 | 已锁事实 |\n|---|---|\n| 频率/次数 | 218 次 |\n"
    real = fake.replace("219 次", "218 次")
    d1 = make_work(tmp, "作品庚", body, fake)
    rc1, out1 = run(["python3", "scripts/fuben_setting_years.py", d1])
    ok1 = rc1 == 1 and "219" in out1
    d2 = make_work(tmp, "作品辛", body, real)
    rc2, out2 = run(["python3", "scripts/fuben_setting_years.py", d2])
    ok2 = rc2 == 0
    return ok1 and ok2, f"散文层 219 假账被抓={ok1} 218 口径放行={ok2}"

def t_setting_years(tmp):
    ledger = """## 物件台账

| 物件 | 首次出现 |
|---|---|
| 二手单反（1200） | 2021 年购入 |

"""
    locks = """## 事实锁

| 字段 | 已锁事实 |
|---|---|
| 单价/金额 | 二手单反 1200 元（2021） |
"""
    bad = "# 75 · 测试\n\n## 主线\n\n- 设定：一台二手单反 2015 年开光。\n\n" + ledger + locks
    good = bad.replace("2015 年开光", "2021 年买入")
    d1 = make_work(tmp, "作品丙", MIN_BODY, bad)
    rc1, out1 = run(["python3", "scripts/fuben_setting_years.py", d1])
    ok1 = rc1 == 1 and "2015" in out1
    d2 = make_work(tmp, "作品丁", MIN_BODY, good)
    rc2, out2 = run(["python3", "scripts/fuben_setting_years.py", d2])
    ok2 = rc2 == 0
    return ok1 and ok2, f"散文层双出身被抓={ok1} 口径一致放行={ok2}"

def t_corpus(tmp):
    """R20 语料反审红绿样：大师写法不得拦（首屏词表代理/围观对位/主体品牌/行业词/一日编年），
    真病灶必须仍拦（叙述者宣判报应/运营黑话/开头钟面账）。"""
    green = ("今天体验的人生副本是\n换肾买iPhone的人\n15岁那年冬天\n你还是县一中的初三学生\n每天下午5:50放学铃响\n"
             "你把兼职赚的260块交给母亲\n所有人都看着你\n你攥紧收据\n灯灭了\n第二天\n"
             "iPhone的手感是新皮的\n分期36期你在纸上算\n手是抖的\n经理说 完不成KPI就滚\n你把本子合上\n笔停了\n"
             "早上六点整 闹钟又响\n你把收据收进铁盒\n铁盒满了 你数了一遍\n灯又灭了\n你睡了\n")
    red = ("今天体验的人生副本是\n测试人\n你每天老实干活\n这就是报应\n你被孤立了\n疏远了你\n"
           "你开始赋能团队\n你建立闭环\n把手收拢\n灯灭了\n笔停了\n第二天\n你继续干活\n把本子合上\n手是暖的\n")
    st = "# T6 · 语料红绿样\n"
    d1 = make_work(tmp, "语料绿", green, st)
    _, g1 = run(["python3", "scripts/fuben_loop.py", "draft", d1])
    _, g2 = run(["python3", "scripts/fuben_lint.py", d1])
    ok_green = ("BAD 叙述者不替观众判决" not in g1 and "BAD 首屏" not in g1
                and "品牌" not in [x.split()[1] for x in g1.splitlines() if x.startswith("BAD ")]
                and "BAD 开头不堆时戳" not in g1 and "BAD 陌生术语" not in g2
                and "BAD 运营黑话" not in g2 and "BAD 每45行" not in g2)
    d2 = make_work(tmp, "语料红", red, st)
    _, r1 = run(["python3", "scripts/fuben_loop.py", "draft", d2])
    _, r2 = run(["python3", "scripts/fuben_lint.py", d2])
    ok_red = ("BAD 叙述者不替观众判决" in r1 and "BAD 运营黑话≤1" in r2)
    return ok_green and ok_red, f"大师写法放行={ok_green} 报应/黑话仍拦={ok_red}"


def t_witness(tmp):
    """R21 在场腿红绿样：≥+5 爽点必须登记见证人且名字落在锚点±10行。
    绿＝卖家在锚点邻近行；红A＝在场填「你」自报独享；红B＝登记了场面里没出现的人名。"""
    base = SIX_ROWS.replace("| 序 | 位置 | 情绪值 | 事件 | 类型 | 锚点 |",
                            "| 序 | 位置 | 情绪值 | 事件 | 类型 | 锚点 | 在场 |")
    green = (base.replace("| 1 | 2% | +7 | 钩子 | 钩子 | 测试用的一条人 |",
                          "| 1 | 2% | +7 | 钩子 | 钩子 | 测试用的一条人 | —")
                 .replace("| 2 | 20% | +5 | 买机器 | 兑现 | 买了台二手单反 |",
                          "| 2 | 20% | +5 | 买机器 | 兑现 | 买了台二手单反 | 卖家")
                 .replace("| 4 | 55% | +8 | 收柜子 | 收束 | 把它收回柜子 |",
                          "| 4 | 55% | +8 | 收柜子 | 收束 | 把它收回柜子 | 卖家"))
    solo = green.replace("| 4 | 55% | +8 | 收柜子 | 收束 | 把它收回柜子 | 卖家",
                         "| 4 | 55% | +8 | 收柜子 | 收束 | 把它收回柜子 | 你")
    ghost = green.replace("| 4 | 55% | +8 | 收柜子 | 收束 | 把它收回柜子 | 卖家",
                          "| 4 | 55% | +8 | 收柜子 | 收束 | 把它收回柜子 | 校长")
    st = "# T7 · 在场腿\n"
    res = {}
    for tag, rows in (("green", green), ("solo", solo), ("ghost", ghost)):
        d = make_work(tmp, f"在场{tag}", MIN_BODY, st + rows)
        _, out = run(["python3", "scripts/fuben_hype.py", d])
        res[tag] = out
    ok_green = ("OK  无独享高爽点" in res["green"] and "OK  见证人落锚点" in res["green"])
    ok_solo = "BAD 无独享高爽点" in res["solo"]
    ok_ghost = "BAD 见证人落锚点" in res["ghost"]
    return ok_green and ok_solo and ok_ghost, f"绿放行={ok_green} 独享拦={ok_solo} 幽灵见证拦={ok_ghost}"


GREEN = ["58b_反骨嘉豪_代价版", "64_活人微死的AI人", "65_寝室里那个人畜无害的女生", "66_寝室里什么都不争的那个女生", "67_分手时说「我们不合适」的男生",
         "70_三次把同一个人推开的女生", "71_只会按字面意思办事的新人", "72_每天买一张彩票的人",
         "73_合影时永远在按快门的人", "75_人生副本作者的一天"]

def works_regression():
    fails = []
    for w in GREEN:
        d = os.path.join(ROOT, "作品", w)
        if not os.path.isdir(d):
            continue
        _, out = run(["python3", "scripts/fuben_run.py", d])
        if "全部机械闸 PASS" not in out:
            fails.append(w)
    return not fails, f"应绿 {len(GREEN)} 篇，失败 {len(fails)}：{fails}"

def main():
    tmp = tempfile.mkdtemp(prefix="fuben_test_")
    results = []
    try:
        results.append(("T1 hype 否定窗口",) + t_negation(tmp))
        results.append(("T2 设定散文层对账",) + t_setting_years(tmp))
        results.append(("T4 反流水账时戳闸",) + t_stamp(tmp))
        results.append(("T5 散文层计数对账",) + t_numclaim(tmp))
        results.append(("T6 语料反审红绿样",) + t_corpus(tmp))
        results.append(("T7 在场腿红绿样",) + t_witness(tmp))
        if "--works" in sys.argv:
            results.append(("T3 全库七闸回归",) + works_regression())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    bad = 0
    for name, ok, detail in results:
        print(("OK  " if ok else "FAIL") + f" {name}  {detail}")
        bad += 0 if ok else 1
    print("GATE-TESTS:", "PASS" if not bad else f"FAIL {bad}")
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main())
