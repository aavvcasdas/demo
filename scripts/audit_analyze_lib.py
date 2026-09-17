#!/usr/bin/env python3
"""按 skills/story-short-analyze 输出契约机械校验 拆文库/ 各条目。用法：python3 scripts/audit_analyze_lib.py"""
import json, os, re, glob
root='拆文库'
REQ_FILES=['拆文报告.md','情节节点.md','写作手法.md','_meta.json']
REQ_META=['version','word_count','genre_detected','created_at','stages_completed','last_stage_in_progress','structure_counts']
SC={'beats':4,'hooks':3,'setup_clues':3,'character_archetypes':2,'reusable_structures':3}
ENUM={'视角反转','身份反转','动机反转','时间线反转','信息反转','认知反转','无反转'}
BLOCK_SECTIONS={'故事核':r'故事核','结构划分':r'结构划分|功能分段|结构段|段落结构|段界','情感曲线':r'情感曲线','爆点':r'爆点','反转':r'反转','人物':r'人物','五维':r'五维','共鸣':r'共鸣','可复用':r'可复用','话题性':r'话题性','爆点性':r'爆点性'}  # 节奏速报/开头/结尾 非 [BLOCK]，不计
WARN_SECTIONS={'节奏速报':r'节奏速报'}
rows=[]
for d in sorted(glob.glob(root+'/*/')):
    name=os.path.basename(d.rstrip('/'))
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
print('\nBAD count:',sum(1 for r in rows if r[2]),'/',len(rows))
