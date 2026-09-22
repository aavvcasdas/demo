"""Software invariants, counterexamples, and failure injection; no model calls.

Temporary fixtures are not corpus originals. A passing suite is not editorial QA.
"""
import copy
from decimal import Decimal
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from fuben_engine import inspect_path, literal_checks, sha256, style_diagnostics
from fuben_numbers import number, numeric
from fuben_hype import _cn_value
import fuben_data as data
import fuben_release as release
from fuben_scene_check import inspect_scenes
from fuben_loop import review


def run(*args, cwd=ROOT, **kwargs):
    return subprocess.run([str(a) for a in args], cwd=cwd, text=True, capture_output=True, timeout=40, **kwargs)


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='fuben_tests_')
        self.dir = Path(self.tmp.name)
        self.body = self.dir / '正文.md'
        self.body.write_text('今天体验的人生副本是：普通的一天\n你把饭端上桌。\n妈妈接过碗，没有说话。\n', encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def inspect(self, text=None, **kwargs):
        if text is not None:
            self.body.write_text(text, encoding='utf-8')
        return inspect_path(self.body, run_style=False, **kwargs)


class NumberTests(unittest.TestCase):
    def test_formal_numbers(self):
        examples = {'二百': 200, '二百五十': 250, '三百六十': 360, '一千二百': 1200,
                    '一万': 10000, '两万': 20000, '一千零二': 1002, '一万零一': 10001,
                    '一亿二千万': 120000000, '一万亿': 10**12, '二零二六': 2026,
                    '〇一八八': 188, '零': 0, '十': 10, '十二': 12, '一千一百七十六': 1176,
                    '四千三百二十万': 43200000, '１２００': 1200, '1,200': 1200,
                    '2.5万': 25000, '三点六': Decimal('3.6'), '负二百': -200}
        for text, expected in examples.items():
            with self.subTest(text=text):
                self.assertEqual(number(text), expected)
                self.assertEqual(Decimal(str(_cn_value(text))), expected)

    def test_ambiguous_colloquial_requires_opt_in(self):
        for text, expected in [('二百五', 250), ('一千二', 1200), ('七万二', 72000)]:
            with self.subTest(text=text):
                self.assertIsNone(numeric(text, colloquial=False))
                self.assertEqual(numeric(text, colloquial=True), expected)

    def test_malformed_number_never_guesses_first_digit(self):
        for text in ('', '很多', '一百二百', '万', '十十', '1,20', 'Infinity', 'NaN'):
            with self.subTest(text=text):
                self.assertIsNone(numeric(text))


class EngineTests(Fixture):
    def test_no_novel_or_sensory_quotas(self):
        text = '今天体验的人生副本是：一直赢的普通人\n' + '你又猜对了。\n' * 100
        report = self.inspect(text)
        self.assertTrue(report['mechanical_pass'])
        self.assertFalse(any(f['severity'] == 'BLOCK' and f['category'] == 'style' for f in report['findings']))
        self.assertFalse(report['editorially_approved'])
        self.assertFalse(report['release_ready'])

    def test_empty_heading_binary_and_missing_inputs(self):
        for text in ('', '   ', '# 只有标题\n'):
            self.assertEqual(self.inspect(text)['exit_code'], 1)
        self.assertEqual(self.inspect('正文\x00损坏')['exit_code'], 2)
        self.assertEqual(inspect_path(self.dir / '不存在.md')['exit_code'], 2)
        self.body.write_bytes(b'\xff\xfe')
        self.assertEqual(inspect_path(self.body)['exit_code'], 2)

    def test_bad_profile_marker_is_error(self):
        for marker in ('{', '[]', '{"schema_version":2,"profile":"fuben"}', '{"schema_version":true,"profile":"fuben"}'):
            (self.dir / '.fuben.json').write_text(marker)
            self.assertEqual(self.inspect()['status'], 'ERROR')

    def test_explicit_arithmetic_green_red(self):
        for text in ('账目 2000×36=72000', '800+1200+23000=25000', '2+3×4=14', '10/13 = 77%', '1÷3=0.33', '三百六十+二百五十=六百一十'):
            with self.subTest(text=text):
                self.assertFalse(any(f['severity'] == 'BLOCK' for f in literal_checks(text, self.body, 'draft')))
        for text in ('账目 2000×36=7200', '账上，2000×36=7200，还有别的。', '800+1200+23000=24000', '2+3×4=20', '10/13=20%', '三百六十+二百五十=五百'):
            with self.subTest(text=text):
                self.assertTrue(any(f['severity'] == 'BLOCK' for f in literal_checks(text, self.body, 'draft')))

    def test_character_error_not_forced_into_authorial_truth(self):
        for text in ('他故意写错了：2+2=5。', '她说：“2+2=5”。', '他错写了五个字「欢迎回家」'):
            report = self.inspect(text)
            self.assertEqual(report['status'], 'PASS_WITH_REVIEW')
            self.assertFalse(report['editorially_approved'])

    def test_division_zero_is_review_not_crash(self):
        self.assertEqual(self.inspect('0/0=1')['findings'][0]['severity'], 'REVIEW')

    def test_quoted_counts_including_adjacent_quotes(self):
        self.assertEqual(self.inspect('你写了五个字「欢迎回家」')['status'], 'FAIL')
        self.assertEqual(self.inspect('你写了四个字「欢迎回家」')['status'], 'PASS')
        self.assertEqual(self.inspect('「忙」「干」两字应付')['status'], 'PASS')
        self.assertEqual(self.inspect('「自家人」两个字')['status'], 'FAIL')
        self.assertFalse(any(f['severity'] == 'BLOCK' for f in self.inspect('「AI」两个字')['findings']))

    def test_literal_count_horizontal_spacing_is_not_a_bypass(self):
        for text in ('最后一行5 个字「我信一次」', '「我信一次」5 个字',
                     '最后一行5\t个\t汉字「我信一次」'):
            with self.subTest(text=text):
                self.assertEqual(self.inspect(text)['status'], 'FAIL')
        for text in ('最后一行4 个字「我信一次」', '「我信一次」4 个字',
                     '「忙」「干」2 个字'):
            with self.subTest(text=text):
                self.assertEqual(self.inspect(text)['status'], 'PASS')
        for text in ('第5个字「我」', '第 5 个字「我」', '第五个字「我」'):
            self.assertFalse(any(f['severity'] == 'BLOCK' for f in literal_checks(text, self.body, 'draft')))
        # A layout/ASR gap cannot be silently joined into a certain assertion.
        self.assertFalse(any(f['severity'] == 'BLOCK' for f in
                             literal_checks('5\n个字「我信一次」', self.body, 'draft')))

    def test_real_author_count_fixes_keep_red_and_green_controls(self):
        examples = [('别谢了', 4, 3), ('不是一路人', 4, 5), ('今天没回消息', 7, 6),
                    ('我信一次', 5, 4), ('自家人', 2, 3), ('弃', 2, 1),
                    ('替她谢谢你', 6, 5), ('你自己', 2, 3),
                    ('现在我就是世一中', 7, 8), ('脸疼吗', 4, 3)]
        for quote, wrong, right in examples:
            with self.subTest(quote=quote):
                self.assertEqual(len(quote), right)
                bad = literal_checks(f'{wrong}个字「{quote}」', self.body, 'draft')
                good = literal_checks(f'{right}个字「{quote}」', self.body, 'draft')
                self.assertTrue(any(f['severity'] == 'BLOCK' for f in bad))
                self.assertFalse(any(f['severity'] == 'BLOCK' for f in good))

    def test_asr_uncertainty_does_not_mean_fact_verified(self):
        report = self.inspect('你打了两个字\n你自己', profile='reference')
        self.assertEqual(report['status'], 'PASS_WITH_REVIEW')
        self.assertIn('external factual truth', report['unverified'])

    def test_flashback_and_different_objects_not_hard_errors(self):
        (self.dir / '设定.md').write_text('## 事实锁\n她搬来七年。\n')
        report = self.inspect('2026年你回家。\n2019年她来过这里。\n你的猫八年没换过窝。')
        self.assertTrue(report['mechanical_pass'])
        self.assertTrue(any(f['rule_id'] == 'YEAR_BACKTRACK' and f['severity'] == 'REVIEW' for f in report['findings']))

    def test_explicit_daily_date_count_still_blocks(self):
        (self.dir / '设定.md').write_text('## 事实锁\n每天一张\n起始日期：2026-01-01\n第4张：2026-01-02\n')
        self.assertTrue(any(f['rule_id'] == 'DATE_COUNT_MISMATCH' and f['severity'] == 'BLOCK' for f in self.inspect()['findings']))
        # Without a daily-frequency promise, arithmetic must not assume one.
        (self.dir / '设定.md').write_text('## 事实锁\n起始日期：2026-01-01\n第4张：2026-01-02\n')
        self.assertFalse(any(f['rule_id'] == 'DATE_COUNT_MISMATCH' for f in self.inspect()['findings']))

    def test_style_whitelist_never_exempts_math(self):
        self.body.write_text('你写了五个字「欢迎回家」。')
        (self.dir / '.deslop-whitelist').write_text(self.body.read_text())
        self.assertEqual(inspect_path(self.body)['exit_code'], 1)

    def test_review_is_not_self_approval_or_vacuous_callbacks(self):
        report = review(self.dir)
        self.assertEqual(report['review_status'], 'PROVISIONAL')
        self.assertFalse(report['editorially_approved'])
        self.assertNotIn('0/0', json.dumps(report))

    def test_missing_node_checker_crash_bad_json_and_exit_mismatch(self):
        fixtures = ["require('not-installed-for-fuben-test');",
                    "console.log('PASS')", "console.log(JSON.stringify({findings:[]}));process.exit(1)",
                    "console.log(JSON.stringify({findings:[{severity:'blocking',line:1}]}))",
                    "console.log(JSON.stringify({findings:[{severity:'advisory',line:'1'}]}))",
                    "console.log(JSON.stringify({findings:[]}));process.exit(2)"]
        for script in fixtures:
            with self.subTest(script=script):
                checker = self.dir / 'broken.js'
                checker.write_text(script)
                report = inspect_path(self.body, checker=checker)
                self.assertEqual(report['status'], 'ERROR')
                self.assertEqual(report['exit_code'], 2)
        self.assertEqual(inspect_path(self.body, executable='/no/such/node')['status'], 'ERROR')

    def test_checker_timeout_is_error(self):
        with patch('fuben_engine.subprocess.run', side_effect=subprocess.TimeoutExpired('node', 1)):
            findings, tool = style_diagnostics(self.body)
        self.assertEqual(findings[0]['severity'], 'ERROR')
        self.assertEqual(tool['state'], 'ERROR')

    def test_clis_share_fact_severity(self):
        self.body.write_text('你写了五个字「欢迎回家」。')
        for name in ('fuben_run.py', 'fuben_lint.py', 'fuben_consistency.py'):
            result = run(sys.executable, ROOT / 'scripts' / name, self.dir)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        result = run(sys.executable, ROOT / 'scripts/fuben_loop.py', 'review', self.dir, '--json')
        self.assertEqual(result.returncode, 1)
        self.assertFalse(json.loads(result.stdout)['editorially_approved'])

    def test_density_advisory_and_shotmap_argument_parsing(self):
        self.body.write_text('123 456 789\n' * 50)
        result = run(sys.executable, ROOT / 'scripts/fuben_density.py', self.body, '--json')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)[0]['status'], 'DESCRIPTIVE')
        result = run(sys.executable, ROOT / 'scripts/fuben_shotmap.py', self.dir, '--cps', '6.4', '--json')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)[0]['cps'], 6.4)
        for value in ('0', '-1', 'nan', 'inf'):
            self.assertEqual(run(sys.executable, ROOT / 'scripts/fuben_shotmap.py', self.dir, '--cps', value).returncode, 2)


class RouteTests(Fixture):
    def setUp(self):
        super().setUp()
        self.core = ROOT / 'skills/story-setup/references/templates/hooks/story_hook_core.js'
        self.phase2 = ROOT / 'skills/story-short-write/scripts/check-phase2-contract.js'
        self.ai = ROOT / 'skills/story-review/scripts/check-ai-patterns.js'

    def test_generic_novel_contract_remains_blocking_fuben_is_na(self):
        self.body.unlink()
        (self.dir / '设定.md').write_text('普通知乎盐选小说的设定')
        self.assertEqual(run('node', self.phase2, self.dir).returncode, 1)
        (self.dir / '设定.md').write_text('平台：抖音「人生副本」第二人称口播')
        result = run('node', self.phase2, self.dir)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)['applicability'], 'not_applicable')
        (self.dir / '.fuben.json').write_text('{')
        self.assertEqual(run('node', self.phase2, self.dir).returncode, 2)

    def test_generic_ai_styles_still_block_only_novel(self):
        self.body.write_text('这不是退让，而是宣战。\n')
        generic = run('node', self.ai, '--profile=novel', '--fail-on=blocking', self.body)
        fuben = run('node', self.ai, '--profile=fuben', '--fail-on=blocking', '--json', self.body)
        self.assertEqual(generic.returncode, 1)
        self.assertEqual(fuben.returncode, 0)
        self.assertTrue(json.loads(fuben.stdout)['findings'])
        (self.dir / '.fuben.json').write_text('{"schema_version":1,"profile":"fuben"}')
        self.assertEqual(run('node', self.ai, '--fail-on=blocking', self.body).returncode, 0)

    def test_js_python_and_bash_outline_routes(self):
        self.body.unlink()
        hook = ROOT / 'skills/story-setup/references/codex/hooks/story_codex_hook.py'
        spec = importlib.util.spec_from_file_location('fixture_codex_hook', hook)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        guard = ROOT / 'skills/story-setup/references/templates/hooks/guard-outline-before-prose.sh'
        for setting, blocked in [('普通小说', True), ('平台：抖音「人生副本」口播', False)]:
            with self.subTest(setting=setting):
                (self.dir / '设定.md').write_text(setting)
                reason = module.prose_block_reason(self.dir, self.body)
                self.assertEqual(bool(reason), blocked)
                script = f"const c=require({json.dumps(str(self.core))}); console.log(JSON.stringify(c.proseBlockReason(process.argv[1],process.argv[2])));"
                result = run('node', '-e', script, self.dir, self.body)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(bool(json.loads(result.stdout)), blocked)
                env = {**os.environ, 'CLAUDE_PROJECT_DIR': str(self.dir)}
                result = run('bash', guard, input=json.dumps({'tool_name': 'Write', 'tool_input': {'file_path': str(self.body)}}), env=env, cwd=self.dir)
                self.assertEqual(result.returncode, 2 if blocked else 0, result.stderr)

    def test_nonprose_and_invalid_profile_repair_remain_editable(self):
        helper = ROOT / 'skills/story-short-write/scripts/story-profile.js'
        probe = f"const c=require({json.dumps(str(helper))});console.log(c.isFubenProject(process.argv[1]));"
        (self.dir / 'tool.py').write_text('print(1)')
        result = run('node', '-e', probe, self.dir / 'tool.py')
        self.assertEqual((result.returncode, result.stdout.strip()), (0, 'true'), result.stderr)
        dotted_dir = self.dir / 'project.md'; dotted_dir.mkdir()
        (dotted_dir / '正文.md').write_text(self.body.read_text())
        result = run('node', '-e', probe, dotted_dir)
        self.assertEqual((result.returncode, result.stdout.strip()), (0, 'true'), result.stderr)
        spec = importlib.util.spec_from_file_location('codex_file_kind_test', ROOT / 'skills/story-setup/references/codex/hooks/story_codex_hook.py')
        codex = importlib.util.module_from_spec(spec); spec.loader.exec_module(codex)
        self.assertTrue(codex.is_fuben_project(self.dir / 'tool.py'))
        self.assertTrue(codex.is_fuben_project(dotted_dir))
        (self.dir / '.fuben.json').write_text('{bad configuration')
        (self.dir / 'tool.py').write_text('print(1)')
        script = f"const c=require({json.dumps(str(self.core))});console.log(JSON.stringify(c.proseBlockReason(process.argv[1],process.argv[2])));"
        for name in ('tool.py', '.fuben.json'):
            result = run('node', '-e', script, self.dir, self.dir / name)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIsNone(json.loads(result.stdout))
            for hook in ('guard-outline-before-prose.sh', 'check-prose-after-write.sh'):
                result = run('bash', ROOT / 'skills/story-setup/references/templates/hooks' / hook,
                             input=json.dumps({'tool_name': 'Write', 'tool_input': {'file_path': str(self.dir / name)}}),
                             env={**os.environ, 'CLAUDE_PROJECT_DIR': str(self.dir)}, cwd=self.dir)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_deployed_prompt_templates_do_not_reintroduce_novel_quotas(self):
        import tomllib
        base = ROOT / 'skills/story-setup/references'
        roots = [base / 'templates/CLAUDE.md.tmpl', base / 'antigravity/rules/oh-story.md',
                 *[base / host / 'AGENTS.md.tmpl' for host in ('codex', 'opencode', 'zcode', 'openclaw', 'reasonix', 'generic')]]
        for path in roots:
            text = path.read_text()
            self.assertIn('人生副本优先分流', text[:1300], str(path))
            self.assertIn('fuben-review', text[:1300], str(path))
        agents = [*(base / 'templates/agents').glob('*.md'), *(base / 'opencode/agents').glob('*.md'),
                  *(base / 'codex/agents').glob('*.toml')]
        self.assertEqual(len(agents), 21)
        for path in agents:
            if path.suffix == '.toml':
                text = tomllib.loads(path.read_text())['developer_instructions']
            else:
                frontmatter, text = path.read_text().split('\n---\n', 1)
                self.assertNotIn('人生副本优先分流', frontmatter, str(path))
            self.assertIn('人生副本优先分流（profile=fuben）', text[:1400], str(path))
            self.assertIn('机器接口不因本分支改变', text, str(path))
        generated = self.dir / 'antigravity-generated'
        result = run('node', ROOT / 'skills/story-setup/scripts/generate-antigravity-agents.mjs', '--dest', generated)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(list(generated.glob('*/agent.md'))), 7)
        for path in generated.glob('*/agent.md'):
            self.assertIn('人生副本优先分流（profile=fuben）', path.read_text(), str(path))
        for path in (base / 'templates/rules').glob('*.md'):
            self.assertIn('以下为普通小说规则', path.read_text()[:500], str(path))

    def test_all_current_fuben_works_are_routed(self):
        helper = ROOT / 'skills/story-review/scripts/story-profile.js'
        script = ("const fs=require('fs'),p=require('path'),{isFubenProject}=require(process.argv[1]);"
                  "const ds=fs.readdirSync(process.argv[2]).filter(d=>/^\\d/.test(d)&&fs.statSync(p.join(process.argv[2],d)).isDirectory());"
                  "console.log(JSON.stringify({checked:ds.length,unrouted:ds.filter(d=>!isFubenProject(p.join(process.argv[2],d)))}));")
        result = run('node', '-e', script, helper, ROOT / '作品')
        self.assertEqual(result.returncode, 0, result.stderr)
        inventory = json.loads(result.stdout)
        expected = sum(p.is_dir() and p.name[0].isdigit() for p in (ROOT / '作品').iterdir())
        self.assertGreater(expected, 0)
        self.assertEqual(inventory['checked'], expected)
        self.assertEqual(inventory['unrouted'], [])

    def test_hook_postwrite_does_not_force_fuben_style_cleanup(self):
        (self.dir / '.fuben.json').write_text('{"schema_version":1,"profile":"fuben"}')
        self.body.write_text('这不是退让，而是宣战\n')
        script = f"const c=require({json.dumps(str(self.core))});console.log(c.proseAfterWrite(process.argv[1],process.argv[2]));"
        result = run('node', '-e', script, self.dir, self.body)
        self.assertIn('NOTE', result.stdout)
        self.assertNotIn('本章须清零', result.stdout)

    def test_deployment_inventory_includes_fuben_review(self):
        import runpy
        module = runpy.run_path(str(ROOT / 'skills/story-setup/scripts/deploy-antigravity-skills.py'))
        actual = {p.parent.name for p in (ROOT / 'skills').glob('*/SKILL.md')}
        self.assertEqual(set(module['KNOWN_SKILLS']), actual)
        self.assertIn('fuben-review', actual)

    def test_distributed_sources_are_identical(self):
        scripts = [ROOT / 'skills' / name / 'scripts' for name in ('story-review', 'story-short-write', 'story-long-write', 'story-deslop')]
        for name in ('check-ai-patterns.js', 'story-profile.js'):
            self.assertEqual(len({(p / name).read_bytes() for p in scripts}), 1)
        core_paths = [self.core, ROOT / 'skills/story-setup/references/opencode/story_hook_core.js',
                      ROOT / 'skills/story-setup/references/antigravity/hooks/story_hook_core.js', ROOT / 'skills/story-setup/references/zcode/hooks/story_hook_core.js']
        self.assertEqual(len({p.read_bytes() for p in core_paths}), 1)
        helper = (scripts[0] / 'story-profile.js').read_text()
        inline = helper[helper.index('function readOptional'):helper.index('module.exports')].rstrip()
        self.assertIn(inline, self.core.read_text())

    def test_standalone_tool_deployment_works_outside_source(self):
        dest = self.dir / 'deployment'
        installer = ROOT / 'skills/story-setup/scripts/deploy-fuben-tools.py'
        result = run(sys.executable, installer, '--dest', dest)
        self.assertEqual(result.returncode, 0, result.stderr)
        body = dest / '作品/1_测试/正文.md'
        body.parent.mkdir(parents=True)
        body.write_text('今天体验的人生副本是：一场梦\n你醒了。')
        result = run(sys.executable, dest / 'scripts/fuben_run.py', body, '--json', cwd=self.dir)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['tools'][0]['state'], 'COMPLETED')
        (dest / 'scripts/fuben_run.py').write_text('# user edited')
        self.assertEqual(run(sys.executable, installer, '--dest', dest).returncode, 2)


class InventoryTests(Fixture):
    def test_new_sources_are_discovered_and_missing_inputs_are_not_skipped(self):
        from fuben_corpus import discover
        from fuben_health import inspect_collection
        source = self.dir / '拆文库/99_新样本/原文/自定义文件名.txt'
        source.parent.mkdir(parents=True)
        source.write_text('这是后来加的新原文。')
        self.assertEqual(discover(self.dir), [source])
        (self.dir / '拆文库/100_遗漏原文').mkdir()
        with self.assertRaises(ValueError): discover(self.dir)
        (self.dir / '作品/999_缺正文').mkdir(parents=True)
        report = inspect_collection(root=self.dir)
        self.assertEqual(report['coverage']['work'], 1)
        self.assertEqual(report['errors'], 1)


class SceneTests(Fixture):
    def test_missing_optional_table_not_claimed_pass(self):
        result = inspect_scenes(self.dir)
        self.assertEqual(result['scene_status'], 'NOT_ASSESSED')
        self.assertTrue(result['mechanical_pass'])

    def test_global_word_hit_does_not_prove_local_scene(self):
        self.body.write_text('甲场景\n碗\n乙场景\n手机')
        evidence = {'schema_version': 1, 'body_sha256': sha256(self.body),
                    'scenes': [{'name': '甲', 'start_line': 1, 'end_line': 2, 'props': ['手机']}]}
        file = self.dir / '场面证据.json'
        file.write_text(json.dumps(evidence))
        result = inspect_scenes(self.dir)
        self.assertTrue(any(f['rule_id'] == 'SCENE_SPAN_MISS' for f in result['findings']))
        evidence['scenes'][0]['props'] = []
        file.write_text(json.dumps(evidence))
        self.assertEqual(inspect_scenes(self.dir)['status'], 'ERROR')
        self.body.write_text('改稿')
        self.assertEqual(inspect_scenes(self.dir)['status'], 'FAIL')


class ReleaseTests(Fixture):
    def valid_fixture(self):
        # Simulated media and mock metadata only. No actual listening claimed by tests.
        (self.dir / '成片.mp4').write_bytes(b'fixture: not a real media asset')
        (self.dir / '审核报告.md').write_text('测试审核证据：此为隔离夹具，不是真实发布结论。')
        document = release.template(self.dir)
        document['media'] = {'path': '成片.mp4', 'sha256': sha256(self.dir / '成片.mp4')}
        document['owner_publication_authorized'] = True
        for name, item in document['reviews'].items():
            item.update(status='APPROVED', reviewer='fixture-reviewer', reviewed_at='2026-09-19T16:00:00+08:00')
            item['evidence']['sha256'] = sha256(self.dir / '审核报告.md')
            if name == 'media':
                item['reviewed_media_sha256'] = document['media']['sha256']
        return document

    def check(self, document=None, **kwargs):
        if document is not None:
            (self.dir / '.发布证据.json').write_text(json.dumps(document))
        return release.check(self.dir, probe=kwargs.get('probe', lambda path: {'duration_seconds': 20, 'measurement': 'TEST_FIXTURE'}))

    def test_missing_evidence_and_template_are_provisional(self):
        self.assertEqual(self.check()['status'], 'PROVISIONAL')
        self.assertEqual(self.check(release.template(self.dir))['exit_code'], 3)

    def test_valid_fixture_is_not_publication(self):
        result = self.check(self.valid_fixture())
        self.assertEqual(result['status'], 'READY_FOR_OWNER_CONFIRMATION')
        self.assertFalse(result['published'])
        self.assertFalse(result['attestation_identity_verified'])

    def test_changed_body_and_refreshing_manifest_cannot_launder_old_review(self):
        document = self.valid_fixture()
        self.body.write_text('正文已经改了，审核仍是原来那次。')
        self.assertEqual(self.check(document)['status'], 'BLOCKED')
        document['inputs_sha256'] = release.inputs(self.dir, '正文.md')
        result = self.check(document)
        self.assertTrue(any(i['code'] == 'STALE_REVIEW_BINDING' for i in result['issues']))

    def test_setting_media_and_review_hash_changes_block(self):
        for path in ('设定.md', '成片.mp4', '审核报告.md'):
            with self.subTest(path=path):
                document = self.valid_fixture()
                (self.dir / path).write_text('changed')
                self.assertEqual(self.check(document)['status'], 'BLOCKED')

    def test_refreshed_media_hash_still_needs_media_review(self):
        document = self.valid_fixture()
        (self.dir / '成片.mp4').write_bytes(b'new clip')
        document['media']['sha256'] = sha256(self.dir / '成片.mp4')
        result = self.check(document)
        self.assertTrue(any(i['code'] == 'STALE_MEDIA_REVIEW' for i in result['issues']))

    def test_media_tool_failure_is_not_estimated_pass(self):
        def fail(path):
            raise ValueError('no ffprobe')
        self.assertEqual(self.check(self.valid_fixture(), probe=fail)['status'], 'ERROR')
        with patch('fuben_release.subprocess.run', side_effect=FileNotFoundError()):
            with self.assertRaises(ValueError):
                release.probe_media(self.dir / '成片.mp4')

    def test_explicit_duration_limit_and_reviewer_fix(self):
        document = self.valid_fixture()
        document['constraints'] = {'max_duration_seconds': 15}
        self.assertEqual(self.check(document)['status'], 'BLOCKED')
        document['constraints'] = {}
        document['reviews']['facts']['status'] = 'FIX'
        self.assertEqual(self.check(document)['status'], 'BLOCKED')


class DataTests(Fixture):
    def setUp(self):
        super().setUp()
        self.work_body = self.dir / '作品/1_测试/正文.md'
        self.work_body.parent.mkdir(parents=True)
        self.work_body.write_text('测试正文。')

    def record(self):
        doc = data.template()
        doc.update(work_id='1', text_version='v1', text_path='作品/1_测试/正文.md', text_sha256=sha256(self.work_body),
                   video_id='fixture-id', video_version='v1', published_at='2026-09-19T12:00:00+08:00',
                   snapshot_at='2026-09-19T13:00:00+08:00', duration_seconds=446)
        doc['observed'].update(plays=798, likes=12, average_watch_seconds=18)
        doc['source'].update(location='isolated test report', reported_by='fixture')
        return doc

    def test_strict_schema_and_missing_values(self):
        doc = self.record()
        self.assertEqual(data.validate(doc), doc)
        self.assertIsNone(doc['observed']['completion_rate'])
        invalid_path = copy.deepcopy(doc); invalid_path['text_path'] = '作品'
        with self.assertRaises(ValueError): data.validate(invalid_path, bind=True, root=self.dir)
        for field, bad in [('snapshot_at', '2026-09-19T13:00:00'), ('duration_seconds', 0), ('text_sha256', 'bad')]:
            with self.subTest(field=field):
                changed = copy.deepcopy(doc); changed[field] = bad
                with self.assertRaises(ValueError): data.validate(changed)
        for key, value in [('plays', 'published'), ('completion_rate', 99), ('likes', -1), ('average_watch_seconds', float('nan'))]:
            changed = copy.deepcopy(doc); changed['observed'][key] = value
            with self.assertRaises(ValueError): data.validate(changed)

    def test_mean_watch_fraction_is_not_completion(self):
        doc = self.record()
        metrics = data.derived(doc)
        self.assertAlmostEqual(metrics['mean_watched_fraction'], 18 / 446)
        self.assertNotIn('completion_rate', metrics)
        self.assertIsNone(doc['observed']['completion_rate'])
        doc['observed']['plays'] = 0
        self.assertIsNone(data.derived(doc)['like_rate'])

    def test_atomic_roundtrip_decreasing_likes_and_idempotency(self):
        directory = self.dir / '数据'
        first = self.record()
        self.assertEqual(data.append_record(first, directory, self.dir), 'RECORDED_UNVERIFIED_SOURCE')
        self.assertEqual(data.append_record(first, directory, self.dir), 'ALREADY_RECORDED')
        second = copy.deepcopy(first); second['snapshot_at'] = '2026-09-19T14:00:00+08:00'; second['observed']['likes'] = 8
        data.append_record(second, directory, self.dir)
        self.assertEqual(len(data.read_records(directory / 'snapshots.jsonl')), 2)
        bad = copy.deepcopy(second); bad['observed']['likes'] = 9
        with self.assertRaises(ValueError): data.append_record(bad, directory, self.dir)
        self.assertEqual(len(data.read_records(directory / 'snapshots.jsonl')), 2)

    def test_corrupt_active_data_fails_closed(self):
        path = self.dir / 'snapshots.jsonl'
        path.write_text('{broken}\n')
        with self.assertRaises(ValueError): data.read_records(path)

    def test_legacy_migration_preserves_raw_and_never_guesses_shifted_rows(self):
        old = self.dir / 'legacy.csv'
        raw = 'id,likes\r\n1,12,shifted\r\n2,published\r\n'.encode()
        old.write_bytes(raw)
        out = self.dir / 'data'
        result = data.migrate([old], out, write=True)
        self.assertEqual(result['wrong_width'], 1)
        self.assertEqual(result['verified_observations_imported'], 0)
        self.assertEqual(old.read_bytes(), raw)
        self.assertEqual(next((out / 'legacy_raw').glob('*.csv')).read_bytes(), raw)
        self.assertEqual(len((out / 'legacy_quarantine.jsonl').read_text().splitlines()), 2)

    def test_old_unsafe_record_command_rejected_without_data_mutation(self):
        old = [ROOT / '作品/_数据.csv', ROOT / '作品/_数据_v2.csv']
        before = [sha256(p) for p in old]
        result = run(sys.executable, ROOT / 'scripts/fuben_loop.py', 'record', '78', '123', '456')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(before, [sha256(p) for p in old])


if __name__ == '__main__':
    unittest.main()
