"""Build the explicitly named combined launcher using the selected PyCharm icon."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from pycharm_capture_launcher import validate_pycharm
from rebuild import version_resource
from builder_names import validate_name


def build_launcher(ide_path, label='PyCharm', company='Personal launcher', version_number='1.0.0.0', copyright_text='', description='Combined launcher for PyCharm Community 2024.1.3 and a capture app', product_name=None):
    title = validate_name(label)
    metadata = version_resource(title,
        description, company, version_number, copyright_text, product_name)
    ide = validate_pycharm(ide_path)
    icon = ide.parent / 'pycharm.ico'
    if not icon.is_file():
        raise ValueError('Original pycharm.ico not found beside pycharm64.exe.')
    root = Path(__file__).resolve().parent
    work = root / 'build' / 'combined-launcher' / title
    work.mkdir(parents=True, exist_ok=True)
    version = work / 'version.txt'
    version.write_text(metadata, encoding='utf-8')
    branding = work / 'launcher-branding.json'
    branding.write_text(json.dumps({'title': title}), encoding='utf-8')
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--onefile',
        '--windowed', '--name', title, '--icon', str(icon),
        '--version-file', str(version), '--specpath', str(work),
        '--add-data', str(branding) + ';.',
        '--workpath', str(work / 'cache'), '--distpath', str(root / 'dist' / 'Launcher'),
        str(root / 'pycharm_capture_launcher.py')], check=True)
    print('Built:', root / 'dist' / 'Launcher' / (title + '.exe'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pycharm', required=True, type=Path, help='Installed Community 2024.1.3 pycharm64.exe')
    parser.add_argument('--label', default='PyCharm')
    parser.add_argument('--company', default='Personal launcher')
    parser.add_argument('--version', default='1.0.0.0')
    parser.add_argument('--copyright', default='')
    parser.add_argument('--description', default='Combined launcher for PyCharm Community 2024.1.3 and a capture app')
    parser.add_argument('--product-name')
    args = parser.parse_args()
    try:
        build_launcher(args.pycharm, args.label, args.company, args.version, args.copyright, args.description, args.product_name)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
