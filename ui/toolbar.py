from PySide6.QtGui import QAction

def create_actions(window):
    open_folder=QAction("Open Folder",window)
    open_folder.setShortcut("Ctrl+O")
    return {
        "open_folder":open_folder
    }
