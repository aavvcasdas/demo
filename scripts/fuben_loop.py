#!/usr/bin/env python3
"""人生副本 loop engineering：设计门禁 → 成稿门禁 → 数据回流 → 规则归因。

用法
  python3 scripts/fuben_loop.py design 作品/NN_xxx/设定.md            # 写正文前：剧本层门禁
  python3 scripts/fuben_loop.py draft  作品/NN_xxx/                   # 写完后：呼应回收/侧面/宣判/收束
  python3 scripts/fuben_loop.py record NN 点赞 [播放] [备注]           # 发布后：写入 作品/_数据.csv
  python3 scripts/fuben_loop.py report                                # 全量：特征 × 点赞 归因，输出该改 skill 哪一层
"""
import re, sys, os, csv, glob, json, statistics as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKS = os.path.join(ROOT, '作品'); LIB = os.path.join(ROOT, '拆文库'); DATA = os.path.join(WORKS, '_数据.csv')
HAN = lambda s: len(re.findall(r'[\u4e00-\u9fff]', s))

def read(p):
    return open(p, encoding='utf-8').read() if os.path.exists(p) else ''

def lib_titles():
    return [os.path.basename(d).split('_', 1)[-1] for d in glob.glob(os.path.join(LIB, '[0-9]*'))]

# ---------- L1 设计门禁（剧本层，写正文前） ----------
def design(path):
    t = read(path); bad = []
    def need(name, ok, why=''):
        print(('OK  ' if ok else 'BAD ') + name + ('' if ok else '  ← ' + why))
        if not ok: bad.append(name)
    need('志/曲线已选', bool(re.search(r'(志|曲线)', t)) and bool(re.search(r'(清算|沉沦|实录|代价|迷因|荒诞|加冕|逆袭|身体|温情)', t)), '设定.md 首屏写明 志 + 曲线')
    m = re.search(r'拆文库/(\d+\w*)', t)
    need('模板篇已指定', bool(m), '写「模板 = 拆文库/NN」并抄其六段占比表')
    need('六段占比表', len(re.findall(r'\|\s*\d{1,2}%', t)) >= 5, '六段各占比')
    need('原型清单≥5条', len(re.findall(r'^\s*\d+\.\s', t, re.M)) >= 5, '搜到的原型逐条列出并标落点')
    need('放大事件（开篇）', bool(re.search(r'(开篇|放大|巅峰|11%)', t)), '指定哪一个事件占开篇 10–15%')
    need('戳穿机关', bool(re.search(r'(戳穿|机关|证据|截图|对账|翻转)', t)), '写清「外圈第一次看见人后」是什么物证')
    sec = re.search(r'##[^\n]*呼应[^\n]*\n(.*?)(?=\n## |\Z)', t, re.S)
    pairs = len(re.findall(r'^\|\s*\d+\s*\|', sec.group(1) if sec else '', re.M))
    need('呼应表≥8对', pairs >= 8, f'现有 {pairs} 对（合集均值 8–10）')
    need('侧面四通道', all(k in t for k in ['旁观者', '环境', '器物', '不作为']) or '侧面' in t, '旁观者身体/旁观者的话/环境规格/权力者不作为')
    if re.search(r'(双面|人前|表面|老好人|人畜无害|塑料)', t):
        need('双面配比表', '人前' in t and '人后' in t and len(re.findall(r'^\|', t, re.M)) >= 10, '§15.10：每个人后恶行前有一个有观众的人前善举')
    need('收束=器物/动作', bool(re.search(r'(收束|结尾).{0,80}(器物|动作|赞|鞋|碗|门|票|一个|空)', t, re.S)), '结尾落到一件东西，不落到抒情')
    # 同题撞正主
    title = re.search(r'#\s*\d+\s*[·・]\s*([^（(\n]+)', t)
    if title:
        key = title.group(1).strip()
        hits = [x for x in lib_titles() if any(w in x for w in re.findall(r'[\u4e00-\u9fff]{2,}', key)[:3])]
        need('同题撞正主检查', ('同题' in t or '换视角' in t) or not hits, f'拆文库已有 {hits[:3]}：必须换视角或加深谷，并在设定里写明差异')
    print('\nDESIGN:', 'PASS' if not bad else f'FAIL {len(bad)} → 先改设定.md 再写正文')
    return len(bad)

# ---------- L2 成稿门禁（呼应回收 / 侧面 / 宣判 / 收束） ----------
INNER = r'^(你觉得|你以为|你认为|你知道|你明白|你终于|你意识到|你心里|你感到|你想)'
VERDICT = r'(被孤立|被排挤|疏远了你|没人再|再也没有人|所有人都|大家都不|众叛亲离|自食其果|报应)'
LYRIC_END = r'(是不是也|也许|或许|大概|你在想|不知道.*吗|吧$|呢$)'
def draft(d):
    d = d.rstrip('/'); body = read(os.path.join(d, '正文.md')); setting = read(os.path.join(d, '设定.md'))
    lines = [l for l in body.split('\n') if l.strip() and not l.startswith('#')]
    n = HAN(body); bad = []
    def need(name, ok, info=''):
        print(('OK  ' if ok else 'BAD ') + f'{name:14} {info}')
        if not ok: bad.append(name)
    need("字数 2000–3000", 2000 <= n <= 3000, n)
    # 呼应回收：设定.md 呼应表第 3 列的关键词要能在正文后 40% 找到
    sec = re.search(r'##[^\n]*呼应[^\n]*\n(.*?)(?=\n## |\Z)', setting, re.S)
    rows = re.findall(r'^\|\s*\d+\s*\|([^|]+)\|([^|]+)\|', sec.group(1) if sec else setting, re.M)
    tail = ''.join(lines[int(len(lines) * .55):]); head = ''.join(lines[:int(len(lines) * .6)])
    miss = []
    for setup, payoff in rows:
        kws = [k for k in re.findall(r'[\u4e00-\u9fff]{2,4}', payoff) if k not in ('没有', '一个', '你的', '她的')]
        if not any(k in tail for k in kws[:6]): miss.append(payoff.strip()[:14])
    need('呼应回收到位', len(rows) >= 8 and not miss, f'{len(rows)}对, 未在后半找到: {miss}' if miss else f'{len(rows)}对')
    inner = [l for l in lines if re.search(INNER, l)]
    need('主角内心≤3', len(inner) <= 3, f'{len(inner)}: ' + ' / '.join(x[:12] for x in inner[:5]))
    ver = [l for l in lines if re.search(VERDICT, l)]
    need('叙述者不宣判', not ver, ' / '.join(x[:16] for x in ver[:3]))
    dlg = [l for l in lines if re.search(r'(^|\s)(你|他|她)说\s|^\s*[「"]', l)]
    need('正面台词≤3行', len(dlg) <= 3, len(dlg))
    end = lines[-6:]
    need('收束不抒情', not any(re.search(LYRIC_END, l) for l in end[:-1]), ' / '.join(end[-3:])[:60])
    need('末句≤25字', HAN(end[-1]) <= 25, end[-1][:30])
    brands = re.findall(r'(资生堂|Mac|MAC|空军一号|AJ|耐克|阿迪|苹果|iPhone|华为|小米|星巴克|瑞幸|喜茶|优衣库|ZARA)', body)
    need('无品牌', not brands, set(brands))
    misread = [l for l in lines if re.search(r'(你把.{0,6}归给|你觉得.{0,6}(不礼貌|关系好|正常|没事)|你没听清|你没在意|你没注意)', l)]
    need('主角误读≥2', len(misread) >= 2, len(misread))
    print('\nDRAFT:', 'PASS' if not bad else f'FAIL {len(bad)}')
    return len(bad)

# ---------- L3 数据回流 ----------
def features(d):
    body = read(os.path.join(d, '正文.md')); setting = read(os.path.join(d, '设定.md'))
    lines = [l for l in body.split('\n') if l.strip() and not l.startswith('#')]
    if not lines: return None
    tail = ''.join(lines[-6:])
    return dict(
        字数=HAN(body),
        呼应对=len(re.findall(r'^\|\s*\d+\s*\|', setting, re.M)),
        内心句=sum(bool(re.search(INNER, l)) for l in lines),
        宣判句=sum(bool(re.search(VERDICT, l)) for l in lines),
        台词行=sum(bool(re.search(r'(^|\s)(你|他|她)说\s', l)) for l in lines),
        抒情收束=int(bool(re.search(LYRIC_END, tail))),
        误读句=sum(bool(re.search(r'(归给|你没听清|你没在意|你觉得.{0,6}(不礼貌|关系好))', l)) for l in lines),
        价格数=len(re.findall(r'\d+(?:\.\d+)?\s*(?:块|元|万)', body)),
        制度词=len(re.findall(r'(规定|表格|Excel|签到|考勤|流程|评分|投票|截图|申请|通知)', body)),
        人际词=len(re.findall(r'(舍友|室友|同学|班长|师傅|老师|辅导员)', body)),
    )

def record(args):
    nid, likes = args[0], int(args[1]); plays = int(args[2]) if len(args) > 2 and args[2].isdigit() else ''
    note = ' '.join(args[3:]) if len(args) > 3 else ''
    d = next((x for x in glob.glob(os.path.join(WORKS, f'{nid}_*')) if os.path.isdir(x)), None)
    if not d: sys.exit(f'找不到 作品/{nid}_*')
    f = features(d) or {}
    new = not os.path.exists(DATA)
    with open(DATA, 'a', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        if new: w.writerow(['id', '目录', '点赞', '播放', '备注'] + list(f))
        w.writerow([nid, os.path.basename(d), likes, plays, note] + list(f.values()))
    print('已记录 →', DATA); print(json.dumps(f, ensure_ascii=False))

def report():
    if not os.path.exists(DATA): sys.exit('还没有数据：先 record')
    rows = list(csv.DictReader(open(DATA, encoding='utf-8')))
    if len(rows) < 4: print(f'仅 {len(rows)} 条，归因不稳；先列出：')
    keys = [k for k in rows[0] if k not in ('id', '目录', '点赞', '播放', '备注')]
    print(f"{'篇':6}{'点赞':>6}  " + ' '.join(f'{k:>5}' for k in keys))
    for r in rows: print(f"{r['id']:6}{r['点赞']:>6}  " + ' '.join(f"{r[k]:>5}" for k in keys))
    if len(rows) >= 4:
        likes = [float(r['点赞']) for r in rows]; hi = st.median(likes)
        print('\n特征 × 点赞（>中位 vs ≤中位 的均值差；|差| 大且方向稳定的才是该进 skill 的规则）')
        for k in keys:
            try:
                a = [float(r[k]) for r in rows if float(r['点赞']) > hi]; b = [float(r[k]) for r in rows if float(r['点赞']) <= hi]
                if a and b: print(f'  {k:6} 高组 {st.mean(a):7.1f}  低组 {st.mean(b):7.1f}  差 {st.mean(a)-st.mean(b):+7.1f}')
            except ValueError: pass
        print('\n处置：差值方向与 skill 现行门槛相反的条款 → 降为 advisory；连续 3 篇验证同向的 → 升为 BLOCK。修改后在 人生副本实录.md §零 记一行变更。')

if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == 'design': sys.exit(design(args[0]))
    if cmd == 'draft': sys.exit(draft(args[0]))
    if cmd == 'record': record(args)
    elif cmd == 'report': report()
    else: sys.exit(__doc__)
