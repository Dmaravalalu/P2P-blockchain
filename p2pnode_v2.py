import socket
import threading
import os

LISTEN_PORT = 5001  # Customize as needed

# === Receiver Thread ===
def listen_for_incoming():
    server = socket.socket()
    server.bind(('0.0.0.0', LISTEN_PORT))
    server.listen(5)
    print(f"[Receiver] Listening on port {LISTEN_PORT}...")

    while True:
        conn, addr = server.accept()
        print(f"[Receiver] Connected by {addr}")

        # Receive filename
        filename = conn.recv(1024).decode()
        conn.send(b'FILENAME_RECEIVED')

        with open(f"received_{filename}", 'wb') as f:
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                f.write(data)
        print(f"[Receiver] File received: received_{filename}")
        conn.close()

# === Sender ===
def send_file(target_ip, target_port, filename):
    try:
        s = socket.socket()
        s.connect((target_ip, target_port))

        # Send filename
        s.send(filename.encode())
        ack = s.recv(1024).decode()
        if ack != 'FILENAME_RECEIVED':
            print("[Sender] Failed to handshake.")
            s.close()
            return

        with open(filename, 'rb') as f:
            data = f.read(1024)
            while data:
                s.send(data)
                data = f.read(1024)

        print(f"[Sender] File '{filename}' sent to {target_ip}.")
    except Exception as e:
        print(f"[Sender] Error: {e}")
    finally:
        s.close()

# === Main Logic ===
def main():
    # Start listener thread
    listener = threading.Thread(target=listen_for_incoming, daemon=True)
    listener.start()

    # Command loop
    while True:
        cmd = input("\n[COMMAND] Enter: send <IP> <filename> or 'exit': ").strip()
        if cmd.lower() == 'exit':
            print("[System] Exiting...")
            break
        elif cmd.startswith("send"):
            try:
                _, ip, filename = cmd.split()
                send_file(ip, LISTEN_PORT, filename)
            except ValueError:
                print("[!] Usage: send <IP> <filename>")
        else:
            print("[!] Unknown command.")

if __name__ == "__main__":
    main()
