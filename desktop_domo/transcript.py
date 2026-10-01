"""The transcript view — the chat log as speech bubbles, with LaTeX by KaTeX.

KaTeX is a JavaScript library, so rendering math means hosting a browser
engine: the transcript is a ``QWebEngineView`` showing ``assets/transcript.html``
and messages are pushed in through ``appendMessage(role, text, time)``.
Identical on Windows and Linux — QtWebEngine ships inside the PySide6 wheel
on both.

The KaTeX dist is loaded from ``assets/katex/`` if you've vendored a copy there,
and from the jsDelivr CDN otherwise (cached on disk between runs). If
QtWebEngine can't be loaded at all, ``build()`` falls back to a native
``QScrollArea`` of ``MessageRow`` bubbles that looks the same: the chat still
works, math just stays as raw LaTeX.

Either widget takes ``append_message(role, text, time)`` — role is "user",
"assistant" or "note" — and ``set_typing(on)``.
"""

import json
from html import escape
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from desktop_domo import theme

ASSETS = Path(__file__).resolve().parent / "assets"
TEMPLATE = ASSETS / "transcript.html"
# Optional offline copy: unpack a KaTeX release here and it's used instead of
# the CDN. Expected layout is the dist folder's own — katex.min.js,
# katex.min.css, contrib/auto-render.min.js, fonts/.
LOCAL_KATEX = ASSETS / "katex"
CDN_KATEX = "https://cdn.jsdelivr.net/npm/katex@0.16/dist"

PLACEHOLDER = "Come on, do something!"
TYPING_TEXT = f"✎  {theme.ASSISTANT_NAME} is typing..."

# Bubble widths, as a share of the message area.
INCOMING_MAX = 0.82
OUTGOING_MAX = 0.78

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
    return NativeTranscript(parent)


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
        self._page.setBackgroundColor(QColor(theme.BACKGROUND))
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

    def append_message(self, role, text, time=""):
        self._call("appendMessage", role, text, time)

    def set_typing(self, on):
        self._call("setTyping", bool(on))

    def _call(self, function, *args):
        if self._ready:
            self._run(function, args, smooth=True)
        else:
            self._pending.append((function, args))

    def _run(self, function, args, smooth):
        # json.dumps produces correctly escaped JS literals (and escapes
        # non-ASCII), so message text never breaks out of the call. The
        # trailing flag is the page's `smooth` scroll argument.
        literals = ", ".join(json.dumps(a) for a in (*args, smooth))
        self.page().runJavaScript(f"{function}({literals});")

    def _on_load_finished(self, ok):
        self._ready = bool(ok)
        if not self._ready:
            return
        # Queued calls are the saved history arriving at startup: jump
        # straight to the bottom. Live messages scroll there smoothly.
        for function, args in self._pending:
            self._run(function, args, smooth=False)
        self._pending.clear()


class NativeTranscript(QScrollArea):
    """Fallback with no web engine: the same bubbles, drawn with Qt widgets.

    Math stays as raw LaTeX here — there's nothing to typeset it.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.NoFrame)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        body = QWidget()
        body.setObjectName("log")
        self._rows = QVBoxLayout(body)
        self._rows.setContentsMargins(12, 14, 12, 14)
        self._rows.setSpacing(10)
        # The stretch on top keeps a short chat sitting at the bottom.
        self._rows.addStretch(1)

        self._placeholder = QLabel(PLACEHOLDER)
        self._placeholder.setFont(theme.app_font(theme.SMALL_PX, italic=True))
        self._placeholder.setObjectName("placeholder")
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._rows.addWidget(self._placeholder)

        # Always the last item, so it stays under the newest message.
        self._typing = TypingIndicator()
        self._rows.addWidget(self._typing)
        self.setWidget(body)

        self.setStyleSheet(
            f"""
            QScrollArea, QWidget#log {{ background: {theme.BACKGROUND}; border: none; }}
            QLabel#placeholder {{ color: {theme.MUTED}; }}
            QScrollBar:vertical {{ background: transparent; width: 8px; margin: 0; }}
            QScrollBar::handle:vertical {{
                background: {theme.SCROLL_HANDLE}; border-radius: 4px; min-height: 24px;
            }}
            QScrollBar::handle:vertical:hover {{ background: {theme.SCROLL_HANDLE_HOVER}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
            """
        )

        # Follow new messages down, unless you've scrolled up to read.
        self._pinned = True
        bar = self.verticalScrollBar()
        bar.valueChanged.connect(self._on_scrolled)
        bar.rangeChanged.connect(self._on_range_changed)

    def append_message(self, role, text, time=""):
        self._placeholder.hide()
        row = MessageRow(role, text, time)
        row.fit_to(self.viewport().width())
        # Insert above the typing indicator, which always stays last.
        self._rows.insertWidget(self._rows.count() - 1, row)
        self._pinned = True

    def set_typing(self, on):
        self._typing.setVisible(on)
        self._pinned = True

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refit()

    def showEvent(self, event):
        super().showEvent(event)
        self._refit()

    def _refit(self):
        width = self.viewport().width()
        for row in self.widget().findChildren(MessageRow):
            row.fit_to(width)

    def _on_scrolled(self, value):
        self._pinned = value >= self.verticalScrollBar().maximum() - 4

    def _on_range_changed(self, _minimum, maximum):
        if self._pinned:
            self.verticalScrollBar().setValue(maximum)


class MessageRow(QWidget):
    """One message: a word-wrapped bubble, its time, and Domo's avatar."""

    def __init__(self, role, text, time="", parent=None):
        super().__init__(parent)
        self._role = role
        incoming = role == "assistant"
        small = theme.app_font(theme.SMALL_PX)

        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(2)

        # Fonts are set in code, not in the stylesheet below: a QSS font rule
        # is resolved before the row joins the window and drops the family.
        # fit_to also measures the text before then, so it needs them early.
        self.bubble = QLabel(text)
        self.bubble.setFont(small if role == "note" else theme.app_font())
        self.bubble.setTextFormat(Qt.PlainText)
        self.bubble.setWordWrap(True)
        self.bubble.setTextInteractionFlags(Qt.TextSelectableByMouse)
        # Padding as margins, not QSS `padding`: QLabel counts stylesheet
        # padding twice when wrapping, so short lines would wrap early.
        if role != "note":
            self.bubble.setContentsMargins(12, 8, 12, 8)

        stamp = QLabel(time)
        stamp.setFont(small)
        stamp.setVisible(bool(time))

        if role == "note":
            self.bubble.setObjectName("note")
            self.bubble.setAlignment(Qt.AlignCenter)
            grid.addWidget(self.bubble, 0, 0, Qt.AlignHCenter)
        elif incoming:
            avatar = avatar_label()
            self.bubble.setObjectName("bubbleIn")
            stamp.setObjectName("timeIn")
            grid.addWidget(avatar, 0, 0, Qt.AlignBottom)
            grid.addWidget(self.bubble, 0, 1, Qt.AlignLeft)
            grid.addWidget(stamp, 1, 1, Qt.AlignLeft)
            grid.setColumnStretch(2, 1)
        else:
            self.bubble.setObjectName("bubbleOut")
            stamp.setObjectName("timeOut")
            grid.setColumnStretch(0, 1)
            grid.addWidget(self.bubble, 0, 1, Qt.AlignRight)
            grid.addWidget(stamp, 1, 1, Qt.AlignRight)

        self.setStyleSheet(
            f"""
            QLabel#bubbleIn {{
                background: {theme.BUBBLE_IN}; color: {theme.INK};
                border-top-left-radius: 14px; border-top-right-radius: 14px;
                border-bottom-right-radius: 14px; border-bottom-left-radius: 3px;
            }}
            QLabel#bubbleOut {{
                background: {theme.CLAY}; color: {theme.CREAM};
                border-top-left-radius: 14px; border-top-right-radius: 14px;
                border-bottom-right-radius: 3px; border-bottom-left-radius: 14px;
            }}
            QLabel#avatar[fallback="true"] {{
                background: {theme.CLAY}; color: {theme.CREAM}; border-radius: 3px;
            }}
            QLabel#timeIn, QLabel#timeOut, QLabel#note {{ color: {theme.MUTED}; }}
            QLabel#timeIn {{ margin-left: 4px; }}
            QLabel#timeOut {{ margin-right: 4px; }}
            """
        )

    def fit_to(self, area_width):
        """Size the bubble for a message area ``area_width`` wide.

        Word-wrapped QLabels guess their own width badly (they wrap short
        lines early and clip their height), so the size is worked out here:
        as wide as the longest line of text, capped at the bubble's share of
        the area, and exactly as tall as the text needs at that width. The
        transcript calls this on every resize.
        """
        share = {"assistant": INCOMING_MAX, "user": OUTGOING_MAX}.get(self._role, 0.9)
        cap = max(80, int(area_width * share))

        label = self.bubble
        label.ensurePolished()  # measure it as styled, not as constructed
        margins = label.contentsMargins()
        chrome = margins.left() + margins.right()
        metrics = label.fontMetrics()
        natural = max(metrics.horizontalAdvance(line) for line in label.text().split("\n"))
        # +2 so rounding never tips a line that just fits onto two.
        width = min(natural + chrome + 2, cap)
        # Width first, and drop the last fit's height: QLabel clamps its own
        # heightForWidth to the current size limits.
        label.setFixedWidth(width)
        label.setMinimumHeight(0)
        label.setFixedHeight(label.heightForWidth(width))


def avatar_label(width=theme.AVATAR_W, height=theme.AVATAR_H, name="avatar"):
    """Domo's picture in a fixed width x height box, whatever the reply length.

    Used beside each reply and in the chat's title bar. If Helper.png is
    missing it shows ASSISTANT_INITIAL instead, with the ``fallback`` property
    set so a stylesheet can draw it as a lettered square.
    """
    label = QLabel()
    label.setObjectName(name)
    label.setFixedSize(width, height)
    label.setAlignment(Qt.AlignCenter)
    pixmap = QPixmap(str(theme.AVATAR_IMAGE))
    if pixmap.isNull():
        label.setText(theme.ASSISTANT_INITIAL)
        label.setProperty("fallback", True)
        return label
    # Scaled for the screen's pixel density so it stays sharp on high-DPI.
    ratio = label.devicePixelRatioF()
    scaled = pixmap.scaled(
        int(width * ratio),
        int(height * ratio),
        Qt.KeepAspectRatio,
        Qt.SmoothTransformation,
    )
    scaled.setDevicePixelRatio(ratio)
    label.setPixmap(scaled)
    return label


class TypingIndicator(QLabel):
    """'Domo is typing...' — shown while a reply is on its way."""

    def __init__(self, parent=None):
        super().__init__(TYPING_TEXT, parent)
        self.setFont(theme.app_font(theme.SMALL_PX, italic=True))
        self.setStyleSheet(f"color: {theme.MUTED};")
        self.hide()


def _page_html():
    """The transcript page with its palette, KaTeX location and strings filled in."""
    vendored = (LOCAL_KATEX / "katex.min.js").exists()
    katex = QUrl.fromLocalFile(str(LOCAL_KATEX)).toString() if vendored else CDN_KATEX
    avatar = theme.AVATAR_IMAGE
    avatar_url = QUrl.fromLocalFile(str(avatar)).toString() if avatar.exists() else ""
    return (
        TEMPLATE.read_text(encoding="utf-8")
        .replace("__THEME__", f"{theme.font_face_css()}\n{theme.css_variables()}")
        .replace("__KATEX__", katex)
        .replace("__PLACEHOLDER__", PLACEHOLDER)
        .replace("__TYPING__", escape(TYPING_TEXT))
        .replace("__INITIAL__", theme.ASSISTANT_INITIAL)
        .replace("__AVATAR__", avatar_url)
    )
