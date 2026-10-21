# Quiet Capture Demo — Windows

A windowless capture and character-replay app for a staged recording. No PyCharm plugin, taskbar button, tray icon, overlay, capture sound, clipboard access, or automatic screenshot/code files. It remains a normal, inspectable Windows process. This is a prototype: actual mouse hardware, your keyboard layout, PyCharm, and the recorder require a rehearsal.

## Setup

1. Keep this folder in its final location. Install Python 3.11+ if needed.
2. Open PowerShell in this folder and run `powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1`. This installs Pillow into a local virtual environment and creates a Start menu shortcut. Setup is visible; do it before recording. No administrator privileges are required.
3. Enter your Gemini key at the masked local prompt. Do not send it in chat. It is encrypted with Windows DPAPI for your Windows user and stored as `key.dpapi`. Other programs running as your user can decrypt it. The key exists in plaintext in memory during use. `GEMINI_API_KEY`, if present, overrides this file.
4. In `config.json`, set `rehearsal` to `true` for the first test. Button 5 will load a fixed short Python snippet without a capture or network call. Set it back to `false` for Gemini. Model and language are configurable; the default is `gemini-3.8-flash` / Python 3. Availability depends on your API account.
5. Press **Ctrl+Alt+F8** to start. The shortcut launches `pythonw.exe`, without a console. Windows Explorer must be running for the shortcut hotkey. If another app owns the same shortcut, change its Shortcut key in the Start menu shortcut properties. The shortcut is discoverable and can also be launched manually; this is a convenience trigger, not an access-control mechanism.

Nothing is installed in PyCharm. A Quiet Capture shortcut in your Windows Startup folder launches the app at sign-in. No service or scheduled task is installed. Moving the folder requires running setup again.

## Controls

| Input | Action |
| --- | --- |
| Ctrl+Alt+F8 | Start the app; a second instance exits |
| Ctrl+Alt+F9 | Pause/resume, clear capture and answer; starts paused with start_paused=true |
| Ctrl+Alt+F12 | Exit and release hooks |
| Hold mouse Button 4, drag, release | Capture the rectangle between start and end points |
| Mouse Button 5 | Send the most recent capture to Gemini; repeated presses during an in-flight request are ignored |
| Hold Right Alt and tap keys | One output character per distinct key press, in the foreground allowed app |
| Right Alt+Escape | Discard capture/answer |
| Ctrl+Alt+F10 | Explicitly write `status.txt` with status and character counts for diagnosis |

Release Right Alt before using the Ctrl+Alt controls. Modifiers do not advance output. Holding a letter down does not repeat output: release and tap again. While waiting, after exhaustion, or after an error, taps are swallowed. Right Alt outside an allowed app retains its normal behavior. Button 4 and Button 5 retain normal behavior when paused or exited. Hardware utilities must expose these buttons as standard Windows XBUTTON1/XBUTTON2, not remap them to shortcuts.

There is deliberately no selection border: aim the pointer at one corner and release at the opposite corner. Capture occurs in a worker just after release, so moving screen content may differ slightly from the exact release instant. A new capture invalidates the previous answer. Pausing/discarding cannot retract an API request already sent, but its eventual result is ignored. There is no application request timeout: it waits for a response, a server error, or a network failure. A silent open connection can wait indefinitely. While a request is pending, new sends are ignored. To abandon a stuck request, close the debug console (or exit the windowless app) and relaunch; Ctrl+Alt+F12 cancels locally; Ctrl+Alt+F9 only pauses input.

## PyCharm rehearsal

Use a blank scratch Python file. Put the caret in the editor before holding Right Alt. Type the rehearsal snippet, release Right Alt, and compare the resulting text with:

```python
def demo():
    return "ready"

print(demo())
```

In PyCharm settings, search for and disable automatic indentation on Enter, automatic paired brackets/quotes, and completion popups if these modify the snippet. These are ordinary editor preferences, not a plugin. The app does not change these settings. Indentation is sent literally, one space per tap; Enter still goes through the editor's normal handler. Exact behavior is not verified on your PyCharm version. If editor automation cannot be disabled sufficiently, this version cannot promise exact reproduction.

The allowlist checks the foreground process (`pycharm64.exe` or `pycharm.exe` by default), not the selected file or focused widget. It cannot distinguish an editor from PyCharm's search box, terminal, or dialog. Click the intended editor deliberately. You can add other process names in config, but they have the same limitation. Switching foreground windows stops replay for that Right Alt hold; release and re-hold to target the next window. There is a small OS focus-change race between the foreground check and input injection. Do not switch windows while replaying. Right Alt may be AltGr on international layouts, which can generate extra Ctrl events; rehearse with your actual layout. Secure desktop inputs and some OS-reserved shortcuts cannot be intercepted.

Run the app and editor at the same privilege level (normally neither as administrator). Windows can block input into elevated applications. The model can produce incorrect code or prose despite the prompt; the app does not execute, validate, or guarantee a correct solution. Truncated, blocked, and empty API responses are rejected. Optional outer Markdown fences are removed.

## Observable evidence and traces

* **On the recording:** pointer movement, the selection drag motion, generated code appearing, editor suggestions, syntax highlighting, and errors can be visible. The app creates no visible UI, but this is not a guarantee against every recording or monitoring product. Setup terminals, Explorer, config files, status files, and Task Manager will be visible if you open them while recording.
* **Windows:** `pythonw.exe`, its command line and loaded libraries, input hooks, and screen-capture activity remain observable. Windows marks synthesized input as injected. This app does not mask those flags or hide itself from Task Manager or security software. Security software can raise its own notifications.
* **Disk:** this folder, source, virtual environment, encrypted key, and Start menu shortcut are persistent. Explicit diagnostic output goes to `status.txt`; startup failures write only an exception class to `startup-error.txt`. Python is launched with `-B` to avoid new bytecode caches during ordinary use. Installation/testing can create caches and package-manager records. Windows, antivirus, crash reports, backups, pagefiles, and hibernation can preserve additional data. In-memory images/code are not a secure-erasure guarantee.
* **Network/provider:** Button 5 transmits the selected screen content and prompt to Google over HTTPS. Network monitoring may observe the destination and traffic timing; managed endpoints may inspect more. API account usage, billing, and provider retention are outside this app's control. Only capture content you intend to send.
* **Editor:** output becomes real file content and may enter PyCharm local history, autosaves, version control, backups, or terminal history if the wrong widget is focused.

This implementation does not erase OS logs or bypass monitoring. Closing the app releases its hooks; uninstalling does not erase historical records.

## Diagnosis and removal

Press Ctrl+Alt+F10, then inspect `status.txt` outside recording. States include `captured`, `waiting`, `ready`, `finished`, `api-http-401/403/429`, `input-blocked`, and local error class names. No response body or credential is logged. If nothing happens at launch, inspect `startup-error.txt`; hotkey conflicts are a possible cause. Status files are snapshots and may be stale. For a visible local debugging run, use `.\.venv\Scripts\python.exe -B app.py`.

To remove: exit with Ctrl+Alt+F12, remove the **Quiet Capture Demo** shortcut from your Start menu Programs folder, then delete this app folder if no longer needed. If necessary, identify its `pythonw.exe` command line in Task Manager and end only that process.

## Verification and sources

Run `python -B -m unittest -v test_core.py test_windows.py`. All 12 tests passed during creation. Tests cover selection geometry, stale response rejection, output exhaustion, request composition, rejection of truncated responses, input packet layout, key suppression, and focus changes. They make no API calls and install no hooks. A separate paused native smoke test successfully registered/released both hooks and all three runtime hotkeys, then exited. No screenshot or API request was made during that smoke test. Live Gemini generation, the actual mouse, and exact replay in PyCharm have not been verified.

API: https://ai.google.dev/gemini-api/docs/generate-content/image-understanding

Input behavior: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput

Injected flags: https://learn.microsoft.com/en-us/windows/win32/winmsg/lowlevelkeyboardproc

## Temporary debug console

Double-click `debug.cmd` to run continuously with a visible status console. In this debug mode only, Ctrl+Alt+F12 pauses capture and typing without ending the process. Ctrl+Alt+F9 toggles pause/resume. Release Right Alt before these hotkeys. There is no restart menu during normal use; close the console to stop the debug process. Restart the launcher to load code or configuration changes.

The console shows startup stages, button events, capture/request status, timing, HTTP errors, and failure source locations. It does not print API keys, screenshots, generated code, or response bodies, and does not save a console log. If startup fails or the process ends unexpectedly, the launcher keeps the output visible for inspection.

This behavior is temporary and enabled only by `--debug`. Normal windowless mode launched with Ctrl+Alt+F8 still exits on Ctrl+Alt+F12. Close the debug console before starting windowless mode.

## Starting and enabling capture

With `start_paused=true` in config.json, launching the program starts its background hotkey listener with capture and typing OFF. Ctrl+Alt+F9 toggles them ON/OFF. Debug output explicitly reports each toggle. Ctrl+Alt+F8 launches the normal windowless app when it is not already running; it does not enable capture.

`enable-startup.ps1` installs a shortcut named Quiet Capture in your Windows Startup folder. It starts the windowless app at sign-in, initially paused with the current configuration. To disable sign-in startup, remove only Quiet Capture.lnk from the folder opened by Win+R, `shell:startup`. The Python process remains identifiable as pythonw.exe in Task Manager.

## Cancelling requests

Ctrl+Alt+F12 now clears the capture, answer, and queued actions, closes the active request connection locally, and frees the request slot. Debug mode stays paused; windowless mode exits. Closing the process also closes its connections. No fixed request timeout is imposed. Cancelling locally cannot guarantee Google stops processing a request it already received, and requests from earlier closed instances cannot be recalled. A connection still resolving DNS or establishing TLS may take time to unwind, but its cancelled result cannot be used.

## Opening debug while the app is already running

The debug launcher attaches a status monitor instead of exiting. It checks the running app every half second and prints changes plus a heartbeat every ten seconds. It shows capture ON/OFF, request pending/none, and app status. The attached monitor does not install input hooks or alter the owner process. Closing it leaves that process running. F12 follows the owner mode: pause/cancel for debug, exit/cancel for windowless. Status is shared in memory only. An older running version must be restarted once to publish status; otherwise the monitor explicitly reports state unknown. The monitor stays open if the app stops and detects a later relaunch.

Right Alt release pauses replay and keeps the current answer position. Holding it again resumes from the next unsent character. Queued taps from an earlier hold are discarded without advancing the answer. Debug logs show REPLAY PAUSED/RESUMED and position counts. Ordinary typing while Right Alt is released does not advance the generated answer; manual edits may therefore make the document diverge from it. Editor auto-indent and automatic bracket/quote insertion still need to be disabled for exact replay.
