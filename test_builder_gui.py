import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from builder_gui import validate_options, commands, collect_outputs


class BuilderGuiTests(unittest.TestCase):
    def options(self, root):
        return dict(app='StudyApp', monitor='StudyMonitor', label='Study', company='My Tools',
                    version='1.0.0.0', pycharm=str(root / 'pycharm64.exe'), output=str(root / 'out'))

    def test_validation_and_argument_lists(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'pycharm.ico').touch()
            with patch('builder_gui.validate_pycharm', return_value=root / 'pycharm64.exe'):
                values = self.options(root)
                values.update(app='svchost', monitor='RuntimeBroker', company='Microsoft / JetBrains', app_company='', monitor_company='x' * 120)
                options = validate_options(values)
            self.assertEqual(options['title'], 'Study')
            steps = commands(options)
            self.assertEqual(len(steps), 2)
            self.assertIn('svchost', steps[0])
            self.assertEqual(options['app_company'], '')
            self.assertIn('Microsoft / JetBrains', steps[1])
            self.assertIn('--app-company', steps[0])
            self.assertIn('--monitor-version', steps[0])

    def test_duplicate_names_rejected(self):
        options = self.options(Path('.'))
        options['monitor'] = 'studyapp'
        with self.assertRaises(ValueError):
            validate_options(options)

    def test_collect_only_three_exes_into_unique_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            options = self.options(root)
            options['title'] = 'Study + Capture'
            app = root / 'dist' / 'Windows11-Portable' / 'StudyApp'
            launcher = root / 'dist' / 'Launcher'
            app.mkdir(parents=True)
            launcher.mkdir(parents=True)
            for name in ('StudyApp', 'StudyMonitor'):
                (app / (name + '.exe')).write_bytes(b'test binary')
            (launcher / 'Study + Capture.exe').write_bytes(b'launcher')
            (app / 'openai-key.dpapi').write_bytes(b'not copied')
            destination = collect_outputs(options, root)
            self.assertEqual(sorted(p.name for p in destination.iterdir()), ['Study + Capture.exe', 'StudyApp.exe', 'StudyMonitor.exe'])
            self.assertNotEqual(destination, collect_outputs(options, root))

    def test_missing_build_output_prevents_collection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            options = self.options(root)
            options['title'] = 'Study + Capture'
            with self.assertRaises(FileNotFoundError):
                collect_outputs(options, root)
            self.assertFalse((root / 'out').exists())


if __name__ == '__main__':
    unittest.main()
