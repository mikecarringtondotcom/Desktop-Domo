"""The chat window that pops up when you click the bubble.

Step 4 scope: this is just the UI shell — a header, a scrollable transcript,
an input box and a Send button. Sending currently only echoes your own text
into the transcript; talking to Claude is wired up in a later step.
"""

import os
import time

from PySide6.QtCore import Qt, QPoint, QEvent, QSize
from PySide6.QtGui import QPixmap, QImage, QIcon
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QPlainTextEdit,
    QFrame,
    QApplication,
    QDialog,
    QDialogButtonBox,
)

from desktop_domo import api, config, history, screenshot, transcript

# --- Look & feel knobs ----------------------------------------------------
CHAT_WIDTH = 360
CHAT_HEIGHT = 480
GAP_ABOVE_BUBBLE = 12     # space between the chat window and the bubble

# Custom artwork for the "show my screen" button, sitting at the repo root.
CAPTURE_ICON = config.PROJECT_ROOT / "Screenshot  Icon.png"
EXPAND_ICON = config.PROJECT_ROOT / "fullscreen ICON.png"


class ChatWindow(QWidget):
    """A small, frameless, always-on-top chat panel."""

    def __init__(self):
        super().__init__()

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.resize(CHAT_WIDTH, CHAT_HEIGHT)

        # For dragging the frameless window by its header.
        self._drag_offset = None

        # Expand/shrink state. When expanded we remember the small geometry
        # so shrinking restores the exact previous size and position.
        self._expanded = False
        self._normal_geometry = None

        # Conversation state. `history` is the list of {role, content} dicts
        # we send to Claude and persist to disk.
        self.history = history.load()
        self._client = None          # created lazily on first send
        self._worker = None          # the in-flight background request

        # The bubble window, set by main() so we can hide it during capture.
        self.bubble = None

        self._build_ui()
        self._render_history()

    # -- UI construction ----------------------------------------------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())
        root.addWidget(self._build_transcript(), stretch=1)
        root.addLayout(self._build_input_row())

        # A subtle overall style so the frameless panel reads as a card.
        self.setStyleSheet(
            """
            ChatWindow { background: #371B11; }
            QLabel#title { color: #eaeaea; font-weight: bold; padding-left: 4px; }
            /* Only reaches the plain-text fallback transcript; the web-view
               one styles itself in assets/transcript.html, to match. */
            QTextEdit#transcript {
                background: #371B11; color: #eaeaea; border: none;
                padding: 8px; font-size: 16px;
            }
            QPlainTextEdit#input {
                background: #F9EFEB; color: #140A06; border: none;
                padding: 6px; font-size: 16px; border-radius: 4px;
            }
            QPushButton {
                background: #CE7D5F; color: #eaeaea; border: none;
                padding: 6px 10px; border-radius: 4px;
            }
            QPushButton:hover { background: #D99982; }
            QPushButton#kill {
                background: #7a1f1f; color: #fff; font-weight: bold;
                font-size: 11px; padding: 4px 8px;
            }
            QPushButton#kill:hover { background: #a12626; }
            QFrame#header { background: #7D3D26; }
            """
        )

    def _build_header(self):
        header = QFrame()
        header.setObjectName("header")
        header.setFixedHeight(36)

        row = QHBoxLayout(header)
        row.setContentsMargins(8, 0, 6, 0)

        self.title_label = QLabel("Desktop Domo")
        self.title_label.setObjectName("title")
        title = self.title_label

        self.capture_btn = QPushButton()
        self.capture_btn.setFixedSize(32, 32)
        # Use the bundled PNG if it's present; fall back to the emoji glyph so
        # the button still reads clearly if the artwork is ever missing.
        icon = QIcon(str(CAPTURE_ICON))
        if not icon.isNull():
            self.capture_btn.setIcon(icon)
            self.capture_btn.setIconSize(QSize(22, 22))
        else:
            self.capture_btn.setText("SS")
        self.capture_btn.setToolTip("Show Desktop Domo my screen (asks before sending)")
        self.capture_btn.clicked.connect(self._on_capture)

        self.expand_btn = QPushButton()
        self.expand_btn.setFixedSize(32, 32)
        # Use the bundled PNG if it's present; fall back to the glyph so the
        # button still reads clearly if the artwork is ever missing.
        self._expand_icon = QIcon(str(EXPAND_ICON))
        if not self._expand_icon.isNull():
            self.expand_btn.setIcon(self._expand_icon)
            self.expand_btn.setIconSize(QSize(28, 28))
        else:
            self.expand_btn.setText("⤢")
        self.expand_btn.setToolTip("Expand to fill the screen")
        self.expand_btn.clicked.connect(self.toggle_expanded)

        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(32, 32)
        self.close_btn.setToolTip("Hide the chat window (Doesn't actually kill the app)")
        self.close_btn.clicked.connect(self.hide)

        # Fully quits the app (bubble included), unlike ✕ which only hides.
        self.kill_btn = QPushButton("KILL")
        self.kill_btn.setObjectName("kill")
        self.kill_btn.setFixedHeight(32)
        self.kill_btn.setToolTip("Quit Desktop Domo completely")
        self.kill_btn.clicked.connect(self._on_kill)

        row.addWidget(title)
        row.addStretch(1)
        row.addWidget(self.capture_btn)
        row.addWidget(self.expand_btn)
        row.addWidget(self.close_btn)
        row.addWidget(self.kill_btn)

        # Let the header act as a drag handle for the frameless window.
        header.mousePressEvent = self._header_press
        header.mouseMoveEvent = self._header_move
        header.mouseReleaseEvent = self._header_release
        return header

    def _build_transcript(self):
        # A web view when KaTeX can run (see transcript.py), a QTextEdit when
        # it can't — either way it takes append_message(sender, text).
        self.transcript = transcript.build(self)
        self.transcript.setObjectName("transcript")
        return self.transcript

    def _build_input_row(self):
        row = QHBoxLayout()
        row.setContentsMargins(8, 8, 8, 8)
        row.setSpacing(8)

        self.input = QPlainTextEdit()
        self.input.setObjectName("input")
        self.input.setFixedHeight(56)
        self.input.setPlaceholderText("Type a message…")
        # Enter sends; Shift+Enter inserts a newline (handled in eventFilter).
        self.input.installEventFilter(self)

        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self._on_send)

        row.addWidget(self.input, stretch=1)
        row.addWidget(self.send_btn)
        return row

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
        self.history.append({"role": "user", "content": text})
        self.append_message("You", text)
        history.save(self.history)
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
        self.history.append({"role": "user", "content": content})
        self.append_message("You", f"📷 [screenshot] {text}".strip())
        history.save(self.history)   # image stripped to a placeholder on disk
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
            self.append_message("⚠️", f"Couldn't capture the screen: {exc}")
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
                self.append_message("⚠️", str(exc))
                return None
        return self._client

    def _on_reply(self, text):
        self.history.append({"role": "assistant", "content": text})
        self.append_message("Domo", text)
        history.save(self.history)
        self._set_busy(False)

    def _on_error(self, message):
        self.append_message("⚠️", f"Something went wrong: {message}")
        self._set_busy(False)

    def _clear_worker(self):
        self._worker = None

    def _set_busy(self, busy):
        """Toggle the 'waiting on Claude' UI state."""
        self.send_btn.setEnabled(not busy)
        self.capture_btn.setEnabled(not busy)
        self.input.setReadOnly(busy)
        self.title_label.setText("Domo · thinking…" if busy else "Desktop Domo")

    def append_message(self, sender, text):
        self.transcript.append_message(sender, text)

    def _render_history(self):
        """Show any conversation loaded from disk in the transcript."""
        label = {"user": "You", "assistant": "Domo"}
        for message in self.history:
            name = label.get(message["role"], message["role"])
            content = message["content"]
            if isinstance(content, str):
                self.append_message(name, content)
            elif isinstance(content, list):
                self.append_message(name, self._summarize_blocks(content))

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
            if self._expand_icon.isNull():
                self.expand_btn.setText("⤡")
            self.expand_btn.setToolTip("Shrink back down")
        else:
            if self._normal_geometry is not None:
                self.setGeometry(self._normal_geometry)
            self._expanded = False
            if self._expand_icon.isNull():
                self.expand_btn.setText("⤢")
            self.expand_btn.setToolTip("Expand to fill the screen")

    def _on_kill(self):
        """Fully quit the app — closes the chat, the bubble, everything.

        Unlike the ✕ button (which only hides this window), this tears down
        the whole process immediately — bubble included — so no instance is
        left running in the background. os._exit skips Qt's cleanup, which is
        fine here and guarantees we exit even with an in-flight request thread.
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

    # -- Frameless-window dragging -----------------------------------------
    def _header_press(self, event):
        # No dragging while expanded — it's already filling the screen.
        if event.button() == Qt.LeftButton and not self._expanded:
            self._drag_offset = event.globalPosition().toPoint() - self.pos()

    def _header_move(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    def _header_release(self, event):
        self._drag_offset = None


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

        self.setStyleSheet(
            """
            QDialog { background: #371B11; }
            QLabel { color: #eaeaea; }
            QPlainTextEdit {
                background: #F9EFEB; color: #140A06; border: solid; padding: 6px;
            }
            QPushButton {
                background: #CE7D5F; color: #eaeaea; border: none;
                padding: 6px 12px; border-radius: 4px;
            }
            QPushButton:hover { background: #D99982; }
            """
        )

    def question(self):
        """The user's optional question about the screenshot (may be empty)."""
        return self._question.toPlainText().strip()
