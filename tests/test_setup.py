"""導入先保護と設定生成を、実際の一時ディレクトリで検証する。"""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('setup_manager', Path(__file__).parents[1] / 'scripts/manage.py')
manager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manager)

class SetupTests(unittest.TestCase):
    def test_標準保存先と指定ポートで設定される(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'instance'
            manager.initialize(root, 'immich-test', 2294, 44, 109, 'test-image:fixed')
            env = (root / '.env').read_text()
            self.assertIn('UPLOAD_LOCATION=./library\n', env)
            self.assertIn('DB_DATA_LOCATION=./postgres\n', env)
            self.assertIn('IMMICH_PORT=2294\n', env)
            self.assertIn('COMPOSE_PROJECT_NAME=immich-test\n', env)
            self.assertEqual((root / '.env').stat().st_mode & 0o777, 0o600)
            self.assertTrue((root / 'library').is_dir())
            self.assertNotIn('container_name:', (root / 'compose.yaml').read_text())
            self.assertNotIn('external: true', (root / 'compose.yaml').read_text())

    def test_既存ディレクトリのファイルを上書きしない(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / '.env').write_text('本番の設定')
            with self.assertRaises(ValueError):
                manager.initialize(root, 'immich-test', 2294, 44, 109, 'test-image:fixed')
            self.assertEqual((root / '.env').read_text(), '本番の設定')
            self.assertFalse((root / '.m75q-instance.json').exists())

    def test_再実行でパスワードと設定を保持する(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'instance'
            manager.initialize(root, 'immich-test', 2294, 44, 109, 'test-image:fixed')
            before = (root / '.env').read_bytes()
            manager.initialize(root, 'immich-test', 2294, 44, 109, 'test-image:fixed')
            self.assertEqual((root / '.env').read_bytes(), before)
            with self.assertRaises(ValueError):
                manager.initialize(root, 'immich-test', 2283, 44, 109, 'test-image:fixed')
            self.assertEqual((root / '.env').read_bytes(), before)

    def test_不正な名前とポートを拒否する(self):
        for project, port in [('bad/name', 2283), ('UPPER', 2283), ('good', 0), ('good', 65536)]:
            with self.subTest(project=project, port=port), tempfile.TemporaryDirectory() as temp:
                root = Path(temp) / 'instance'
                with self.assertRaises(ValueError):
                    manager.initialize(root, project, port, 44, 109, 'test-image:fixed')
                self.assertFalse(root.exists())

    def test_ポート番号の上下限を受け付ける(self):
        for port in [1, 65535]:
            with self.subTest(port=port), tempfile.TemporaryDirectory() as temp:
                root = Path(temp) / 'instance'
                state = manager.initialize(root, 'valid', port, 44, 109, 'test-image:fixed')
                self.assertEqual(state['port'], port)
                self.assertIn(f'IMMICH_PORT={port}\n', (root / '.env').read_text())

    def test_構成ファイルの手動変更を検出する(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'instance'
            manager.initialize(root, 'valid', 2294, 44, 109, 'test-image:fixed')
            (root / 'compose.yaml').write_text('services: {}\n')
            with self.assertRaises(ValueError):
                manager.load_instance(root)

    def test_別ディレクトリにコピーされた管理情報を拒否する(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'instance'
            manager.initialize(root, 'immich-test', 2294, 44, 109, 'test-image:fixed')
            state = json.loads((root / '.m75q-instance.json').read_text())
            state['directory'] = '/別の場所'
            (root / '.m75q-instance.json').write_text(json.dumps(state))
            with self.assertRaises(ValueError):
                manager.load_instance(root)

if __name__ == '__main__':
    unittest.main()
