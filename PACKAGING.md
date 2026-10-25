# Executables, names, and icons

The app is `QuietCapture.exe`; the optional monitor is `QuietCaptureMonitor.exe`. Both omit embedded icons (`--icon NONE`) so Windows/Task Manager can select its generic fallback. The exported ICO and PNG files are reference assets and are not used by the build. Names and file descriptions remain identifiable as QuietCapture.

## Rebuild with your own application name

Use an identifiable name for your app, for example StudyCapture. In PowerShell:

```powershell
cd C:\quiet-capture
.\stop.cmd
# Close monitor windows before rebuilding their executable.
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1 -AppName StudyCapture -MonitorName StudyCaptureMonitor
.\start.cmd
```

The build updates executable filenames, internal names, product names, file descriptions, embedded icons, package-paths.json, and startup/manual shortcuts together. Do not simply rename an executable: shortcuts and restart paths may otherwise become inconsistent. The build script needs PyInstaller and Pillow in .venv. Both were installed during packaging.

Task Manager's Details tab shows executable filenames. Its Processes tab may show the embedded file description. The monitor's console can also have a Windows-owned host process such as cmd.exe or Windows Terminal; these system components retain their own names/icons. This build does not rename Python itself, Windows processes, or unrelated programs. Explorer/Task Manager can cache icons until refreshed or reopened.

## Files and restart

Keep the project folder in place: executables load the external config.json and encrypted key.dpapi from it. Credentials are NOT embedded in the executables or copied to dist. A distributable would require separate user setup; do not share key.dpapi.

Ctrl+Alt+F12 restarts the packaged executable and reloads configuration/key settings. Source-code changes require running build.ps1 again; restarting cannot update code already compiled into an executable. Use stop.cmd to stop without restarting. The monitor remains optional and independent.

One-directory builds keep dependencies in their matching dist subfolder. Do not move just the EXE without its _internal directory. Older build artifacts are retained, but current launchers use only package-paths.json.

## Point startup to an already-built executable

From the project folder, validate first:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\enable-startup.ps1 -ExecutablePath ".\dist\StudyCapture\StudyCapture.exe" -CheckOnly
```

Then run the same command without `-CheckOnly` to save the Startup and Start menu shortcuts. Use the path to your main app, not the monitor. It must be a compatible build with the current config.json layout. No app is launched. Relative paths resolve from the script folder. For a different drive, an absolute path is accepted.

This changes startup/manual shortcuts only. The start.cmd/debug.cmd/restart.cmd launchers use package-paths.json. Building through build.ps1 updates that manifest and startup together, so it is the simplest way to keep a newly named main app and monitor consistent. Stop the app and close the monitor before rebuilding files that are in use. After rebuilding, Ctrl+Alt+F12 restarts an already-running instance of the same executable; if changing to another name or path, stop the old instance and launch the new one.
# Temporary Wi-Fi for API requests

## Experimental PyCharm Tab replay

`pycharm_tab_replay: true` enables an experimental append-only replay mode.
Use an empty Python file, a single caret at its beginning, and PyCharm Python
code style with Use tab character OFF, Tab size 4, and Indent 4. Disable paired
insertion and automatic completion that can change the generated text. Do not
move the caret or edit existing text during replay. This mode has simulated
tests, not verified compatibility with PyCharm 2024.1.3.

Each newline sends Enter, waits briefly, selects the prefix using Shift+Home,
and deletes it before sending the generated indentation with Tab and leftover
spaces. One typing tap processes the newline and indentation together. Delete
is used for cleanup so an empty final line is not joined to the previous line.
The prefix is assumed to contain only auto-inserted whitespace: it is not read
back from the editor. Therefore this must not be used to insert into existing
code. Right Alt+Backspace selects/deletes one previous character instead of
using PyCharm's configurable smart Backspace. Partial failures pause replay;
start a fresh capture in an empty editor rather than retrying that operation.

Set `pycharm_tab_replay` to false to restore the previous character-by-character
mode. A rebuild is required for this new feature. Compare the saved editor file
with debug-last-answer.txt before considering the indentation issue resolved.

`config.json` now includes `temporary_wifi_profile: "MAKATI"`. Remove that field
or set it to an empty string to disable automatic Wi-Fi connection management.
This feature requires rebuilding the app; restarting an old executable is not enough.

Before loading the API key, the app checks HTTPS reachability to OpenAI without
credentials. If reachable, it leaves all connections unchanged. Otherwise, it
requires exactly one disconnected WLAN interface with the saved MAKATI profile,
enables any software-disabled radio on that interface, and waits up to 30 seconds
for connection and HTTPS reachability. It never changes Ethernet or firewall rules.
Hardware-disabled radios and administratively disabled adapters require manual action.

After a response, failure, or cancellation, it disconnects the temporary WLAN
connection and restores any radio it enabled. If the user switches to a different
Wi-Fi profile during the request, cleanup leaves that connection alone. Connection
and cleanup outcomes appear in the monitor. Existing connected Wi-Fi is preserved.
The API request itself still has no fixed timeout: a stalled request can keep the
temporary connection active until cancelled. Forced termination, power loss, and
OS failure can bypass cleanup; exact restoration in those cases is not guaranteed.
