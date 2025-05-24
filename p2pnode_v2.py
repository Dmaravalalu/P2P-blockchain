import socket
import threading
import time
import os

LISTEN_PORT = 5001
DISCOVERY_PORT = 5002
BROADCAST_INTERVAL = 5  # seconds

discovered_peers = set()

# === Receiver Thread ===
def listen_for_incoming():
    server = socket.socket()
    server.bind(('0.0.0.0', LISTEN_PORT))
    server.listen(5)
    print(f"[Receiver] Listening on port {LISTEN_PORT}...")

    while True:
        conn, addr = server.accept()
        print(f"[Receiver] Connected by {addr}")

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

# === Peer Discovery: Broadcast ===
def broadcast_presence():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    while True:
        message = b'P2P_PEER_HERE'
        sock.sendto(message, ('<broadcast>', DISCOVERY_PORT))
        time.sleep(BROADCAST_INTERVAL)

# === Peer Discovery: Listener ===
def listen_for_peers():
    global discovered_peers
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', DISCOVERY_PORT))

    while True:
        data, addr = sock.recvfrom(1024)
        if data == b'P2P_PEER_HERE':
            ip = addr[0]
            if ip != socket.gethostbyname(socket.gethostname()) and ip not in discovered_peers:
                discovered_peers.add(ip)
                print(f"[Discovery] New peer discovered: {ip}")

# === Main ===
def main():
    # Start background threads
    threading.Thread(target=listen_for_incoming, daemon=True).start()
    threading.Thread(target=broadcast_presence, daemon=True).start()
    threading.Thread(target=listen_for_peers, daemon=True).start()

    while True:
        cmd = input("\n[COMMAND] Enter: send <IP> <filename>, 'list', or 'exit': ").strip()
        if cmd.lower() == 'exit':
            print("[System] Exiting...")
            break
        elif cmd.lower() == 'list':
            if discovered_peers:
                print("[Peers] Discovered Peers:")
                for peer in discovered_peers:
                    print(f" - {peer}")
            else:
                print("[Peers] No peers discovered yet.")
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
