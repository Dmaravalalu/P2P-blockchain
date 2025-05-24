import socket
import threading
import os
import json
import platform
import time

LISTEN_PORT = 5001  # Customize as needed
BROADCAST_PORT = 5002
BROADCAST_INTERVAL = 5  # seconds
BROADCAST_IP = '255.255.255.255'

# Get peer name
PEER_NAME = platform.node() or socket.gethostname()

# Dictionary to store discovered peers
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
    threading.Thread(target=listen_for_incoming, daemon=True).start()
    threading.Thread(target=broadcast_presence, daemon=True).start()
    threading.Thread(target=listen_for_broadcasts, daemon=True).start()

    # Command loop
    while True:
        print("\n[Discovered Peers]")
        for idx, (ip, name) in enumerate(discovered_peers.items(), start=1):
            print(f"{idx}. {name} ({ip})")

        cmd = input("\n[COMMAND] Enter: send <#> <filename> or 'exit': ").strip()
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
        else:
            print("[!] Unknown command.")

if __name__ == "__main__":
    main()
