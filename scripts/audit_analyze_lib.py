#!/usr/bin/env python3
"""拆文库契约审计（范围感知版）。

- 未在 `_audit_scope.json` 登记的目录：按 skills/story-short-analyze 输出契约机械校验
  （拆文报告.md / 情节节点.md / 写作手法.md / 原文/ / _meta.json + 结构计数阈值 + [BLOCK] 段）。
- scope=long-analyze：按 story-long-analyze 长篇管道契约校验
  （原文/ 非空 + 至少一份阶段产物：拆文报告.md / 快速预览.md / 概要.md / _progress.md）。
  status=in-progress 记为 PENDING：不计 OK 也不计 BAD，但必须写 reason（空 reason 视为 BAD，防止用
  「在途」绕过审计）。

用法：python3 scripts/audit_analyze_lib.py
退出码：有任何 BAD → 1（CI 依赖）；全部 OK/PENDING/LONG-OK → 0。
2026-09-19：扩库到 54 条目后旧版「45/45」声明漂移失效，改为范围感知审计 + CI 强制（.github/workflows/audit.yml）。
"""
import json, os, re, glob, sys

root = '拆文库'
REQ_FILES = ['拆文报告.md', '情节节点.md', '写作手法.md', '_meta.json']
REQ_META = ['version', 'word_count', 'genre_detected', 'created_at', 'stages_completed', 'last_stage_in_progress', 'structure_counts']
SC = {'beats': 4, 'hooks': 3, 'setup_clues': 3, 'character_archetypes': 2, 'reusable_structures': 3}
ENUM = {'视角反转', '身份反转', '动机反转', '时间线反转', '信息反转', '认知反转', '无反转'}
BLOCK_SECTIONS = {'故事核': r'故事核', '结构划分': r'结构划分|功能分段|结构段|段落结构|段界', '情感曲线': r'情感曲线', '爆点': r'爆点', '反转': r'反转', '人物': r'人物', '五维': r'五维', '共鸣': r'共鸣', '可复用': r'可复用', '话题性': r'话题性', '爆点性': r'爆点性'}  # 节奏速报/开头/结尾 非 [BLOCK]，不计

LONG_ARTIFACTS = ['拆文报告.md', '快速预览.md', '概要.md', '_progress.md']

scope_path = os.path.join(root, '_audit_scope.json')
scope_entries = {}
if os.path.exists(scope_path):
    try:
        scope_entries = json.load(open(scope_path, encoding='utf-8')).get('entries', {})
    except Exception as e:
        print(f'BAD _audit_scope.json 非法 JSON: {e}')
        sys.exit(1)

rows = []
for d in sorted(glob.glob(root + '/*/')):
    name = os.path.basename(d.rstrip('/'))
    issues = []
    entry = scope_entries.get(name)
    if entry is not None:
        status = entry.get('status', 'complete')
        reason = (entry.get('reason') or '').strip()
        if entry.get('scope') != 'long-analyze':
            issues.append(f'scope值非法:{entry.get("scope")}')
        if not reason:
            issues.append('scope登记缺reason（空reason视为绕过审计）')
        if not os.path.isdir(d + '原文') or not os.listdir(d + '原文'):
            issues.append('缺原文/')
        if status == 'in-progress' and not issues:
            rows.append((name, 'LONG-pending', []))
            continue
        if not any(os.path.exists(d + a) for a in LONG_ARTIFACTS):
            issues.append('长篇管道无任何阶段产物（' + '/'.join(LONG_ARTIFACTS) + '）')
        rows.append((name, 'LONG-ok' if not issues else 'LONG', issues))
        continue

    # ---- 短篇契约（默认） ----
    for f in REQ_FILES:
        if not os.path.exists(d + f):
            issues.append(f'缺文件:{f}')
    if not os.path.isdir(d + '原文') or not os.listdir(d + '原文'):
        issues.append('缺原文/')
    m = {}
    if os.path.exists(d + '_meta.json'):
        try:
            m = json.load(open(d + '_meta.json', encoding='utf-8'))
        except Exception as e:
            issues.append(f'meta非法JSON:{e}')
    for k in REQ_META:
        if k not in m:
            issues.append(f'meta缺{k}')
    sc = m.get('structure_counts', {}) or {}
    rt = sc.get('reversal_type')
    for k, v in SC.items():
        if k == 'setup_clues' and rt == '无反转':
            continue
        if k not in sc:
            issues.append(f'sc缺{k}')
        elif not isinstance(sc[k], int) or sc[k] < v:
            issues.append(f'sc.{k}={sc[k]}<{v}')
    if rt not in ENUM:
        issues.append(f'reversal_type非枚举:{rt}')
    if m.get('stages_completed') != [2, 3, 4, 5, 6]:
        issues.append(f'stages={m.get("stages_completed")}')
    if m.get('last_stage_in_progress') is not None:
        issues.append('last_stage非空')
    # word count vs 原文
    wc_real = None
    for f in glob.glob(d + '原文/*'):
        t = open(f, encoding='utf-8', errors='ignore').read()
        wc_real = (wc_real or 0) + len(re.sub(r'\s', '', t))
    if wc_real and m.get('word_count') and abs(wc_real - m['word_count']) / max(wc_real, 1) > 0.15:
        issues.append(f'word_count={m["word_count"]} vs 原文实测{wc_real}')
    if os.path.exists(d + '拆文报告.md'):
        rep = open(d + '拆文报告.md', encoding='utf-8').read().split('合规核查追加')[0]  # 忽略追加的待补附录
        miss = [k for k, p in BLOCK_SECTIONS.items() if not re.search(p, rep)]
        if miss:
            issues.append('报告缺段:' + '/'.join(miss))
        if len(rep) < 3000:
            issues.append(f'报告仅{len(rep)}字')
    rows.append((name, m.get('genre_detected'), issues))

bad = ok_s = ok_l = pend = 0
for n, g, i in rows:
    if not i and g == 'LONG-ok':
        print(f'LONG-ok {n}')
        ok_l += 1
    elif not i and g == 'LONG-pending':
        print(f'PENDing {n}（长篇在途，见 _audit_scope.json reason）')
        pend += 1
    elif not i:
        print(f'OK  {n} [{g}]')
        ok_s += 1
    else:
        print(f'BAD {n} [{g}]')
        for x in i:
            print('     -', x)
        bad += 1

print(f'\n短篇契约 OK: {ok_s} ｜ 长篇管道 OK: {ok_l} ｜ 长篇 PENDING: {pend}')
print('BAD count:', bad, '/', len(rows))
sys.exit(1 if bad else 0)
