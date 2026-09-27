"""Application entry point.

Run with `run.cmd` / `run.ps1` on Windows, `./run.sh` on Linux, or — from an
activated venv — `python -m desktop_domo.main`.
"""

import os
import sys

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from desktop_domo import config
from desktop_domo.bubble import BubbleWindow
from desktop_domo.chat import ChatWindow

APP_ICON = config.PROJECT_ROOT / "Helper.png"


def _claim_windows_taskbar_identity():
    """Tell Windows this process belongs to the Desktop Domo shortcut.

    Without an explicit AppUserModelID, Windows attributes the process to
    ``python.exe`` — so the tray/taskbar shows a generic Python icon and the
    Start Menu shortcut doesn't group with the running app. No-op elsewhere.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            config.APP_USER_MODEL_ID
        )
    except (OSError, AttributeError):
        pass  # cosmetic only — never worth failing startup over


def _build_tray(app, bubble, chat, icon):
    """A tray icon so there's always a way back to the bubble, and a way out.

    Both windows are Qt.Tool windows with no taskbar entry, so if the bubble
    ends up hidden or off-screen the tray is the only handle on the app.
    Returns the QSystemTrayIcon, or None if this desktop has no tray.
    """
    if not QSystemTrayIcon.isSystemTrayAvailable():
        return None

    tray = QSystemTrayIcon(icon, app)
    tray.setToolTip("Desktop Domo")

    menu = QMenu()

    open_chat = QAction("Open chat", menu)
    open_chat.triggered.connect(lambda: _show_chat(bubble, chat))
    menu.addAction(open_chat)

    toggle_bubble = QAction("Hide bubble", menu)

    def _toggle_bubble():
        if bubble.isVisible():
            bubble.hide()
            toggle_bubble.setText("Show bubble")
        else:
            bubble.show()
            bubble.move_to_corner()
            toggle_bubble.setText("Hide bubble")

    toggle_bubble.triggered.connect(_toggle_bubble)
    menu.addAction(toggle_bubble)

    menu.addSeparator()

    quit_action = QAction("Quit Desktop Domo", menu)
    # Same hard exit as the chat's KILL button: app.quit() can hang waiting on
    # an in-flight request thread, and there's no state left to flush.
    quit_action.triggered.connect(lambda: os._exit(0))
    menu.addAction(quit_action)

    # Keep a reference on the tray: a QMenu with no owner gets garbage
    # collected and the menu silently stops appearing.
    tray.setContextMenu(menu)
    tray._menu = menu

    # Left-clicking the tray icon opens the chat, like clicking the bubble.
    tray.activated.connect(
        lambda reason: _show_chat(bubble, chat)
        if reason == QSystemTrayIcon.Trigger
        else None
    )
    tray.show()
    return tray


def _show_chat(bubble, chat):
    """Bring the chat up, wherever the bubble currently is."""
    if not chat.isVisible():
        chat.toggle_near(bubble)
    else:
        chat.raise_()
        chat.activateWindow()


def main():
    _claim_windows_taskbar_identity()

    app = QApplication(sys.argv)
    icon = QIcon(str(APP_ICON))
    # Icon shown for the app in the taskbar / window switcher.
    app.setWindowIcon(icon)
    app.setApplicationName("Desktop Domo")
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

    # Held in a local so the tray icon isn't garbage collected mid-run.
    tray = _build_tray(app, bubble, chat, icon)  # noqa: F841

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
