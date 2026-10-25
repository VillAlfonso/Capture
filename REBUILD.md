# Reusable named builds

Each EXE has its own manually entered copyright field. The builder stores exactly
that text in LegalCopyright; blank stays blank. It no longer generates copyright
from the publisher or year. This text does not add a digital signature.

## Graphical builder

Double-click `open-builder.cmd`, or run `.\.venv\Scripts\python.exe -B builder_gui.py`.
The interface collects the app/monitor names, launcher label/publisher/version,
separate publisher and four-part version fields for the capture app and monitor,
installed PyCharm Community 2024.1.3 path, and a transfer-output folder.
Click **Build all three EXEs**. Live compiler output appears in the window;
success enables **Open transfer folder**. Each successful run creates a new
timestamped transfer folder with exactly the three EXEs, never keys or settings.
The capture app keeps the current generic icon; the launcher uses PyCharm's icon.
The build environment still needs PyInstaller/Pillow/tkinter. The destination
laptop only needs the built EXEs and its PyCharm installation.
The GUI never starts those apps or changes startup. Wait for compilation to
finish before closing the window. Existing same-named intermediate build outputs
are replaced by the underlying builders; existing transfer folders are retained.

Run from PowerShell:

```powershell
cd C:\quiet-capture
.\.venv\Scripts\python.exe -B rebuild.py
```

Enter an app name and monitor name without .exe. Enter accepts the displayed
default. Names must be distinct, valid Windows filenames. There are no custom name or publisher blacklists, ASCII-only rules, or 48-character limits. Launcher names are used as entered, without an added suffix.
This creates two single-file EXEs in `dist\Windows11-Portable\<AppName>\`.
The builder uses the project virtual environment when available and requires
PyInstaller, Pillow and tkinter on the build computer. Those dependencies are
bundled for the destination laptop. It does not install dependencies automatically.

Optional noninteractive example:

```powershell
.\.venv\Scripts\python.exe -B rebuild.py --name StudyCapture --monitor-name StudyMonitor
```

To embed an icon, add `--icon .\icon.png` (or an .ico file). Without that option,
the current generic-icon behavior is preserved.

The name updates the EXE filename, FileDescription, ProductName, InternalName,
OriginalFilename, CompanyName, setup/error window titles, monitor labels, startup
diagnostic name, and `%LOCALAPPDATA%\<AppName>` settings folder. Descriptions retain
the functional labels "capture utility" and "status monitor". Source filenames,
internal logger name, environment variable and the shared mutex/status channel
are intentionally stable, ensuring differently named builds cannot install two
capture hooks. The matching monitor observes that same shared app instance.

Changing the app name selects a new data folder and requires first-run setup
again; old keys/settings are not deleted or migrated. Old build folders are kept.
Rebuilding the same name overwrites that named output; close it first. Update
any external launcher or shortcut to point at the new EXE path yourself.

PyCharm selection and automatic PyCharm launching have been removed. The app
starts capture only, paused. API/model/Wi-Fi first-run setup remains. Legacy
pycharm_path settings are ignored and removed when setup is saved. Your separate
launcher can start this EXE with --start-paused and start PyCharm independently.

No running process, startup shortcut, current package-paths.json or existing EXE
is changed merely by editing the source. Run the builder to produce the update.
