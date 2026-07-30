import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import Qt

from models.signal_model import SignalModel
from viewmodels.main_viewmodel import MainViewModel
from views.main_view import MainView

def apply_dark_theme(app: QApplication):
    """Applies a consistent Dark Fusion palette across the entire GUI."""
    app.setStyle("Fusion")
    dark_palette = QPalette()
    
    # Base color assignments
    dark_palette.setColor(QPalette.Window, QColor(35, 38, 41))
    dark_palette.setColor(QPalette.WindowText, QColor(240, 240, 240))
    dark_palette.setColor(QPalette.Base, QColor(25, 27, 29))
    dark_palette.setColor(QPalette.AlternateBase, QColor(35, 38, 41))
    dark_palette.setColor(QPalette.ToolTipBase, QColor(240, 240, 240))
    dark_palette.setColor(QPalette.ToolTipText, QColor(240, 240, 240))
    dark_palette.setColor(QPalette.Text, QColor(240, 240, 240))
    dark_palette.setColor(QPalette.Button, QColor(45, 49, 53))
    dark_palette.setColor(QPalette.ButtonText, QColor(240, 240, 240))
    dark_palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
    dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    
    app.setPalette(dark_palette)

def main():
    app = QApplication(sys.argv)
    apply_dark_theme(app)

    # Instantiate MVVM Architecture
    model = SignalModel()
    viewmodel = MainViewModel(model)
    view = MainView(viewmodel)

    view.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
    