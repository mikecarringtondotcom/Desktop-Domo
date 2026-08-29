"""Application entry point.

Run with `./run.sh` (recommended) or, from an activated venv:
    python -m claude_bubble.main
"""

import sys

from PySide6.QtWidgets import QApplication

from claude_bubble.bubble import BubbleWindow
from claude_bubble.chat import ChatWindow


def main():
    app = QApplication(sys.argv)
    # Don't quit when the chat window is closed — the bubble stays alive and
    # is the app's real "home". Closing the chat just hides it.
    app.setQuitOnLastWindowClosed(False)

    bubble = BubbleWindow()
    chat = ChatWindow()

    # Clicking the bubble toggles the chat window open/closed near it.
    bubble.clicked.connect(lambda: chat.toggle_near(bubble))

    bubble.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
