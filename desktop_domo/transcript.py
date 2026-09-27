"""The transcript view — the chat log, with LaTeX rendered by KaTeX.

KaTeX is a JavaScript library, so rendering math means hosting a browser
engine: the transcript is a ``QWebEngineView`` showing ``assets/transcript.html``
and messages are pushed in through ``appendMessage(sender, text)``. Identical
on Windows and Linux — QtWebEngine ships inside the PySide6 wheel on both.

The KaTeX dist is loaded from ``assets/katex/`` if you've vendored a copy there,
and from the jsDelivr CDN otherwise (cached on disk between runs). If
QtWebEngine can't be loaded at all, ``build()`` falls back to a plain
``QTextEdit``: the chat still works, math just stays as raw LaTeX.
"""

import json
from html import escape
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QTextEdit

ASSETS = Path(__file__).resolve().parent / "assets"
TEMPLATE = ASSETS / "transcript.html"
# Optional offline copy: unpack a KaTeX release here and it's used instead of
# the CDN. Expected layout is the dist folder's own — katex.min.js,
# katex.min.css, contrib/auto-render.min.js, fonts/.
LOCAL_KATEX = ASSETS / "katex"
CDN_KATEX = "https://cdn.jsdelivr.net/npm/katex@0.16/dist"

PLACEHOLDER = "Come on, do something!"
BACKGROUND = "#371B11"          # matches the chat window, so there's no flash

try:
    from PySide6.QtWebEngineCore import (
        QWebEnginePage,
        QWebEngineProfile,
        QWebEngineSettings,
    )
    from PySide6.QtWebEngineWidgets import QWebEngineView

    HAVE_WEBENGINE = True
except ImportError:  # PySide6-Essentials, or a distro package without it
    HAVE_WEBENGINE = False

# Without QtWebEngine there's no QWebEngineView to subclass, and MathTranscript
# is never instantiated — it just needs a base class so the module still imports.
_WebView = QWebEngineView if HAVE_WEBENGINE else object


def prepare():
    """Qt setup that has to happen before the QApplication is constructed.

    QtWebEngine wants OpenGL contexts shared across the whole app, and the
    attribute is ignored once QApplication exists — so ``main()`` calls this
    first thing. No-op when there's no web engine to set up.
    """
    if HAVE_WEBENGINE:
        QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)


def build(parent=None):
    """Return the transcript widget — KaTeX-capable if we can manage it."""
    if HAVE_WEBENGINE:
        try:
            return MathTranscript(parent)
        except Exception:
            # A web engine that imports but won't start (missing system libs,
            # no usable GPU/display) shouldn't take the whole chat down.
            pass
    return PlainTranscript(parent)


class MathTranscript(_WebView):
    """Chat log rendered as a web page so KaTeX can typeset the math."""

    def __init__(self, parent=None):
        super().__init__(parent)

        # A named profile keeps an on-disk HTTP cache, so the KaTeX files are
        # fetched once rather than on every launch. The default profile is
        # off-the-record and caches nothing.
        self._profile = QWebEngineProfile("desktop-domo", self)
        self._page = QWebEnginePage(self._profile, self)
        self.setPage(self._page)
        self._page.setBackgroundColor(QColor(BACKGROUND))
        # The page's own origin is file://, so it needs this to pull the KaTeX
        # stylesheet and scripts off the CDN when there's no vendored copy.
        self._page.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
        )
        self.setContextMenuPolicy(Qt.NoContextMenu)

        # Messages can arrive (from the saved history) before the page is up.
        self._ready = False
        self._pending = []
        self.loadFinished.connect(self._on_load_finished)
        # Base URL is the assets folder so a vendored katex/ resolves, and so
        # the page has a stable local origin either way.
        self.setHtml(_page_html(), QUrl.fromLocalFile(f"{ASSETS}/"))

    def append_message(self, sender, text):
        if self._ready:
            self._push(sender, text)
        else:
            self._pending.append((sender, text))

    def _on_load_finished(self, ok):
        self._ready = bool(ok)
        if not self._ready:
            return
        for sender, text in self._pending:
            self._push(sender, text)
        self._pending.clear()

    def _push(self, sender, text):
        # json.dumps produces a correctly escaped JS string literal (and
        # escapes non-ASCII), so the text never breaks out of the call.
        self.page().runJavaScript(
            f"appendMessage({json.dumps(sender)}, {json.dumps(text)});"
        )


class PlainTranscript(QTextEdit):
    """Fallback with no web engine: the chat works, math stays as raw LaTeX."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setPlaceholderText(PLACEHOLDER)

    def append_message(self, sender, text):
        # escape() keeps '<', '&' etc. in messages from being read as HTML.
        body = escape(text).replace("\n", "<br>")
        self.append(f"<b>{escape(sender)}:</b> {body}")


def _page_html():
    """The transcript page with its KaTeX location and empty-state filled in."""
    vendored = (LOCAL_KATEX / "katex.min.js").exists()
    katex = QUrl.fromLocalFile(str(LOCAL_KATEX)).toString() if vendored else CDN_KATEX
    return (
        TEMPLATE.read_text(encoding="utf-8")
        .replace("__KATEX__", katex)
        .replace("__PLACEHOLDER__", PLACEHOLDER)
    )
