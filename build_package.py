"""Build clearly named executables; keep user configuration and secrets outside bundles."""
import json
import os
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parent
app_name = os.environ.get('QUIET_CAPTURE_APP_NAME', 'QuietCapture')
monitor_name = os.environ.get('QUIET_CAPTURE_MONITOR_NAME', 'QuietCaptureMonitor')
assets = root / 'build' / 'branding'
assets.mkdir(parents=True, exist_ok=True)
# No embedded icon: allow Windows/Task Manager to select its generic fallback.
icon_args = ['--icon', 'NONE']
for name, source, console, description in (
    (app_name, 'app.py', False, app_name + ' background capture utility'),
    (monitor_name, 'monitor.py', True, monitor_name + ' status monitor'),
):
    version = assets / (name + '-version.txt')
    strings = {'CompanyName': 'Quiet Capture', 'FileDescription': description,
               'FileVersion': '1.0.0.0', 'InternalName': name, 'OriginalFilename': name + '.exe',
               'ProductName': name, 'ProductVersion': '1.0.0.0'}
    entries = ','.join('StringStruct(%r, %r)' % pair for pair in strings.items())
    version.write_text("VSVersionInfo(ffi=FixedFileInfo(filevers=(1,0,0,0),prodvers=(1,0,0,0),mask=0x3f,flags=0,OS=0x40004,fileType=1,subtype=0,date=(0,0)),kids=[StringFileInfo([StringTable('040904B0',[" + entries + "])]),VarFileInfo([VarStruct('Translation',[1033,1200])])])", encoding='utf-8')
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--onedir',
                    '--console' if console else '--windowed', '--name', name,
                    *icon_args, '--version-file', str(version),
                    '--specpath', str(assets), '--distpath', str(root/'dist'),
                    '--workpath', str(root/'build'/'packages'), str(root/source)], check=True)
(root/'package-paths.json').write_text(json.dumps({
    'app': f'dist/{app_name}/{app_name}.exe',
    'monitor': f'dist/{monitor_name}/{monitor_name}.exe'}, indent=2) + '\n')
print('Built app and monitor. Config and encrypted key remain in the project root.')
