"""Screen capture backend for the "Show Claude my screen" feature.

Read-only by construction: this module captures a *static* image of the
display and returns PNG bytes. It never controls the machine, injects input,
or acts on what it sees.

Nothing is written to a location that persists. On Linux we must go through an
external tool (Qt's ``grabWindow`` returns a black image under Wayland /
XWayland), so we capture to a transient temp file — preferring the RAM-backed
``XDG_RUNTIME_DIR`` — and delete it immediately after reading the bytes.

Capture engine is chosen per-OS behind ``capture_screen()``:

    Windows / macOS : Qt ``QScreen.grabWindow(0)``  (native, zero deps)
    Linux / KDE     : ``spectacle -b -n -f``          (Wayland-safe)

The portal (``org.freedesktop.portal.Screenshot``) was evaluated as the Linux
engine: the D-Bus call succeeds, but the result vardict comes back as a
``QDBusArgument`` whose nested variant this PySide6 build cannot demarshal, so
the saved file's URI is unreachable. spectacle is present, reliable, and just
as read-only, so it is the Linux engine.
"""

import os
import subprocess
import sys
import tempfile
import time

from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QGuiApplication, QImage

from desktop_domo import config


class CaptureError(RuntimeError):
    """Raised when the screen could not be captured."""


def capture_screen():
    """Capture the primary display and return PNG bytes.

    Raises :class:`CaptureError` on any failure so the caller can show a
    friendly message instead of crashing.
    """
    engine = config.CAPTURE_ENGINE
    if engine == "auto":
        engine = _default_engine()

    if engine == "qt":
        return _capture_qt()
    if engine == "spectacle":
        return _capture_spectacle()
    raise CaptureError(f"Unknown capture engine: {engine!r}")


def _default_engine():
    """Pick the capture engine for this OS."""
    if sys.platform in ("win32", "darwin"):
        return "qt"
    return "spectacle"


# -- Engines ----------------------------------------------------------------
def _capture_qt():
    """Full-screen capture via Qt. Native on Windows/macOS; black on Wayland."""
    app = QGuiApplication.instance()
    screen = app.primaryScreen() if app is not None else None
    if screen is None:
        raise CaptureError("No screen is available to capture.")
    pixmap = screen.grabWindow(0)
    if pixmap.isNull():
        raise CaptureError("Screen capture returned an empty image.")
    return _image_to_png(pixmap.toImage())


def _capture_spectacle():
    """Full-screen capture via KDE's spectacle into a transient temp file."""
    base = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
    # spectacle's background save won't overwrite an existing file, so hand it
    # a fresh path inside our own temp dir rather than pre-creating the file.
    directory = tempfile.mkdtemp(prefix="claude_shot_", dir=base)
    path = os.path.join(directory, "screen.png")
    # Don't leak our own Qt platform choice (the app forces xcb/offscreen)
    # into spectacle — it is its own Qt app and must pick its natural backend,
    # or its background capture silently produces nothing.
    child_env = {k: v for k, v in os.environ.items() if k != "QT_QPA_PLATFORM"}
    try:
        try:
            subprocess.run(
                # -b background (no GUI), -n no notification, -f full screen,
                # -o write to our file.
                ["spectacle", "-b", "-n", "-f", "-o", path],
                check=True,
                capture_output=True,
                timeout=30,
                env=child_env,
            )
        except FileNotFoundError:
            raise CaptureError("spectacle is not installed — cannot capture the screen.")
        except subprocess.TimeoutExpired:
            raise CaptureError("spectacle timed out while capturing the screen.")
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or b"").decode(errors="replace").strip()
            raise CaptureError(f"spectacle failed to capture the screen. {detail}".strip())

        # In background mode (-b), spectacle hands the capture to a D-Bus
        # service and returns *before* the file is written, so poll briefly
        # for a non-empty file to appear.
        _wait_for_file(path, timeout=10.0)

        image = QImage(path)
        if image.isNull() or image.width() == 0 or image.height() == 0:
            raise CaptureError("The captured image was empty or unreadable.")
        return _image_to_png(image)
    finally:
        # Never leave the screenshot on disk, even on error.
        try:
            os.remove(path)
        except OSError:
            pass
        try:
            os.rmdir(directory)
        except OSError:
            pass


def _wait_for_file(path, timeout):
    """Block until ``path`` is a non-empty, stable file, or raise on timeout.

    Stable = its size stops growing between two polls, so we don't read a
    half-written file.
    """
    deadline = time.monotonic() + timeout
    last_size = -1
    while time.monotonic() < deadline:
        try:
            size = os.path.getsize(path)
        except OSError:
            size = 0
        if size > 0 and size == last_size:
            return
        last_size = size
        time.sleep(0.1)
    raise CaptureError("spectacle did not produce a screenshot in time.")


# -- Image helpers ----------------------------------------------------------
def downscale_png(data, max_edge):
    """Return PNG bytes whose long edge is at most ``max_edge`` pixels.

    Images already within the limit are returned unchanged.
    """
    image = QImage.fromData(data, "PNG")
    if image.isNull():
        return data
    long_edge = max(image.width(), image.height())
    if long_edge <= max_edge:
        return data
    scaled = image.scaledToWidth(max_edge) if image.width() >= image.height() \
        else image.scaledToHeight(max_edge)
    return _image_to_png(scaled)


def _image_to_png(image):
    """Encode a QImage to PNG bytes."""
    # Keep the QByteArray alive in its own name: passing a temporary
    # QByteArray to QBuffer lets it be freed mid-write and segfaults.
    store = QByteArray()
    buffer = QBuffer(store)
    buffer.open(QIODevice.WriteOnly)
    image.save(buffer, "PNG")
    buffer.close()
    return bytes(store.data())
