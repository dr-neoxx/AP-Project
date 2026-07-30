"""
ViewModel Layer: Manages application state, signal selection, 
and transforms raw data into presentation format for the View.
"""

import numpy as np
from PySide6.QtCore import QObject, Signal

class MainViewModel(QObject):
    data_updated = Signal()
    status_changed = Signal(str, bool)
    error_occurred = Signal(str)
    metrics_updated = Signal(int)

    def __init__(self, model):
        super().__init__()
        self._model = model
        
        # State Properties
        self._selected_channel = 0
        self._signal_mode = "Original"  # "Original", "RMS", "Filtered"
        self._plot_all = False
        self._gain = 1.0
        self._packet_count = 0

        self._model.data_updated.connect(self._on_data_updated)
        self._model.status_changed.connect(self.status_changed.emit)
        self._model.error_occurred.connect(self.error_occurred.emit)

    def _on_data_updated(self):
        self._packet_count += 1
        self.metrics_updated.emit(self._packet_count)
        self.data_updated.emit()

    def connect_tcp(self, host: str, port: int):
        self._packet_count = 0
        self._model.start_connection(host, port)

    def disconnect_tcp(self):
        self._model.stop_connection()

    # --- Properties ---
    @property
    def selected_channel(self) -> int:
        return self._selected_channel

    @selected_channel.setter
    def selected_channel(self, index: int):
        self._selected_channel = max(0, min(index, 31))
        self.data_updated.emit()

    @property
    def signal_mode(self) -> str:
        return self._signal_mode

    @signal_mode.setter
    def signal_mode(self, mode: str):
        if mode in ["Original", "RMS", "Filtered"]:
            self._signal_mode = mode
            self.data_updated.emit()

    @property
    def plot_all(self) -> bool:
        return self._plot_all

    @plot_all.setter
    def plot_all(self, value: bool):
        self._plot_all = value
        self.data_updated.emit()

    @property
    def gain(self) -> float:
        return self._gain

    @gain.setter
    def gain(self, value: float):
        self._gain = max(0.1, min(value, 10.0))
        self.data_updated.emit()

    # --- Processing Handlers ---
    def _process_data(self, data: np.ndarray) -> np.ndarray:
        """Applies active Signal Mode (Original, RMS, or Filtered) to dataset."""
        if data.size == 0:
            return data
        
        scaled_data = data * self._gain
        if self._signal_mode == "RMS":
            return self._model.compute_rms(scaled_data)
        elif self._signal_mode == "Filtered":
            return self._model.apply_butterworth_filter(scaled_data)
        return scaled_data

    def get_processed_live_data(self) -> np.ndarray:
        """Returns live rolling buffer processed by active Signal Mode."""
        return self._process_data(self._model.live_buffer.copy())

    def get_processed_offline_data(self) -> np.ndarray:
        """Returns recorded session matrix processed by active Signal Mode."""
        return self._process_data(self._model.get_recorded_signal())

    def compute_offline_statistics(self) -> dict:
        """Computes statistical metrics for all recorded channels."""
        data = self.get_processed_offline_data()
        if data.size == 0:
            return {}
        
        stats = {}
        for ch in range(data.shape[0]):
            ch_data = data[ch, :]
            stats[ch + 1] = {
                "mean": np.mean(ch_data),
                "std": np.std(ch_data),
                "peak_to_peak": np.ptp(ch_data),
                "rms": np.sqrt(np.mean(ch_data**2))
            }
        return stats
