"""Build ``icon.ico`` from the bubble artwork, for the Windows shortcut.

A .lnk can only point at an .ico (or an exe/dll), not a PNG, so the Start Menu
shortcut needs this. Helper.png is wider than it is tall, so it gets centred
on a square transparent canvas rather than squashed.

Run it directly, or let ``setup.ps1`` call it:
    .venv\\Scripts\\python.exe make_icon.py
"""

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter

SOURCE = "Helper.png"
TARGET = "icon.ico"
SIZE = 256  # the largest size Windows asks for


def main():
    # QImage needs a Qt application object before it will load image plugins.
    QGuiApplication(sys.argv)

    source = QImage(SOURCE)
    if source.isNull():
        print(f"Could not read {SOURCE}", file=sys.stderr)
        return 1

    scaled = source.scaled(
        SIZE, SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation
    )

    canvas = QImage(SIZE, SIZE, QImage.Format_ARGB32)
    canvas.fill(Qt.transparent)
    painter = QPainter(canvas)
    painter.drawImage(
        (SIZE - scaled.width()) // 2, (SIZE - scaled.height()) // 2, scaled
    )
    painter.end()

    if not canvas.save(TARGET, "ICO"):
        print(f"Could not write {TARGET}", file=sys.stderr)
        return 1
    print(f"Wrote {TARGET} ({SIZE}x{SIZE})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
