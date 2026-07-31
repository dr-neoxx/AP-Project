import socket
import pickle
import time
import threading
from pathlib import Path

import numpy as np


class EMGTCPServer:
    def __init__(
        self,
        host="127.0.0.1",
        port=12345,
        pkl_file="recording.pkl",
    ):
        self.host = host
        self.port = port
        self.pkl_file = Path(__file__).parent / pkl_file

        self.server_socket = None
        self.clients = []
        self.running = False

        self.channels = 32
        self.samples_per_packet = 18

        self.load_data()

    def load_data(self):
        """Load the recorded biosignal from recording.pkl."""
        try:
            with open(self.pkl_file, "rb") as file:
                data = pickle.load(file)

            self.signal = data["biosignal"][: self.channels, :, :]
            self.sampling_rate = data["device_information"]["sampling_frequency"]

            print("Recording loaded successfully.")
            print(f"Signal shape: {self.signal.shape}")
            print(f"Sampling rate: {self.sampling_rate} Hz")

        except FileNotFoundError:
            raise FileNotFoundError(
                f"Could not find '{self.pkl_file}'. "
                "Place recording.pkl in the same folder as server.py."
            )

        except (KeyError, pickle.UnpicklingError) as error:
            raise RuntimeError(
                f"Error reading recording.pkl: {error}"
            ) from error

    def start(self):
        """Start the TCP server."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1,
        )

        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)

        self.running = True

        print("=" * 60)
        print("TCP Signal Server Started")
        print(f"Host: {self.host}")
        print(f"Port: {self.port}")
        print("=" * 60)

        threading.Thread(
            target=self.accept_connections,
            daemon=True,
        ).start()

    def accept_connections(self):
        """Accept incoming TCP client connections."""
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()

                print(f"Client connected: {address}")

                self.clients.append(client_socket)

                threading.Thread(
                    target=self.handle_client,
                    args=(client_socket,),
                    daemon=True,
                ).start()

            except OSError:
                if self.running:
                    print("Error accepting connection.")

    def handle_client(self, client_socket):
        """Continuously stream the recording to one connected client."""
        try:
            num_windows = self.signal.shape[2]

            while self.running:
                for window in range(num_windows):

                    packet = (
                        self.signal[:, :, window]
                        .astype(np.float64)
                        .copy(order="C")
                    )

                    client_socket.sendall(packet.tobytes())

                    time.sleep(
                        self.samples_per_packet /
                        self.sampling_rate
                    )

        except (
            BrokenPipeError,
            ConnectionResetError,
            ConnectionAbortedError,
            OSError,
        ):
            print("Client disconnected.")

        finally:
            if client_socket in self.clients:
                self.clients.remove(client_socket)

            client_socket.close()

    def stop(self):
        """Stop the server."""
        self.running = False

        if self.server_socket:
            self.server_socket.close()

        for client in self.clients:
            try:
                client.close()
            except Exception:
                pass

        self.clients.clear()

        print("Server stopped.")


if __name__ == "__main__":
    server = EMGTCPServer()

    try:
        server.start()

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nStopping server...")
        server.stop()