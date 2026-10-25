"""Desktop frontend for the existing standalone builders."""
from datetime import datetime
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
from pycharm_capture_launcher import validate_pycharm
from rebuild import version_resource
from builder_names import validate_name

ROOT = Path(__file__).resolve().parent


def validate_options(values):
    options = {key: value.strip() for key, value in values.items()}
    for key in ('app_copyright', 'monitor_copyright', 'copyright', 'app_description', 'monitor_description', 'description', 'app_product_name', 'monitor_product_name', 'product_name'):
        options[key] = values.get(key, '')
    options['app'] = validate_name(options['app'])
    options['monitor'] = validate_name(options['monitor'])
    options['label'] = validate_name(options['label'])
    options['title'] = options['label']
    if len({options[key].casefold() for key in ('app', 'monitor', 'title')}) != 3:
        raise ValueError('The three executable names must be different.')
    company = options['company']
    version_resource(options['title'], 'Combined launcher', company, options['version'])
    for key in ('app', 'monitor'):
        publisher = options.setdefault(key + '_company', 'Personal project')
        version = options.setdefault(key + '_version', '1.0.0.0')
        version_resource(options[key], key, publisher, version)
    ide = validate_pycharm(options['pycharm'])
    if not (ide.parent / 'pycharm.ico').is_file():
        raise ValueError('The selected PyCharm installation is missing pycharm.ico.')
    options['pycharm'] = str(ide)
    if not options['output']:
        raise ValueError('Choose an output folder.')
    output = Path(options['output']).expanduser().resolve()
    if output.exists() and not output.is_dir():
        raise ValueError('Output must be a folder.')
    options['output'] = str(output)
    return options


def commands(options):
    python = ROOT / '.venv' / 'Scripts' / 'python.exe'
    interpreter = str(python) if python.exists() else sys.executable
    return [
        [interpreter, '-B', 'rebuild.py', '--name', options['app'], '--monitor-name', options['monitor'],
         '--app-company', options['app_company'], '--app-version', options['app_version'],
         '--monitor-company', options['monitor_company'], '--monitor-version', options['monitor_version'],
         '--app-copyright', options['app_copyright'], '--monitor-copyright', options['monitor_copyright'],
         '--app-description', options['app_description'], '--monitor-description', options['monitor_description'],
         '--app-product-name', options['app_product_name'], '--monitor-product-name', options['monitor_product_name']],
        [interpreter, '-B', 'build_launcher.py', '--pycharm', options['pycharm'],
         '--label', options['label'], '--company', options['company'], '--version', options['version'],
         '--copyright', options['copyright'], '--description', options['description'], '--product-name', options['product_name']],
    ]


def collect_outputs(options, root=ROOT):
    sources = [root / 'dist' / 'Windows11-Portable' / options['app'] / (name + '.exe')
               for name in (options['app'], options['monitor'])]
    sources.append(root / 'dist' / 'Launcher' / (options['title'] + '.exe'))
    for source in sources:
        if not source.is_file():
            raise FileNotFoundError('Build output missing: ' + str(source))
    destination = Path(options['output']) / ('Transfer-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    destination.mkdir(parents=True, exist_ok=False)
    try:
        for source in sources:
            shutil.copy2(source, destination / source.name)
    except OSError:
        # Keep partial files for inspection, but never report a complete package.
        raise OSError('Could not finish copying outputs. Incomplete folder: ' + str(destination))
    return destination


class BuilderWindow:
    def __init__(self, window):
        self.window = window
        self.running = False
        self.output = None
        self.events = queue.Queue()
        window.title('Capture Suite Builder')
        window.geometry('860x820')
        window.minsize(730, 740)
        frame = ttk.Frame(window, padding=18)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Build your transfer package', font=('Segoe UI', 18, 'bold')).pack(anchor='w')
        ttk.Label(frame, text='Three standalone EXEs: capture app, monitor, and a launcher.').pack(anchor='w', pady=(5, 14))
        form_area = ttk.Frame(frame)
        form_area.pack(fill='x')
        canvas = tk.Canvas(form_area, height=410, highlightthickness=0)
        scrollbar = ttk.Scrollbar(form_area, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='x', expand=True)
        form = ttk.Frame(canvas)
        form_id = canvas.create_window((0, 0), window=form, anchor='nw')
        form.bind('<Configure>', lambda event: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda event: canvas.itemconfigure(form_id, width=event.width))
        form.columnconfigure(1, weight=1)
        defaults = [('app', 'Capture app name', 'QuietCapture'),
                    ('app_product_name', 'Capture app product name', ''),
                    ('app_description', 'Capture app file description', ''),
                    ('app_company', 'Capture app publisher', 'Personal project'),
                    ('app_version', 'Capture app version', '1.0.0.0'),
                    ('app_copyright', 'Capture app copyright', ''),
                    ('monitor', 'Monitor name', 'QuietCaptureMonitor'),
                    ('monitor_product_name', 'Monitor product name', ''),
                    ('monitor_description', 'Monitor file description', ''),
                    ('monitor_company', 'Monitor publisher', 'Personal project'),
                    ('monitor_version', 'Monitor version', '1.0.0.0'),
                    ('monitor_copyright', 'Monitor copyright', ''),
                    ('label', 'Launcher name', 'PyCharm'),
                    ('product_name', 'Launcher product name', ''),
                    ('description', 'Launcher file description', ''),
                    ('company', 'Launcher publisher', 'Personal launcher'),
                    ('version', 'Launcher version', '1.0.0.0'),
                    ('copyright', 'Launcher copyright', ''),
                    ('pycharm', 'PyCharm Community 2024.1.3 EXE', r'C:\Morrow Glass\tools\PyCharm-2024.1.3\bin\pycharm64.exe'),
                    ('output', 'Transfer output folder', str(ROOT / 'dist' / 'TransferPackages'))]
        self.variables = {}
        self.inputs = []
        for row, (key, label, default) in enumerate(defaults):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky='w', padx=(0, 12), pady=2)
            variable = tk.StringVar(value=default)
            self.variables[key] = variable
            entry = ttk.Entry(form, textvariable=variable)
            entry.grid(row=row, column=1, sticky='ew', pady=2)
            self.inputs.append(entry)
            if key in ('pycharm', 'output'):
                button = ttk.Button(form, text='Browse…', command=lambda k=key: self.browse(k))
                button.grid(row=row, column=2, padx=(8, 0))
                self.inputs.append(button)
        ttk.Label(frame, text='Icons keep the current defaults. Builds replace same-named build outputs; transfer folders are new each time.\nNo apps will be launched and no startup shortcuts will be changed.', wraplength=790).pack(anchor='w', pady=12)
        buttons = ttk.Frame(frame)
        buttons.pack(fill='x')
        self.build_button = ttk.Button(buttons, text='Build all three EXEs', command=self.start)
        self.build_button.pack(side='left')
        self.open_button = ttk.Button(buttons, text='Open transfer folder', command=self.open_output, state='disabled')
        self.open_button.pack(side='left', padx=10)
        ttk.Button(buttons, text='Save session', command=self.save_session).pack(side='left', padx=5)
        ttk.Button(buttons, text='Load session', command=self.load_session).pack(side='left', padx=5)
        self.progress = ttk.Progressbar(frame, mode='indeterminate')
        self.progress.pack(fill='x', pady=(12, 6))
        self.status = tk.StringVar(value='Ready. Close any previous build with the same name before rebuilding.')
        ttk.Label(frame, textvariable=self.status, wraplength=790).pack(anchor='w')
        self.log = scrolledtext.ScrolledText(frame, height=15, wrap='word', state='disabled')
        self.log.pack(fill='both', expand=True, pady=(8, 0))
        window.protocol('WM_DELETE_WINDOW', self.close)
        window.after(100, self.poll)

    def save_session(self):
        path = filedialog.asksaveasfilename(parent=self.window, title='Save builder session',
                                          defaultextension='.json', initialfile='builder-session.json',
                                          filetypes=[('Builder session', '*.json')])
        if not path:
            return
        try:
            Path(path).write_text(json.dumps({key: value.get() for key, value in self.variables.items()},
                                            indent=2, ensure_ascii=False), encoding='utf-8')
        except OSError as error:
            messagebox.showerror('Could not save session', str(error), parent=self.window)
            return
        self.status.set('Session saved to ' + path)

    def load_session(self):
        if self.running:
            return
        path = filedialog.askopenfilename(parent=self.window, title='Load builder session',
                                         filetypes=[('Builder session', '*.json')])
        if not path:
            return
        try:
            values = json.loads(Path(path).read_text(encoding='utf-8'))
            if not isinstance(values, dict) or any(not isinstance(v, str) for v in values.values()):
                raise ValueError('Session must contain text fields.')
        except (OSError, ValueError) as error:
            messagebox.showerror('Could not load session', str(error), parent=self.window)
            return
        for key, value in values.items():
            if key in self.variables:
                self.variables[key].set(value)
        self.status.set('Session loaded. Review settings before building.')

    def browse(self, key):
        result = (filedialog.askdirectory(parent=self.window) if key == 'output' else
                  filedialog.askopenfilename(parent=self.window, filetypes=[('Executable', '*.exe')]))
        if result:
            self.variables[key].set(result)

    def start(self):
        try:
            options = validate_options({key: value.get() for key, value in self.variables.items()})
        except (ValueError, OSError, KeyError) as error:
            messagebox.showerror('Check build settings', str(error), parent=self.window)
            return
        self.running = True
        self.output = None
        self.open_button.configure(state='disabled')
        for widget in self.inputs + [self.build_button]:
            widget.configure(state='disabled')
        self.progress.start()
        self.status.set('Building capture app and monitor…')
        threading.Thread(target=self.worker, args=(options,), daemon=True).start()

    def worker(self, options):
        try:
            for index, command in enumerate(commands(options), 1):
                self.events.put(('status', f'Build stage {index}/2: ' + ('capture app and monitor' if index == 1 else 'combined launcher')))
                environment = os.environ.copy()
                environment['PYTHONUNBUFFERED'] = '1'
                with subprocess.Popen(command, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                      text=True, encoding='utf-8', errors='replace', env=environment,
                                      creationflags=subprocess.CREATE_NO_WINDOW) as process:
                    for line in process.stdout:
                        self.events.put(('log', line))
                    if process.wait() != 0:
                        raise RuntimeError(f'Build stage {index} failed. See the output above; no complete transfer folder was created.')
            self.events.put(('done', str(collect_outputs(options))))
        except Exception as error:
            self.events.put(('error', str(error)))

    def poll(self):
        for _ in range(250):
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == 'log':
                self.log.configure(state='normal')
                self.log.insert('end', value)
                self.log.see('end')
                self.log.configure(state='disabled')
            elif kind == 'status':
                self.status.set(value)
            else:
                self.running = False
                self.progress.stop()
                for widget in self.inputs + [self.build_button]:
                    widget.configure(state='normal')
                if kind == 'done':
                    self.output = value
                    self.open_button.configure(state='normal')
                    self.status.set('Complete. Three EXEs saved to ' + value)
                else:
                    self.status.set('Build failed.')
                    messagebox.showerror('Build failed', value, parent=self.window)
        self.window.after(100, self.poll)

    def open_output(self):
        if self.output:
            os.startfile(self.output)

    def close(self):
        if self.running:
            messagebox.showinfo('Build in progress', 'Wait for the build to finish before closing this window.', parent=self.window)
        else:
            self.window.destroy()


if __name__ == '__main__':
    window = tk.Tk()
    BuilderWindow(window)
    window.mainloop()
