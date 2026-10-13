"""程序入口。"""
import sys

from PySide6.QtWidgets import QApplication

from cyg.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("畅易阁角色筛选器-v0.0.3")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
