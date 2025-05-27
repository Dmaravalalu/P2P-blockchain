import socket
import threading
import os
import json
import platform
import time
import hashlib
from datetime import datetime

# === Blockchain Config ===
BLOCKCHAIN_PORT = 9000
blockchain = []

def create_block(metadata, prev_hash):
    block = {
        'index': len(blockchain) + 1,
        'timestamp': datetime.utcnow().isoformat(),
        'metadata': metadata,
        'prev_hash': prev_hash,
    }
    block['hash'] = hash_block(block)
    return block

def hash_block(block):
    block_string = json.dumps({k: block[k] for k in block if k != 'hash'}, sort_keys=True).encode()
    return hashlib.sha256(block_string).hexdigest()

def handle_blockchain_client(conn, addr):
    try:
        data = conn.recv(65536).decode()
        request = json.loads(data)

        if request['type'] == 'metadata':
            metadata = request['data']
            prev_hash = blockchain[-1]['hash'] if blockchain else '0'
            block = create_block(metadata, prev_hash)
            blockchain.append(block)
            print(f"[BLOCKCHAIN] Block added: {metadata}")
            conn.send(json.dumps({'status': 'success', 'block': block}).encode())

        elif request['type'] == 'get_blockchain':
            conn.send(json.dumps({'status': 'success', 'chain': blockchain}).encode())
        else:
            conn.send(json.dumps({'status': 'error', 'message': 'Invalid request'}).encode())
    except Exception as e:
        conn.send(json.dumps({'status': 'error', 'message': str(e)}).encode())
    finally:
        conn.close()

def start_blockchain_server():
    server = socket.socket()
    server.bind(('0.0.0.0', BLOCKCHAIN_PORT))
    server.listen(5)
    print(f"[BLOCKCHAIN] Listening on port {BLOCKCHAIN_PORT}")
    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_blockchain_client, args=(conn, addr), daemon=True).start()

# === Peer Config ===
LISTEN_PORT = 5001
BROADCAST_PORT = 5002
BROADCAST_INTERVAL = 5
BROADCAST_IP = '255.255.255.255'
PEER_NAME = platform.node() or socket.gethostname()
discovered_peers = {}

def listen_for_incoming():
    server = socket.socket()
    server.bind(('0.0.0.0', LISTEN_PORT))
    server.listen(5)
    print(f"[RECEIVER] Listening on port {LISTEN_PORT}...")

    while True:
        conn, addr = server.accept()
        filename = conn.recv(1024).decode()
        conn.send(b'FILENAME_RECEIVED')
        filepath = f"received_{filename}"
        with open(filepath, 'wb') as f:
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                f.write(data)
        print(f"[RECEIVER] File received: {filepath}")
        conn.close()

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

def send_file(target_ip, target_port, filename):
    try:
        s = socket.socket()
        s.connect((target_ip, target_port))

        s.send(os.path.basename(filename).encode())
        ack = s.recv(1024).decode()
        if ack != 'FILENAME_RECEIVED':
            print("[SENDER] Handshake failed.")
            return

        with open(filename, 'rb') as f:
            data = f.read(1024)
            while data:
                s.send(data)
                data = f.read(1024)

        print(f"[SENDER] File sent to {target_ip}")

        # === Send metadata to blockchain host (itself)
        metadata = {
            'sender': socket.gethostbyname(socket.gethostname()),
            'receiver': target_ip,
            'filename': os.path.basename(filename),
            'timestamp': datetime.utcnow().isoformat()
        }

        # Since this host is the blockchain host, we connect to self
        client = socket.socket()
        client.connect(('127.0.0.1', BLOCKCHAIN_PORT))
        request = json.dumps({'type': 'metadata', 'data': metadata}).encode()
        client.send(request)
        resp = json.loads(client.recv(65536).decode())
        print("[BLOCKCHAIN] Block added:", resp.get('block'))
        client.close()

    except Exception as e:
        print(f"[SENDER] Error: {e}")
    finally:
        s.close()

def request_blockchain():
    try:
        client = socket.socket()
        client.connect(('127.0.0.1', BLOCKCHAIN_PORT))
        request = json.dumps({'type': 'get_chain'}).encode()
        client.send(request)
        resp = json.loads(client.recv(65536).decode())
        for block in resp['chain']:
            print(json.dumps(block, indent=2))
        client.close()
    except Exception as e:
        print(f"[CHAIN] Error fetching blockchain: {e}")

# === Main ===
def main():
    # Start threads
    threading.Thread(target=start_blockchain_server, daemon=True).start()
    threading.Thread(target=listen_for_incoming, daemon=True).start()
    threading.Thread(target=broadcast_presence, daemon=True).start()
    threading.Thread(target=listen_for_broadcasts, daemon=True).start()

    # Command loop
    while True:
        print("\n[Discovered Peers]")
        for idx, (ip, name) in enumerate(discovered_peers.items(), start=1):
            print(f"{idx}. {name} ({ip})")

        cmd = input("\n[COMMAND] send <#> <file> | chain | exit: ").strip()
        if cmd == 'exit':
            break
        elif cmd == 'chain':
            request_blockchain()
        elif cmd.startswith("send"):
            try:
                _, idx, filename = cmd.split()
                ip = list(discovered_peers.keys())[int(idx) - 1]
                send_file(ip, LISTEN_PORT, filename)
            except:
                print("[!] Invalid send command")
        else:
            print("[!] Unknown command")

if __name__ == "__main__":
    main()
