# Desktop Domo

A small floating chat bubble for the desktop that talks to Claude. Click the
semi-transparent bubble in the bottom-right corner to open a chat window;
type a message and Claude replies.

Built with Python + PySide6, using the official `anthropic` SDK. Personal,
local tool DEFINATELY not production-grade haha.

Runs on Windows and Linux.

## Setup

### Windows

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

That creates `.venv\`, installs the dependencies, builds `icon.ico`, and adds
a **Desktop Domo** entry to the Start Menu. Re-running it is safe. Pass
`-NoShortcut` to skip the Start Menu entry.

### Linux

```bash
python -m venv .venv && ./.venv/bin/pip install -r requirements.txt
```

A desktop entry can be installed at
`~/.local/share/applications/desktop-domo.desktop`.

### API key

Put your Anthropic API key in `.env.local`:

```
ANTHROPIC_API_KEY=sk-ant-...
```

An `ANTHROPIC_API_KEY` already exported in your environment takes precedence.

## Running it

| | |
|---|---|
| **Windows, everyday** | Double-click `run.cmd`, or search **"Desktop Domo"** in the Start Menu. |
| **Windows, debugging** | `powershell -ExecutionPolicy Bypass -File .\run.ps1` — same app, but on a console so tracebacks are visible. |
| **Linux** | `./run.sh` |

Neither window shows up in the taskbar, so there are three ways out:

- The **KILL** button in the chat header quits everything.
- **Quit Desktop Domo** in the tray icon's right-click menu.
- `Ctrl+C` in the terminal, if you launched it from one.

The ✕ button only *hides* the chat — the bubble stays alive. The tray icon
also lets you hide the bubble itself and get it back later, which is handy if
it lands somewhere awkward.

## Show Claude your screen

Click the square button in the chat header to let Claude see your display.
It is **read-only and always gated**:

- The screen is captured as a **static image** — Claude can look, not act.
- A **preview dialog** shows the exact image first, with an optional question
  and **Send to Claude / Cancel**. Nothing leaves your machine until you click
  Send.
- Your chat window and the bubble are hidden during capture so they aren't in
  the shot.
- Screenshots **are never written to disk**. On Windows the capture happens
  entirely in memory; on Linux it goes through a transient temp file
  (RAM-backed `XDG_RUNTIME_DIR`) that's deleted immediately. Either way the
  image data is stripped to a `[screenshot]` placeholder before the transcript
  is saved to `history.json`.
- A sent screenshot stays in the in-memory conversation for the session, so
  follow-up questions work.

## Web search

Domo can look things up. The server-side `web_search` tool is attached to
every request, so searching runs on Anthropic's side — nothing extra is
installed locally, and there's no separate API key. Turn it off with
`ENABLE_WEB_SEARCH = False` in `desktop_domo/config.py`.

## Layout

| File | What it does |
|------|--------------|
| `desktop_domo/bubble.py` | The round floating bubble (hover, click) |
| `desktop_domo/chat.py`   | The chat window (transcript, input, expand/shrink) |
| `desktop_domo/api.py`    | Claude client + background request thread |
| `desktop_domo/config.py` | Settings, paths, API-key loading |
| `desktop_domo/history.py`| Load/save the conversation (strips screenshots) |
| `desktop_domo/screenshot.py`| Read-only screen capture backend (per-OS) |
| `desktop_domo/main.py`   | App entry point, tray icon |
| `make_icon.py`           | Builds `icon.ico` for the Windows shortcut |
| `setup.ps1` / `run.cmd` / `run.ps1` | Windows setup and launchers |
| `run.sh`                 | Linux launcher (sets XWayland, uses the venv) |

## Things you might want to tweak

Everything below lives in `desktop_domo/config.py` unless noted.

- **Which model:** `MODEL`. Currently `claude-fable-5-1` — the most capable
  model, but it always runs extended thinking, so it's slower and pricier
  ($10/$50 per 1M tokens) than `claude-opus-5` ($5/$25).
- **How hard it thinks:** `EFFORT` (`low` … `max`). `medium` keeps replies
  snappy; raise it for harder questions.
- **Reply length:** `MAX_TOKENS`. Thinking tokens count against this, so don't
  set it too low or answers get cut off mid-sentence.
- **Personality:** `SYSTEM_PROMPT`.
- **Bubble look:** size, colour, opacity, position — constants at the top of
  `desktop_domo/bubble.py`.
- **Start fresh:** delete `history.json` to clear the saved conversation.
