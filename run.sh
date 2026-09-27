#!/usr/bin/env bash
# Launch Desktop Domo — the floating Domo assistant.
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

# The transcript is a QtWebEngine view (that's what runs KaTeX). If it comes up
# blank on your machine it's almost always the GPU process; either of these
# usually sorts it out:
#   export QTWEBENGINE_CHROMIUM_FLAGS="--disable-gpu"
#   export QTWEBENGINE_CHROMIUM_FLAGS="--no-sandbox"

exec ./.venv/bin/python -m desktop_domo.main "$@"
