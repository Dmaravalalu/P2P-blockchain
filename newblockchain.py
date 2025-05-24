import socket
import threading
import os
import json
import platform
import time
import hashlib
from datetime import datetime

LISTEN_PORT = 5001  # Customize as needed
BROADCAST_PORT = 5002
BROADCAST_INTERVAL = 5  # seconds
BROADCAST_IP = '255.255.255.255'

PEER_NAME = platform.node() or socket.gethostname()
discovered_peers = {}

# Blockchain implementation
class Blockchain:
    def __init__(self):
        self.chain = []
        self.pending_transactions = []
        self.create_genesis_block()

    def create_genesis_block(self):
        genesis_block = {
            'index': 0,
            'timestamp': str(datetime.now()),
            'transactions': [],
            'proof': 1,
            'previous_hash': '0'
        }
        self.chain.append(genesis_block)

    def add_transaction(self, transaction):
        self.pending_transactions.append(transaction)

    def create_block(self, proof, previous_hash):
        block = {
            'index': len(self.chain),
            'timestamp': str(datetime.now()),
            'transactions': self.pending_transactions,
            'proof': proof,
            'previous_hash': previous_hash
        }
        self.chain.append(block)
        self.pending_transactions = []
        return block

    def get_previous_block(self):
        return self.chain[-1] if self.chain else None

    def display_blockchain(self):
        for block in self.chain:
            print(f"Block {block['index']}")
            print(f"Timestamp: {block['timestamp']}")
            print("Transactions:")
            for tx in block['transactions']:
                print(f"  - {tx}")
            print(f"Proof: {block['proof']}")
            print(f"Previous Hash: {block['previous_hash']}\n")

# Initialize blockchain
blockchain = Blockchain()

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

        # Add transaction to blockchain
        transaction = {
            'filename': filename,
            'sender': addr[0],
            'receiver': PEER_NAME,
            'timestamp': str(datetime.now())
        }
        blockchain.add_transaction(transaction)
        previous_block = blockchain.get_previous_block()
        proof = 1  # Simplified proof of work
        previous_hash = hashlib.sha256(json.dumps(previous_block).encode()).hexdigest()
        blockchain.create_block(proof, previous_hash)

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

        # Add transaction to blockchain
        transaction = {
            'filename': filename,
            'sender': PEER_NAME,
            'receiver': discovered_peers.get(target_ip, 'Unknown'),
            'timestamp': str(datetime.now())
        }
        blockchain.add_transaction(transaction)
        previous_block = blockchain.get_previous_block()
        proof = 1  # Simplified proof of work
        previous_hash = hashlib.sha256(json.dumps(previous_block).encode()).hexdigest()
        blockchain.create_block(proof, previous_hash)

    except Exception as e:
        print(f"[Sender] Error: {e}")
    finally:
        s.close()

def main():
    threading.Thread(target=listen_for_incoming, daemon=True).start()
    threading.Thread(target=broadcast_presence, daemon=True).start()
    threading.Thread(target=listen_for_broadcasts, daemon=True).start()

    while True:
        print("\n[Discovered Peers]")
        for idx, (ip, name) in enumerate(discovered_peers.items(), start=1):
            print(f"{idx}. {name} ({ip})")

        cmd = input("\n[COMMAND] Enter: send <#> <filename>, blockchain, or 'exit': ").strip()
        if cmd.lower() == 'exit':
            print("[System] Exiting...")
            break
        elif cmd.lower() == 'blockchain':
            blockchain.display_blockchain()
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