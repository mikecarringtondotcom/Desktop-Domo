"""The chat window that pops up when you click the bubble.

Laid out like an old-school messenger window, top to bottom with no gaps:

    TitleBar        clay bar: Domo's avatar + "Online", and the window buttons
    timestamp strip "Chat started today at 9:41 AM"
    transcript      speech bubbles (transcript.py), takes the leftover height
    InputBar        text field + Send, and the "Press Enter to send" hint

Colours and fonts live in theme.py.
"""

import os
import time
from datetime import datetime

from PySide6.QtCore import Qt, QPoint, QPointF, QRectF, QEvent, QSize
from PySide6.QtGui import (
    QColor,
    QFontMetrics,
    QIcon,
    QImage,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QPixmap,
    QRegion,
)
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizeGrip,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from desktop_domo import api, history, screenshot, theme, transcript

# --- Look & feel knobs ----------------------------------------------------
CHAT_WIDTH = 440
CHAT_HEIGHT = 580
CHAT_MIN_WIDTH = 360
GAP_ABOVE_BUBBLE = 12     # space between the chat window and the bubble
CORNER_RADIUS = 6
# The text field is one line tall — the same height as Send — and only grows
# (up to this many lines, then scrolls) when you add lines with Shift+Enter.
INPUT_MAX_LINES = 3
FIELD_PAD_V, FIELD_PAD_H = 7, 9


def _one_line_height():
    """Height of a one-line text field: a line of text + padding + 1px borders.

    The Send button is pinned to this too, so the two always line up.
    """
    return QFontMetrics(theme.app_font()).lineSpacing() + 2 * (FIELD_PAD_V + 1)


def _glyph_icon(kind, color=theme.CREAM, size=16):
    """A small flat line icon for the title bar, drawn in ``color``.

    kind is "capture" (viewfinder), "expand" (arrows out) or "shrink" (arrows
    in). Drawn rather than loaded so they stay crisp and readable on the clay
    bar at any DPI.
    """
    ratio = 2  # draw at 2x so they're sharp on high-DPI screens too
    pixmap = QPixmap(size * ratio, size * ratio)
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor(color), 1.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    c = size / 2
    corners = [(1, -1), (1, 1), (-1, 1), (-1, -1)]

    if kind == "capture":
        reach, arm = c - 2, 4
        for sx, sy in corners:
            corner = QPointF(c + sx * reach, c + sy * reach)
            painter.drawLine(corner, corner - QPointF(sx * arm, 0))
            painter.drawLine(corner, corner - QPointF(0, sy * arm))
        painter.drawEllipse(QPointF(c, c), 2.5, 2.5)
    else:
        outer, inner, head = c - 2, 2, 3.5
        for sx, sy in corners:
            far = QPointF(c + sx * outer, c + sy * outer)
            near = QPointF(c + sx * inner, c + sy * inner)
            painter.drawLine(near, far)
            # Arrowhead at the tip: the far end for expand, the near for shrink.
            tip, back = (far, -1) if kind == "expand" else (near, 1)
            painter.drawLine(tip, tip + QPointF(back * sx * head, 0))
            painter.drawLine(tip, tip + QPointF(0, back * sy * head))
    painter.end()
    return QIcon(pixmap)


class ChatWindow(QWidget):
    """A small, frameless, always-on-top chat panel with rounded corners."""

    def __init__(self):
        super().__init__()

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        # Round corners come from a window mask (see _round_corners), not
        # WA_TranslucentBackground: with QtWebEngine inside a translucent
        # window, Windows display scaling leaves a see-through 1px seam where
        # the transcript meets the input bar.
        self.setFont(theme.app_font())
        self.resize(CHAT_WIDTH, CHAT_HEIGHT)
        self.setMinimumWidth(CHAT_MIN_WIDTH)

        # Expand/shrink state. When expanded we remember the small geometry
        # so shrinking restores the exact previous size and position.
        self._expanded = False
        self._normal_geometry = None

        # Conversation state. `history` is the list of {role, content, time}
        # dicts we persist to disk; api.py strips `time` before sending.
        self.history = history.load()
        self._client = None          # created lazily on first send
        self._worker = None          # the in-flight background request
        self._started = datetime.now()

        # The bubble window, set by main() so we can hide it during capture.
        self.bubble = None

        self._build_ui()
        self._render_history()

    # -- UI construction ----------------------------------------------------
    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        container = QFrame()
        container.setObjectName("container")
        outer.addWidget(container)

        column = QVBoxLayout(container)
        # 1px inset so the sections sit inside the container's border.
        column.setContentsMargins(1, 1, 1, 1)
        column.setSpacing(0)

        self.title_bar = TitleBar(self)
        column.addWidget(self.title_bar)

        strip = QLabel(f"Chat started today at {theme.format_time(self._started)}")
        strip.setObjectName("strip")
        column.addWidget(strip)

        # A web view when KaTeX can run (see transcript.py), native Qt bubbles
        # when it can't — either way it takes append_message(role, text, time).
        self.transcript = transcript.build(self)
        column.addWidget(self.transcript, stretch=1)

        self.input_bar = InputBar()
        column.addWidget(self.input_bar)

        # Shortcuts to the controls the behaviour code below works with.
        self.capture_btn = self.title_bar.capture_btn
        self.expand_btn = self.title_bar.expand_btn
        self.input = self.input_bar.input
        self.send_btn = self.input_bar.send_btn

        self.capture_btn.clicked.connect(self._on_capture)
        self.expand_btn.clicked.connect(self.toggle_expanded)
        self.title_bar.minimize_btn.clicked.connect(self.hide)
        self.title_bar.close_btn.clicked.connect(self._on_kill)
        self.send_btn.clicked.connect(self._on_send)
        # Enter sends; Shift+Enter inserts a newline (handled in eventFilter).
        self.input.installEventFilter(self)

        t = theme
        r = CORNER_RADIUS
        self.setStyleSheet(
            f"""
            QFrame#container {{
                background: {t.BACKGROUND};
                border: 1px solid {t.BORDER}; border-radius: {r}px;
            }}

            QFrame#titleBar {{
                background: {t.CLAY}; border-bottom: 1px solid {t.CLAY_DARK};
                border-top-left-radius: {r - 1}px; border-top-right-radius: {r - 1}px;
            }}
            /* Only when Helper.png is missing: a cream square with the initial. */
            QLabel#titleAvatar[fallback="true"] {{
                background: {t.CREAM}; color: {t.CLAY};
                border: 1px solid {t.CLAY_DARK}; border-radius: 3px;
                font-size: {t.TEXT_PX}px; font-weight: 500;
            }}
            QLabel#titleName {{
                color: {t.CREAM}; font-size: {t.TEXT_PX}px; font-weight: 500;
            }}
            QLabel#titleStatus {{ color: {t.CREAM}; font-size: {t.SMALL_PX}px; }}
            QPushButton#titleBtn, QPushButton#closeBtn {{
                background: transparent; color: {t.CREAM}; border: none;
                border-radius: 3px; padding: 0; font-size: {t.TEXT_PX}px;
            }}
            QPushButton#titleBtn:hover {{ background: {t.CLAY_LIGHT}; }}
            QPushButton#titleBtn:pressed {{ background: {t.CLAY_DARK}; }}
            /* ✕ quits everything, so it warns on hover like the old KILL. */
            QPushButton#closeBtn:hover {{ background: {t.DANGER}; }}

            QLabel#strip {{
                background: {t.SURFACE}; color: {t.MUTED};
                border-bottom: 1px solid {t.DIVIDER};
                padding: 6px 10px; font-size: {t.SMALL_PX}px;
            }}

            QFrame#inputBar {{
                background: {t.SURFACE}; border-top: 1px solid {t.BORDER};
                border-bottom-left-radius: {r - 1}px; border-bottom-right-radius: {r - 1}px;
            }}
            QTextEdit#input {{
                background: {t.FIELD}; color: {t.FIELD_TEXT};
                border: 1px solid {t.FIELD_BORDER}; border-radius: 3px;
                padding: {FIELD_PAD_V}px {FIELD_PAD_H}px; font-size: {t.TEXT_PX}px;
                selection-background-color: {t.CLAY}; selection-color: {t.CREAM};
            }}
            QTextEdit#input:focus {{ border-color: {t.CLAY}; }}
            QPushButton#send {{
                background: {t.CLAY}; color: {t.CREAM};
                border: 1px solid {t.CLAY_DARK}; border-radius: 3px;
                padding: 0 14px; font-size: {t.TEXT_PX}px; font-weight: 500;
            }}
            QPushButton#send:hover {{ background: {t.CLAY_HOVER}; }}
            QPushButton#send:pressed {{ background: {t.CLAY_DARK}; }}
            QPushButton#send:disabled {{ background: {t.CLAY_DARK}; color: {t.MUTED}; }}
            QLabel#hint {{ color: {t.MUTED}; font-size: {t.SMALL_PX}px; }}
            """
        )

    # -- Behaviour ----------------------------------------------------------
    def _on_send(self):
        if self._worker is not None:
            return  # a request is already in flight; ignore extra sends
        text = self.input.toPlainText().strip()
        if not text:
            return

        client = self._ensure_client()
        if client is None:
            return  # missing API key — message already shown to the user

        self.input.clear()
        self.input.setFocus()
        self._add_message("user", text)
        self._dispatch()

    def _dispatch(self):
        """Send the current history to Claude on a background thread."""
        self._set_busy(True)
        self._worker = api.ClaudeWorker(self._client, self.history, self)
        self._worker.succeeded.connect(self._on_reply)
        self._worker.failed.connect(self._on_error)
        self._worker.finished.connect(self._clear_worker)
        self._worker.start()

    # -- Screen vision ------------------------------------------------------
    def _on_capture(self):
        """Capture the screen, then open the preview + Send/Cancel dialog.

        Read-only: this only ever produces a static image, and nothing is sent
        until you click Send in the preview.
        """
        if self._worker is not None:
            return  # a request is in flight; ignore
        if self._ensure_client() is None:
            return  # no API key — message already shown

        png = self._grab_screen()
        if png is None:
            return  # capture failed — message already shown

        dialog = ScreenshotPreviewDialog(png, self)
        if dialog.exec() != QDialog.Accepted:
            return  # cancelled — the image is discarded, never sent

        text = dialog.question()
        content = api.build_user_content(text, png)
        # The image is stripped to a placeholder when history hits the disk.
        self._add_message("user", content, shown=f"📷 [screenshot] {text}".strip())
        self._dispatch()

    def _grab_screen(self):
        """Hide our own windows, capture the display, restore. Returns PNG bytes.

        On failure, shows the error in the transcript and returns None.
        """
        windows = [w for w in (self, self.bubble) if w is not None and w.isVisible()]
        for w in windows:
            w.hide()
        # Let the compositor repaint without our windows before capturing.
        QApplication.processEvents()
        time.sleep(0.25)
        try:
            return screenshot.capture_screen()
        except screenshot.CaptureError as exc:
            self._note(f"Couldn't capture the screen: {exc}")
            return None
        finally:
            for w in windows:
                w.show()
            self.raise_()
            self.activateWindow()

    def _ensure_client(self):
        """Create the Claude client on first use; report a missing key nicely."""
        if self._client is None:
            try:
                self._client = api.ClaudeClient()
            except RuntimeError as exc:
                self._note(str(exc))
                return None
        return self._client

    def _on_reply(self, text):
        self._set_busy(False)
        self._add_message("assistant", text)

    def _on_error(self, message):
        self._set_busy(False)
        self._note(f"Something went wrong: {message}")

    def _clear_worker(self):
        self._worker = None

    def _set_busy(self, busy):
        """Toggle the 'waiting on Claude' UI state.

        The text field stays editable so you can write your next message while
        Domo answers; it just can't be sent until the reply lands.
        """
        self.send_btn.setEnabled(not busy)
        self.capture_btn.setEnabled(not busy)
        self.transcript.set_typing(busy)

    def _add_message(self, role, content, shown=None):
        """Record a message in the history, save it, and show it as a bubble.

        ``shown`` overrides the bubble text, for content that isn't plain text.
        """
        now = datetime.now()
        self.history.append({
            "role": role,
            "content": content,
            "time": now.isoformat(timespec="seconds"),
        })
        history.save(self.history)
        self.transcript.append_message(
            role, shown if shown is not None else content, theme.format_time(now)
        )

    def _note(self, text):
        """A notice from the app itself (errors etc.) — shown, never saved."""
        self.transcript.append_message("note", text)

    def _render_history(self):
        """Show any conversation loaded from disk in the transcript."""
        now = datetime.now()
        for message in self.history:
            content = message["content"]
            if isinstance(content, list):
                content = self._summarize_blocks(content)
            elif not isinstance(content, str):
                continue
            self.transcript.append_message(
                message["role"], content, self._stamp(message.get("time"), now)
            )

    @staticmethod
    def _stamp(saved, now):
        """Format a saved ISO time; blank for messages saved without one."""
        try:
            return theme.format_time(datetime.fromisoformat(saved), now)
        except (TypeError, ValueError):
            return ""

    @staticmethod
    def _summarize_blocks(content):
        """Render a multimodal message's blocks as a single transcript line."""
        parts = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "image":
                parts.append("📷 [screenshot]")
            elif block.get("type") == "text":
                parts.append(block.get("text", ""))
        return " ".join(p for p in parts if p)

    def toggle_expanded(self):
        """Switch between the small panel and filling the screen work area."""
        if not self._expanded:
            # Remember where we were, then grow to fill the work area.
            self._normal_geometry = self.geometry()
            self.setGeometry(self.screen().availableGeometry())
            self._expanded = True
        else:
            if self._normal_geometry is not None:
                self.setGeometry(self._normal_geometry)
            self._expanded = False
        self.title_bar.show_expanded(self._expanded)
        # Nothing to resize from while filling the screen.
        self.input_bar.grip.setVisible(not self._expanded)
        self._round_corners()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._round_corners()

    def _round_corners(self):
        """Clip the window to the container's rounded rectangle.

        Square while expanded, since it's filling the screen anyway.
        """
        if self._expanded:
            self.clearMask()
            return
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), CORNER_RADIUS, CORNER_RADIUS)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def _on_kill(self):
        """Fully quit the app — closes the chat, the bubble, everything.

        Unlike the – button (which only tucks this window away), this tears
        down the whole process immediately — bubble included — so no instance
        is left running in the background. os._exit skips Qt's cleanup, which
        is fine here and guarantees we exit even with an in-flight request
        thread.
        """
        os._exit(0)

    def toggle_near(self, bubble):
        """Show the window just above the bubble, or hide it if already open."""
        if self.isVisible():
            self.hide()
            return
        self._position_near(bubble)
        self.show()
        self.raise_()
        self.activateWindow()
        self.input.setFocus()

    def _position_near(self, bubble):
        """Place the chat window's bottom-right corner just above the bubble."""
        bubble_geo = bubble.frameGeometry()
        x = bubble_geo.right() - self.width()
        y = bubble_geo.top() - self.height() - GAP_ABOVE_BUBBLE

        # Keep it on-screen if the bubble is near the top/left edges.
        screen = bubble.screen().availableGeometry()
        x = max(screen.left(), x)
        y = max(screen.top(), y)
        self.move(QPoint(x, y))

    # -- Input handling -----------------------------------------------------
    def eventFilter(self, obj, event):
        """Enter sends the message; Shift+Enter inserts a newline."""
        if obj is self.input and event.type() == QEvent.KeyPress:
            is_enter = event.key() in (Qt.Key_Return, Qt.Key_Enter)
            if is_enter and not (event.modifiers() & Qt.ShiftModifier):
                self._on_send()
                return True  # consume the event; don't add a newline
        return super().eventFilter(obj, event)


class TitleBar(QFrame):
    """The clay bar: Domo's picture, name + status, window buttons. Drag to move."""

    def __init__(self, window):
        super().__init__(window)
        self.setObjectName("titleBar")
        self._window = window
        self._drag_offset = None

        row = QHBoxLayout(self)
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(0)

        avatar = transcript.avatar_label(
            theme.TITLE_AVATAR_W, theme.TITLE_AVATAR_H, name="titleAvatar"
        )
        row.addWidget(avatar)
        row.addSpacing(8)

        name = QLabel(theme.ASSISTANT_NAME)
        name.setObjectName("titleName")
        status = QLabel("Online")
        status.setObjectName("titleStatus")

        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.setSpacing(4)
        status_row.addWidget(StatusDot(), alignment=Qt.AlignVCenter)
        status_row.addWidget(status)
        status_row.addStretch(1)

        lines = QVBoxLayout()
        lines.setContentsMargins(0, 0, 0, 0)
        lines.setSpacing(1)
        lines.addWidget(name)
        lines.addLayout(status_row)
        row.addLayout(lines)
        row.addStretch(1)

        self.capture_btn = self._button(
            "Show Domo my screen (asks before sending)", icon=_glyph_icon("capture")
        )
        self._expand_icon = _glyph_icon("expand")
        self._shrink_icon = _glyph_icon("shrink")
        self.expand_btn = self._button("Expand to fill the screen", icon=self._expand_icon)
        self.minimize_btn = self._button("Tuck the chat away (the bubble stays)", text="–")
        self.close_btn = self._button("Quit Desktop Domo completely", text="✕")
        self.close_btn.setObjectName("closeBtn")

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(10)
        for button in (self.capture_btn, self.expand_btn, self.minimize_btn, self.close_btn):
            buttons.addWidget(button)
        row.addLayout(buttons)

    @staticmethod
    def _button(tooltip, text="", icon=None):
        button = QPushButton(text)
        button.setObjectName("titleBtn")
        button.setFixedSize(20, 18)
        button.setFlat(True)
        button.setFocusPolicy(Qt.NoFocus)
        button.setCursor(Qt.PointingHandCursor)
        button.setToolTip(tooltip)
        if icon is not None:
            button.setIcon(icon)
            button.setIconSize(QSize(14, 14))
        return button

    def show_expanded(self, expanded):
        self.expand_btn.setIcon(self._shrink_icon if expanded else self._expand_icon)
        self.expand_btn.setToolTip("Shrink back down" if expanded else "Expand to fill the screen")

    # -- Frameless-window dragging -----------------------------------------
    def mousePressEvent(self, event):
        # No dragging while expanded — it's already filling the screen.
        if event.button() == Qt.LeftButton and not self._window._expanded:
            self._drag_offset = event.globalPosition().toPoint() - self._window.pos()

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self._window.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None


class StatusDot(QWidget):
    """The 7px green 'online' dot."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(7, 7)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(theme.ONLINE_GREEN))
        painter.drawEllipse(self.rect())


class InputBar(QFrame):
    """Text field + Send, the hint line, and a corner grip to resize the window."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("inputBar")

        column = QVBoxLayout(self)
        column.setContentsMargins(8, 8, 8, 8)
        column.setSpacing(5)

        self.input = MessageInput()
        self.input.setObjectName("input")

        self.send_btn = QPushButton("Send")
        self.send_btn.setObjectName("send")
        self.send_btn.setFixedHeight(_one_line_height())
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.setFocusPolicy(Qt.NoFocus)  # keep focus in the field

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.addWidget(self.input, stretch=1)
        # Stays on the last line if the field grows.
        row.addWidget(self.send_btn, alignment=Qt.AlignBottom)
        column.addLayout(row)

        hint = QLabel("Press Enter to send  ·  Shift+Enter for a new line")
        hint.setObjectName("hint")
        # Wraps rather than holding the window wider than CHAT_MIN_WIDTH —
        # the mono font makes this line longer than the window's narrowest.
        hint.setWordWrap(True)
        self.grip = ResizeGrip(self)

        hint_row = QHBoxLayout()
        hint_row.setContentsMargins(0, 0, 0, 0)
        # The hint takes all the spare width, so it only wraps when it must.
        hint_row.addWidget(hint, stretch=1)
        hint_row.addWidget(self.grip, alignment=Qt.AlignBottom | Qt.AlignRight)
        column.addLayout(hint_row)


class MessageInput(QTextEdit):
    """A plain-text field, one line tall, that grows a little for extra lines."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptRichText(False)   # pasting keeps the text, drops formatting
        self.setTabChangesFocus(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setPlaceholderText("Type a message...")
        # The stylesheet's padding is the only inset we want.
        self.document().setDocumentMargin(0)
        self.document().documentLayout().documentSizeChanged.connect(self._fit_height)

        palette = self.palette()
        palette.setColor(QPalette.PlaceholderText, QColor(theme.PLACEHOLDER))
        self.setPalette(palette)
        self.setFixedHeight(_one_line_height())

    def _fit_height(self, *_):
        line = QFontMetrics(theme.app_font()).lineSpacing()
        extra_lines = round(self.document().size().height() / line) - 1
        extra_lines = max(0, min(extra_lines, INPUT_MAX_LINES - 1))
        self.setFixedHeight(_one_line_height() + extra_lines * line)
        # Past the cap the text scrolls; only then is a scrollbar worth showing.
        capped = self.document().size().height() > line * INPUT_MAX_LINES + 1
        self.setVerticalScrollBarPolicy(
            Qt.ScrollBarAsNeeded if capped else Qt.ScrollBarAlwaysOff
        )


class ResizeGrip(QSizeGrip):
    """The usual bottom-right resize grip, drawn to suit the dark input bar."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setFixedSize(11, 11)
        self.setToolTip("Drag to resize")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(theme.MUTED), 1))
        w, h = self.width(), self.height()
        for step in (3, 6, 9):
            painter.drawLine(QPointF(w - step, h - 0.5), QPointF(w - 0.5, h - step))


class ScreenshotPreviewDialog(QDialog):
    """Show the captured screenshot with Send to Claude / Cancel.

    This is the permission moment: the exact image that would leave the machine
    is shown here, and it is only sent if the user clicks Send. On Cancel the
    caller discards the image immediately.
    """

    PREVIEW_MAX_W = 420
    PREVIEW_MAX_H = 260

    def __init__(self, png_bytes, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Send this screenshot to Domo?")
        self.setModal(True)
        self.setFont(theme.app_font())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        layout.addWidget(QLabel("Domo/Claude will see this static image. It can look, not act."))

        image = QImage.fromData(png_bytes, "PNG")
        pixmap = QPixmap.fromImage(image).scaled(
            self.PREVIEW_MAX_W,
            self.PREVIEW_MAX_H,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        thumb = QLabel()
        thumb.setPixmap(pixmap)
        thumb.setAlignment(Qt.AlignCenter)
        layout.addWidget(thumb)

        self._question = QPlainTextEdit()
        self._question.setPlaceholderText("Ask about this screenshot… (optional)")
        self._question.setFixedHeight(64)
        layout.addWidget(self._question)

        buttons = QDialogButtonBox()
        send = buttons.addButton("Send to Domo", QDialogButtonBox.AcceptRole)
        buttons.addButton("Cancel", QDialogButtonBox.RejectRole)
        send.setDefault(True)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        t = theme
        self.setStyleSheet(
            f"""
            QDialog {{ background: {t.BACKGROUND}; }}
            QLabel {{ color: {t.INK}; font-size: {t.TEXT_PX}px; }}
            QPlainTextEdit {{
                background: {t.FIELD}; color: {t.FIELD_TEXT};
                border: 1px solid {t.FIELD_BORDER}; border-radius: 3px;
                padding: {FIELD_PAD_V}px {FIELD_PAD_H}px; font-size: {t.TEXT_PX}px;
            }}
            QPlainTextEdit:focus {{ border-color: {t.CLAY}; }}
            QPushButton {{
                background: {t.CLAY}; color: {t.CREAM};
                border: 1px solid {t.CLAY_DARK}; border-radius: 3px;
                padding: 7px 14px; font-size: {t.TEXT_PX}px; font-weight: 500;
            }}
            QPushButton:hover {{ background: {t.CLAY_HOVER}; }}
            QPushButton:pressed {{ background: {t.CLAY_DARK}; }}
            """
        )

    def question(self):
        """The user's optional question about the screenshot (may be empty)."""
        return self._question.toPlainText().strip()
