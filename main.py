#!/usr/bin/env python3
import sys
from PySide6.QtWidgets import QApplication
from rquickshare_app.settings import SettingsManager
from rquickshare_app.gui import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("RQuickShare")
    app.setOrganizationName("dev.mandre.rquickshare")
    app.setQuitOnLastWindowClosed(False)

    settings = SettingsManager()
    window = MainWindow(settings)

    if not settings.get("startminimized", False):
        window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
