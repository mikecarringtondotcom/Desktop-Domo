#!/usr/bin/env bash
# Launch the floating Claude bubble.
#
# We force the Qt "xcb" platform so the app runs through XWayland. On native
# KDE Wayland an app cannot pin itself to a screen corner or force itself
# always-on-top; under XWayland those behave normally, and KDE runs XWayland
# transparently so you won't notice a difference.

set -euo pipefail

# Resolve the directory this script lives in, so it works from anywhere.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

export QT_QPA_PLATFORM=xcb

exec ./.venv/bin/python -m claude_bubble.main "$@"
