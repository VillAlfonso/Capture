import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from pycharm_capture_launcher import launch, validate_pycharm
from build_launcher import build_launcher


class LauncherTests(unittest.TestCase):
    def install(self, root, version='2024.1.3', product='PC'):
        (root / 'bin').mkdir()
        ide = root / 'bin' / 'pycharm64.exe'
        ide.touch()
        (root / 'product-info.json').write_text(json.dumps({'version': version, 'productCode': product}))
        return ide

    def test_launches_both_with_capture_paused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ide = self.install(root)
            capture = root / 'Study Capture.exe'
            capture.touch()
            with patch('pycharm_capture_launcher.subprocess.Popen') as start:
                launch({'pycharm': str(ide), 'capture': str(capture)})
            self.assertEqual(start.call_count, 2)
            self.assertEqual(start.call_args_list[0].args[0], [str(capture), '--start-paused'])
            self.assertEqual(start.call_args_list[1].args[0], [str(ide)])

    def test_wrong_version_does_not_launch_anything(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ide = self.install(root, version='2026.2.3')
            with patch('pycharm_capture_launcher.subprocess.Popen') as start, self.assertRaises(ValueError):
                launch({'pycharm': str(ide), 'capture': 'missing.exe'})
            start.assert_not_called()

    def test_professional_edition_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            ide = self.install(Path(directory), product='PY')
            with self.assertRaises(ValueError):
                validate_pycharm(ide)

    def test_custom_metadata_and_icon_build_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ide = self.install(root)
            (ide.parent / 'pycharm.ico').touch()
            with patch('build_launcher.__file__', str(root / 'build_launcher.py')), patch('build_launcher.subprocess.run') as build:
                build_launcher(ide, 'Study', 'Microsoft / JetBrains ' + 'x' * 110, '2.3.4.5')
            command = build.call_args.args[0]
            self.assertEqual(command[command.index('--name') + 1], 'Study')
            self.assertEqual(command[command.index('--icon') + 1], str(ide.parent / 'pycharm.ico'))
            version = Path(command[command.index('--version-file') + 1]).read_text()
            self.assertIn('Microsoft / JetBrains ' + 'x' * 110, version)
            self.assertIn('filevers=(2,3,4,5)', version)
            self.assertIn('Combined launcher', version)
            data = root / 'build' / 'combined-launcher' / 'Study' / 'launcher-branding.json'
            self.assertEqual(json.loads(data.read_text())['title'], 'Study')


if __name__ == '__main__':
    unittest.main()
