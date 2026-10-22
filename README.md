# Quiet Capture — Windows

One windowless background app owns the input hooks and hotkeys. A separate, read-only terminal monitors it. Opening or closing the monitor never starts, pauses, or stops capture. The app remains a normal identifiable Windows process.

## Setup and launch

Run `powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1` from this folder. Enter your OpenAI key at the masked local prompt, never in chat. Setup installs dependencies and a Quiet Capture shortcut in your Windows Startup folder. At sign-in, the app starts paused and listens for Ctrl+Alt+F9. The current `start_paused=true` configuration controls this initial state.

- `start.cmd`: start the background app now. A named mutex prevents a second owner.
- `debug.cmd`: open the status monitor only. Close it freely; the background app keeps running.
- `stop.cmd`: explicitly stop the background app and close its request connection.
- `restart.cmd`: stop the app and start it again to load saved code/configuration changes.

Multiple Python launcher/monitor process entries can appear in Task Manager; only one app instance installs capture hooks. The monitor prints state changes plus a heartbeat every ten seconds. It reports a missing heartbeat honestly instead of assuming capture is paused. It waits for a later launch if the app stops.

## Controls

| Input | Action |
| --- | --- |
| Ctrl+Alt+F8 | Launch through the Start menu shortcut if installed |
| Ctrl+Alt+F9 | Toggle capture and replay ON/OFF; listener remains running |
| Ctrl+Alt+F12 | Cancel locally, clear capture/answer, restart the background app with fresh code/configuration; returns paused |
| Hold Button 4, drag diagonally, release | Capture the selected region without an overlay |
| Button 5 | Submit the capture; ignored while a request is already pending |
| Hold Right Alt and tap keys in PyCharm | Replay one generated character per key press |
| Release Right Alt | Pause replay and save the answer position |
| Hold Right Alt again | Resume from the next unsent character |
| Right Alt+Escape | Clear capture/answer |
| Ctrl+Alt+F10 | Explicitly write a diagnostic status.txt snapshot |

Release Right Alt before Ctrl+Alt hotkeys. Normal typing resumes outside replay. Old queued taps cannot spill into a new Right Alt hold. Manual editor changes do not adjust the generated answer position. A new capture invalidates the previous answer.

## Requests and cancellation

Screenshots are sent to OpenAI only when Button 5 is pressed. Each request contains the current screenshot and prompt; there is no conversation or screenshot history. No fixed application request timeout is imposed. A silent connection may remain pending indefinitely.

Ctrl+Alt+F12 or explicit exit closes the local connection and discards pending work. It cannot guarantee OpenAI stops processing a received request or reverse quota usage. Requests from earlier closed instances cannot be recalled. DNS/TLS establishment may take time to unwind, but a cancelled answer cannot be replayed. Ctrl+Alt+F9 pauses input but does not cancel a pending request.

The monitor reports `api-http-503` when the API returned HTTP 503; this is distinct from local process state. A missing API response cannot establish quota exhaustion or key validity.

## Rehearsal and editor behavior

Set `rehearsal=true` in config.json and restart for an offline test. Button 5 loads a fixed Python snippet without sending a request. Set it back to false and restart for OpenAI.

PyCharm auto-indent, bracket/quote pairing, and completion may alter character-by-character output. Disable these editor features for exact replay. The app checks the foreground process, not whether focus is in the editor versus a search box or terminal. Keep the app and editor at the same privilege level. Actual hardware, keyboard layout, and editor behavior require rehearsal.

## Observable evidence and traces

* **On the recording:** pointer movement, the selection drag motion, generated code appearing, editor suggestions, syntax highlighting, and errors can be visible. The app creates no visible UI, but this is not a guarantee against every recording or monitoring product. Setup terminals, Explorer, config files, status files, and Task Manager will be visible if you open them while recording.
* **Windows:** `pythonw.exe`, its command line and loaded libraries, input hooks, and screen-capture activity remain observable. Windows marks synthesized input as injected. This app does not mask those flags or hide itself from Task Manager or security software. Security software can raise its own notifications.
* **Disk:** this folder, source, virtual environment, encrypted key, and Start menu shortcut are persistent. Explicit diagnostic output goes to `status.txt`; startup failures write only an exception class to `startup-error.txt`. Python is launched with `-B` to avoid new bytecode caches during ordinary use. Installation/testing can create caches and package-manager records. Windows, antivirus, crash reports, backups, pagefiles, and hibernation can preserve additional data. In-memory images/code are not a secure-erasure guarantee.
* **Network/provider:** Button 5 transmits the selected screen content and prompt to OpenAI over HTTPS. Network monitoring may observe the destination and traffic timing; managed endpoints may inspect more. API account usage, billing, and provider retention are outside this app's control. Only capture content you intend to send.
* **Editor:** output becomes real file content and may enter PyCharm local history, autosaves, version control, backups, or terminal history if the wrong widget is focused.

This implementation does not erase OS logs or bypass monitoring. Closing the app releases its hooks; uninstalling does not erase historical records.

## Removal and verification

Run stop.cmd. Remove Quiet Capture.lnk from the folder opened with Win+R, `shell:startup`, to disable sign-in startup. Remove the Quiet Capture Demo shortcut from Start menu Programs if no longer wanted.

Run `.\.venv\Scripts\python.exe -B -m unittest test_core.py test_windows.py`. Tests use mocked input and API operations and do not send screenshots to OpenAI.

The monitor shows the latest 50 diagnostic events from the current app instance when opened, then streams new events by polling shared memory every 250 ms. App publication also runs every 250 ms, so this is near-live rather than hard real-time. Event IDs prevent duplicates. History is bounded and memory-only, and resets when the app restarts. Events include capture, request stages, HTTP diagnostics, cancellation, and replay pause/resume; no key, screenshot content, or generated answer is logged.

Right Alt + Backspace deletes one replayed character and rewinds the answer by one, so the next normal replay tap types it again. It also works after the answer finishes. At position zero or before an answer is available it does nothing. Each distinct Backspace press erases once. Keep the caret at the end of the replayed text, with no selection; editor smart-backspace, auto-indent, or automatic bracket pairing can delete more than one character and break correspondence. Backspace outside Right Alt remains ordinary editor input and does not rewind the answer.

Ctrl+Alt+F12 now restarts the background app instead of only pausing. The old instance releases its hotkeys/hooks and singleton mutex before launching the new instance. The replacement reloads code, config, and key on the next request, starts paused, and responds to Ctrl+Alt+F9. The monitor remains open and detects the new PID. The answer and capture are discarded. Use Ctrl+Alt+F9 for a pause without restart and stop.cmd for an explicit stop without relaunch.

## Packaged executable

The maintained package uses QuietCapture.exe and QuietCaptureMonitor.exe, with the image from icon.png embedded in both. See PACKAGING.md for rebuild steps, changing your own app name/icon, and the distinction between source changes (rebuild required) and configuration changes (restart sufficient). Startup and launch scripts read package-paths.json. Existing older build artifacts are not used.

## OpenAI key and migration

Run `powershell -NoProfile -ExecutionPolicy Bypass -File .\set-openai-key.ps1` and paste your OpenAI key into the hidden prompt. The key is encrypted for your Windows user in openai-key.dpapi. OPENAI_API_KEY overrides it. The old Gemini key.dpapi is preserved but is never used by the OpenAI code. The default model is gpt-5.6-terra and can be changed in config.json. Requests use https://api.openai.com/v1/responses with screenshot image input and store=false. API access and billing belong to your OpenAI API project.

Existing executables still contain the previous provider code. Rebuild a clearly named QuietCapture package before using the saved OpenAI key; simply restarting an old Gemini executable does not migrate it. No live API request was made during migration tests.
