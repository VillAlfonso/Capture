# PyCharm + Capture

## Custom name, publisher and version

Run `.\.venv\Scripts\python.exe -B customize_launcher.py` from C:\quiet-capture.
Enter your preferred label, publisher text, four-part version, and local
PyCharm Community 2024.1.3 path. The script rebuilds the launcher; it does not
edit a previously built EXE in place or start either application.

It updates the EXE name, ProductName, InternalName, OriginalFilename,
CompanyName, FileVersion/ProductVersion, and setup/error window title. The name is used as entered, with no forced suffix. The original PyCharm icon remains. The stable settings folder is still
%LOCALAPPDATA%\PyCharmCaptureLauncher, so an existing setup can be reused.

Output: `dist\Launcher\<Label>.exe`. The same name replaces its old
output; a different name leaves the old EXE intact. Update shortcuts yourself.

Noninteractive equivalent:

```powershell
.\.venv\Scripts\python.exe -B build_launcher.py --pycharm 'C:\path\bin\pycharm64.exe' --label Study --company 'My Tools' --version 2.0.0.0
```

Transfer `dist/Launcher/<Label>.exe` with your independently built
capture app. PyCharm Community Edition 2024.1.3 must already be installed.
The launcher does not include or install PyCharm or the capture app.

On first launch, select that installation's `bin/pycharm64.exe` and then your
capture EXE (not its monitor). The launcher checks PyCharm's product-info.json
for Community product code PC and version 2024.1.3. It then launches capture with
--start-paused and opens PyCharm. Capture's own setup may appear if needed.
The launcher exits and does not revive terminated processes. A running capture
instance's existing state is governed by its single-instance protection.

Saved paths are in `%LOCALAPPDATA%/PyCharmCaptureLauncher/settings.json`.
To change them, launch with `--setup`; this saves settings without opening apps.
Paths must be selected again after transferring to a new computer.

The launcher has the original installed PyCharm icon, with the filename and
metadata selected in the builder. Original PyCharm files,
shortcuts and startup entries are unchanged. Neither app is stopped when the
launcher exits. Closing one app does not close the other.

Build again with:

```powershell
cd C:\quiet-capture
.\.venv\Scripts\python.exe -B build_launcher.py --pycharm 'C:\path\to\PyCharm-2024.1.3\bin\pycharm64.exe'
```

Three mock launch/version tests and the packaged Tk self-test were checked on
the build computer. A full launch of both applications and Windows 11 behavior
must still be tested on the destination machine.
