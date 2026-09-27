"""Load and save the chat transcript so it survives between sessions.

Stored as a JSON list of {"role", "content"} dicts in `history.json` — the
same shape the Anthropic API expects, so we can send it straight back.
"""

import json

from desktop_domo import config


def load():
    """Return the saved conversation, or an empty list if none/unreadable."""
    path = config.HISTORY_FILE
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return []
    # Basic sanity check: must be a list of role/content dicts.
    if not isinstance(data, list):
        return []
    return [
        m for m in data
        if isinstance(m, dict) and m.get("role") in ("user", "assistant") and "content" in m
    ]


def save(history):
    """Write the conversation to disk (best effort).

    Screenshots are never written to disk: image blocks are replaced with a
    ``[screenshot]`` text placeholder before saving. The in-memory ``history``
    the app holds is left untouched, so image data stays available for
    follow-up questions during the session.
    """
    safe = _strip_images(history)
    try:
        config.HISTORY_FILE.write_text(
            json.dumps(safe, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass  # not worth crashing the app over a failed history write


def _strip_images(history):
    """Return a copy of ``history`` with image blocks reduced to a placeholder.

    Text stays; each ``{"type": "image", ...}`` block becomes
    ``{"type": "text", "text": "[screenshot]"}`` so the saved file never
    contains screen contents while remaining a valid message shape.
    """
    cleaned = []
    for message in history:
        content = message.get("content")
        if isinstance(content, list):
            new_content = [
                {"type": "text", "text": "[screenshot]"}
                if isinstance(block, dict) and block.get("type") == "image"
                else block
                for block in content
            ]
            cleaned.append({**message, "content": new_content})
        else:
            cleaned.append(message)
    return cleaned
