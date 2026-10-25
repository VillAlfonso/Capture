"""Standalone Quiet Capture launcher and first-run configuration."""
import ctypes as C
from ctypes import wintypes as W
import json
import os
from pathlib import Path
import runpy
import sys
from branding import APP_NAME


def data_directory():
    path = Path(os.environ['LOCALAPPDATA']) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_key(path, text):
    class Blob(C.Structure):
        _fields_ = [('size', W.DWORD), ('data', C.POINTER(C.c_ubyte))]
    crypt = C.WinDLL('crypt32')
    kernel = C.WinDLL('kernel32')
    crypt.CryptProtectData.argtypes = [C.POINTER(Blob), W.LPCWSTR, C.c_void_p,
        C.c_void_p, C.c_void_p, W.DWORD, C.POINTER(Blob)]
    crypt.CryptProtectData.restype = W.BOOL
    kernel.LocalFree.argtypes = [C.c_void_p]
    kernel.LocalFree.restype = C.c_void_p
    raw = text.encode('utf-8')
    buffer = (C.c_ubyte * len(raw)).from_buffer_copy(raw)
    source, target = Blob(len(raw), buffer), Blob()
    try:
        if not crypt.CryptProtectData(C.byref(source), APP_NAME + ' API key', None, None, None, 1, C.byref(target)):
            raise OSError('Could not encrypt API key for this Windows user')
        path.write_bytes(C.string_at(target.data, target.size))
    finally:
        C.memset(buffer, 0, len(raw))
        if target.data:
            kernel.LocalFree(target.data)


def configure(root):
    import tkinter as tk
    from tkinter import messagebox, simpledialog
    window = tk.Tk()
    window.withdraw()
    try:
        config_path = root / 'config.json'
        if config_path.exists():
            settings = json.loads(config_path.read_text(encoding='utf-8'))
        else:
            settings = json.loads((Path(__file__).parent / 'portable-defaults.json').read_text(encoding='utf-8'))
        settings.pop('pycharm_path', None)
        messagebox.showinfo(APP_NAME + ' setup',
            'The app starts paused. Ctrl+Alt+F9 enables capture.\nSettings and diagnostics are stored in:\n' + str(root))
        model = simpledialog.askstring('API model', 'OpenAI API model:', initialvalue=settings['model'])
        if model is None:
            return False
        settings['model'] = model.strip()
        wifi = simpledialog.askstring('Optional Wi-Fi management',
            'Saved Wi-Fi profile for temporary offline connection. Leave empty to disable:',
            initialvalue=settings.get('temporary_wifi_profile', ''))
        if wifi is None:
            return False
        settings['temporary_wifi_profile'] = wifi.strip()
        key = simpledialog.askstring('OpenAI API key',
            'Enter key locally. Leave blank to keep the saved key or use OPENAI_API_KEY:', show='*')
        if key is None:
            return False
        if key.strip():
            save_key(root / 'openai-key.dpapi', key.strip())
        if not ((root / 'openai-key.dpapi').exists() or os.environ.get('OPENAI_API_KEY')):
            messagebox.showwarning('No API key', 'Capture can start, but API requests will fail until you set a key. Run with --setup to configure later.')
        settings['start_paused'] = True
        config_path.write_text(json.dumps(settings, indent=2) + '\n', encoding='utf-8')
        return True
    finally:
        window.destroy()


def main():
    # This check loads bundled dependencies without hooks, credentials or network.
    if '--self-test' in sys.argv:
        import tkinter
        import PIL.Image
        import app
        import temporary_wifi
        root = data_directory()
        (root / 'portable-self-test.txt').write_text('Bundled imports passed\n', encoding='utf-8')
        return
    root = data_directory()
    os.environ['QUIET_CAPTURE_PORTABLE_DATA'] = str(root)
    special = any(flag in sys.argv for flag in ('--stop', '--monitor'))
    if not special and ('--setup' in sys.argv or not (root / 'config.json').exists()):
        if not configure(root) or '--setup' in sys.argv:
            return
    runpy.run_module('app', run_name='__main__')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        root = data_directory()
        (root / 'launcher-error.txt').write_text(type(error).__name__ + '\n', encoding='utf-8')
        import tkinter as tk
        from tkinter import messagebox
        window = tk.Tk()
        window.withdraw()
        messagebox.showerror(APP_NAME + ' could not start',
            'Setup or launch failed (' + type(error).__name__ + ').\nRun with --setup to check configuration.\nDetails folder: ' + str(root))
        window.destroy()
        sys.exit(1)
