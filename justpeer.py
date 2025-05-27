import socket
import threading
import os
import json
import platform
import time
from datetime import datetime

LISTEN_PORT = 5001
BROADCAST_PORT = 5002
BROADCAST_INTERVAL = 5  # seconds
BROADCAST_IP = '255.255.255.255'

# IP and port of the blockchain host (replace with your host's IP)
HOST_IP = '192.168.1.X'        # <-- set your blockchain host IP here
HOST_BLOCKCHAIN_PORT = 6000    # Port host listens on for blockchain metadata & queries

PEER_NAME = platform.node() or socket.gethostname()
discovered_peers = {}

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

        received_file_path = f"received_{filename}"
        with open(received_file_path, 'wb') as f:
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                f.write(data)

        print(f"[Receiver] File received: {received_file_path}")
        conn.close()

# === Broadcast Presence ===
def broadcast_presence():
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    udp.settimeout(0.2)

    while True:
        msg = json.dumps({
            "name": PEER_NAME,
            "ip": socket.gethostbyname(socket.gethostname()),
            "port": LISTEN_PORT
        }).encode()
        udp.sendto(msg, (BROADCAST_IP, BROADCAST_PORT))
        time.sleep(BROADCAST_INTERVAL)

# === Listen for Broadcasts ===
def listen_for_broadcasts():
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.bind(("", BROADCAST_PORT))
    while True:
        try:
            data, addr = udp.recvfrom(1024)
            peer_info = json.loads(data.decode())
            ip = peer_info.get("ip")
            name = peer_info.get("name")
            if ip != socket.gethostbyname(socket.gethostname()):
                discovered_peers[ip] = name
        except:
            continue

# === Send metadata to blockchain host before file transfer ===
def send_metadata_to_host(filename, receiver_ip):
    metadata = {
        'sender': socket.gethostbyname(socket.gethostname()),
        'receiver': receiver_ip,
        'filename': os.path.basename(filename),
        'timestamp': datetime.utcnow().isoformat()
    }
    try:
        s = socket.socket()
        s.connect((HOST_IP, HOST_BLOCKCHAIN_PORT))
        s.send(json.dumps({'type': 'metadata', 'data': metadata}).encode())
        print(f"[Metadata] Sent to host for file: {filename}")
        s.close()
    except Exception as e:
        print(f"[Metadata] Error sending to host: {e}")

# === Request full blockchain from host ===
def request_blockchain_from_host():
    try:
        s = socket.socket()
        s.connect((HOST_IP, HOST_BLOCKCHAIN_PORT))
        s.send(json.dumps({'type': 'get_blockchain'}).encode())
        blockchain_data = b''
        while True:
            part = s.recv(4096)
            if not part:
                break
            blockchain_data += part
        print(f"[Blockchain] Received:\n{blockchain_data.decode()}")
        s.close()
    except Exception as e:
        print(f"[Blockchain] Error requesting from host: {e}")

# === Sender ===
def send_file(target_ip, target_port, filename):
    try:
        # Send metadata to host first
        send_metadata_to_host(filename, target_ip)

        # Start socket to send file
        s = socket.socket()
        s.connect((target_ip, target_port))

        file_basename = os.path.basename(filename)
        s.send(file_basename.encode())
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

        print(f"[Sender] File sent: {filename} → {target_ip}")
    except Exception as e:
        print(f"[Sender] Error: {e}")
    finally:
        s.close()

# === Main Logic ===
def main():
    threading.Thread(target=listen_for_incoming, daemon=True).start()
    threading.Thread(target=broadcast_presence, daemon=True).start()
    threading.Thread(target=listen_for_broadcasts, daemon=True).start()

    while True:
        print("\n[Discovered Peers]")
        for idx, (ip, name) in enumerate(discovered_peers.items(), start=1):
            print(f"{idx}. {name} ({ip})")

        cmd = input("\n[COMMAND] Enter: send <#> <filename>, getchain or 'exit': ").strip()
        if cmd.lower() == 'exit':
            print("[System] Exiting...")
            break
        elif cmd.startswith("send"):
            try:
                _, index, filename = cmd.split()
                index = int(index) - 1
                ip = list(discovered_peers.keys())[index]
                send_file(ip, LISTEN_PORT, filename)
            except (ValueError, IndexError):
                print("[!] Usage: send <peer_number> <filename>")
        elif cmd.lower() == 'getchain':
            request_blockchain_from_host()
        else:
            print("[!] Unknown command.")

if __name__ == "__main__":
    main()
