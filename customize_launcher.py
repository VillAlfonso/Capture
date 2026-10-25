"""Interactive launcher metadata editor and rebuilder."""
from pathlib import Path
import subprocess
from build_launcher import build_launcher


def main():
    print('Customize your independent PyCharm + Capture launcher.')
    label = input('Launcher label [PyCharm]: ').strip() or 'PyCharm'
    company = input('Your name/publisher label [Personal launcher]: ').strip() or 'Personal launcher'
    version = input('Version [1.0.0.0]: ').strip() or '1.0.0.0'
    copyright_text = input('Copyright text: ')
    default = Path(r'C:\Morrow Glass\tools\PyCharm-2024.1.3\bin\pycharm64.exe')
    suffix = f' [{default}]' if default.is_file() else ''
    entered = input('Installed Community 2024.1.3 executable' + suffix + ': ').strip().strip('"')
    if not entered and not default.is_file():
        raise ValueError('A local PyCharm path is required for its icon and version check.')
    build_launcher(Path(entered) if entered else default, label, company, version, copyright_text)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error))
