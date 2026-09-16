#!/usr/bin/env python3
"""L2.6 可读性 lint：说话行总量 / 她他指代 / 术语 / 清单段。用法: python3 scripts/fuben_lint.py 作品/NN_xxx/ [--fix-list]"""
import re, sys, os
d = sys.argv[1].rstrip('/')
L = [l.strip() for l in open(os.path.join(d, '正文.md'), encoding='utf8') if l.strip() and not l.startswith('#')]
S = open(os.path.join(d, '设定.md'), encoding='utf8').read()
N = len(L); bad = 0
def show(k, ok, v): print(('OK  ' if ok else 'BAD ') + f'{k:18} {v}')
# 1 说话行总量（含转述）≤8%（37 原文 6%）
sp = [i for i, l in enumerate(L) if re.search(r'(说|问|喊|念|嘀咕|提了一句|回了)', l) and not re.search(r'(没有?说|不说|说不|说话|说清楚|来说|说法|换回|回来|回去|回头|回自己|问号|据说|听说)', l)]
# 反杀现场（五拍收尾句「再也没有主动」往前 ≤80 行）内的说话行豁免：审讯/面试/对质型场景本就靠问答
end5 = next((i for i, l in enumerate(L) if '再也没有主动' in l), None)
scene = set(range(max(0, end5 - 80), end5)) if end5 else set()
sp_out = [i for i in sp if i not in scene]
ok = len(sp_out) <= (N - len(scene)) * .08; show('说话行≤8%(反杀现场豁免)', ok, f'现场外 {len(sp_out)}/{N-len(scene)}={len(sp_out)/max(1,N-len(scene)):.0%}  现场内 {len(sp)-len(sp_out)}'); bad += not ok
# 2 她/他 指代：前 6 行内出现 ≥2 个不同人名，或 0 个人名且不是「你」→ 摸不着头脑
names = set(re.findall(r'(林悦|周雨|陈静|辅导员|老板娘|老头|老周|表弟|同学|室友|同事|主管|小陈|大老板|门卫|前台|你妈|你爸|她妈|他妈|学姐|系办老师|陈老师|导师|客户|小伙|工作人员|买车的人|小妹)', S + ''.join(L)))
FEM = {'林悦','周雨','陈静','辅导员','老板娘','你妈','她妈','学姐','系办老师','室友','前台','小妹','工作人员'}
MAS = {'老头','老周','表弟','同事','主管','小陈','大老板','门卫','你爸','他妈','陈老师','导师','客户','小伙','买车的人','同学'}
mo = re.search(r'对手[:：]\s*([^\s/（(]+)', S); opp = mo.group(1) if mo else None
opp_pron = '她' if (opp in FEM or (opp and re.search(r'(女|她|前女友|妈|娘|姐)', opp))) else '他'
amb = []
for i, l in enumerate(L):
    if not re.search(r'(^|[^你])(她|他)(?![们])', l): continue
    pron = re.search(r'(她|他)', l).group(1)
    same = FEM if pron == '她' else MAS
    win = set(n for j in range(max(0, i - 12), i) for n in names if n in L[j] and n in same)
    # 主对手（设定「对手: X」）无需点名；窗口内出现 ≥2 个同性别人物，或没有对手且窗口无人名 → 模糊
    if (opp and pron == opp_pron): win.discard(opp)
    if len(win) >= 2 or (not win and not opp and i > 3): amb.append((i + 1, l[:16], sorted(win)[:3]))
ok = len(amb) <= max(6, N * .015); show('她/他指代模糊≤1.5%', ok, f'{len(amb)} 处：' + ' | '.join(f'L{a} {b} ←{c}' for a, b, c in amb[:5])); bad += not ok
# 3 术语（初中生测试）
jar = [l for l in L if re.search(r'(评优|综测|推免|经手人|申报|编号|绩点|学分|德育分|OA|KPI|对齐|复盘|赋能|抓手|闭环)', l)]
ok = len(jar) <= 2; show('术语行≤2', ok, f'{len(jar)}：' + ' | '.join(x[:12] for x in jar[:4])); bad += not ok
# 4 清单段（第一件/条/张…）：每条 ≤7 行，总长 ≤45
heads = [i for i, l in enumerate(L) if re.match(r'^第[一二三四五六七八九]+(件|条)$', l)]
heads = [h for k, h in enumerate(heads) if (k and h - heads[k-1] <= 15) or (k + 1 < len(heads) and heads[k+1] - h <= 15)]
if len(heads) >= 3:
    lens = [b - a for a, b in zip(heads, heads[1:])]
    ok = max(lens) <= 7 and (heads[-1] - heads[0] + lens[-1]) <= 45; show('清单段 每条≤7 总≤45', ok, f'各条 {lens} 起 L{heads[0]+1}'); bad += not ok
# 5 每 30 行至少 1 个身体/环境行（反流水账）
phys = re.compile(r'(手|耳朵|后背|喉咙|胃|膝盖|呼吸|汗|发麻|发烫|发凉|嗡|味道|声音|灯|门|窗|风|雨|凉|热|空调|冷气|响|湿|烫|烟味|太阳|键盘声)')
gaps = [k for k in range(0, N, 30) if not any(phys.search(l) for l in L[k:k + 30])]
ok = not gaps; show('每30行有身体/环境', ok, f'空窗起行 {[g+1 for g in gaps]}'); bad += not ok
print('\nLINT:', 'PASS' if not bad else f'FAIL {bad}')
if '--fix-list' in sys.argv:
    print('\n== 修改清单 ==')
    for i in sp: print(f'L{i+1} 说话行 → 转述压缩/改动作: {L[i][:20]}')
    for a, b, c in amb: print(f'L{a} 指代 → 换人名: {b}')
sys.exit(bad)
