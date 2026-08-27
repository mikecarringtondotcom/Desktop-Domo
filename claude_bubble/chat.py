"""The chat window that pops up when you click the bubble.

Step 4 scope: this is just the UI shell — a header, a scrollable transcript,
an input box and a Send button. Sending currently only echoes your own text
into the transcript; talking to Claude is wired up in a later step.
"""

from PySide6.QtCore import Qt, QPoint, QEvent
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QPlainTextEdit,
    QFrame,
)

from claude_bubble import api, history

# --- Look & feel knobs ----------------------------------------------------
CHAT_WIDTH = 360
CHAT_HEIGHT = 480
GAP_ABOVE_BUBBLE = 12     # space between the chat window and the bubble


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
            ChatWindow { background: #1e1e1e; }
            QLabel#title { color: #eaeaea; font-weight: bold; padding-left: 4px; }
            QTextEdit#transcript {
                background: #141414; color: #eaeaea; border: none;
                padding: 8px; font-size: 13px;
            }
            QPlainTextEdit#input {
                background: #262626; color: #eaeaea; border: none;
                padding: 6px; font-size: 13px;
            }
            QPushButton {
                background: #333; color: #eaeaea; border: none;
                padding: 6px 10px; border-radius: 4px;
            }
            QPushButton:hover { background: #444; }
            QFrame#header { background: #2a2a2a; }
            """
        )

    def _build_header(self):
        header = QFrame()
        header.setObjectName("header")
        header.setFixedHeight(36)

        row = QHBoxLayout(header)
        row.setContentsMargins(8, 0, 6, 0)

        self.title_label = QLabel("Claude")
        self.title_label.setObjectName("title")
        title = self.title_label

        self.expand_btn = QPushButton("⤢")
        self.expand_btn.setFixedSize(24, 24)
        self.expand_btn.setToolTip("Expand to fill the screen")
        self.expand_btn.clicked.connect(self.toggle_expanded)

        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setToolTip("Close")
        self.close_btn.clicked.connect(self.hide)

        row.addWidget(title)
        row.addStretch(1)
        row.addWidget(self.expand_btn)
        row.addWidget(self.close_btn)

        # Let the header act as a drag handle for the frameless window.
        header.mousePressEvent = self._header_press
        header.mouseMoveEvent = self._header_move
        header.mouseReleaseEvent = self._header_release
        return header

    def _build_transcript(self):
        self.transcript = QTextEdit()
        self.transcript.setObjectName("transcript")
        self.transcript.setReadOnly(True)
        self.transcript.setPlaceholderText("Say hello…")
        return self.transcript

    def _build_input_row(self):
        row = QHBoxLayout()
        row.setContentsMargins(8, 8, 8, 8)
        row.setSpacing(8)

        self.input = QPlainTextEdit()
        self.input.setObjectName("input")
        self.input.setFixedHeight(56)
        self.input.setPlaceholderText("Type a message…  (Enter to send, Shift+Enter for newline)")
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

        self._set_busy(True)
        self._worker = api.ClaudeWorker(client, self.history, self)
        self._worker.succeeded.connect(self._on_reply)
        self._worker.failed.connect(self._on_error)
        self._worker.finished.connect(self._clear_worker)
        self._worker.start()

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
        self.append_message("Claude", text)
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
        self.input.setReadOnly(busy)
        self.title_label.setText("Claude · thinking…" if busy else "Claude")

    def append_message(self, sender, text):
        # escape() keeps '<', '&' etc. in messages from being read as HTML.
        from html import escape
        safe = escape(text).replace("\n", "<br>")
        self.transcript.append(f"<b>{escape(sender)}:</b> {safe}")

    def _render_history(self):
        """Show any conversation loaded from disk in the transcript."""
        label = {"user": "You", "assistant": "Claude"}
        for message in self.history:
            content = message["content"]
            if isinstance(content, str):
                self.append_message(label.get(message["role"], message["role"]), content)

    def toggle_expanded(self):
        """Switch between the small panel and filling the screen work area."""
        if not self._expanded:
            # Remember where we were, then grow to fill the work area.
            self._normal_geometry = self.geometry()
            self.setGeometry(self.screen().availableGeometry())
            self._expanded = True
            self.expand_btn.setText("⤡")
            self.expand_btn.setToolTip("Shrink back down")
        else:
            if self._normal_geometry is not None:
                self.setGeometry(self._normal_geometry)
            self._expanded = False
            self.expand_btn.setText("⤢")
            self.expand_btn.setToolTip("Expand to fill the screen")

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
