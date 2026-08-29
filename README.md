# Desktop Domo

A small floating chat bubble for the desktop that talks to Claude. Click the
semi-transparent bubble in the bottom-right corner to open a chat window;
type a message and Claude replies.

Built with Python + PySide6, using the official `anthropic` SDK. Personal,
local tool DEFINATELY not production-grade haha.

## Running it

- **From the app menu:** search for **"Desktop Domo"** (a desktop entry is
  installed at `~/.local/share/applications/desktop-domo.desktop`).
- **From a terminal:** `./run.sh`

To close it, click the bubble again to hide the chat, and quit from the
terminal with `Ctrl+C` or quit from task-bar hover.

## Setup

1. Dependencies live in a local virtualenv (`.venv/`), already created. To
   recreate it: `python -m venv .venv && ./.venv/bin/pip install -r requirements.txt`.
2. Put your Anthropic API key in `.env.local`:
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   ```
   An `ANTHROPIC_API_KEY` already exported in your shell takes precedence.

## Show Claude your screen

Click the square button in the chat header to let Claude see your display.
It is **read-only and always gated**:

- The screen is captured as a **static image** — Claude can look, not act.
- A **preview dialog** shows the exact image first, with an optional question
  and **Send to Claude / Cancel**. Nothing leaves your machine until you click
  Send.
- Your chat window and the bubble are hidden during capture so they aren't in
  the shot.
- Screenshots **are never written to disk**. On Linux they're captured to a
  transient temp file (RAM-backed `XDG_RUNTIME_DIR`) that's deleted
  immediately, and image data is stripped to a `[screenshot]` placeholder
  before the transcript is saved to `history.json`.
- A sent screenshot stays in the in-memory conversation for the session, so
  follow-up questions work.

## Layout

| File | What it does |
|------|--------------|
| `desktop_domo/bubble.py` | The round floating bubble (hover, click) |
| `desktop_domo/chat.py`   | The chat window (transcript, input, expand/shrink) |
| `desktop_domo/api.py`    | Claude client + background request thread |
| `desktop_domo/config.py` | Settings, paths, API-key loading |
| `desktop_domo/history.py`| Load/save the conversation (strips screenshots) |
| `desktop_domo/screenshot.py`| Read-only screen capture backend (per-OS) |
| `desktop_domo/main.py`   | App entry point |
| `run.sh`                  | Launcher (sets XWayland, uses the venv) |

## Things you might want to tweak

- **Bubble look:** size, colour, opacity, position — constants at the top of
  `desktop_domo/bubble.py`.
- **Claude's behaviour:** model, reply length (`MAX_TOKENS`), and personality
  (`SYSTEM_PROMPT`) — `desktop_domo/config.py`.
- **Start fresh:** delete `history.json` to clear the saved conversation.
