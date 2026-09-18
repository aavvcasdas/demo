#!/usr/bin/env python3
"""按 skills/story-short-analyze 输出契约机械校验 拆文库/ 各条目。
用法：python3 scripts/audit_analyze_lib.py [--scope=fuben|long|all]
口径：数字前缀目录（00_/01_…/28b/46/48a-c）= 人生副本 fuben 条目（本仓库生产合同范围，默认校验对象）；
非数字前缀目录 = story-long-analyze 管道的长篇网文条目，schema 不同，不得混入 fuben 口径
（2026-09-10 合规核查只覆盖 45 个 fuben 条目；长篇条目单独用 --scope=long 看）。
"""
import json, os, re, glob, sys
root='拆文库'
SCOPE='fuben'
for a in sys.argv[1:]:
    m=re.fullmatch(r'--scope=(fuben|long|all)',a)
    if not m: raise SystemExit(f'未知参数: {a}（用法: --scope=fuben|long|all，默认 fuben）')
    SCOPE=m.group(1)
is_fuben=lambda name: re.match(r'^\d',name) is not None  # 目录名前缀是唯一能把 54 个条目全分类的判据（5 个 BAD 长篇连 _meta 都缺）
REQ_FILES=['拆文报告.md','情节节点.md','写作手法.md','_meta.json']
REQ_META=['version','word_count','genre_detected','created_at','stages_completed','last_stage_in_progress','structure_counts']
SC={'beats':4,'hooks':3,'setup_clues':3,'character_archetypes':2,'reusable_structures':3}
ENUM={'视角反转','身份反转','动机反转','时间线反转','信息反转','认知反转','无反转'}
BLOCK_SECTIONS={'故事核':r'故事核','结构划分':r'结构划分|功能分段|结构段|段落结构|段界','情感曲线':r'情感曲线','爆点':r'爆点','反转':r'反转','人物':r'人物','五维':r'五维','共鸣':r'共鸣','可复用':r'可复用','话题性':r'话题性','爆点性':r'爆点性'}  # 节奏速报/开头/结尾 非 [BLOCK]，不计
WARN_SECTIONS={'节奏速报':r'节奏速报'}
rows=[]
for d in sorted(glob.glob(root+'/*/')):
    name=os.path.basename(d.rstrip('/'))
    if SCOPE=='fuben' and not is_fuben(name): continue
    if SCOPE=='long' and is_fuben(name): continue
    issues=[]
    for f in REQ_FILES:
        if not os.path.exists(d+f): issues.append(f'缺文件:{f}')
    if not os.path.isdir(d+'原文') or not os.listdir(d+'原文'): issues.append('缺原文/')
    m={}
    if os.path.exists(d+'_meta.json'):
        try: m=json.load(open(d+'_meta.json'))
        except Exception as e: issues.append(f'meta非法JSON:{e}')
    for k in REQ_META:
        if k not in m: issues.append(f'meta缺{k}')
    sc=m.get('structure_counts',{}) or {}
    rt=sc.get('reversal_type')
    for k,v in SC.items():
        if k=='setup_clues' and rt=='无反转': continue
        if k not in sc: issues.append(f'sc缺{k}')
        elif not isinstance(sc[k],int) or sc[k]<v: issues.append(f'sc.{k}={sc[k]}<{v}')
    if rt not in ENUM: issues.append(f'reversal_type非枚举:{rt}')
    if m.get('stages_completed')!=[2,3,4,5,6]: issues.append(f'stages={m.get("stages_completed")}')
    if m.get('last_stage_in_progress') is not None: issues.append('last_stage非空')
    # word count vs 原文
    wc_real=None
    for f in glob.glob(d+'原文/*'):
        t=open(f,encoding='utf-8',errors='ignore').read()
        wc_real=(wc_real or 0)+len(re.sub(r'\s','',t))
    if wc_real and m.get('word_count') and abs(wc_real-m['word_count'])/max(wc_real,1)>0.15:
        issues.append(f'word_count={m["word_count"]} vs 原文实测{wc_real}')
    if os.path.exists(d+'拆文报告.md'):
        rep=open(d+'拆文报告.md',encoding='utf-8').read().split('合规核查追加')[0]  # 忽略追加的待补附录
        miss=[k for k,p in BLOCK_SECTIONS.items() if not re.search(p,rep)]
        if miss: issues.append('报告缺段:'+'/'.join(miss))
        if len(rep)<3000: issues.append(f'报告仅{len(rep)}字')
    rows.append((name,m.get('genre_detected'),issues))
for n,g,i in rows:
    print(f'{"OK " if not i else "BAD"} {n} [{g}]'); 
    for x in i: print('     -',x)
bad=sum(1 for r in rows if r[2])
print(f'\nscope={SCOPE}  条目={len(rows)}  BAD count: {bad} / {len(rows)}')
if SCOPE=='fuben' and bad==0:
    print('fuben 口径全绿：README/合规核查宣称的 45/45 以本行为准。')
sys.exit(1 if bad else 0)
