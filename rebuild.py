"""Interactive portable builder; does not start apps or modify startup."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from builder_names import validate_name


def version_resource(name, description, company=None, version='1.0.0.0', copyright_text='', product_name=None):
    components = version.split('.')
    if len(components) != 4 or any(not c.isdecimal() or not 0 <= int(c) <= 65535 for c in components):
        raise ValueError('Version must contain four numbers from 0 to 65535, for example 1.0.0.0.')
    numbers = ','.join(str(int(c)) for c in components)
    fields = {'CompanyName': name if company is None else company, 'FileDescription': description, 'FileVersion': version,
              'LegalCopyright': copyright_text, 'InternalName': name, 'OriginalFilename': name + '.exe',
              'ProductName': name if product_name is None else product_name, 'ProductVersion': version}
    entries = ','.join('StringStruct(%r, %r)' % pair for pair in fields.items())
    return ("VSVersionInfo(ffi=FixedFileInfo(filevers=(" + numbers + "),prodvers=(" + numbers + "),mask=0x3f,flags=0,OS=0x40004,fileType=1,subtype=0,date=(0,0)),kids=[StringFileInfo([StringTable('040904B0',["
            + entries + "])]),VarFileInfo([VarStruct('Translation',[1033,1200])])])")


def build(root, name, monitor, icon=None, app_company=None, app_version='1.0.0.0', monitor_company=None, monitor_version='1.0.0.0', app_copyright='', monitor_copyright='', app_description=None, monitor_description=None, app_product_name=None, monitor_product_name=None):
    name = validate_name(name)
    monitor = validate_name(monitor)
    if name.casefold() == monitor.casefold():
        raise ValueError('App and monitor names must differ.')
    resources = {
        name: version_resource(name, name + ' capture utility' if app_description is None else app_description, app_company, app_version, app_copyright, app_product_name),
        monitor: version_resource(monitor, monitor + ' status monitor' if monitor_description is None else monitor_description, monitor_company, monitor_version, monitor_copyright, monitor_product_name),
    }
    python = root / '.venv' / 'Scripts' / 'python.exe'
    python = str(python if python.exists() else Path(sys.executable))
    subprocess.run([python, '-c', 'import PyInstaller, PIL, tkinter'], check=True)
    work = root / 'build' / 'portable' / name
    output = root / 'dist' / 'Windows11-Portable' / name
    work.mkdir(parents=True, exist_ok=True)
    defaults = json.loads((root / 'config.json').read_text(encoding='utf-8-sig'))
    defaults.pop('pycharm_path', None)
    (work / 'portable-defaults.json').write_text(json.dumps(defaults), encoding='utf-8')
    (work / 'portable-branding.json').write_text(json.dumps({'app_name': name, 'monitor_name': monitor}), encoding='utf-8')
    for product, entry, console, role in [(name, 'portable_entry.py', False, 'capture utility'), (monitor, 'monitor.py', True, 'status monitor')]:
        version = work / (product + '-version.txt')
        version.write_text(resources[product], encoding='utf-8')
        subprocess.run([python, '-m', 'PyInstaller', '--noconfirm', '--onefile',
            '--console' if console else '--windowed', '--name', product,
            '--icon', str(icon) if icon else 'NONE', '--version-file', str(version),
            '--hidden-import', 'app', '--hidden-import', 'temporary_wifi',
            '--add-data', str(work / 'portable-defaults.json') + ';.',
            '--add-data', str(work / 'portable-branding.json') + ';.',
            '--specpath', str(work), '--workpath', str(work / 'cache'),
            '--distpath', str(output), str(root / entry)], check=True)
    print('Built both EXEs in:', output)
    print('Data folder: %LOCALAPPDATA%\\' + name)
    print('No app started; no startup shortcuts changed. Other named builds remain in their folders.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', help='App name without .exe')
    parser.add_argument('--monitor-name', help='Monitor name without .exe')
    parser.add_argument('--icon', type=Path, help='Optional .ico or .png; default is the generic icon')
    parser.add_argument('--app-company')
    parser.add_argument('--app-version', default='1.0.0.0')
    parser.add_argument('--monitor-company')
    parser.add_argument('--monitor-version', default='1.0.0.0')
    parser.add_argument('--app-copyright', default='')
    parser.add_argument('--monitor-copyright', default='')
    parser.add_argument('--app-description')
    parser.add_argument('--monitor-description')
    parser.add_argument('--app-product-name')
    parser.add_argument('--monitor-product-name')
    args = parser.parse_args()
    try:
        name = args.name if args.name is not None else (input('App name [QuietCapture]: ').strip() or 'QuietCapture')
        default_monitor = name + 'Monitor'
        monitor = args.monitor_name if args.monitor_name is not None else (input(f'Monitor name [{default_monitor}]: ').strip() or default_monitor)
        if args.icon and not args.icon.is_file():
            raise ValueError('Icon file does not exist.')
        build(Path(__file__).resolve().parent, name, monitor, args.icon.resolve() if args.icon else None,
              args.app_company, args.app_version, args.monitor_company, args.monitor_version,
              args.app_copyright, args.monitor_copyright, args.app_description, args.monitor_description, args.app_product_name, args.monitor_product_name)
    except (ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()