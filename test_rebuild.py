import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import portable_entry
from rebuild import build, version_resource
from builder_names import validate_name


class RebuildTests(unittest.TestCase):
    def test_invalid_names_rejected(self):
        for name in ('../bad', 'NUL', 'COM1', 'x/y', ''):
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_name(name)
        for name in ('Study Capture', 'svchost', 'RuntimeBroker', '123 App', '工具 & Notes', 'a' * 80, 'bad.exe'):
            self.assertEqual(validate_name(name), name)

    def test_metadata_is_valid_resource(self):
        from PyInstaller.utils.win32.versioninfo import VSVersionInfo
        from PyInstaller.utils.win32 import versioninfo
        resource = eval(version_resource('Study Capture', 'Study Capture capture utility'), vars(versioninfo))
        self.assertIsInstance(resource, VSVersionInfo)
        self.assertIn('Study Capture.exe', str(resource))
        self.assertNotIn('QuietCapture', str(resource))
        self.assertIn('LegalCopyright', str(resource))
        self.assertNotIn('Copyright (c)', str(resource))
        custom = version_resource('Study', 'Capture utility', copyright_text='Copyright © 2026 Example Author')
        self.assertIn('Copyright © 2026 Example Author', custom)

    def test_invalid_version_rejected(self):
        for version in ('1.0', '1.2.3.-1', '1.2.3.65536', '1.2.3.x'):
            with self.subTest(version=version), self.assertRaises(ValueError):
                version_resource('Study', 'Capture utility', version=version)

    def test_build_plan_uses_branding_without_credentials_or_launching(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'config.json').write_text(json.dumps({'model': 'test', 'pycharm_path': 'old.exe'}))
            with patch('rebuild.subprocess.run') as run:
                build(root, 'Study Capture', 'Study Monitor', app_company='App Author', app_version='2.0.0.1', monitor_company='Monitor Author', monitor_version='3.0.0.2')
            self.assertEqual(run.call_count, 3)
            command = run.call_args_list[1].args[0]
            self.assertIn('--onefile', command)
            self.assertIn('--version-file', command)
            self.assertEqual(command[command.index('--name') + 1], 'Study Capture')
            work = root / 'build' / 'portable' / 'Study Capture'
            self.assertEqual(json.loads((work / 'portable-branding.json').read_text())['monitor_name'], 'Study Monitor')
            self.assertNotIn('pycharm_path', (work / 'portable-defaults.json').read_text())
            self.assertFalse((root / 'package-paths.json').exists())
            self.assertIn('App Author', (work / 'Study Capture-version.txt').read_text())
            self.assertIn('filevers=(2,0,0,1)', (work / 'Study Capture-version.txt').read_text())
            self.assertIn('Monitor Author', (work / 'Study Monitor-version.txt').read_text())
            self.assertIn('filevers=(3,0,0,2)', (work / 'Study Monitor-version.txt').read_text())

    def test_existing_pycharm_config_is_ignored_on_launch(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'config.json').write_text(json.dumps({'pycharm_path': 'does-not-exist.exe'}))
            with patch('portable_entry.data_directory', return_value=root), patch('portable_entry.sys.argv', ['app.exe']), patch('portable_entry.runpy.run_module') as run, patch.dict('os.environ'):
                portable_entry.main()
            run.assert_called_once_with('app', run_name='__main__')


if __name__ == '__main__':
    unittest.main()
