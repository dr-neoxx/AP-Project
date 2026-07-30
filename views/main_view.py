"""
View Layer: PySide6 Layout hosting VisPy Canvas (with fixed axis bounds)
and Matplotlib Canvas (for offline analysis across all Signal Modes).
"""

import os
import numpy as np
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QComboBox, QCheckBox, QTabWidget, 
    QGroupBox, QSlider, QStatusBar, QTableWidget, QTableWidgetItem,
    QFileDialog, QHeaderView, QMessageBox
)
from PySide6.QtCore import Qt

# VisPy Canvas & Axis Widgets
from vispy import scene

# Matplotlib Canvas
import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class MainView(QMainWindow):
    def __init__(self, viewmodel):
        super().__init__()
        self.vm = viewmodel
        self.setWindowTitle("TCP Signal Visualization Application — MVVM Architecture")
        self.resize(1200, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)

        self._create_connection_panel()
        self._create_control_panel()
        self._create_tabs_panel()
        self._create_status_bar()

        self.vm.data_updated.connect(self._update_live_vispy_plot)
        self.vm.status_changed.connect(self._on_status_changed)
        self.vm.error_occurred.connect(self._on_error_occurred)
        self.vm.metrics_updated.connect(self._on_metrics_updated)

    # --- Connection Panel ---
    def _create_connection_panel(self):
        group = QGroupBox("TCP Connection Settings")
        layout = QHBoxLayout(group)

        layout.addWidget(QLabel("Host:"))
        self.host_input = QLineEdit("127.0.0.1")
        layout.addWidget(self.host_input)

        layout.addWidget(QLabel("Port:"))
        self.port_input = QLineEdit("5000")
        layout.addWidget(self.port_input)

        self.btn_connect = QPushButton("Connect")
        self.btn_connect.clicked.connect(self._on_connect_clicked)
        layout.addWidget(self.btn_connect)

        self.btn_disconnect = QPushButton("Disconnect")
        self.btn_disconnect.setEnabled(False)
        self.btn_disconnect.clicked.connect(self._on_disconnect_clicked)
        layout.addWidget(self.btn_disconnect)

        self.status_lbl = QLabel("Status: Disconnected")
        self.status_lbl.setStyleSheet("color: #ff5555; font-weight: bold;")
        layout.addWidget(self.status_lbl)

        self.main_layout.addWidget(group)

    # --- Control Panel ---
    def _create_control_panel(self):
        group = QGroupBox("Signal Controls & Display Options")
        layout = QHBoxLayout(group)

        layout.addWidget(QLabel("Signal Mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Original", "RMS", "Filtered"])
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        layout.addWidget(self.mode_combo)

        layout.addWidget(QLabel("Channel:"))
        self.channel_combo = QComboBox()
        self.channel_combo.addItems([f"Channel {i+1}" for i in range(32)])
        self.channel_combo.currentIndexChanged.connect(self._on_channel_changed)
        layout.addWidget(self.channel_combo)

        self.cb_plot_all = QCheckBox("Plot All Channels")
        self.cb_plot_all.toggled.connect(self._on_plot_all_toggled)
        layout.addWidget(self.cb_plot_all)

        layout.addWidget(QLabel("Gain Zoom:"))
        self.gain_slider = QSlider(Qt.Horizontal)
        self.gain_slider.setRange(1, 50)
        self.gain_slider.setValue(10)
        self.gain_slider.valueChanged.connect(self._on_gain_changed)
        layout.addWidget(self.gain_slider)
        
        self.gain_val_lbl = QLabel("1.0x")
        layout.addWidget(self.gain_val_lbl)

        self.main_layout.addWidget(group)

    # --- Tabs Panel ---
    def _create_tabs_panel(self):
        self.tabs = QTabWidget()
        
        # Tab 1: VisPy Live View with Scaled Grid & Constrained Axes
        self.vispy_tab = QWidget()
        vispy_layout = QVBoxLayout(self.vispy_tab)
        
        self.canvas = scene.SceneCanvas(keys='interactive', show=True, bgcolor='#121212')
        grid = self.canvas.central_widget.add_grid(margin=15)
        grid.spacing = 0

        # Main Plot Viewport
        self.view = grid.add_view(row=0, col=1)
        self.view.camera = 'panzoom'
        self.view.camera.rect = (0, -2, 4.0, 4)

        # X-Axis (Bottom) with increased margins to prevent line overlap
        self.x_axis = scene.AxisWidget(
            orientation='bottom', 
            axis_label='Time (seconds)',
            axis_font_size=10,
            tick_font_size=9,
            tick_label_margin=32,
            axis_label_margin=65
        )
        self.x_axis.height_max = 90

        # Y-Axis (Left)
        self.y_axis = scene.AxisWidget(
            orientation='left', 
            axis_label='Amplitude',
            axis_font_size=10,
            tick_font_size=9,
            tick_label_margin=12,
            axis_label_margin=55
        )
        self.y_axis.width_max = 90

        grid.add_widget(self.x_axis, row=1, col=1)
        grid.add_widget(self.y_axis, row=0, col=0)
        
        # Right margin buffer to prevent clipping of rightmost X-tick values
        right_padding = grid.add_widget(row=0, col=2)
        right_padding.width_max = 30

        self.x_axis.link_view(self.view)
        self.y_axis.link_view(self.view)

        # Pre-allocate 32 VisPy lines
        self.lines = []
        colors = ['#00ffff', '#ff00ff', '#ffff00', '#00ff00', '#ff8800', '#0088ff']
        for i in range(32):
            line = scene.visuals.Line(color=colors[i % len(colors)], parent=self.view.scene)
            line.visible = (i == 0)
            self.lines.append(line)
            
        vispy_layout.addWidget(self.canvas.native)
        self.tabs.addTab(self.vispy_tab, "Live View (VisPy)")

        # Tab 2: Matplotlib Offline Inspection
        self.mpl_tab = QWidget()
        mpl_layout = QHBoxLayout(self.mpl_tab)

        left_box = QWidget()
        left_layout = QVBoxLayout(left_box)
        
        self.btn_inspect = QPushButton("Inspect & Plot Offline Data")
        self.btn_inspect.clicked.connect(self._on_inspect_offline_clicked)
        left_layout.addWidget(self.btn_inspect)

        self.fig = Figure(figsize=(6, 4), facecolor='#1e1e1e')
        self.canvas_mpl = FigureCanvas(self.fig)
        left_layout.addWidget(self.canvas_mpl)

        export_layout = QHBoxLayout()
        self.btn_export_plot = QPushButton("Export Plot (PNG)")
        self.btn_export_plot.clicked.connect(self._export_plot)
        self.btn_export_csv = QPushButton("Export Data (CSV)")
        self.btn_export_csv.clicked.connect(self._export_csv)
        export_layout.addWidget(self.btn_export_plot)
        export_layout.addWidget(self.btn_export_csv)
        left_layout.addLayout(export_layout)

        mpl_layout.addWidget(left_box, stretch=2)

        right_box = QWidget()
        right_layout = QVBoxLayout(right_box)
        right_layout.addWidget(QLabel("<b>Channel Statistics Summary</b>"))
        
        self.stats_table = QTableWidget(32, 4)
        self.stats_table.setHorizontalHeaderLabels(["Mean", "Std Dev", "Pk-Pk", "RMS"])
        self.stats_table.setVerticalHeaderLabels([f"Ch {i+1}" for i in range(32)])
        self.stats_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        right_layout.addWidget(self.stats_table)

        mpl_layout.addWidget(right_box, stretch=1)

        self.tabs.addTab(self.mpl_tab, "Offline Analytics (Matplotlib)")
        self.main_layout.addWidget(self.tabs)

    # --- Status Bar ---
    def _create_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        self.sb_packets_lbl = QLabel("Packets Received: 0")
        self.sb_rate_lbl = QLabel("Sample Rate: 250 Hz")
        
        self.status_bar.addPermanentWidget(self.sb_rate_lbl)
        self.status_bar.addPermanentWidget(self.sb_packets_lbl)
        self.status_bar.showMessage("Ready.")

    # --- Event Handlers ---
    def _on_connect_clicked(self):
        host = self.host_input.text().strip()
        try:
            port = int(self.port_input.text().strip())
            self.vm.connect_tcp(host, port)
        except ValueError:
            QMessageBox.critical(self, "Invalid Input", "Port must be an integer.")

    def _on_disconnect_clicked(self):
        self.vm.disconnect_tcp()

    def _on_mode_changed(self, text):
        self.vm.signal_mode = text
        if self.tabs.currentIndex() == 1:
            self._on_inspect_offline_clicked()

    def _on_channel_changed(self, index):
        self.vm.selected_channel = index
        if self.tabs.currentIndex() == 1:
            self._on_inspect_offline_clicked()

    def _on_plot_all_toggled(self, checked):
        self.vm.plot_all = checked
        self.channel_combo.setEnabled(not checked)
        if self.tabs.currentIndex() == 1:
            self._on_inspect_offline_clicked()

    def _on_gain_changed(self, val):
        gain_factor = val / 10.0
        self.gain_val_lbl.setText(f"{gain_factor:.1f}x")
        self.vm.gain = gain_factor

    def _on_status_changed(self, msg, connected):
        self.status_lbl.setText(f"Status: {msg}")
        if connected:
            self.status_lbl.setStyleSheet("color: #55ff55; font-weight: bold;")
            self.btn_connect.setEnabled(False)
            self.btn_disconnect.setEnabled(True)
            self.status_bar.showMessage("Streaming TCP data...")
        else:
            self.status_lbl.setStyleSheet("color: #ff5555; font-weight: bold;")
            self.btn_connect.setEnabled(True)
            self.btn_disconnect.setEnabled(False)
            self.status_bar.showMessage("Disconnected.")

    def _on_error_occurred(self, err):
        self.status_bar.showMessage(f"Error: {err}")

    def _on_metrics_updated(self, packet_count):
        self.sb_packets_lbl.setText(f"Packets Received: {packet_count}")

    # --- VisPy Live Plot Update ---
    def _update_live_vispy_plot(self):
        data = self.vm.get_processed_live_data()
        n_samples = data.shape[1]
        time_x = np.linspace(0, 4.0, n_samples)

        if self.vm.plot_all:
            offset_step = 2.0
            for ch in range(32):
                y = data[ch, :] + (15.5 - ch) * offset_step
                pts = np.column_stack((time_x, y))
                self.lines[ch].set_data(pos=pts)
                self.lines[ch].visible = True
            self.view.camera.rect = (0, -35, 4.0, 70)
        else:
            sel_ch = self.vm.selected_channel
            for ch in range(32):
                if ch == sel_ch:
                    pts = np.column_stack((time_x, data[ch, :]))
                    self.lines[ch].set_data(pos=pts)
                    self.lines[ch].visible = True
                else:
                    self.lines[ch].visible = False
            
            # Adapt Y-axis camera limits based on signal mode
            if self.vm.signal_mode == "RMS":
                # RMS is strictly positive [0, +4]
                self.view.camera.rect = (0, 0, 4.0, 4)
            else:
                # Original and Filtered modes oscillate around 0 [-3, +3]
                self.view.camera.rect = (0, -3, 4.0, 6)
    

    # --- Offline Matplotlib Inspection ---
    def _on_inspect_offline_clicked(self):
        recorded = self.vm.get_processed_offline_data()
        if recorded.size == 0 or recorded.shape[1] == 0:
            QMessageBox.warning(self, "No Recorded Data", "No signal data available for offline plotting. Connect to server first.")
            return

        self.fig.clear()
        ax = self.fig.add_subplot(111)
        ax.set_facecolor('#121212')
        ax.tick_params(colors='white')
        ax.xaxis.label.set_color('white')
        ax.yaxis.label.set_color('white')
        ax.title.set_color('white')

        time_axis = np.arange(recorded.shape[1]) / 250.0
        mode_str = self.vm.signal_mode

        if self.vm.plot_all:
            for ch in range(min(8, recorded.shape[0])):
                ax.plot(time_axis, recorded[ch, :] + ch * 2, label=f"Ch {ch+1}")
            ax.set_title(f"Offline Inspection — Multi-Channel ({mode_str} Mode)")
            ax.legend(loc="upper right", fontsize='small')
        else:
            ch = self.vm.selected_channel
            ax.plot(time_axis, recorded[ch, :], color='#00ffff')
            ax.set_title(f"Offline Inspection — Channel {ch+1} ({mode_str} Mode)")

        ax.set_xlabel("Time (seconds)")
        ax.set_ylabel("Amplitude")
        ax.grid(True, color='#333333')
        self.fig.tight_layout()
        self.canvas_mpl.draw()

        stats = self.vm.compute_offline_statistics()
        for ch, metrics in stats.items():
            self.stats_table.setItem(ch - 1, 0, QTableWidgetItem(f"{metrics['mean']:.3f}"))
            self.stats_table.setItem(ch - 1, 1, QTableWidgetItem(f"{metrics['std']:.3f}"))
            self.stats_table.setItem(ch - 1, 2, QTableWidgetItem(f"{metrics['peak_to_peak']:.3f}"))
            self.stats_table.setItem(ch - 1, 3, QTableWidgetItem(f"{metrics['rms']:.3f}"))

    def _export_plot(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Plot", "offline_signal.png", "PNG Image (*.png);;PDF File (*.pdf)")
        if file_path:
            self.fig.savefig(file_path, dpi=300)
            QMessageBox.information(self, "Export Complete", f"Saved plot to {os.path.basename(file_path)}")

    def _export_csv(self):
        recorded = self.vm.get_processed_offline_data()
        if recorded.size == 0:
            QMessageBox.warning(self, "Export Error", "No data to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Save Data CSV", "recorded_signals.csv", "CSV File (*.csv)")
        if file_path:
            np.savetxt(file_path, recorded.T, delimiter=",", header=",".join([f"Ch_{i+1}" for i in range(32)]))
            QMessageBox.information(self, "Export Complete", f"Saved data to {os.path.basename(file_path)}")