# Claude Bubble

A small floating chat bubble for the desktop that talks to Claude. Click the
semi-transparent bubble in the bottom-right corner to open a chat window;
type a message and Claude replies.

Built with Python + PySide6, using the official `anthropic` SDK. Personal,
local tool — not production-grade.

## Running it

- **From the app menu:** search for **"Claude Bubble"** (a desktop entry is
  installed at `~/.local/share/applications/claude-bubble.desktop`).
- **From a terminal:** `./run.sh`

To close it, click the bubble again to hide the chat, and quit from the
terminal with `Ctrl+C` (or however you launched it).

## Setup

1. Dependencies live in a local virtualenv (`.venv/`), already created. To
   recreate it: `python -m venv .venv && ./.venv/bin/pip install -r requirements.txt`.
2. Put your Anthropic API key in `.env.local` (git-ignored):
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   ```
   An `ANTHROPIC_API_KEY` already exported in your shell takes precedence.

## Wayland note

`run.sh` sets `QT_QPA_PLATFORM=xcb` so the app runs through XWayland. On native
KDE Wayland an app can't pin itself to a screen corner or force always-on-top;
under XWayland both work, and KDE runs XWayland transparently.

## Layout

| File | What it does |
|------|--------------|
| `claude_bubble/bubble.py` | The round floating bubble (hover, click) |
| `claude_bubble/chat.py`   | The chat window (transcript, input, expand/shrink) |
| `claude_bubble/api.py`    | Claude client + background request thread |
| `claude_bubble/config.py` | Settings, paths, API-key loading |
| `claude_bubble/history.py`| Load/save the conversation |
| `claude_bubble/main.py`   | App entry point |
| `run.sh`                  | Launcher (sets XWayland, uses the venv) |

## Things you might want to tweak

- **Bubble look:** size, colour, opacity, position — constants at the top of
  `claude_bubble/bubble.py`.
- **Claude's behaviour:** model, reply length (`MAX_TOKENS`), and personality
  (`SYSTEM_PROMPT`) — `claude_bubble/config.py`.
- **Start fresh:** delete `history.json` to clear the saved conversation.
# Claude-Overlay
