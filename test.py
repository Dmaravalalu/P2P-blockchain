import socket
import threading
import os

# === CONFIGURATION ===
LISTEN_PORT = 5001  # Port to receive files
PEER_IP = input("Enter peer's IP address: ")  # IP of the other computer
PEER_PORT = 5001

# === RECEIVER THREAD ===
def receive_files():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('0.0.0.0', LISTEN_PORT))
    server_socket.listen(5)
    print(f"[RECEIVER] Listening on port {LISTEN_PORT}...")

    while True:
        conn, addr = server_socket.accept()
        print(f"[RECEIVER] Connected by {addr}")

        # Receive filename and filesize
        filename = conn.recv(1024).decode()
        filesize = int(conn.recv(1024).decode())

        # Receive the file data
        with open(f"received_{filename}", 'wb') as f:
            received = 0
            while received < filesize:
                data = conn.recv(4096)
                if not data:
                    break
                f.write(data)
                received += len(data)

        print(f"[RECEIVER] File received: received_{filename} ({filesize} bytes)")
        conn.close()

# === SENDER FUNCTION ===
def send_file():
    while True:
        filepath = input("\nEnter the path of the file to send (or type 'exit' to quit): ").strip()
        if filepath.lower() == 'exit':
            break
        if not os.path.exists(filepath):
            print("❌ File not found. Try again.")
            continue

        filename = os.path.basename(filepath)
        filesize = os.path.getsize(filepath)

        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((PEER_IP, PEER_PORT))

            client_socket.send(filename.encode())
            client_socket.send(str(filesize).encode())

            with open(filepath, 'rb') as f:
                while True:
                    bytes_read = f.read(4096)
                    if not bytes_read:
                        break
                    client_socket.sendall(bytes_read)

            print(f"[SENDER] File sent successfully: {filename} ({filesize} bytes)")
            client_socket.close()

        except Exception as e:
            print(f"❌ Could not send file: {e}")

# === MAIN ===
if __name__ == "__main__":
    # Start receiver in background thread
    threading.Thread(target=receive_files, daemon=True).start()

    # Start sender loop
    send_file()

    print("Exiting program.")
