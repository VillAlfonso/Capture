# Process Icon Extractor

Run `dist/ProcessIconExtractor/ProcessIconExtractor.exe`, or double-click
`process-icons.cmd` to run the source using this project's environment.

Select a process, select an icon group, and click **Export original .ICO**.
The filter searches process names, PIDs, and paths. **Open EXE / DLL** also
works on files whose processes are not running. **Windows process icon (blue and
white)** reads group 15 from this Windows installation's imageres.dll. That internal
resource number is verified on this machine, not guaranteed across Windows versions.

`windows-process.ico` is an already-exported copy of that blue-and-white icon.
It contains original 16, 20, 24, 32, 40, 48, 64, and 256 pixel frames.
`windows-process-256.png` is its original largest frame for previewing.
The older `windows-default.ico` is a different green icon, not the requested one.
No screenshot cropping, tracing, enlargement, or recompression of ICO frames is used.
The preview shows each available size at native dimensions.

For crisp executable icons, supply the ICO directly to your packager (`--icon
windows-process.ico` in PyInstaller). Do not convert it to a single PNG and
regenerate all sizes. Keep the application's own name and description.
The existing capture application and its build settings are unchanged.

This is a resource extractor, not a Task Manager screenshot scraper. Task Manager
can use window-provided icons, generic fallback icons, or cached icons, so a file's
first embedded icon need not match its current Task Manager appearance. Protected
processes may not expose a path; open a readable executable manually instead.
No process is injected into or modified. Files are loaded as data/resources only.

Build the standalone GUI:

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --onedir --windowed --name ProcessIconExtractor --distpath dist --workpath build/icon-extractor --specpath build/icon-extractor process_icons.py
```

Keep the entire `dist/ProcessIconExtractor` folder together.
