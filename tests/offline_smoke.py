"""Targeted offline regression checks. No model calls, accounts or browser connections."""
from pathlib import Path
import importlib.util
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'tools/gpt-writer'))
sys.path.insert(0, str(REPO / 'app/adapters'))
from gptw import knowledge, materials
import xhs_daily


class Smoke(unittest.TestCase):
    def test_new_user_materials_and_private_history(self):
        with tempfile.TemporaryDirectory(prefix='xhs 中文 空格 ') as temp:
            root = Path(temp)
            shutil.copytree(REPO / 'knowledge', root / 'knowledge')
            shutil.copytree(REPO / 'seed/knowledge', root / 'knowledge', dirs_exist_ok=True)
            markers = {}
            for index, (_, relative) in enumerate(knowledge.FIXED_FILES):
                path = root / 'knowledge' / relative
                self.assertTrue(path.is_file(), relative)
                markers[relative] = f'PRIVATE_FIXTURE_{index}'
                path.write_text(path.read_text(encoding='utf-8-sig') + '\n' + markers[relative], encoding='utf-8')
            old = knowledge.XHS_ROOT
            try:
                knowledge.XHS_ROOT = root
                result = materials.build({'topic': '新人开场', 'problem': '开播紧张', 'audience': '新人'})
                self.assertEqual(result['stats']['fixed_missing'], [])
                for marker in markers.values():
                    self.assertIn(marker, result['user'])
            finally:
                knowledge.XHS_ROOT = old

    def test_draft_fields_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            images = []
            for i in range(6):
                path = Path(temp) / f'{i}.png'
                path.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\0' * 8 + struct.pack('>II', 1080, 1440))
                images.append(path)
            detail = {'title': '标题', 'text': '完整正文\n#甲 #乙', 'tags': ['#甲', '#乙'],
                      'topic_nodes': ['#甲', '#乙'], 'slides': 6, 'imgs': [{'w': 1080, 'h': 1440}] * 6}
            self.assertEqual(xhs_daily.compare_draft('标题', '完整正文', ['甲', '乙'], images, detail)[0], [])
            for field, bad in [('text', '完整正文多余内容 #甲 #乙'), ('topic_nodes', []),
                               ('tags', ['#乙', '#甲']), ('imgs', []), ('title', '错标题')]:
                changed = {**detail, field: bad}
                self.assertTrue(xhs_daily.compare_draft('标题', '完整正文', ['甲', '乙'], images, changed)[0], field)

    def test_existing_or_failed_draft_is_not_recreated(self):
        self.assertTrue(xhs_daily.should_resume_existing({'stage': 'failed', 'title': '标题'}, '标题'))
        self.assertTrue(xhs_daily.should_resume_existing({'stage': 'failed', 'title': '旧标题', 'draft': {'identity': 'title:旧标题'}}, '新标题'))
        self.assertFalse(xhs_daily.should_resume_existing({'stage': 'prepared', 'title': '标题'}, '标题'))

    def test_writer_project_entry_mock(self):
        with tempfile.TemporaryDirectory(prefix='xhs 中文 空格 ') as temp:
            root = Path(temp)
            shutil.copytree(REPO / 'app/adapters', root / 'app/adapters')
            shutil.copytree(REPO / 'tools/gpt-writer', root / 'tools/gpt-writer')
            shutil.copytree(REPO / 'knowledge', root / 'knowledge')
            shutil.copytree(REPO / 'seed/knowledge', root / 'knowledge', dirs_exist_ok=True)
            (root / 'config').mkdir()
            paths = {'root': str(root), 'xhs_python': sys.executable,
                     'playwright_browsers': str(root / 'custom browsers'), 'tmp_dir': str(root / 'custom temp')}
            (root / 'config/paths.json').write_text(json.dumps(paths), encoding='utf-8')
            task = root / 'task.json'
            task.write_text(json.dumps({'topic': '开播紧张', 'problem': '新人开场'}), encoding='utf-8')
            env = dict(os.environ, XHSWORK_ROOT=str(root), XHS_PATHS=str(root / 'config/paths.json'))
            run = root / 'run'
            result = subprocess.run([sys.executable, str(root / 'app/adapters/run_writer.py'), '--task',
                                     str(task), '--run-dir', str(run), '--mock'], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            meta = json.loads((run / 'gpt_meta.json').read_text(encoding='utf-8-sig'))
            self.assertEqual(meta['mode'], 'mock')
            self.assertFalse(meta['real_call'])
            self.assertTrue((run / 'cards.md').is_file())


if __name__ == '__main__':
    unittest.main(verbosity=2)
