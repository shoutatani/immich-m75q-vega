"""導入先保護と設定生成を、実際の一時ディレクトリで検証する。"""
import importlib.util
import json
import re
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('setup_manager', Path(__file__).parents[1] / 'scripts/manage.py')
manager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manager)

class SetupTests(unittest.TestCase):
    def test_サーバーと推論イメージが331で揃う(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'instance'
            manager.initialize(root, 'valid', 2295, 44, 109, manager.image_tag())
            self.assertIn('IMMICH_VERSION=v3.3.1\n', (root / '.env').read_text())
            self.assertIn('immich-server:v3.3.1', (root / 'compose.yaml').read_text())
            self.assertTrue(manager.image_tag().startswith('immich-m75q-vega-ml:v3.3.1-'))

    def test_旧バージョンの環境は再ビルドでも変更しない(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'instance'
            manager.initialize(root, 'valid', 2295, 44, 109, 'old-image:fixed')
            env = root / '.env'
            env.write_text(re.sub(r'IMMICH_VERSION=[^\n]+', 'IMMICH_VERSION=v3.2.0', env.read_text()))
            before = {name: (root / name).read_bytes() for name in ['.env', 'compose.yaml', manager.MARKER]}
            with self.assertRaises(ValueError):
                manager.initialize(root, 'valid', 2295, 44, 109, 'new-image:fixed', replace_image=True)
            for name, content in before.items():
                self.assertEqual((root / name).read_bytes(), content)

    def test_envだけ更新した旧構成も再ビルドで変更しない(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'instance'
            manager.initialize(root, 'valid', 2295, 44, 109, 'old-image:fixed')
            compose = root / 'compose.yaml'
            compose.write_text(compose.read_text().replace('immich-server:v3.3.1', 'immich-server:v3.2.0'))
            marker = root / manager.MARKER
            state = json.loads(marker.read_text())
            state['compose_sha256'] = manager.digest(compose)
            marker.write_text(json.dumps(state))
            before = {name: (root / name).read_bytes() for name in ['.env', 'compose.yaml', manager.MARKER]}
            with self.assertRaises(ValueError):
                manager.initialize(root, 'valid', 2295, 44, 109, 'new-image:fixed', replace_image=True)
            for name, content in before.items():
                self.assertEqual((root / name).read_bytes(), content)

    def test_標準保存先と指定ポートで設定される(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'instance'
            manager.initialize(root, 'immich-test', 2294, 44, 109, 'test-image:fixed')
            env = (root / '.env').read_text()
            self.assertIn('UPLOAD_LOCATION=./library\n', env)
            self.assertIn('DB_DATA_LOCATION=./postgres\n', env)
            self.assertIn('IMMICH_HTTP_PORT=2294\n', env)
            self.assertNotIn('IMMICH_PORT=', env)
            self.assertIn('${IMMICH_HTTP_PORT:-2283}:2283', (root / 'compose.yaml').read_text())
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
                self.assertIn(f'IMMICH_HTTP_PORT={port}\n', (root / '.env').read_text())

    def test_構成ファイルの手動変更を検出する(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'instance'
            manager.initialize(root, 'valid', 2294, 44, 109, 'test-image:fixed')
            (root / 'compose.yaml').write_text('services: {}\n')
            with self.assertRaises(ValueError):
                manager.load_instance(root)

    def test_明示した再ビルドだけ推論イメージを更新する(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'instance'
            manager.initialize(root, 'valid', 2294, 44, 109, 'old-image:fixed')
            old_env = (root / '.env').read_text()
            with self.assertRaises(ValueError):
                manager.initialize(root, 'valid', 2294, 44, 109, 'new-image:fixed')
            manager.initialize(root, 'valid', 2294, 44, 109, 'new-image:fixed', replace_image=True)
            self.assertEqual((root / '.env').read_text(), old_env.replace('old-image:fixed', 'new-image:fixed'))
            self.assertEqual(manager.load_instance(root)['image'], 'new-image:fixed')
            with self.assertRaises(ValueError):
                manager.initialize(root, 'wrong-project', 2294, 44, 109, 'new-image:fixed', replace_image=True)

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
