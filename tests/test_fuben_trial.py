"""Label blinding and missing-data tests. All fixture prose/model labels are synthetic."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import fuben_trial_blind as trial


class TrialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='fuben_trial_fixture_')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.pack = self.root / 'pack'; self.pack.mkdir()
        self.responses = self.root / 'responses'; self.responses.mkdir()
        self.out = self.root / 'export'
        manifest = {'schema_version': 1, 'scope': 'manual_one_shot_prompt_text_pilot_not_full_skill_workflow',
                    'cases': [], 'inputs': {}, 'frozen_files': {}}
        self.registration = {'schema_version': 1, 'model_label': 'FIXTURE_NOT_A_REAL_MODEL',
                             'settings': {'temperature': None, 'max_output_tokens': None},
                             'fresh_session_per_output_attested': True, 'same_model_settings_attested': True,
                             'raw_outputs_unedited_attested': True, 'outputs': {}}
        objects = iter(('杯子', '钥匙', '外套', '雨伞', '水壶', '书包', '手套', '围巾', '票根'))
        for case_id in ('H01', 'H02', 'H03'):
            shared = self.pack / (case_id + '.md'); shared.write_text('这是虚构的工程测试题面。')
            shared_sha = trial.digest(shared.read_bytes())
            manifest['cases'].append({'id': case_id, 'shared_path': shared.name, 'shared_sha256': shared_sha})
            manifest['frozen_files'][shared.name] = shared_sha
            for arm in 'ABC':
                key = case_id + '_' + arm
                prompt = self.pack / (key + '.md'); prompt.write_text('固定的工程夹具输入 ' + key)
                sha = trial.digest(prompt.read_bytes())
                manifest['inputs'][key] = {'case_id': case_id, 'condition': arm, 'path': prompt.name,
                                           'sha256': sha, 'shared_sha256': shared_sha}
                self.registration['outputs'][key] = {'input_packet_sha256': sha, 'session_label': 'fixture-' + key,
                    'stop_reason': 'COMPLETE', 'actual_input_tokens': None, 'actual_output_tokens': None}
                (self.responses / (key + '.md')).write_text(f'# 临时夹具\n你把{next(objects)}放回桌上。\n这不是模型生成结果。\n')
        (self.pack / '清单.json').write_text(json.dumps(manifest, ensure_ascii=False))
        self.save_registration()

    def save_registration(self):
        (self.responses / '运行登记.json').write_text(json.dumps(self.registration, ensure_ascii=False))

    def test_export_hides_labels_binds_originals_and_does_not_judge(self):
        before = {p.name: trial.digest(p.read_bytes()) for p in self.responses.iterdir()}
        result = trial.export_blind(self.pack, self.responses, self.out)
        self.assertEqual(result['status'], 'EXPORTED_NOT_JUDGED')
        self.assertFalse(result['quality_assessed'])
        self.assertFalse(result['independence_verified'])
        self.assertFalse(result['budget_verified'])
        mapping = json.loads((self.out / '主持人勿外发/映射.json').read_text())
        self.assertEqual(len(mapping['mapping']), 9)
        self.assertEqual(len({m['body_sha256'] for m in mapping['mapping']}), 9)
        self.assertEqual(len({m['anonymous_id'] for m in mapping['mapping']}), 9)
        public = '\n'.join(p.read_text() for p in (self.out / '给评审').iterdir())
        for key in self.registration['outputs']:
            self.assertNotIn(key, public)
        for item in mapping['mapping']:
            self.assertEqual(item['body_sha256'], before[item['source_key'] + '.md'])
            case_id = item['anonymous_id'].split('-')[0]
            packet = (self.out / '给评审' / (case_id + '.md')).read_text()
            section = packet.split('## 稿件 ' + item['anonymous_id'] + '\n', 1)[1].split('## 稿件 ', 1)[0]
            self.assertIn((self.responses / (item['source_key'] + '.md')).read_text(), section)
        template = json.loads((self.out / '给评审/评审记录.json').read_text())
        self.assertEqual(template['status'], 'NOT_REVIEWED')
        self.assertTrue(all(not c['ranking_with_ties'] for c in template['cases']))
        self.assertEqual(before, {p.name: trial.digest(p.read_bytes()) for p in self.responses.iterdir()})
        with self.assertRaises(ValueError):
            trial.export_blind(self.pack, self.responses, self.out)

    def test_failed_or_missing_outputs_cannot_be_silently_dropped(self):
        self.registration['outputs']['H02_B']['stop_reason'] = 'TRUNCATED'
        self.save_registration()
        result = trial.export_blind(self.pack, self.responses, self.out)
        self.assertEqual(result['status'], 'INCOMPLETE')
        self.assertEqual(result['expected_outputs'], 9)
        self.assertEqual(result['complete_outputs'], 8)
        self.assertFalse(self.out.exists())
        del self.registration['outputs']['H02_B']
        self.save_registration()
        with self.assertRaises(ValueError): trial.inspect(self.pack, self.responses)

    def test_changed_prompt_and_bad_binding_are_errors(self):
        prompt = self.pack / 'H01_A.md'
        original = prompt.read_bytes(); prompt.write_text('事后改输入')
        with self.assertRaises(ValueError): trial.inspect(self.pack, self.responses)
        prompt.write_bytes(original)
        self.registration['outputs']['H01_A']['input_packet_sha256'] = '0' * 64
        self.save_registration()
        with self.assertRaises(ValueError): trial.inspect(self.pack, self.responses)

    def test_distinct_sessions_nullable_usage_and_valid_schema(self):
        self.registration['outputs']['H02_B']['session_label'] = self.registration['outputs']['H01_A']['session_label']
        self.save_registration()
        with self.assertRaises(ValueError): trial.inspect(self.pack, self.responses)
        self.registration['outputs']['H02_B']['session_label'] = 'fixture-other'
        self.registration['outputs']['H02_B']['actual_output_tokens'] = -1
        self.save_registration()
        with self.assertRaises(ValueError): trial.inspect(self.pack, self.responses)
        self.registration['outputs']['H02_B']['actual_output_tokens'] = None
        self.registration['schema_version'] = True
        self.save_registration()
        with self.assertRaises(ValueError): trial.inspect(self.pack, self.responses)

    def test_empty_text_metadata_leak_and_symlinks_do_not_export(self):
        text = self.responses / 'H01_A.md'
        for content in ('', '# 只有标题\n', '按轻量规则v11写出的正文。'):
            text.write_text(content)
            result = trial.export_blind(self.pack, self.responses, self.out)
            self.assertEqual(result['status'], 'INCOMPLETE')
            self.assertFalse(self.out.exists())
        text.write_text('你看了洗衣店的新规则，店员让B组的人先排队。')
        self.assertEqual(trial.inspect(self.pack, self.responses)[0]['status'], 'READY_FOR_BLIND_READING')
        text.unlink(); external = self.root / 'outside.md'; external.write_text('不应沿输入链接读取。')
        text.symlink_to(external)
        with self.assertRaises(ValueError): trial.inspect(self.pack, self.responses)

    def test_real_pack_template_is_frozen_and_not_a_completed_experiment(self):
        empty = self.root / 'empty-response-set'; empty.mkdir()
        (empty / '运行登记.json').write_bytes((trial.DEFAULT_PACK / '运行登记.template.json').read_bytes())
        result, _ = trial.inspect(trial.DEFAULT_PACK, empty)
        self.assertEqual(result['status'], 'INCOMPLETE')
        self.assertEqual(result['expected_outputs'], 9)
        self.assertEqual(result['complete_outputs'], 0)
        self.assertFalse(result['quality_assessed'])


if __name__ == '__main__':
    unittest.main()
