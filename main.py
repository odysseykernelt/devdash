# DevDash 入口：一句谜 Loader → 仪表盘
import os
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app import storage, theme
from app.ui_loader import LoaderWindow

ICON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.png")


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("DevDash")
    if os.path.exists(ICON):
        app.setWindowIcon(QIcon(ICON))
    settings = storage.load_settings()
    app.setStyleSheet(theme.qss(settings.get("theme", "dark")))
    win = LoaderWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
