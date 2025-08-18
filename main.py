\
# main.py — Entry point for Icho v1.0
#
# This file bootstraps the Qt application and shows the main window.
# Keeping this minimal makes testing and packaging easier.

import sys
from PySide6.QtWidgets import QApplication
from icho.ui.main_window import MainWindow

def main() -> None:
    """
    Create the QApplication, instantiate MainWindow, and enter the event loop.
    The event loop blocks until the user quits, then we return an exit code.
    """
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
