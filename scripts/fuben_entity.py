#!/usr/bin/env python3
"""连续性锁（第三把锁）：题眼、器物、人物、时间的前后一致。

事实锁管数字真伪，爽感归审稿读通判断；本锁管「换词/换场景换到一半」的
残留：物件位置三变、旧版孤词、时间跨度打架、夜进夜散、代词无头、第N件事
换施力者、题眼与事件错位。每条 finding 都引用冲突原句；都是候选不是判决，
审稿层（fuben-review 读通专项）仍要人来读。表 → 脚本实测 → 闸门的回填
入口：--ledger 输出实测台账，作者粘贴回 设定.md，不得目测填数。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# 复用事实锁的否定句处理：反事实清单/否定语境里的词不能当事实用（PR#5 修过的误报面）。
from fuben_consistency import _has_positive, section

# ---------------------------------------------------------------------------
# 词表（可在 设定.md 的 实体台账 / 题眼锚 里扩展，见 parse_ledger/parse_anchor）
# ---------------------------------------------------------------------------

# 食物类名词：孤词检查（只出现一次且落在尾部 + 吃/点/夹上下文）
FOOD_WORDS = {
    '火锅', '麻辣烫', '烧烤', '串串', '炸鸡', '汉堡', '奶茶', '可乐', '啤酒', '零食',
    '薯片', '蛋糕', '甜品', '水果', '米饭', '面条', '馒头', '包子', '饺子', '汤',
    '鸡胸肉', '牛肉', '毛肚', '鸭血', '鸭肠', '羊肉', '虾', '鱼', '蟹', '青菜',
    '豆腐', '土豆', '丸子', '花生米', '瓜子', '夜宵', '宵夜', '代餐', '蟹柳', '烤鱼',
    '锅底', '蘸料', '螺蛳粉', '披萨', '寿司', '小龙虾', '卤味', '辣条', '泡面',
}

# 容器/位置词：器物状态轨迹用
CONTAINERS = ('碗', '锅', '盘', '碟', '杯', '瓶', '桌', '包', '兜', '袋', '盒', '盆', '筐', '冰箱')

# 搬运动词 + 方向/落点：有这些衔接，器物换位置才算合法
RELOCATE = re.compile(
    r'[捞夹放推塞倒拿端扔丢盛舀递揣架摆挂收搬移转拽拎提抓掏]\s*(?:出|进|到|回|入|来|去|上|下|过去|过来|回来|回去|出来|进去|上去)'
    r'|[捞夹放推塞倒拿端扔丢盛舀递揣架摆挂收搬移转拽拎提抓掏][^，。？！\s]{0,6}[碗锅盘碟杯瓶桌包兜袋盒盆][里中上边]?'
)

# 「不在场」语境词：时间跨度只在这些语境里对账，训练/目标时长不算
ABSENCE_MARKS = re.compile(
    r'免打扰|闭关|消失|失联|不见|没露面|没出现|没喊|没找|没联系|没去|没出|登仙|蒸发|匿迹|静音|不回|没冒泡|没现身|失约|放鸽子'
)

# 人物先行词：代词回溯窗口里出现这些，才算有头
PERSON_ROLES = (
    '教练', '老板', '老板娘', '师傅', '姑娘', '小伙', '医生', '老师', '同学', '同事', '室友',
    '发小', '邻居', '大爷', '大妈', '阿姨', '叔叔', '前台', '服务员', '店员', '主管', '店长',
    '经理', '组长', '班长', '领导', '甲方', '客户', '博主', '网友', '快递员', '保安', '司机',
    '护士', '警察', '秘书', '助理', '实习生', '主编', '编辑', '师娘', '师弟', '师妹', '师兄', '师姐',
)
PERSON_NAME_SUFFIX = re.compile(r'[一-龥]{1,3}(?:哥|姐|师傅|老板|大叔|大爷|阿姨|大姐|老哥|小子|丫头)')
PERSON_DEMONSTRATIVE = re.compile(r'(?<![一-龥])(?:这人|那人|对方)')
# 不定人称：永远不能当代词的锚
INDEFINITE_PERSON = re.compile(r'一个人|有人|别人|旁人|人家|每个人|没人|任何人')

PRONOUN = re.compile(r'(?<![一-龥a-zA-Z0-9])(?P<p>他|她)(?![们姐哥弟妹叔姨婶])')

# 开头立论的人物类 vs 第N件事的竞争压力源
FRIEND_CLASS = ('朋友', '兄弟', '哥们', '闺蜜', '发小', '室友', '同学', '同事', '群', '他们', '她们', '老友', '熟人', '哥们儿')
RIVAL_CLASS = ('博主', '网友', '评论区', '弹幕', '陌生人', '路人', '算法', '系统', '平台', '流量', '热搜', '网上', '全网', '推送', '大数据', '陌生人')

THESIS = re.compile(r'最[难大狠可怕]{1,2}的[，,\s]*(?:是)?[你你们咱们的]{0,2}(?P<actor>[一-龥]{2,6})')
ENUM_EVENT = re.compile(r'第(?P<n>[一二三四五六])件[事]')

# 题眼类词表：标题/口号的核心词类 vs 三场主事件的压力类
THEME_CLASSES = {
    '吃': ('吃', '涮', '夹', '喝', '啃', '嗦', '尝', '碗', '锅', '筷', '蘸', '蛋白', '代餐',
           '宵夜', '夜宵', '碳水', '充碳', '热量', '饭局', '聚餐', '下馆', '火锅', '麻辣烫',
           '烧烤', '串串', '炸鸡', '汉堡', '奶茶', '可乐', '啤酒', '零食', '薯片', '蛋糕',
           '甜品', '水果', '米饭', '面', '鸡胸肉', '牛肉', '毛肚', '鸭血', '羊肉', '虾',
           '鱼', '蟹', '青菜', '豆腐', '土豆', '丸子', '花生', '瓜子', '汤'),
    '耍': ('耍', '玩', '打牌', '麻将', '摸牌', '出牌', '凑人头', '三缺一', '唱歌', 'K歌',
           '出门', '浪', '嗨', '剧本杀', '桌游', '打游戏', '游戏', '打球', '篮球', '足球',
           '开黑', '组局', '局', '钓鱼', '野餐', '旅游', '逛街', '唱', '跳', '牌'),
    '练': ('练', '健身', '举铁', '训练', '薄肌', '肌肉', '增肌', '减脂', '课表', '跑步',
           '有氧', '无氧', '卧推', '深蹲', '硬拉', '下颌线', '体脂', '健身房', '月卡',
           '热身', '拉伸', '组数', '线条', '撸铁', '私教课'),
    '学': ('学', '上课', '刷题', '考试', '复习', '背书', '作业', '自习', '图书馆', '模拟',
           '错题', '上岸', '考研', '考公', '高考', '笔记', '卷'),
    '班': ('上班', '加班', '开会', '工位', '周报', '甲方', '项目', '绩效', '打卡', '通勤',
           '老板', '工资', '离职', '辞职', '饭碗'),
}

DURATION = re.compile(r'(?<![第\d])(?P<n>[一二两三四五六七八九十百\d]+|半)\s*(?P<u>个?月|星期|礼拜|周|天|日)(?![期末间])')

EXIT_SCENE = re.compile(r'散场|散局|离场|散了')
LIGHT_STATE = re.compile(r'全黑|天黑|黑透|全亮|天亮|亮了|蒙蒙亮|泛白|鱼肚白|黑下来|亮起来')
DAY_PART = re.compile(r'晚上|夜里|半夜|深夜|凌晨|清早|早上|上午|中午|下午|傍晚|黄昏|入夜|天黑|天亮')
CLOCK = re.compile(r'(?P<h>[零一二两三四五六七八九十\d]{1,3})点(?P<m>[零一二三四五六七八九十\d]{1,3})?分?')
MINUTE_TIME = re.compile(r'[零一二两三四五六七八九十\d]{1,3}点[零一二三四五六七八九十\d]{1,3}分')

PRONOUN_WINDOW_CHARS = 200
ORPHAN_TAIL_PCT = 75.0
SPAN_WINDOW_CHARS = 500

_CN = {'零': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10, '半': 0.5}


def _num_days(tok: str, unit: str):
    from fuben_numbers import numeric
    if tok == '半':
        value = 0.5
    else:
        value = numeric(tok, colloquial=True)
    if value is None:
        return None
    if '月' in unit:
        return value * 30
    if unit in ('星期', '礼拜', '周'):
        return value * 7
    return value


# ---------------------------------------------------------------------------
# 文本模型：内容单元（非空非标题行）+ 内容字符位置
# ---------------------------------------------------------------------------

def units_of(text: str):
    units, offset = [], 0
    for raw_no, raw in enumerate(text.splitlines(), 1):
        s = raw.strip()
        if not s or s.startswith('#'):
            continue
        units.append({'u': len(units) + 1, 'raw_no': raw_no, 'text': s, 'start': offset, 'end': offset + len(s)})
        offset += len(s)
    total = offset or 1
    for unit in units:
        unit['pct'] = round(unit['start'] * 100.0 / total, 1)
    return units, total


def _unit_text_window(units, idx, back_chars, min_units=3):
    """从 units[idx] 往回取窗口：至少 min_units 个单元，且不少于 back_chars 内容字符。"""
    lo = idx
    while lo > 0 and (units[idx]['start'] - units[lo - 1]['start'] < back_chars or idx - (lo - 1) < min_units):
        lo -= 1
    return units[lo:idx + 1]


def _quote(unit):
    return '「' + unit['text'][:36] + ('…' if len(unit['text']) > 36 else '') + '」'


# ---------------------------------------------------------------------------
# 检查 1：题眼锚（标题/口号核心词类 vs 主事件压力类）
# ---------------------------------------------------------------------------

def parse_anchor(setting: str):
    """读 设定.md 的 ## 题眼锚：核心词 / 同类词。"""
    out = {}
    sec = section(setting, '题眼锚') if setting else ''
    if not sec:
        return out
    for line in sec.splitlines():
        m = re.match(r'-?\s*\**核心词\**\s*[:：]\s*(.+)', line.strip())
        if m:
            out['core'] = m.group(1).strip().strip('`*')
        m = re.match(r'-?\s*\**同类词\**\s*[:：]\s*(.+)', line.strip())
        if m:
            out['sames'] = [w.strip() for w in re.split(r'[、/，,]', m.group(1)) if w.strip()]
    return out


def _class_of(word: str):
    for cls, words in THEME_CLASSES.items():
        if word in words or word == cls:
            return cls
    return None


def theme_anchor(setting: str, units):
    issues = []
    if not units:
        return issues
    # 标题区：开头框架（标题+口号+立志），累计 120 内容字符、上限 8 个单元
    title_units, cut = [], units[0]['start']
    for unit in units[:8]:
        title_units.append(unit)
        cut = unit['end']
        if cut - units[0]['start'] >= 120:
            break
    title_text = ' '.join(u['text'] for u in title_units)
    event_units = [u for u in units if u['start'] >= cut]
    event_text = ' '.join(u['text'] for u in event_units)
    if not event_text:
        return issues

    anchor = parse_anchor(setting)
    counts = {cls: sum(event_text.count(w) for w in words) for cls, words in THEME_CLASSES.items()}
    if anchor.get('core'):
        core = anchor['core']
        core_cls = _class_of(core)
        if core_cls is None:
            # 「吃起」落在「吃」类上：声明的核心词并入既有类，不另立山头
            for cls, words in THEME_CLASSES.items():
                if any(w and w in core for w in words):
                    core_cls = cls
                    break
        core_cls = core_cls or core
        class_words = set(THEME_CLASSES.get(core_cls, ()))
        declared_words = [core] + [w for w in anchor.get('sames', []) if w]
        extra = [w for w in declared_words if w not in class_words]
        counts[core_cls] = counts.get(core_cls, 0) + sum(event_text.count(w) for w in extra)
        core_hits = sum(title_text.count(w) for w in declared_words)
        core_event = counts.get(core_cls, 0)
    else:
        # 自动模式只判「口号型标题」（主义/时代/全网/浪潮/口号）：题眼错位病专属于
        # 这类把大词写进标题的稿子；普通题面题材词表覆盖不了，乱判全是误报。
        if not re.search(r'主义|口号|时代|浪潮|全网|热梗|都在传|都喊', title_text):
            return issues
        title_counts = {}
        title_unit_hits = {}
        for cls, words in THEME_CLASSES.items():
            title_counts[cls] = sum(title_text.count(w) for w in words)
            title_unit_hits[cls] = sum(1 for u in title_units if any(w in u['text'] for w in words))
        best = max(title_counts, key=lambda c: title_counts[c])
        # 自动探测要过门槛：核心词类在标题区 ≥3 处、跨 ≥2 个单元（口号复读才算题眼）。
        if title_counts[best] < 3 or title_unit_hits[best] < 2:
            return issues
        core_cls, core_event, core_hits = best, counts[best], title_counts[best]
        core_words = list(THEME_CLASSES[core_cls])
    rivals = {c: n for c, n in counts.items() if n >= core_event * 1.5 and n > core_event}
    if rivals:
        top = max(rivals, key=rivals.get)
        issues.append(('S2', 'THEME_ANCHOR_MISMATCH',
                       f'L{title_units[0]["raw_no"]} 标题「{title_units[0]["text"][:24]}」题眼类=「{core_cls}」'
                       f'（标题区命中 {core_hits} 处），但正文事件区最大压力类是「{top}」（{rivals[top]} 处，'
                       f'「{core_cls}」类仅 {core_event} 处）。标题说世界疯「{core_cls}」，事件演的是「{top}」——'
                       f'题眼错位：要么标题跟着事件改，要么三场事件按题眼重写；返工阶段禁止单换核心词。'))
    return issues


# ---------------------------------------------------------------------------
# 检查 2：器物/食物状态漂移（位置三变、无动作衔接）
# ---------------------------------------------------------------------------

def _ledger_entities(setting: str):
    rows = []
    sec = section(setting, '实体台账') if setting else ''
    for line in sec.splitlines():
        line = line.strip()
        if not line.startswith('|') or re.match(r'^\|[\s:\-|]+$', line):
            continue
        cells = [c.strip() for c in line.strip('|').split('|')]
        if len(cells) < 3 or cells[0] in ('类型', '---'):
            continue
        rows.append({'type': cells[0], 'name': cells[1].strip('*'), 'alias': cells[2].strip('*') if len(cells) > 2 else ''})
    return rows


def _mentions(units, word, alias=''):
    names = [w for w in (word, alias) if w]
    out = []
    for idx, unit in enumerate(units):
        hit = [n for n in names if n in unit['text']]
        if hit:
            name = max(hit, key=len)
            pos = unit['text'].find(name)
            out.append((idx, unit, pos, name))
        else:
            # 代词回指：上一单元刚提过该实体，本单元以「它/这/那」开头并带位置词
            if idx > 0 and unit['text'][:1] in ('它',) and any(c in unit['text'] for c in CONTAINERS):
                if any(n in units[idx - 1]['text'] for n in names):
                    out.append((idx, unit, 0, word))
    return out


def _container_positions(unit):
    """(pos, container)，排除被搬运动作消费掉的位置（「架进你碗里」的碗属于那次搬运的对象）。"""
    text = unit['text']
    out = []
    for c in CONTAINERS:
        p = text.find(c)
        while p != -1:
            if not any(m.start() <= p < m.end() for m in RELOCATE.finditer(text)):
                out.append((p, c))
            p = text.find(c, p + 1)
    return out


def _primary_container(unit, pos):
    best, best_dist = None, 15  # 距离上限：隔着别的分句的容器不算这个实体的位置
    for p, c in _container_positions(unit):
        dist = abs(p - pos)
        if dist < best_dist:
            best, best_dist = c, dist
    return best


def entity_state_drift(setting: str, units):
    issues = []
    ledger_rows = _ledger_entities(setting)
    person_names = {r['name'] for r in ledger_rows if r['type'] in ('人物', '角色', '配角') and r['name']}
    candidates = {w for w in FOOD_WORDS if sum(u['text'].count(w) for u in units) >= 2}
    for row in ledger_rows:
        if row['type'] in ('器物', '食物', '道具') and row['name']:
            if sum(u['text'].count(row['name']) for u in units) >= 2:
                candidates.add(row['name'])
    for word in sorted(candidates, key=len, reverse=True):
        if any(other != word and other.find(word) != -1 for other in candidates):
            continue  # 「蟹柳棒」在场时跳过短词「蟹柳」的独立对账
        if any(p != word and word in p for p in person_names):
            continue  # 「毛肚」是「毛肚哥」的一部分时，不算独立食物实体
        mentions = _mentions(units, word)
        for (i1, u1, p1, _), (i2, u2, p2, _) in zip(mentions, mentions[1:]):
            c1 = _primary_container(u1, p1)
            c2 = _primary_container(u2, p2)
            if not c1 or not c2 or c1 == c2:
                continue
            if i2 == i1 + 1:
                bridge = ''
            else:
                bridge = ' '.join(u['text'] for u in units[i1 + 1:i2])
            if RELOCATE.search(u1['text'][p1:]) or RELOCATE.search(u2['text'][:p2 + 8]) or (bridge and RELOCATE.search(bridge)):
                continue  # 有搬运动作衔接，位置变化合法
            issues.append(('S2', 'ENTITY_STATE_DRIFT',
                           f'L{u1["raw_no"]} {(_quote(u1))} → L{u2["raw_no"]} {(_quote(u2))}：「{word}」先在{c1}、'
                           f'后在{c2}，两句之间没有搬运动作衔接。换场景只改店名菜名、器物位置没跟着改的典型残留。'))
    return issues


# ---------------------------------------------------------------------------
# 检查 3：孤词（食物只出现一次且落在尾部 + 吃/点上下文 → 旧版残留）
# ---------------------------------------------------------------------------

_CONSUME = re.compile(r'(吃|喝|点|夹|涮|啃|嗦|尝|来|加)[口一了点些个杯勺小大]?[口一了点些个杯勺小大]?$')


def orphan_nouns(setting: str, units, total):
    issues = []
    declared = {r['name'] for r in _ledger_entities(setting)}
    body_text = '\n'.join(u['text'] for u in units)
    for word in sorted(FOOD_WORDS | {r['name'] for r in _ledger_entities(setting) if r['type'] == '食物'}, key=len, reverse=True):
        if word in declared:
            continue  # 作者已进台账背书
        count = body_text.count(word)
        if count != 1 or any(other != word and other.find(word) != -1 for other in FOOD_WORDS if body_text.count(other) > 1):
            continue
        for unit in units:
            pos = unit['text'].find(word)
            if pos == -1:
                continue
            if unit['pct'] < ORPHAN_TAIL_PCT:
                continue
            before = unit['text'][:pos]
            # 复用事实锁的否定句处理：「没点鱼/不吃鱼」不算吃上下文
            if not _has_positive(unit['text'], r'(吃|喝|点|夹|涮|啃|嗦|尝)'):
                continue
            if not _CONSUME.search(before[-8:]):
                continue  # 没有吃/点/夹上下文，可能是正常新道具
            issues.append(('S2', 'ORPHAN_NOUN',
                           f'L{unit["raw_no"]} {_quote(unit)}：「{word}」全篇只出现这一次，且落在后段'
                           f'（{unit["pct"]}%）、带吃/点上下文——孤词：前文无铺垫后文无回收，多为旧版换场景残留。删，或改成已建立的同类物件。'))
    return issues


# ---------------------------------------------------------------------------
# 检查 4：时间跨度冲突（同一「不在场」窗口两种时长）
# ---------------------------------------------------------------------------

def span_conflicts(units):
    issues = []
    marks = []
    for idx, unit in enumerate(units):
        for m in DURATION.finditer(unit['text']):
            value = _num_days(m.group('n'), m.group('u'))
            if value is None or value <= 0:
                continue
            context = ' '.join(u['text'] for u in units[max(0, idx - 1):idx + 2])
            if not ABSENCE_MARKS.search(unit['text']) and not ABSENCE_MARKS.search(context):
                continue
            marks.append((unit['start'], value, unit, m.group(0)))
    marks.sort(key=lambda x: x[0])
    for i in range(len(marks)):
        for j in range(i + 1, len(marks)):
            s1, v1, u1, raw1 = marks[i]
            s2, v2, u2, raw2 = marks[j]
            if s2 - s1 > SPAN_WINDOW_CHARS:
                break
            if abs(v1 - v2) < 1e-9 or (max(v1, v2) / min(v1, v2) < 1.5 and abs(v1 - v2) < 7):
                continue
            issues.append(('S2', 'SPAN_CONFLICT',
                           f'L{u1["raw_no"]} {_quote(u1)}（{raw1}） vs L{u2["raw_no"]} {_quote(u2)}（{raw2}）：'
                           f'同一段「不露面/失联」的时长前后不一（{v1:g}天 vs {v2:g}天）。缩时长只改一处闹钟，另一处就会残留。统一口径后全篇复查。'))
            break
    return issues


# ---------------------------------------------------------------------------
# 检查 5：进场/散场环境状态无变化（夜进夜散）
# ---------------------------------------------------------------------------

def _clock_hour(tok: str, night_ctx: bool):
    from fuben_numbers import numeric
    if tok == '半':
        return 0.5
    v = numeric(tok, colloquial=True)
    if v is None:
        return None
    v = int(v)
    if v <= 12 and night_ctx:
        v += 12
    return v


def scene_state_null(units):
    issues = []
    night_part = False
    last_cue_unit = None
    for idx, unit in enumerate(units):
        text = unit['text']
        part = DAY_PART.search(text)
        if part:
            night_part = part.group(0) in ('晚上', '夜里', '半夜', '深夜', '凌晨', '入夜', '天黑')
            last_cue_unit = idx
        for cm in CLOCK.finditer(text):
            hour = _clock_hour(cm.group('h'), night_part)
            if hour is not None:
                if 19 <= hour or hour <= 5:
                    night_part = True
                elif 7 <= hour <= 18:
                    night_part = False
                last_cue_unit = idx
        if EXIT_SCENE.search(text) and LIGHT_STATE.search(text):
            light = LIGHT_STATE.search(text).group(0)
            exit_dark = ('黑' in light) or ('亮' not in light and light not in ('蒙蒙亮', '泛白', '鱼肚白'))
            entry_dark = None
            for back in range(idx - 1, max(-1, idx - 20), -1):
                if last_cue_unit is not None and back < last_cue_unit:
                    break
                p = DAY_PART.search(units[back]['text'])
                if p:
                    entry_dark = p.group(0) in ('晚上', '夜里', '半夜', '深夜', '凌晨', '入夜', '天黑')
                    break
                cm = CLOCK.search(units[back]['text'])
                if cm:
                    hour = _clock_hour(cm.group('h'), night_part)
                    if hour is not None:
                        entry_dark = 19 <= hour or hour <= 5
                        break
            if entry_dark is not None and exit_dark == entry_dark:
                issues.append(('S3', 'SCENE_STATE_NULL',
                               f'L{unit["raw_no"]} {_quote(unit)}：进场时已是{"夜" if entry_dark else "白天"}，'
                               f'散场又写{"全黑" if exit_dark else "全亮"}——环境状态没变化，这句描述没有信息量。'
                               f'要么写出变化（夜进亮散），要么删掉状态句。'))
    return issues


# ---------------------------------------------------------------------------
# 检查 6：代词无头（他/她 回溯窗口内无具名先行词）
# ---------------------------------------------------------------------------

def _person_refs(text: str):
    found = []
    for role in PERSON_ROLES:
        for m in re.finditer(re.escape(role), text):
            found.append((m.start(), role))
    for m in PERSON_NAME_SUFFIX.finditer(text):
        found.append((m.start(), m.group(0)))
    for m in PERSON_DEMONSTRATIVE.finditer(text):
        found.append((m.start(), m.group(0)))
    return found


PRONOUN_THREAD_MIN = 6  # 同一代词全篇 ≥6 次 = 贯穿主角线（女友/妻子全程在场），不算无头


def pronoun_unresolved(units):
    issues = []
    seen_spans = set()
    last_pos = {}  # 同代词链：上一个同代词的位置（内容字符）
    full_text = '\n'.join(u['text'] for u in units)
    thread = {p: len(re.findall(r'(?<![一-龥a-zA-Z0-9])' + p + r'(?![们姐哥弟妹叔姨婶])', full_text))
              for p in ('他', '她')}
    for idx, unit in enumerate(units):
        for m in PRONOUN.finditer(unit['text']):
            key = (unit['raw_no'], m.start())
            if key in seen_spans:
                continue
            seen_spans.add(key)
            pos = unit['start'] + m.start()
            pron = m.group('p')
            prev = last_pos.get(pron)
            last_pos[pron] = pos
            if thread.get(pron, 0) >= PRONOUN_THREAD_MIN:
                continue  # 贯穿主角线：全篇高频同代词，人物由通篇建立
            window = _unit_text_window(units, idx, PRONOUN_WINDOW_CHARS)
            wtext = ' '.join(u['text'] for u in window)
            if _person_refs(wtext):
                continue  # 窗口内有具名/这那人先行词
            if prev is not None and pos - prev <= 400:
                continue  # 链式续指：同一人物一直在场（400 内容字符内同代词再现）
            indefinite = INDEFINITE_PERSON.search(wtext)
            hint = f'（窗口内只有「{indefinite.group(0)}」这类不定人称）' if indefinite else '（窗口内没有任何人物先行词）'
            issues.append(('S2', 'PRONOUN_UNRESOLVED',
                           f'L{unit["raw_no"]} {_quote(unit)}：「{pron}」回溯约{PRONOUN_WINDOW_CHARS}字'
                           f'无唯一具名先行词、且与上一个「{pron}」隔了整场戏{hint}。拼接残留典型症状：前文靠「一只手/有人」带过，'
                           f'后文突然用代词。给关键配角一个稳定称呼（姓名或功能标签，如「毛肚哥」），再谈代词。'))
    return issues


# ---------------------------------------------------------------------------
# 检查 7：第N件事的施力者与开头立论不一致
# ---------------------------------------------------------------------------

def sequence_source(units, total):
    issues = []
    head_units = units[:max(3, len(units) // 4)]
    head = ' '.join(u['text'] for u in head_units)
    actor = None
    for tm in THESIS.finditer(head):
        before = head[:tm.start()]
        if re.search(r'以为|觉得|认为|猜想$', before[-4:]):
            continue  # 「你以为最难的是举铁」是待否定的错觉，不是立论
        actor = tm.group('actor')  # 取最后一个：修正后的口径才是立论
    if not actor:
        return issues
    friend_tokens = set(FRIEND_CLASS) | {actor}
    thesis_unit = next((u for u in units if actor in u['text']), units[0])
    for idx, unit in enumerate(units):
        em = ENUM_EVENT.search(unit['text'])
        if not em:
            continue
        span = []
        for u2 in units[idx:]:
            if u2 is not unit and (ENUM_EVENT.search(u2['text']) or re.match(r'^(接下来|后来|第[一二三四]个|几[天周个]月?后|半年后|转眼)', u2['text'])):
                break
            span.append(u2)
            if len(span) >= 14:
                break
        span_text = ' '.join(u['text'] for u in span)
        has_friend = any(t in span_text for t in friend_tokens)
        # 复用否定句处理：「不是博主说的，是毛肚哥」里的博主不算施力者
        rivals_hit = [t for t in RIVAL_CLASS if _has_positive(span_text, re.escape(t))]
        if rivals_hit and not has_friend:
            issues.append(('S2', 'SEQUENCE_SOURCE_MISMATCH',
                           f'L{thesis_unit["raw_no"]} {_quote(thesis_unit)} 立论压力源是「{actor}」，'
                           f'但 L{unit["raw_no"]} {_quote(unit)} 这一件的施力者是「{"、".join(rivals_hit[:3])}」——'
                           f'序列断裂：要么把这一件改回朋友作梗，要么开头立论改口径。'))
    return issues


# ---------------------------------------------------------------------------
# 检查 8：无回收的精确细节（精确到分的时间只出现一次）
# ---------------------------------------------------------------------------

def unrecovered_details(units):
    issues = []
    body_text = '\n'.join(u['text'] for u in units)
    reported = set()
    for unit in units:
        for m in MINUTE_TIME.finditer(unit['text']):
            tok = m.group(0)
            if tok in reported:
                continue
            reported.add(tok)
            if unit['text'].startswith(tok):
                continue  # 行首时间戳是消息记录质感，不算无回收细节
            if body_text.count(tok) == 1:
                issues.append(('S3', 'UNRECOVERED_DETAIL',
                               f'L{unit["raw_no"]} {_quote(unit)}：「{tok}」精确到分，但全篇只出现一次、后文无回收。'
                               f'精确细节要为后文服务；用不上就删或模糊成「周五晚上」。'))
    return issues


# ---------------------------------------------------------------------------
# 台账对账：表里的数必须和脚本实测一致（表 → 脚本实测 → 回填）
# ---------------------------------------------------------------------------

def _measure(units, word, alias='', longer_names=()):
    """实测次数与首/末现%；更长具名实体的出现不算进来（毛肚哥里的毛肚不是食物毛肚）。

    别名与本名互为子串时只数子串方：alias=本体（请帖/请帖）或 alias 含本体
    （大姐⊂东北大姐）时，数子串已全覆盖，包含方再数一遍就是重复计数。
    """
    names = list(dict.fromkeys(n for n in (word, alias) if n and n != '—'))
    names = [n for n in names if not any(m in n and m != n for m in names)]
    first = last = None
    count = 0
    for unit in units:
        text = unit['text']
        for long in longer_names:
            if long and len(long) > min(len(n) for n in names or [long]):
                text = text.replace(long, '\u2581' * len(long))
        c = sum(text.count(n) for n in names)
        if c:
            count += c
            if first is None:
                first = unit['pct']
            last = unit['pct']
    return count, first, last


def ledger_issues(setting: str, units):
    issues = []
    if not setting:
        return issues
    sec = section(setting, '实体台账')
    if not sec:
        return issues
    for line in sec.splitlines():
        line = line.strip()
        if not line.startswith('|') or re.match(r'^\|[\s:\-|]+$', line):
            continue
        cells = [c.strip().strip('*') for c in line.strip('|').split('|')]
        if len(cells) < 7 or cells[0] in ('类型', '---', ''):
            continue
        name, alias = cells[1], cells[2] if cells[2] not in ('—', '') else ''
        try:
            claimed_first = float(re.sub(r'[^\d.]', '', cells[3]) or 'nan')
            claimed_last = float(re.sub(r'[^\d.]', '', cells[4]) or 'nan')
            claimed_count = int(re.sub(r'[^\d]', '', cells[5]) or '0')
        except ValueError:
            continue
        declared_names = [r['name'] for r in _ledger_entities(setting) if r['name'] and r['name'] != name]
        count, first, last = _measure(units, name, alias, longer_names=declared_names)
        bad = []
        if count != claimed_count:
            bad.append(f'次数主张 {claimed_count}、实测 {count}')
        if first is not None and (abs(first - claimed_first) > 3 or abs(last - claimed_last) > 3):
            bad.append(f'首现/末现主张 {claimed_first:g}%–{claimed_last:g}%、实测 {first:g}%–{last:g}%')
        if bad:
            issues.append(('S2', 'ENTITY_LEDGER_STALE',
                           f'实体台账「{name}」与正文对不上：{"；".join(bad)}。'
                           f'台账必须脚本实测回填：python3 scripts/fuben_entity.py 作品/NN_主题/ --ledger'))
    return issues


def measured_table(setting: str, body: str) -> str:
    units, _total = units_of(body)
    rows = ['| 类型 | 实体 | 稳定称呼 | 首现% | 末现% | 次数 | 状态轨迹 | 判定 |',
            '|---|---|---|---|---|---|---|---|']
    seen = set()
    declared = _ledger_entities(setting)
    declared_names = [r['name'] for r in declared if r['name']]
    picks = list(declared_names)
    counts = {w: sum(u['text'].count(w) for u in units) for w in FOOD_WORDS}
    picks += [w for w, c in sorted(counts.items(), key=lambda kv: -kv[1]) if c >= 2 and w not in picks][:6]
    # 子串去重：蟹 ⊂ 蟹柳、毛肚 ⊂ 毛肚哥，只留更长的具名实体
    picks = [p for p in picks if not any(p != q and p in q for q in picks)]
    for name in picks:
        alias = next((r['alias'] for r in declared if r['name'] == name), '')
        longer = [n for n in declared_names if n != name and len(n) > len(name)]
        count, first, last = _measure(units, name, alias, longer_names=longer)
        if count == 0 or name in seen:
            continue
        seen.add(name)
        kind = next((r['type'] for r in declared if r['name'] == name), '食物' if name in FOOD_WORDS else '器物')
        rows.append(f'| {kind} | {name} | {alias or "—"} | {first if first is not None else 0} | '
                    f'{last if last is not None else 0} | {count} | （手工：位置怎么变、谁搬的） | （手工：可解释/孤词/漂移） |')
    rows.append('')
    rows.append('> 首现%/末现%/次数为脚本实测（python3 scripts/fuben_entity.py --ledger）；状态轨迹与判定手工填，'
                '返工换场景后必须重跑回填，禁止目测。')
    return '\n'.join(rows) + '\n'


# ---------------------------------------------------------------------------
# 汇总
# ---------------------------------------------------------------------------

def check_text(setting: str, body: str):
    """返回 [(S级, code, message)]；S1=拦交付 S2=交付前必修 S3=留观（信息级，供审稿参考）。"""
    units, total = units_of(body)
    if not units:
        return []
    issues = []
    issues += theme_anchor(setting, units)
    issues += entity_state_drift(setting, units)
    issues += orphan_nouns(setting, units, total)
    issues += span_conflicts(units)
    issues += scene_state_null(units)
    issues += pronoun_unresolved(units)
    issues += sequence_source(units, total)
    issues += unrecovered_details(units)
    issues += ledger_issues(setting, units)
    return issues


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', help='作品目录，或任意正文文件')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--ledger', action='store_true', help='输出脚本实测的实体台账，粘贴回 设定.md')
    args = parser.parse_args(argv)
    from fuben_engine import inspect_path, emit
    source = Path(args.path).resolve()
    if args.ledger:
        body_path = source / '正文.md' if source.is_dir() else source
        setting_path = body_path.parent / '设定.md'
        body = body_path.read_text(encoding='utf-8-sig')
        setting = setting_path.read_text(encoding='utf-8-sig') if setting_path.is_file() else ''
        print(measured_table(setting, body))
        return 0
    report = inspect_path(source, run_style=False, components={'entity'})
    return emit(report, json_output=args.json, label='CONTINUITY')


if __name__ == '__main__':
    raise SystemExit(main())
