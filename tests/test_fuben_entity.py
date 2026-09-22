"""fuben_entity 连续性锁单测：红样必中、绿样必过、全库噪音校准过的边界。

跑法：python3 tests/test_fuben_entity.py（或 python3 -m pytest tests/test_fuben_entity.py -q）
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))

from fuben_entity import (  # noqa: E402
    check_text, measured_table, _measure, parse_anchor, units_of,
)
from fuben_setting_years import spoken_char_claims  # noqa: E402  D1 在事实锁层

ROOT = Path(__file__).resolve().parent.parent
RED = ROOT / '作品/_regression/80a_大耍起时代_红样/正文.md'
GREEN = ROOT / '作品/_regression/80b_大吃起时代_绿样'

LEDGER_HEAD = ('| 类型 | 实体 | 稳定称呼 | 首现% | 末现% | 次数 | 状态轨迹 | 判定 |\n'
               '|---|---|---|---|---|---|---|---|\n')


def codes(text, setting=''):
    return {c for s, c, m in check_text(setting, text)}


class TestRedSample(unittest.TestCase):
    """红样（交接文档附录原文）：连续性 8 类 code 必须打出，S2 ≥5。"""

    @classmethod
    def setUpClass(cls):
        cls.findings = check_text('', RED.read_text(encoding='utf-8-sig'))
        cls.codes = {c for s, c, m in cls.findings}

    def test_red_s2_cluster(self):
        for c in ('THEME_ANCHOR_MISMATCH', 'ENTITY_STATE_DRIFT', 'ORPHAN_NOUN',
                  'SPAN_CONFLICT', 'SEQUENCE_SOURCE_MISMATCH', 'PRONOUN_UNRESOLVED'):
            self.assertIn(c, self.codes, f'红样缺 {c}')

    def test_red_notes(self):
        for c in ('SCENE_STATE_NULL', 'UNRECOVERED_DETAIL'):
            self.assertIn(c, self.codes)

    def test_red_overall_s2_count(self):
        self.assertGreaterEqual(len([1 for s, c, m in self.findings if s == 'S2']), 5)

    def test_red_spoken_char_s1(self):
        """D1（fuben_setting_years）：红样「人生就两字」2vs4 必须 certain 命中。"""
        claims = spoken_char_claims(RED.read_text(encoding='utf-8-sig'))
        hit = [c for c in claims if c[1] != c[2]]
        self.assertTrue(hit, '红样字数主张未命中')
        self.assertTrue(all(c[5] for c in hit), '红样命中项必须 certain（S1/BLOCK）')


class TestGreenSample(unittest.TestCase):
    """绿样（最小修法+题眼锚+台账回填）：连续性锁必须零 finding。"""

    def test_green_zero_findings(self):
        body = (GREEN / '正文.md').read_text(encoding='utf-8-sig')
        setting = (GREEN / '设定.md').read_text(encoding='utf-8-sig')
        self.assertEqual(check_text(setting, body), [])

    def test_green_spoken_clean(self):
        body = (GREEN / '正文.md').read_text(encoding='utf-8-sig')
        self.assertEqual([c for c in spoken_char_claims(body) if c[1] != c[2]], [])


class TestD1SpokenCharClaims(unittest.TestCase):
    """D1 用例基线：声明一个数、实测一个数、只审主张后紧跟内容的形态。"""

    def test_mismatch(self):
        claims = spoken_char_claims('认真回了九个字\n人生就两字\n练完再耍\n')
        self.assertTrue(any(c[1] != c[2] and c[5] for c in claims))

    def test_copula_passes(self):
        self.assertEqual(spoken_char_claims('他说人生就两字\n就是吃起\n'), [])

    def test_plain_claim_passes(self):
        self.assertEqual(spoken_char_claims('你写了三个字\n你留着\n'), [])

    def test_remark_prefix(self):
        claims = spoken_char_claims('转账备注四个字\n别谢了\n')
        self.assertTrue(any(c[1] != c[2] for c in claims))


class TestMeasureSubstrDedup(unittest.TestCase):
    """79 号实测触发的 bug：别名与本名互为子串时重复计数。

    反例（修复前）：alias=本体 → 次数×2；alias 含本体（大姐⊂东北大姐）→ 大姐 5+2=7。
    """

    def test_alias_same_as_name_counts_once(self):
        units, _ = units_of('请帖还立在显示器边上\n')
        self.assertEqual(_measure(units, '请帖', '请帖')[0], 1)

    def test_alias_containing_name_no_double(self):
        units, _ = units_of('东北大姐来了\n大姐刷了一排烟花\n')
        self.assertEqual(_measure(units, '大姐', '东北大姐')[0], 2)

    def test_distinct_alias_still_sums(self):
        units, _ = units_of('赵成举杯\n老刀笑了\n')
        self.assertEqual(_measure(units, '老刀', '赵成')[0], 2)


class TestAnchorDeclaration(unittest.TestCase):
    """题眼锚声明：核心词+同类词并类；声明锚全灵敏。"""

    def test_parse_anchor(self):
        a = parse_anchor('## 题眼锚\n\n- 核心词：命\n- 同类词：散、灰、走、退\n')
        self.assertEqual(a.get('core'), '命')
        self.assertEqual(a.get('sames'), ['散', '灰', '走', '退'])

    def test_declared_anchor_no_rival(self):
        setting = '## 题眼锚\n- 核心词：命\n- 同类词：散、灰、走、退\n'
        body = '他把游戏当命\n人走了 房还挂着\n他没散伙\n你也没退\n'
        self.assertNotIn('THEME_ANCHOR_MISMATCH', codes(body, setting))


class TestLedgerRoundTrip(unittest.TestCase):
    """台账对账：--ledger 实测输出回填后 ledger_issues 必须清零；错数必须报 STALE。"""

    def test_ledger_stale_detected(self):
        setting = ('## 实体台账\n\n' + LEDGER_HEAD +
                   '| 器物 | 蟹柳 | — | 10 | 90 | 9 | 一直锅里 | 稳 |\n')
        body = '锅里的蟹柳翻了个身\n他又夹了一筷子蟹柳\n'
        self.assertIn('ENTITY_LEDGER_STALE', codes(body, setting))

    def test_measured_table_round_trip(self):
        body = '锅里的蟹柳翻了个身\n他又夹了一筷子蟹柳\n'
        table = measured_table('', body)
        lines = [l for l in table.splitlines() if l.startswith('|')]
        data = [l for l in lines if not re_is_sep(l)][0] if lines else ''
        row = [c.strip() for c in data.strip('|').split('|')]
        name, first, last, count = row[1], row[3], row[4], row[5]
        setting = ('## 实体台账\n\n' + LEDGER_HEAD +
                   f'| 器物 | {name} | — | {first} | {last} | {count} | 一直锅里 | 稳 |\n')
        self.assertNotIn('ENTITY_LEDGER_STALE', codes(body, setting))


def re_is_sep(line):
    return line.strip('|').strip().replace(':', '').replace('-', '').strip() == ''


if __name__ == '__main__':
    unittest.main(verbosity=2)
