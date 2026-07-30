"""
Model Layer: Handles TCP socket streaming, byte buffering, 
rolling visualization windows, signal recording, and DSP algorithms.
"""

import socket
import numpy as np
from scipy.signal import butter, filtfilt
from PySide6.QtCore import QObject, Signal, QThread

class TCPClientWorker(QThread):
    """
    Background worker thread for non-blocking TCP socket communication.
    Accumulates raw byte buffers and parses float64 packets.
    """
    data_received = Signal(np.ndarray)
    status_changed = Signal(str, bool)
    error_occurred = Signal(str)

    def __init__(self, host="127.0.0.1", port=5000):
        super().__init__()
        self.host = host
        self.port = port
        self.running = False
        self.socket = None
        
        # Packet Specs: 32 channels * 18 samples * 8 bytes (float64) = 4608 bytes
        self.bytes_per_sample = 8
        self.channels = 32
        self.samples_per_chunk = 18
        self.packet_size = self.channels * self.samples_per_chunk * self.bytes_per_sample

    def run(self):
        """Connects to socket server and continuously streams and unpacks bytes."""
        self.running = True
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(3.0)
            self.socket.connect((self.host, self.port))
            self.status_changed.emit(f"Connected to {self.host}:{self.port}", True)
        except Exception as e:
            self.error_occurred.emit(f"Could not connect: {str(e)}")
            self.status_changed.emit("Disconnected", False)
            self.running = False
            return

        byte_buffer = bytearray()

        while self.running:
            try:
                chunk = self.socket.recv(4096)
                if not chunk:
                    self.error_occurred.emit("Server closed TCP connection.")
                    break
                byte_buffer.extend(chunk)

                # Process complete packets of 4608 bytes
                while len(byte_buffer) >= self.packet_size:
                    raw_data = byte_buffer[:self.packet_size]
                    del byte_buffer[:self.packet_size]

                    # Parse float64 data into shape (32 channels, 18 samples)
                    arr = np.frombuffer(raw_data, dtype=np.float64)
                    arr = arr.reshape((self.channels, self.samples_per_chunk))
                    self.data_received.emit(arr)

            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    self.error_occurred.emit(f"Socket error: {str(e)}")
                break

        self.stop_connection()

    def stop_connection(self):
        """Safely closes socket connection."""
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
            self.socket = None
            self.status_changed.emit("Disconnected", False)


class SignalModel(QObject):
    """
    Model managing signal state, rolling live buffers, full dynamic recording,
    and digital signal processing algorithms (RMS & Butterworth Filter).
    """
    data_updated = Signal()
    status_changed = Signal(str, bool)
    error_occurred = Signal(str)

    def __init__(self, buffer_size=1000):
        super().__init__()
        self.num_channels = 32
        self.buffer_size = buffer_size
        self.sample_rate = 250.0  # Hz

        # Rolling live buffer (32 channels x 1000 samples = 4.0 seconds)
        self.live_buffer = np.zeros((self.num_channels, self.buffer_size))
        
        # Session storage for offline inspection
        self.recorded_chunks = []
        self.worker = None

    def start_connection(self, host: str, port: int):
        if self.worker and self.worker.isRunning():
            self.stop_connection()

        self.worker = TCPClientWorker(host=host, port=port)
        self.worker.data_received.connect(self._handle_incoming_data)
        self.worker.status_changed.connect(self.status_changed.emit)
        self.worker.error_occurred.connect(self.error_occurred.emit)
        self.worker.start()

    def stop_connection(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop_connection()
            self.worker.quit()
            self.worker.wait()

    def _handle_incoming_data(self, chunk: np.ndarray):
        n_samples = chunk.shape[1]
        self.live_buffer = np.roll(self.live_buffer, -n_samples, axis=1)
        self.live_buffer[:, -n_samples:] = chunk

        self.recorded_chunks.append(chunk)
        self.data_updated.emit()

    def get_recorded_signal(self) -> np.ndarray:
        """Returns full session time-series matrix shape (32 channels, N samples)."""
        if not self.recorded_chunks:
            return np.zeros((self.num_channels, 0))
        return np.hstack(self.recorded_chunks)

    # --- DSP Algorithms ---
    @staticmethod
    def compute_rms(data: np.ndarray, window_size: int = 20) -> np.ndarray:
        """Moving Root Mean Square across time axis (Window = 20 samples / 80ms)."""
        if data.size == 0 or data.shape[1] < window_size:
            return np.zeros_like(data)
        output = np.zeros_like(data)
        for i in range(data.shape[1]):
            start_idx = max(0, i - window_size + 1)
            output[:, i] = np.sqrt(np.mean(data[:, start_idx:i+1]**2, axis=1))
        return output

    @staticmethod
    def apply_butterworth_filter(data: np.ndarray, lowcut=0.5, highcut=40.0, fs=250.0) -> np.ndarray:
        """4th-order Butterworth Bandpass Filter (0.5 Hz - 40 Hz)."""
        if data.size == 0 or data.shape[1] < 15:
            return data
        try:
            nyq = 0.5 * fs
            low = lowcut / nyq
            high = highcut / nyq
            b, a = butter(4, [low, high], btype='band')
            return filtfilt(b, a, data, axis=1)
        except Exception:
            return data