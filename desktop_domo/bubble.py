"""The floating bubble itself.

A small, frameless, always-on-top round icon that sits in a corner of the
screen. For Step 2 it has no behaviour beyond being visible and semi-
transparent — hover and click get added in later steps.
"""

from PySide6.QtCore import Qt, QPoint, QSize, QVariantAnimation, QEasingCurve, Signal
from PySide6.QtGui import QColor, QPainter, QBrush, QFont, QPixmap
from PySide6.QtWidgets import QWidget

from desktop_domo import config

# --- Look & feel knobs (tweak these freely) -------------------------------
BUBBLE_DIAMETER = 96          # long-edge size of the bubble, in pixels
SCREEN_MARGIN = 24            # gap between the bubble and the screen edge
REST_OPACITY = 0.5            # ~half see-through when just sitting there
HOVER_OPACITY = 0.95          # nearly solid when the mouse is over it
HOVER_FADE_MS = 120           # how long the darken/lighten fade takes
BUBBLE_COLOR = QColor(0xD9, 0x77, 0x57)  # Anthropic-ish clay/orange
GLYPH = ":("                   # fallback letter, drawn only if the PNG is missing

# Custom bubble artwork sitting at the repo root.
BUBBLE_IMAGE = config.PROJECT_ROOT / "Helper.png"


class BubbleWindow(QWidget):
    """A round, frameless, always-on-top bubble."""

    # Emitted on a left-click (press + release on the bubble).
    clicked = Signal()

    def __init__(self):
        super().__init__()

        # Frameless, floats above other windows, and does not show up as a
        # separate entry in the taskbar / task switcher (Tool window).
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        # Let us paint with transparent corners instead of an opaque square.
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Load the bubble artwork. If it's present, the widget takes the
        # image's aspect ratio (scaled so its long edge is BUBBLE_DIAMETER);
        # otherwise we fall back to the drawn clay circle + glyph.
        self._pixmap = QPixmap(str(BUBBLE_IMAGE))
        self.setFixedSize(self._bubble_size())

        # Current opacity of the drawn circle. Hover fades this between
        # REST_OPACITY and HOVER_OPACITY.
        self._opacity = REST_OPACITY

        # Show a pointing-hand cursor so the bubble reads as clickable.
        self.setCursor(Qt.PointingHandCursor)

        # Reusable animation that smoothly fades _opacity between two values.
        self._fade = QVariantAnimation(self)
        self._fade.setDuration(HOVER_FADE_MS)
        self._fade.setEasingCurve(QEasingCurve.InOutQuad)
        self._fade.valueChanged.connect(self._on_fade_step)

        self.move_to_corner()

    def _bubble_size(self):
        """Widget size: the PNG's aspect ratio scaled to a BUBBLE_DIAMETER long
        edge, or a square fallback when the PNG is missing."""
        if self._pixmap.isNull():
            return QSize(BUBBLE_DIAMETER, BUBBLE_DIAMETER)
        scaled = self._pixmap.size().scaled(
            BUBBLE_DIAMETER, BUBBLE_DIAMETER, Qt.KeepAspectRatio
        )
        # Never collapse to zero on a degenerate image.
        return QSize(max(1, scaled.width()), max(1, scaled.height()))

    def _start_fade(self, target):
        """Animate the circle's opacity toward ``target``."""
        self._fade.stop()
        self._fade.setStartValue(self._opacity)
        self._fade.setEndValue(target)
        self._fade.start()

    def _on_fade_step(self, value):
        self._opacity = value
        self.update()

    def enterEvent(self, event):
        """Mouse moved onto the bubble — darken toward solid."""
        self._start_fade(HOVER_OPACITY)

    def leaveEvent(self, event):
        """Mouse left the bubble — fade back to semi-transparent."""
        self._start_fade(REST_OPACITY)

    def mouseReleaseEvent(self, event):
        """A left-click that lands on the bubble emits ``clicked``."""
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()

    def move_to_corner(self):
        """Park the bubble in the bottom-right corner of the primary screen."""
        screen = self.screen().availableGeometry()
        x = screen.right() - self.width() - SCREEN_MARGIN
        y = screen.bottom() - self.height() - SCREEN_MARGIN
        self.move(QPoint(x, y))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # The same hover fade drives the artwork's opacity.
        painter.setOpacity(self._opacity)

        if not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                self.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            # Centre the image inside the widget.
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
            return

        # Fallback: the original drawn clay circle + glyph.
        color = QColor(BUBBLE_COLOR)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawEllipse(self.rect())

        glyph_color = QColor(Qt.white)
        glyph_color.setAlphaF(min(1.0, self._opacity + 0.3))
        painter.setOpacity(1.0)
        painter.setPen(glyph_color)
        font = QFont()
        font.setPixelSize(int(BUBBLE_DIAMETER * 0.5))
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignCenter, GLYPH)
