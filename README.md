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

- The **✕** button in the chat's title bar quits everything.
- **Quit Desktop Domo** in the tray icon's right-click menu.
- `Ctrl+C` in the terminal, if you launched it from one.

The **–** button only *tucks the chat away* — the bubble stays alive, and
clicking it brings the chat back. The tray icon also lets you hide the bubble
itself and get it back later, which is handy if it lands somewhere awkward.

## The chat window

Styled like an old-school messenger, in dark mode: a clay title bar (drag it
to move the window), a "Chat started today at …" strip, then speech bubbles —
Domo's on the left next to its picture, yours on the right in clay, each with
the time it was sent. "Domo is typing..." shows while a reply is on its way.
Enter sends, Shift+Enter adds a line, and the grip in the bottom-right corner
resizes the window.

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

## Maths

Replies are typeset with [KaTeX](https://katex.org/), so LaTeX shows up as
actual maths instead of source. Both `$inline$` / `\(inline\)` and
`$$display$$` / `\[display\]` work, and Domo is told to use them. A literal
dollar sign is written `\$` so a price doesn't get read as the start of a
formula.

Rendering KaTeX means running JavaScript, so the transcript is a QtWebEngine
view (`desktop_domo/transcript.py` + `desktop_domo/assets/transcript.html`)
rather than a plain text box. QtWebEngine ships inside the PySide6 wheel on
both Windows and Linux, so there's nothing extra to install — it's just why
`pip install` pulls down a few hundred MB.

Code in `backticks` and ``` fences ``` is rendered as code and deliberately
skipped by the maths pass, so asking *how to write* a formula shows the LaTeX
rather than rendering it.

If QtWebEngine can't be loaded at all, the chat falls back to the same
bubbles drawn with plain Qt widgets — everything still works, maths just stays
as raw LaTeX.

### Offline

KaTeX is fetched from the jsDelivr CDN and cached on disk, so it survives
later launches without a connection. For a copy that's always there, unpack a
[KaTeX release](https://github.com/KaTeX/KaTeX/releases) into
`desktop_domo/assets/katex/` (so you get `assets/katex/katex.min.js`,
`katex.min.css`, `contrib/`, `fonts/`) — it's used automatically instead of
the CDN.

### If the transcript is blank on Linux

That's the QtWebEngine GPU process, not KaTeX. Uncomment one of the
`QTWEBENGINE_CHROMIUM_FLAGS` lines in `run.sh`.

## Layout

| File | What it does |
|------|--------------|
| `desktop_domo/bubble.py` | The round floating bubble (hover, click) |
| `desktop_domo/chat.py`   | The chat window (title bar, input bar, expand/shrink) |
| `desktop_domo/theme.py`  | Colours, fonts, Domo's name and avatar — shared by the window and transcript |
| `desktop_domo/transcript.py` | The transcript widget: speech bubbles, KaTeX maths via QtWebEngine |
| `desktop_domo/assets/transcript.html` | The page it renders — bubble styling, KaTeX setup |
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
- **Chat look:** colours, font sizes and the avatar's size in
  `desktop_domo/theme.py`; window size and how many lines the text field grows
  to at the top of `desktop_domo/chat.py`.
- **Font:** NK57 Monospace, loaded from `Fonts/nk57_monospace/` — `FONT_FILES`
  in `desktop_domo/theme.py` picks which width/weight files. If the folder is
  missing the chat falls back to Tahoma.
- **Start fresh:** delete `history.json` to clear the saved conversation.
