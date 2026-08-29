"""Application entry point.

Run with `./run.sh` (recommended) or, from an activated venv:
    python -m desktop_domo.main
"""

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from desktop_domo import config
from desktop_domo.bubble import BubbleWindow
from desktop_domo.chat import ChatWindow

APP_ICON = config.PROJECT_ROOT / "Helper.png"


def main():
    app = QApplication(sys.argv)
    # Icon shown for the app in the taskbar / window switcher.
    app.setWindowIcon(QIcon(str(APP_ICON)))
    # Don't quit when the chat window is closed — the bubble stays alive and
    # is the app's real "home". Closing the chat just hides it.
    app.setQuitOnLastWindowClosed(False)

    bubble = BubbleWindow()
    chat = ChatWindow()
    # Let the chat hide the bubble while capturing the screen.
    chat.bubble = bubble

    # Clicking the bubble toggles the chat window open/closed near it.
    bubble.clicked.connect(lambda: chat.toggle_near(bubble))

    bubble.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
