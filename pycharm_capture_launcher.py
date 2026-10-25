"""Explicit combined launcher. Does not alter PyCharm or restart killed apps."""
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys

_branding = Path(__file__).with_name('launcher-branding.json')
TITLE = json.loads(_branding.read_text(encoding='utf-8'))['title'] if _branding.exists() else 'PyCharm + Capture'


def validate_pycharm(path):
    path = Path(path).resolve()
    if not path.is_file() or path.name.lower() != 'pycharm64.exe':
        raise ValueError('Select the installed pycharm64.exe file.')
    info = json.loads((path.parent.parent / 'product-info.json').read_text(encoding='utf-8'))
    if info.get('version') != '2024.1.3' or info.get('productCode') != 'PC':
        raise ValueError('This launcher requires PyCharm Community Edition 2024.1.3.')
    return path


def validate_capture(path):
    path = Path(path).resolve()
    if not path.is_file() or path.suffix.lower() != '.exe':
        raise ValueError('Select your built capture executable.')
    if path == Path(sys.executable).resolve() or path.name.lower() == 'pycharm64.exe':
        raise ValueError('Select the capture app, not PyCharm or this launcher.')
    return path


def settings_file():
    folder = Path(os.environ['LOCALAPPDATA']) / 'PyCharmCaptureLauncher'
    folder.mkdir(parents=True, exist_ok=True)
    return folder / 'settings.json'


def configure(window):
    from tkinter import filedialog, messagebox
    messagebox.showinfo(TITLE,
        'This launcher opens PyCharm Community 2024.1.3 AND starts your capture app paused.\n'
        'It does not modify PyCharm. Select both executables next.', parent=window)
    ide = filedialog.askopenfilename(parent=window, title='Select PyCharm Community 2024.1.3: pycharm64.exe', filetypes=[('Executable', '*.exe')])
    if not ide:
        return None
    ide = validate_pycharm(ide)
    capture = filedialog.askopenfilename(parent=window, title='Select your capture app EXE (not the monitor)', filetypes=[('Executable', '*.exe')])
    if not capture:
        return None
    capture = validate_capture(capture)
    settings = {'pycharm': str(ide), 'capture': str(capture)}
    settings_file().write_text(json.dumps(settings, indent=2), encoding='utf-8')
    return settings


def launch(settings):
    # Validate both paths before starting either app.
    ide = validate_pycharm(settings['pycharm'])
    capture = validate_capture(settings['capture'])
    frozen = getattr(sys, 'frozen', False)
    if frozen:
        dll_dir = ctypes.WinDLL('kernel32').SetDllDirectoryW
        dll_dir.argtypes, dll_dir.restype = [ctypes.c_wchar_p], ctypes.c_int
        dll_dir(None)
    environment = os.environ.copy()
    environment['PYINSTALLER_RESET_ENVIRONMENT'] = '1'
    # A separately launched companion owns its own settings and runtime.
    environment.pop('QUIET_CAPTURE_PORTABLE_DATA', None)
    try:
        subprocess.Popen([str(capture), '--start-paused'], cwd=str(capture.parent),
                         env=environment, creationflags=subprocess.CREATE_NO_WINDOW)
        subprocess.Popen([str(ide)], cwd=str(ide.parent), env=environment)
    finally:
        if frozen:
            dll_dir(sys._MEIPASS)


def main():
    import tkinter as tk
    from tkinter import messagebox
    window = tk.Tk()
    window.withdraw()
    try:
        if '--self-test' in sys.argv:
            # Proves Tcl/Tk is bundled; no settings, process or network changes.
            window.update_idletasks()
            return
        path = settings_file()
        if '--setup' in sys.argv or not path.exists():
            settings = configure(window)
            if settings is None or '--setup' in sys.argv:
                return
        else:
            settings = json.loads(path.read_text(encoding='utf-8'))
        launch(settings)
    except (OSError, ValueError, KeyError) as error:
        messagebox.showerror(TITLE,
            str(error) + '\n\nRun this launcher with --setup to select the paths again.', parent=window)
        raise SystemExit(1)
    finally:
        window.destroy()


if __name__ == '__main__':
    main()
