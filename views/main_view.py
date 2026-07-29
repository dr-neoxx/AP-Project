import numpy as np
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QComboBox, QCheckBox, QTabWidget,
    QMessageBox, QGroupBox, QSpinBox
)
from PySide6.QtCore import Qt

# VisPy components for real-time visualization
from vispy import scene

# Matplotlib components for offline analysis
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class VisPyPlotCanvas(QWidget):
    """High-performance VisPy SceneCanvas wrapper embedded in Qt layout."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.canvas = scene.SceneCanvas(keys=None, show=False, bgcolor="black")
        self.view = self.canvas.central_widget.add_view()
        self.view.camera = scene.PanZoomCamera(rect=(0, -5, 1000, 10))

        # Add visual line
        self.line = scene.visuals.Line(color="cyan", parent=self.view.scene, antialias=True)
        self.grid = scene.visuals.GridLines(color=(0.3, 0.3, 0.3, 0.5), parent=self.view.scene)

        # Integrate VisPy canvas native widget into PySide6 layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas.native)

    def update_single_channel(self, signal_data: np.ndarray):
        n_samples = len(signal_data)
        x = np.arange(n_samples)
        y = signal_data
        pos = np.column_stack((x, y))
        self.line.set_data(pos=pos, color="cyan")
        
        # Adjust view bounds dynamically
        if n_samples > 0:
            ymin, ymax = np.min(y), np.max(y)
            margin = max(abs(ymax - ymin) * 0.2, 1.0)
            self.view.camera.rect = (0, ymin - margin, n_samples, (ymax - ymin) + 2 * margin)

    def update_all_channels(self, signal_data: np.ndarray, vertical_offset: float = 5.0):
        channels, n_samples = signal_data.shape
        x = np.tile(np.arange(n_samples), channels)
        
        # Apply vertical offset per channel for clean stacked view
        offsets = (np.arange(channels) * vertical_offset)[:, None]
        y_offset = signal_data + offsets
        y = y_offset.flatten()
        
        pos = np.column_stack((x, y))
        self.line.set_data(pos=pos, color="lime", connect="strip")
        
        total_height = channels * vertical_offset
        self.view.camera.rect = (0, -vertical_offset, n_samples, total_height + vertical_offset)


class MainView(QMainWindow):
    """Main Application GUI View."""

    def __init__(self, viewmodel):
        super().__init__()
        self.vm = viewmodel
        self.setWindowTitle("TCP Signal Visualization Application — MVVM")
        self.resize(1100, 750)

        self._init_ui()
        self._bind_viewmodel()

    def _init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # 1. Connection Header
        conn_group = QGroupBox("TCP Connection Settings")
        conn_layout = QHBoxLayout(conn_group)

        conn_layout.addWidget(QLabel("Host:"))
        self.host_input = QLineEdit("127.0.0.1")
        conn_layout.addWidget(self.host_input)

        conn_layout.addWidget(QLabel("Port:"))
        self.port_input = QLineEdit("5000")
        conn_layout.addWidget(self.port_input)

        self.btn_connect = QPushButton("Connect")
        self.btn_disconnect = QPushButton("Disconnect")
        self.btn_disconnect.setEnabled(False)
        conn_layout.addWidget(self.btn_connect)
        conn_layout.addWidget(self.btn_disconnect)

        self.status_label = QLabel("Status: Disconnected")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        conn_layout.addWidget(self.status_label)
        main_layout.addWidget(conn_group)

        # 2. Controls Panel
        ctrl_group = QGroupBox("Signal Controls")
        ctrl_layout = QHBoxLayout(ctrl_group)

        ctrl_layout.addWidget(QLabel("Signal Mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Original", "RMS", "Filtered"])
        ctrl_layout.addWidget(self.mode_combo)

        ctrl_layout.addWidget(QLabel("Channel:"))
        self.channel_spin = QSpinBox()
        self.channel_spin.setRange(1, 32)
        self.channel_spin.setValue(1)
        ctrl_layout.addWidget(self.channel_spin)

        self.btn_plot_all = QCheckBox("Plot All Channels")
        ctrl_layout.addWidget(self.btn_plot_all)
        main_layout.addWidget(ctrl_group)

        # 3. Main Visualization Tabs
        self.tabs = QTabWidget()
        
        # Tab 1: VisPy Live Visualization
        self.vispy_canvas = VisPyPlotCanvas()
        self.tabs.addTab(self.vispy_canvas, "Live View (VisPy)")

        # Tab 2: Matplotlib Offline Inspection
        self.offline_widget = QWidget()
        offline_layout = QVBoxLayout(self.offline_widget)
        
        self.fig = Figure(figsize=(8, 4))
        self.mpl_canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111)
        
        self.btn_refresh_offline = QPushButton("Inspect Offline Data")
        offline_layout.addWidget(self.btn_refresh_offline)
        offline_layout.addWidget(self.mpl_canvas)
        self.tabs.addTab(self.offline_widget, "Offline Inspection (Matplotlib)")

        main_layout.addWidget(self.tabs)

    def _bind_viewmodel(self):
        # Event Handlers -> ViewModel Actions
        self.btn_connect.clicked.connect(
            lambda: self.vm.connect_tcp(self.host_input.text().strip(), self.port_input.text().strip())
        )
        self.btn_disconnect.clicked.connect(self.vm.disconnect_tcp)

        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        self.channel_spin.valueChanged.connect(self._on_channel_changed)
        self.btn_plot_all.toggled.connect(self._on_plot_all_toggled)

        self.btn_refresh_offline.clicked.connect(self.update_offline_plot)

        # ViewModel -> View Updates
        self.vm.status_changed.connect(self.update_connection_status)
        self.vm.error_occurred.connect(self.show_error)
        self.vm.live_data_updated.connect(self.update_live_plot)

    def _on_mode_changed(self, mode_text: str):
        self.vm.signal_mode = mode_text
        self.update_live_plot()

    def _on_channel_changed(self, channel_num: int):
        self.vm.selected_channel = channel_num - 1  # 0-indexed
        self.update_live_plot()

    def _on_plot_all_toggled(self, checked: bool):
        self.vm.plot_all_channels = checked
        self.channel_spin.setEnabled(not checked)
        self.update_live_plot()

    def update_connection_status(self, message: str, is_connected: bool):
        self.status_label.setText(f"Status: {message}")
        if is_connected:
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
            self.btn_connect.setEnabled(False)
            self.btn_disconnect.setEnabled(True)
        else:
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            self.btn_connect.setEnabled(True)
            self.btn_disconnect.setEnabled(False)

    def show_error(self, message: str):
        QMessageBox.warning(self, "Application Error", message)

    def update_live_plot(self):
        if self.tabs.currentIndex() != 0:
            return  # Only update live tab if active

        data = self.vm.get_live_plot_data()
        if data.size == 0:
            return

        if self.vm.plot_all_channels:
            self.vispy_canvas.update_all_channels(data)
        else:
            ch = self.vm.selected_channel
            self.vispy_canvas.update_single_channel(data[ch, :])

    def update_offline_plot(self):
        data = self.vm.get_offline_plot_data()
        self.ax.clear()

        if data.shape[1] == 0:
            self.ax.set_title("No recorded signal available. Run streaming first.")
            self.mpl_canvas.draw()
            return

        time_axis = np.arange(data.shape[1]) / self.vm.model.sample_rate

        if self.vm.plot_all_channels:
            for i in range(data.shape[0]):
                self.ax.plot(time_axis, data[i, :] + (i * 5.0), label=f"Ch {i+1}" if i < 3 else "")
            self.ax.set_ylabel("Amplitude + Vertical Offset")
        else:
            ch = self.vm.selected_channel
            self.ax.plot(time_axis, data[ch, :], color="blue", label=f"Channel {ch+1}")
            self.ax.set_ylabel("Amplitude")

        self.ax.set_title(f"Offline Signal Analysis — Mode: {self.vm.signal_mode}")
        self.ax.set_xlabel("Time (s)")
        self.ax.grid(True)
        self.fig.tight_layout()
        self.mpl_canvas.draw()
        