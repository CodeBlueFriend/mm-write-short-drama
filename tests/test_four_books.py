from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'mm-write-short-drama/scripts'

def run(name, *args):
    return subprocess.run([sys.executable, str(SCRIPTS / name), *map(str, args)],
                          check=True, text=True, capture_output=True).stdout

class FourBooksTests(unittest.TestCase):
    def test_builtin_cards_are_ready_without_a_personal_library(self):
        cases = (
            ('planning', '一句梗概', 'BUILTIN-LOGLINE'),
            ('structure', '整季节拍', 'BUILTIN-SEASON-BEATS'),
            ('dialogue', '言语行动', 'BUILTIN-VERBAL-ACTION'),
        )
        with tempfile.TemporaryDirectory() as temp:
            for stage, query, card_id in cases:
                result = subprocess.run(
                    [sys.executable, str(SCRIPTS / 'search_knowledge.py'), query,
                     '--stage', stage, '--format', 'json'],
                    cwd=temp, check=True, text=True, capture_output=True,
                )
                cards = json.loads(result.stdout)
                self.assertEqual([card['id'] for card in cards], [card_id])
                self.assertEqual(cards[0]['card_origin'], 'builtin')
                self.assertTrue(cards[0]['source_url'].startswith('https://'))
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / 'search_knowledge.py'), '--format', 'ids'],
                cwd=temp, check=True, text=True, capture_output=True,
            )
            self.assertEqual(set(result.stdout.splitlines()), {case[2] for case in cases})
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_only_matching_active_personal_card_replaces_builtin(self):
        capability = 'cap.save-the-cat-short-drama.logline'
        material = ('标题：项目梗概要突出姐妹关系\n规则：立项梗概优先交代姐妹之间的利益冲突。\n'
                    '阶段：planning\n来源：项目原创测试\n来源链接：https://example.com/test\n'
                    f'仓颉能力 ID：{capability}\n'
                    '触发：姐妹题材立项\n诊断：检查关系\n动作：明确争夺资源\n'
                    '输出：一句梗概\n自检：利益明确\n短剧适配：测试实践\n来源核验：测试材料')
        with tempfile.TemporaryDirectory() as temp:
            for status in ('draft', 'active'):
                kb = Path(temp) / status
                personal = json.loads(run('ingest_knowledge.py', '--kb', kb, '--text', material,
                                          '--genre', '都市家庭', '--status', status))['created'][0]
                matching = json.loads(run('search_knowledge.py', '--kb', kb, '--capability', capability,
                                          '--stage', 'planning', '--genre', '都市家庭', '--format', 'json'))
                expected = personal if status == 'active' else 'BUILTIN-LOGLINE'
                self.assertEqual([card['id'] for card in matching], [expected])
                other_genre = run('search_knowledge.py', '--kb', kb, '--capability', capability,
                                  '--genre', '古装悬疑', '--format', 'ids')
                self.assertEqual(other_genre.strip(), 'BUILTIN-LOGLINE')

    def test_provenance_capability_filter_and_duplicate(self):
        with tempfile.TemporaryDirectory() as temp:
            kb = Path(temp) / 'kb'
            material = ('标题：对白试探\n规则：对白试探之后让听者的行动改变策略。\n'
                        '阶段：dialogue\n来源：项目原创测试，不是书籍原文\n'
                        '来源链接：https://example.com/test\n仓颉能力 ID：cap.test.dialogue\n'
                        '触发：对白停滞\n诊断：检查反应\n动作：换策略\n'
                        '输出：对白\n自检：行动变化\n短剧适配：测试实践\n来源核验：测试材料')
            first = json.loads(run('ingest_knowledge.py', '--kb', kb, '--text', material, '--status', 'draft'))
            self.assertEqual(json.loads(run('search_knowledge.py', '--kb', kb, '--capability', 'cap.test.dialogue', '--format', 'json')), [])
            draft = json.loads(run('search_knowledge.py', '--kb', kb, '--status', 'draft', '--capability', 'cap.test.dialogue', '--format', 'json'))
            self.assertEqual(draft[0]['source_url'], 'https://example.com/test')
            self.assertEqual(draft[0]['action'], '换策略')
            self.assertEqual(draft[0]['source_note'], '项目原创测试，不是书籍原文')
            self.assertEqual(json.loads(run('search_knowledge.py', '--kb', kb, '--status', 'draft', '--capability', 'cap.other', '--format', 'json')), [])
            self.assertEqual(json.loads(run('search_knowledge.py', '--kb', kb, '--status', 'draft', '--capability', 'cap.test.dialogue', '--stage', 'planning', '--format', 'json')), [])
            before = (kb / 'index/cards.jsonl').read_bytes()
            second = json.loads(run('ingest_knowledge.py', '--kb', kb, '--text', material, '--status', 'active'))
            self.assertEqual(second['created'], [])
            self.assertEqual(second['duplicates'], 1)
            self.assertEqual(before, (kb / 'index/cards.jsonl').read_bytes())
            context = run('search_knowledge.py', '--kb', kb, '--status', 'draft', '--format', 'context')
            for expected in ('cap.test.dialogue', '项目原创测试', '换策略', '行动变化'):
                self.assertIn(expected, context)
            self.assertEqual(len(first['created']), 1)

if __name__ == '__main__':
    unittest.main()
