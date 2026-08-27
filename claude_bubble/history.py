"""Load and save the chat transcript so it survives between sessions.

Stored as a JSON list of {"role", "content"} dicts in `history.json` — the
same shape the Anthropic API expects, so we can send it straight back.
"""

import json

from claude_bubble import config


def load():
    """Return the saved conversation, or an empty list if none/unreadable."""
    path = config.HISTORY_FILE
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    # Basic sanity check: must be a list of role/content dicts.
    if not isinstance(data, list):
        return []
    return [
        m for m in data
        if isinstance(m, dict) and m.get("role") in ("user", "assistant") and "content" in m
    ]


def save(history):
    """Write the conversation to disk (best effort)."""
    try:
        config.HISTORY_FILE.write_text(json.dumps(history, indent=2))
    except OSError:
        pass  # not worth crashing the app over a failed history write
