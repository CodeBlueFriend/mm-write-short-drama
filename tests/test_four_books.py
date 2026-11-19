from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'mm-write-short-drama/scripts'
sys.path.insert(0, str(SCRIPTS))
from knowledge_lib import iter_cards, read_card, render_card

BUNDLED = ROOT / 'mm-write-short-drama/knowledge-base'
BUNDLED_CARDS = {c['capability_id']: c for c in iter_cards(BUNDLED)}


def snapshot(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}

def run(name, *args):
    return subprocess.run([sys.executable, str(SCRIPTS / name), *map(str, args)],
                          check=True, text=True, capture_output=True).stdout

class FourBooksTests(unittest.TestCase):
    def test_builtin_cards_are_ready_without_a_personal_library(self):
        cases = (
            ('planning', '一句梗概', 'cap.save-the-cat-short-drama.logline'),
            ('structure', '整季节拍', 'cap.save-the-cat-short-drama.beat-sheet'),
            ('dialogue', '言语行动', 'cap.mckee-dialogue-short-drama.verbal-action'),
        )
        with tempfile.TemporaryDirectory() as temp:
            for stage, query, capability in cases:
                result = subprocess.run(
                    [sys.executable, str(SCRIPTS / 'search_knowledge.py'), query,
                     '--stage', stage, '--capability', capability, '--format', 'json'],
                    cwd=temp, check=True, text=True, capture_output=True,
                )
                cards = json.loads(result.stdout)
                self.assertEqual([card['id'] for card in cards], [BUNDLED_CARDS[capability]['id']])
                self.assertEqual(cards[0]['card_origin'], 'builtin')
                self.assertEqual(Path(cards[0]['_knowledge_origin']), BUNDLED)
                self.assertTrue(cards[0]['source_url'].startswith('https://'))
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / 'search_knowledge.py'), '--limit', '50',
                 '--story-limit', '19', '--format', 'json'],
                cwd=temp, check=True, text=True, capture_output=True,
            )
            inventory = json.loads(result.stdout)
            self.assertEqual(len(inventory), 24)
            self.assertEqual({c['capability_id'] for c in inventory}, set(BUNDLED_CARDS))
            self.assertEqual({c['card_origin'] for c in inventory}, {'builtin'})
            self.assertFalse(any(c['id'].startswith('BUILTIN-') for c in inventory))
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_legacy_public_card_remains_a_fallback(self):
        capability = 'cap.save-the-cat-short-drama.logline'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            installed = root / 'skills' / 'mm-write-short-drama'
            shutil.copytree(ROOT / 'mm-write-short-drama', installed,
                            ignore=shutil.ignore_patterns('__pycache__'))
            project = root / 'project'
            project.mkdir()
            target = BUNDLED_CARDS[capability]['id']
            (installed / 'knowledge-base' / 'cards' / (target + '.md')).unlink()
            before = snapshot(installed)
            result = subprocess.run(
                [sys.executable, str(installed / 'scripts/search_knowledge.py'),
                 '--capability', capability, '--format', 'json'],
                cwd=project, check=True, text=True, capture_output=True,
            )
            cards = json.loads(result.stdout)
            self.assertEqual([c['id'] for c in cards], ['BUILTIN-LOGLINE'])
            self.assertEqual(cards[0]['card_origin'], 'builtin')
            self.assertEqual({p: h for p, h in snapshot(installed).items() if '__pycache__' not in p},
                             before)
            self.assertEqual(list(project.iterdir()), [])

    def test_story_limits_and_explicit_personal_only_search(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            kb = project / 'knowledge-base'
            (kb / 'cards').mkdir(parents=True)
            before = snapshot(kb)
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / 'search_knowledge.py'), '--limit', '50',
                 '--format', 'json'], cwd=project, check=True, text=True, capture_output=True,
            )
            cards = json.loads(result.stdout)
            self.assertEqual(sum(c['capability_id'].startswith('cap.mckee-story-short-drama.')
                                 for c in cards), 2)
            self.assertEqual(snapshot(kb), before)
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / 'search_knowledge.py'), '--no-builtin',
                 '--format', 'json'], cwd=project, check=True, text=True, capture_output=True,
            )
            self.assertEqual(json.loads(result.stdout), [])
            self.assertEqual(snapshot(kb), before)

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
                expected = personal if status == 'active' else BUNDLED_CARDS[capability]['id']
                self.assertEqual([card['id'] for card in matching], [expected])
                if status == 'draft':
                    mixed = json.loads(run('search_knowledge.py', '--kb', kb, '--capability', capability,
                                           '--status', 'active,draft', '--format', 'json'))
                    self.assertEqual({c['id'] for c in mixed}, {personal, BUNDLED_CARDS[capability]['id']})
                other_genre = run('search_knowledge.py', '--kb', kb, '--capability', capability,
                                  '--genre', '古装悬疑', '--format', 'ids')
                self.assertEqual(other_genre.strip(), BUNDLED_CARDS[capability]['id'])

    def test_stale_personal_index_cannot_reactivate_a_card(self):
        capability = 'cap.save-the-cat-short-drama.logline'
        with tempfile.TemporaryDirectory() as directory:
            kb = Path(directory) / 'knowledge-base'
            material = ('标题：项目前提\n规则：先讲清姐妹之间争夺的资源。\n'
                        '阶段：planning\n来源：项目原创测试\n'
                        f'仓颉能力 ID：{capability}\n')
            personal = json.loads(run('ingest_knowledge.py', '--kb', kb, '--text', material,
                                      '--status', 'active'))['created'][0]
            path = kb / 'cards' / (personal + '.md')
            card = read_card(path)
            card.pop('_path')
            card['status'] = 'draft'
            path.write_text(render_card(card), encoding='utf-8')
            before = snapshot(kb)
            cards = json.loads(run('search_knowledge.py', '--kb', kb, '--capability', capability,
                                   '--format', 'json'))
            self.assertEqual([c['id'] for c in cards], [BUNDLED_CARDS[capability]['id']])
            self.assertEqual(snapshot(kb), before)

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
