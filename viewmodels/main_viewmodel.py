import numpy as np
from PySide6.QtCore import QObject, Signal


class MainViewModel(QObject):
    """ViewModel managing UI logic, plot modes, and channel selection state."""

    status_changed = Signal(str, bool)
    error_occurred = Signal(str)
    live_data_updated = Signal()

    def __init__(self, model):
        super().__init__()
        self.model = model

        # ViewModel State Properties
        self.selected_channel = 0  # 0 to 31
        self.signal_mode = "Original"  # Options: 'Original', 'RMS', 'Filtered'
        self.plot_all_channels = False

        # Connect model signals
        self.model.status_changed.connect(self.status_changed.emit)
        self.model.error_occurred.connect(self.error_occurred.emit)
        self.model.data_updated.connect(self.live_data_updated.emit)

    def connect_tcp(self, host: str, port_str: str):
        try:
            port = int(port_str)
            if not (1 <= port <= 65535):
                raise ValueError("Port must be between 1 and 65535.")
            self.model.start_connection(host, port)
        except ValueError as e:
            self.error_occurred.emit(f"Invalid Port: {str(e)}")

    def disconnect_tcp(self):
        self.model.stop_connection()

    def process_data(self, data: np.ndarray) -> np.ndarray:
        """Applies selected processing mode (Original, RMS, or Filtered) to signal data."""
        if data.size == 0:
            return data

        if self.signal_mode == "RMS":
            return self.model.compute_rms(data, window_size=25)
        elif self.signal_mode == "Filtered":
            return self.model.apply_filter(data, lowcut=1.0, highcut=40.0)
        return data  # Original

    def get_live_plot_data(self) -> np.ndarray:
        """Retrieves and processes current live buffer window."""
        raw_data = self.model.live_buffer
        return self.process_data(raw_data)

    def get_offline_plot_data(self) -> np.ndarray:
        """Retrieves and processes recorded streaming data."""
        raw_data = self.model.get_recorded_signal()
        return self.process_data(raw_data)
    