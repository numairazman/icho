# main.py — Entry point for Icho v1.4
#
# Minimal bootstrap. Theme is controlled inside MainWindow (Tools → Dark Mode)
# and persisted via QSettings; we do NOT force a palette here.

import sys
from PySide6.QtWidgets import QApplication
from icho.ui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()