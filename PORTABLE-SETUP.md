# Windows 11 portable build

Run rebuild.py as described in REBUILD.md. Transfer the two EXEs from
`dist/Windows11-Portable/<AppName>` (the names below are defaults):

- QuietCapture.exe
- QuietCaptureMonitor.exe

Python, Pillow and the setup UI runtime are bundled. The build is Windows x64;
Windows 11 has not been tested on the destination laptop. PyInstaller extracts
runtime files temporarily when a single-file executable starts. Persistent user
settings and diagnostic files live in `%LOCALAPPDATA%\<AppName>`.

Open the app EXE. First-run setup asks you to confirm
the API model and optional saved Wi-Fi profile, and enter the API key locally in
a masked dialog. A copied key.dpapi/openai-key.dpapi from another device is not
used. The new key is encrypted for the current Windows user.

After setup, opening the app starts capture paused. It no longer selects or
launches PyCharm. Use your separate launcher if you want to open both together.
The existing mutex prevents a second capture instance, including older builds.
Stop the old capture app before testing the new one. Closing PyCharm does not
stop capture. The monitor is independent.

Optional shortcut arguments:

- `--setup`: edit configuration/key using the setup dialogs, then exit.
- `--start-paused`: start only capture, without opening PyCharm.
- `--stop`: stop the capture instance gracefully.
- `--self-test`: load bundled modules without capture/network and write
  portable-self-test.txt in the user-data folder.

Ctrl+Alt+F9 toggles capture; Ctrl+Alt+F12 restarts paused without reopening PyCharm.
No automatic startup shortcut is created by this portable build. If requested,
create a clearly named current-user startup shortcut using --start-paused.
Moving an EXE requires updating any shortcut that points to it.

Use an empty Python editor with Tab size 4, Indent 4, Use tab character OFF, and
paired insertion disabled. Replay remains editor-dependent; compare saved output
with debug-last-answer.txt. Temporary replay diagnostics are enabled by default.
Wi-Fi management uses the configured saved profile, preserves Ethernet, and may
show normal Windows/app connectivity notifications. Forced termination can skip
cleanup. It has no API deadline, so an indefinitely pending request can keep a
temporary Wi-Fi connection active.

The executables need not live in System32. If placed in a protected directory,
copying/updating requires appropriate permissions; run the app as your normal
user, not administrator. No files are written into that directory at runtime.

## Prompt for setup on the laptop

Set up these existing standalone QuietCapture.exe and QuietCaptureMonitor.exe
files on this Windows 11 laptop. Do not install Python or copy an old .venv.
Inspect their location and architecture first. Do not modify PyCharm's executable.
Run the built-in first-run setup or --setup so I can enter my API key in its
local masked dialog. Never request or print the key in chat. Confirm that
configuration lives in %LOCALAPPDATA%\<AppName>, using the chosen build name.
Verify the saved Wi-Fi profile MAKATI without displaying credentials; do not
change Ethernet or firewall settings. Ask before testing network disconnection.
Use a separate explicitly named launcher for both apps if requested; do not configure
automatic startup unless I request it. Stop an older capture instance before
testing the new build. Verify the monitor shows paused, then guide me through
Ctrl+Alt+F9, capture, API request, and replay in an empty PyCharm file. Configure
Tab size 4, Indent 4 and spaces instead of tab characters. Compare actual editor
text against the saved answer. Only send a screenshot/API request when I initiate
the test. Explain anything not verified on this laptop. Do not rename either app
as a Windows component or add automatic revival after termination.
