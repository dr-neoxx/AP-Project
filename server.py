import socket
import time
import numpy as np

def start_server(host='127.0.0.1', port=5000):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(1)
    print(f"Mock TCP Signal Server listening on {host}:{port}...")
    
    conn, addr = server.accept()
    print(f"Connected by GUI application at {addr}")
    
    try:
        t = 0
        while True:
            # Generate 32 channels of synthetic sine wave signals + noise
            t_vector = np.linspace(t, t + 0.072, 18)
            channels_data = []
            for ch in range(32):
                freq = 5 + ch * 0.5
                signal = np.sin(2 * np.pi * freq * t_vector) + 0.1 * np.random.randn(18)
                channels_data.append(signal)
            
            data_matrix = np.array(channels_data, dtype=np.float64)
            conn.sendall(data_matrix.tobytes())
            
            t += 0.072
            time.sleep(0.04) # Stream ~25 chunks per second
            
    except (ConnectionResetError, BrokenPipeError):
        print("Client disconnected.")
    finally:
        conn.close()
        server.close()

if __name__ == "__main__":
    start_server()
    