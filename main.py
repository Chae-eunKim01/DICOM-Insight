import sys
from pathlib import Path
import pydicom

pydicom.config.convert_wrong_length_to_UN=True

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from ui.main_window import MainWindow

def main():
    app=QApplication(sys.argv)

    icon_path=Path(__file__).resolve().parent/"assets"/"DICOM_Insight.ico"

    app.setApplicationName("DICOM Insight")
    app.setOrganizationName("DICOM Insight")
    app.setWindowIcon(QIcon(str(icon_path)))

    window=MainWindow()
    window.setWindowTitle("DICOM Insight")
    window.setWindowIcon(QIcon(str(icon_path)))
    window.show()

    sys.exit(app.exec())

if __name__=="__main__":
    main()