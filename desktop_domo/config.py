"""Configuration, paths, and secret loading.

The Anthropic API key is read from the environment. To keep it out of the
code, we also load a local ``.env.local`` file (if present) into the
environment at startup — so you can keep the key in that file instead of
exporting it in your shell every time.
"""

import os
from pathlib import Path

# --- Where things live ----------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env.local"
HISTORY_FILE = PROJECT_ROOT / "history.json"

# --- Claude settings ------------------------------------------------------
MODEL = "claude-opus-4-8"     # the current top Claude model
MAX_TOKENS = 4096             # cap on reply length; bump up for longer answers
SYSTEM_PROMPT = "You are a helpful assistant living in a small desktop chat bubble. Keep replies concise and friendly."

API_KEY_ENV = "ANTHROPIC_API_KEY"


def load_env_file(path: Path = ENV_FILE):
    """Load simple KEY=value lines from ``path`` into os.environ.

    Tolerant of spaces around '=' and surrounding quotes. Existing
    environment variables are NOT overwritten, so a value exported in your
    shell still wins over the file.
    """
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def get_api_key():
    """Return the Anthropic API key, or None if it isn't set anywhere."""
    load_env_file()
    return os.environ.get(API_KEY_ENV)
