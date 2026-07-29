import sys
from PySide6.QtWidgets import QApplication
from models.signal_model import SignalModel
from viewmodels.main_viewmodel import MainViewModel
from views.main_view import MainView


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Instantiate MVVM Components
    model = SignalModel()
    viewmodel = MainViewModel(model)
    view = MainView(viewmodel)

    view.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
    