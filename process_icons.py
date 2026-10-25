"""Read-only Windows process icon browser; exports original resource bytes."""
import ctypes as C
from ctypes import wintypes as W
import io
import os
from pathlib import Path
import struct
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

k32 = C.WinDLL('kernel32', use_last_error=True)
def api(name, args, result):
    fn = getattr(k32, name)
    fn.argtypes, fn.restype = args, result
    return fn

load = api('LoadLibraryExW', [W.LPCWSTR, W.HANDLE, W.DWORD], W.HMODULE)
free = api('FreeLibrary', [W.HMODULE], W.BOOL)
find = api('FindResourceW', [W.HMODULE, C.c_void_p, C.c_void_p], W.HRSRC)
size = api('SizeofResource', [W.HMODULE, W.HRSRC], W.DWORD)
read = api('LoadResource', [W.HMODULE, W.HRSRC], W.HGLOBAL)
lock = api('LockResource', [W.HGLOBAL], C.c_void_p)
callback_type = C.WINFUNCTYPE(W.BOOL, W.HMODULE, C.c_void_p, C.c_void_p, C.c_ssize_t)
enum = api('EnumResourceNamesW', [W.HMODULE, C.c_void_p, callback_type, C.c_ssize_t], W.BOOL)
open_process = api('OpenProcess', [W.DWORD, W.BOOL, W.DWORD], W.HANDLE)
close = api('CloseHandle', [W.HANDLE], W.BOOL)
query = api('QueryFullProcessImageNameW', [W.HANDLE, W.DWORD, W.LPWSTR, C.POINTER(W.DWORD)], W.BOOL)

def extract_icons(path):
    """Repackage RT_GROUP_ICON + RT_ICON without decoding/resampling images."""
    module = load(str(path), None, 0x22)  # Resource/data only; never execute the file.
    if not module:
        raise C.WinError(C.get_last_error())
    try:
        names = []
        @callback_type
        def collect(_module, _kind, name, _param):
            names.append(name if name <= 65535 else C.wstring_at(name))
            return True
        if not enum(module, 14, collect, 0):
            error = C.get_last_error()
            if error in (1813, 1814):
                return []
            raise C.WinError(error)
        def resource(name, kind):
            holder = C.c_wchar_p(name) if isinstance(name, str) else C.c_void_p(name)
            ref = find(module, C.cast(holder, C.c_void_p), kind)
            if not ref:
                raise C.WinError(C.get_last_error())
            length = size(module, ref)
            address = lock(read(module, ref))
            if not address or not length:
                raise RuntimeError('Empty or unreadable icon resource')
            return C.string_at(address, length)
        results = []
        for name in names:
            group = resource(name, 14)
            reserved, kind, count = struct.unpack_from('<HHH', group)
            if reserved or kind != 1 or not count or len(group) < 6 + count * 14:
                raise ValueError('Invalid icon group')
            entries, images, dimensions = [], [], []
            offset = 6 + count * 16
            for i in range(count):
                w, h, colors, zero, planes, bits, length, ident = struct.unpack_from('<BBBBHHIH', group, 6 + i * 14)
                data = resource(ident, 3)
                if len(data) != length:
                    raise ValueError('Icon resource length mismatch')
                entries.append(struct.pack('<BBBBHHII', w, h, colors, zero, planes, bits, len(data), offset))
                images.append(data)
                dimensions.append((w or 256, h or 256, bits))
                offset += len(data)
            results.append((name, struct.pack('<HHH', 0, 1, count) + b''.join(entries + images), dimensions))
        return results
    finally:
        free(module)

def processes():
    psapi = C.WinDLL('psapi', use_last_error=True)
    fn = psapi.EnumProcesses
    fn.argtypes = [C.POINTER(W.DWORD), W.DWORD, C.POINTER(W.DWORD)]
    fn.restype = W.BOOL
    capacity = 4096
    while True:
        pids = (W.DWORD * capacity)()
        used = W.DWORD()
        if not fn(pids, C.sizeof(pids), C.byref(used)):
            raise C.WinError(C.get_last_error())
        if used.value < C.sizeof(pids):
            break
        capacity *= 2
    result = []
    for pid in pids[:used.value // C.sizeof(W.DWORD)]:
        handle = open_process(0x1000, False, pid)
        if not handle:
            continue
        try:
            buf, length = C.create_unicode_buffer(32768), W.DWORD(32768)
            if query(handle, 0, buf, C.byref(length)):
                result.append((Path(buf.value).name, pid, buf.value))
        finally:
            close(handle)
    return sorted(result, key=lambda row: (row[0].lower(), row[1]))

def main():
    from PIL import Image, ImageTk
    root = tk.Tk()
    root.title('Process Icon Extractor')
    root.geometry('940x650')
    frame = ttk.Frame(root, padding=14)
    frame.pack(fill='both', expand=True)
    ttk.Label(frame, text='Original Windows icons — lossless ICO export', font=('Segoe UI', 14, 'bold')).pack(anchor='w')
    ttk.Label(frame, text='Select a process or open an EXE/DLL. Protected/exited processes may be unavailable.').pack(anchor='w', pady=(4, 10))
    bar = ttk.Frame(frame)
    bar.pack(fill='x')
    search = tk.StringVar()
    ttk.Label(bar, text='Filter:').pack(side='left')
    ttk.Entry(bar, textvariable=search, width=30).pack(side='left', padx=6)
    tree = ttk.Treeview(frame, columns=('name', 'pid', 'path'), show='headings', height=12)
    for col, width in [('name', 220), ('pid', 70), ('path', 570)]:
        tree.heading(col, text=col.upper() if col == 'pid' else col.title())
        tree.column(col, width=width)
    tree.pack(fill='both', expand=True, pady=10)
    choice = ttk.Combobox(frame, state='readonly')
    choice.pack(fill='x')
    preview = ttk.Label(frame)
    preview.pack(anchor='w', pady=10)
    status = tk.StringVar(value='Choose a process to inspect its embedded icon groups.')
    ttk.Label(frame, textvariable=status, wraplength=880).pack(anchor='w')
    rows, icons, photos = [], [], []
    source = ['']

    def filter_rows(*_):
        tree.delete(*tree.get_children())
        for row in rows:
            if search.get().casefold() in (' '.join(map(str, row))).casefold():
                tree.insert('', 'end', values=row)
    def refresh():
        try:
            rows[:] = processes()
            filter_rows()
        except Exception as exc:
            messagebox.showerror('Process list', str(exc))
    def show_icon(*_):
        photos.clear()
        preview.configure(image='')
        index = choice.current()
        if index < 0:
            return
        name, data, dims = icons[index]
        try:
            im = Image.open(io.BytesIO(data))
            native = sorted(im.ico.sizes())
            canvas = Image.new('RGBA', (sum(w + 16 for w, h in native), max(h for w, h in native) + 8), '#f0f0f0')
            x = 0
            for dim in native:
                pic = im.ico.getimage(dim).convert('RGBA')
                canvas.alpha_composite(pic, (x, 4))
                x += dim[0] + 16
            photos.append(ImageTk.PhotoImage(canvas))
            preview.configure(image=photos[-1])
            status.set(f'{source[0]} | Group {name} | Native frames: ' + ', '.join(f'{w}×{h} ({b} bit)' for w, h, b in dims))
        except Exception as exc:
            status.set(f'Preview unavailable ({exc}); original ICO bytes can still be exported.')
    def inspect(path, default=False):
        try:
            icons[:] = extract_icons(path)
            if default:
                # Modern blue-and-white generic process icon, verified locally.
                icons[:] = [item for item in icons if item[0] == 15]
            source[0] = str(path)
            choice['values'] = [f'Icon group {name} — {len(dims)} original frames' for name, _, dims in icons]
            choice.set('')
            preview.configure(image='')
            if icons:
                choice.current(0)
                show_icon()
            else:
                status.set('No embedded icon group found. Task Manager may use a Windows fallback or a window-provided icon. Use Windows default below for the generic application icon.')
        except Exception as exc:
            icons.clear()
            choice.set('')
            preview.configure(image='')
            messagebox.showerror('Cannot read icons', str(exc))
    def selected(*_):
        selection = tree.selection()
        if selection:
            inspect(tree.item(selection[0], 'values')[2])
    def browse():
        path = filedialog.askopenfilename(filetypes=[('Windows resources', '*.exe *.dll *.mun *.cpl'), ('All files', '*.*')])
        if path:
            inspect(path)
    def save():
        index = choice.current()
        if index < 0 or index >= len(icons):
            messagebox.showinfo('Choose an icon', 'Select a process, a file, or Windows default first.')
            return
        path = filedialog.asksaveasfilename(defaultextension='.ico', initialfile=Path(source[0]).stem + '-icon.ico', filetypes=[('Windows icon', '*.ico')])
        if path:
            try:
                Path(path).write_bytes(icons[index][1])
                status.set(f'Saved all original frames without resampling: {path}')
            except OSError as exc:
                messagebox.showerror('Export failed', str(exc))
    ttk.Button(bar, text='Refresh processes', command=refresh).pack(side='left', padx=6)
    ttk.Button(bar, text='Open EXE / DLL…', command=browse).pack(side='left')
    bottom = ttk.Frame(frame)
    bottom.pack(fill='x', pady=(12, 0))
    ttk.Button(bottom, text='Windows process icon (blue and white)', command=lambda: inspect(Path(os.environ['SystemRoot']) / 'System32/imageres.dll', True)).pack(side='left')
    ttk.Button(bottom, text='Export original .ICO…', command=save).pack(side='right')
    ttk.Label(frame, text='Task Manager may use window icons or cached icons. Embedded resources do not guarantee an identical live display.').pack(anchor='w', pady=(8, 0))
    tree.bind('<<TreeviewSelect>>', selected)
    choice.bind('<<ComboboxSelected>>', show_icon)
    search.trace_add('write', filter_rows)
    refresh()
    inspect(Path(os.environ['SystemRoot']) / 'System32/imageres.dll', True)
    root.mainloop()

if __name__ == '__main__':
    main()
