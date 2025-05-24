import socket
import threading
import os
import json
import platform
import time
import hashlib
from datetime import datetime
import uuid

# Configuration
LISTEN_PORT = 5001
BROADCAST_PORT = 5002
BROADCAST_INTERVAL = 5
BROADCAST_IP = '255.255.255.255'
PEER_NAME = platform.node() or socket.gethostname()

# Simple Blockchain Implementation (No external dependencies)
class Block:
    def __init__(self, data, previous_hash="0"):
        self.timestamp = datetime.now().isoformat()
        self.data = data
        self.previous_hash = previous_hash
        self.nonce = 0
        self.hash = self.calculate_hash()
    
    def calculate_hash(self):
        block_string = f"{self.timestamp}{json.dumps(self.data, sort_keys=True)}{self.previous_hash}{self.nonce}"
        return hashlib.sha256(block_string.encode()).hexdigest()
    
    def mine_block(self, difficulty=2):
        target = "0" * difficulty
        start_time = time.time()
        while self.hash[:difficulty] != target:
            self.nonce += 1
            self.hash = self.calculate_hash()
        mining_time = time.time() - start_time
        print(f"[Blockchain] Block mined in {mining_time:.2f}s: {self.hash[:16]}...")

class SimpleBlockchain:
    def __init__(self):
        self.chain = [self.create_genesis_block()]
        self.difficulty = 2
        self.pending_transactions = []
    
    def create_genesis_block(self):
        return Block({
            "type": "genesis", 
            "message": "P2P File Sharing Genesis Block",
            "peer_name": PEER_NAME
        })
    
    def get_latest_block(self):
        return self.chain[-1]
    
    def add_transaction(self, transaction):
        self.pending_transactions.append(transaction)
        print(f"[Blockchain] Transaction added: {transaction['type']}")
    
    def mine_pending_transactions(self):
        if not self.pending_transactions:
            return None
        
        print(f"[Blockchain] Mining block with {len(self.pending_transactions)} transactions...")
        block = Block(
            {"transactions": self.pending_transactions}, 
            self.get_latest_block().hash
        )
        block.mine_block(self.difficulty)
        self.chain.append(block)
        
        # Clear pending transactions
        mined_transactions = self.pending_transactions.copy()
        self.pending_transactions = []
        return mined_transactions
    
    def is_chain_valid(self):
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = self.chain[i-1]
            
            if current_block.hash != current_block.calculate_hash():
                return False
            if current_block.previous_hash != previous_block.hash:
                return False
        return True
    
    def get_file_history(self, file_hash):
        history = []
        for block in self.chain:
            if isinstance(block.data, dict) and "transactions" in block.data:
                for tx in block.data["transactions"]:
                    if tx.get("file_hash") == file_hash:
                        history.append(tx)
        return history
    
    def get_peer_activity(self, peer_id):
        activity = []
        for block in self.chain:
            if isinstance(block.data, dict) and "transactions" in block.data:
                for tx in block.data["transactions"]:
                    if tx.get("sender_id") == peer_id or tx.get("recipient_id") == peer_id:
                        activity.append(tx)
        return activity

class SecureP2PPeer:
    def __init__(self):
        self.blockchain = SimpleBlockchain()
        self.discovered_peers = {}
        self.peer_id = self.generate_peer_id()
        self.session_key = str(uuid.uuid4())
        
    def generate_peer_id(self):
        # Generate a unique peer ID based on hostname and current time
        unique_string = f"{PEER_NAME}-{socket.gethostname()}-{time.time()}"
        return hashlib.sha256(unique_string.encode()).hexdigest()[:16]
    
    def calculate_file_hash(self, filepath):
        """Calculate SHA-256 hash of a file"""
        sha256_hash = hashlib.sha256()
        try:
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        except Exception as e:
            print(f"[Error] Cannot hash file {filepath}: {e}")
            return None
    
    def create_transaction_signature(self, transaction_data):
        """Create a simple signature for transaction integrity"""
        tx_string = json.dumps(transaction_data, sort_keys=True)
        signature_data = f"{tx_string}{self.session_key}{self.peer_id}"
        return hashlib.sha256(signature_data.encode()).hexdigest()
    
    def register_file_transaction(self, filename, file_hash, recipient_id, action="send"):
        """Register a file transfer transaction on the blockchain"""
        transaction = {
            "id": str(uuid.uuid4()),
            "type": "file_transfer",
            "timestamp": datetime.now().isoformat(),
            "filename": filename,
            "file_hash": file_hash,
            "sender_id": self.peer_id,
            "recipient_id": recipient_id,
            "action": action,
            "file_size": os.path.getsize(filename) if os.path.exists(filename) else 0
        }
        
        # Add transaction signature
        transaction["signature"] = self.create_transaction_signature(transaction)
        
        # Add to blockchain
        self.blockchain.add_transaction(transaction)
        
        # Mine the block (in real network, this would be done by miners)
        mined_txs = self.blockchain.mine_pending_transactions()
        
        print(f"[Blockchain] Registered {action}: {filename} -> {recipient_id[:8]}...")
        return transaction
    
    def verify_file_integrity(self, filename, expected_hash):
        """Verify that a received file matches its expected hash"""
        if not os.path.exists(filename):
            return False
        
        actual_hash = self.calculate_file_hash(filename)
        is_valid = actual_hash == expected_hash
        
        if is_valid:
            print(f"[Security] File integrity VERIFIED: {filename}")
        else:
            print(f"[Security] File integrity FAILED: {filename}")
            print(f"[Security] Expected: {expected_hash}")
            print(f"[Security] Actual:   {actual_hash}")
        
        return is_valid
    
    def listen_for_incoming(self):
        """Enhanced receiver with blockchain integration"""
        server = socket.socket()
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('0.0.0.0', LISTEN_PORT))
        server.listen(5)
        print(f"[Receiver] Listening on port {LISTEN_PORT}...")
        
        while True:
            try:
                conn, addr = server.accept()
                print(f"[Receiver] Connection from {addr}")
                
                # Receive metadata first
                metadata_json = conn.recv(4096).decode()
                metadata = json.loads(metadata_json)
                
                filename = metadata['filename']
                expected_hash = metadata['file_hash']
                sender_id = metadata['sender_id']
                
                conn.send(b'METADATA_OK')
                
                # Receive the file
                received_filename = f"received_{int(time.time())}_{filename}"
                total_received = 0
                
                with open(received_filename, 'wb') as f:
                    while True:
                        data = conn.recv(1024)
                        if not data:
                            break
                        f.write(data)
                        total_received += len(data)
                
                print(f"[Receiver] Received {total_received} bytes")
                
                # Verify file integrity
                if self.verify_file_integrity(received_filename, expected_hash):
                    # Register successful receipt on blockchain
                    self.register_file_transaction(
                        filename, expected_hash, sender_id, "receive"
                    )
                    conn.send(b'FILE_VERIFIED')
                    print(f"[Receiver] File saved as: {received_filename}")
                else:
                    # File corrupted - remove it and notify sender
                    os.remove(received_filename)
                    conn.send(b'FILE_CORRUPTED')
                    print(f"[Receiver] Corrupted file removed")
                
            except Exception as e:
                print(f"[Receiver] Error: {e}")
            finally:
                try:
                    conn.close()
                except:
                    pass
    
    def broadcast_presence(self):
        """Broadcast peer presence with blockchain info"""
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        udp.settimeout(0.2)
        
        while True:
            try:
                msg = json.dumps({
                    "name": PEER_NAME,
                    "ip": socket.gethostbyname(socket.gethostname()),
                    "port": LISTEN_PORT,
                    "peer_id": self.peer_id,
                    "blockchain_length": len(self.blockchain.chain),
                    "session_key_hash": hashlib.sha256(self.session_key.encode()).hexdigest()[:8]
                }).encode()
                
                udp.sendto(msg, (BROADCAST_IP, BROADCAST_PORT))
                time.sleep(BROADCAST_INTERVAL)
            except Exception as e:
                print(f"[Broadcast] Error: {e}")
                time.sleep(BROADCAST_INTERVAL)
    
    def listen_for_broadcasts(self):
        """Listen for peer broadcasts"""
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        udp.bind(("", BROADCAST_PORT))
        
        while True:
            try:
                data, addr = udp.recvfrom(2048)
                peer_info = json.loads(data.decode())
                ip = peer_info.get("ip")
                
                # Don't add ourselves
                if ip != socket.gethostbyname(socket.gethostname()):
                    self.discovered_peers[ip] = {
                        "name": peer_info.get("name"),
                        "peer_id": peer_info.get("peer_id"),
                        "blockchain_length": peer_info.get("blockchain_length", 0),
                        "last_seen": datetime.now().isoformat()
                    }
            except Exception as e:
                continue
    
    def send_file(self, target_ip, target_port, filename):
        """Enhanced file sender with blockchain integration"""
        try:
            if not os.path.exists(filename):
                print(f"[Sender] File not found: {filename}")
                return False
            
            # Calculate file hash before sending
            file_hash = self.calculate_file_hash(filename)
            if not file_hash:
                print(f"[Sender] Cannot calculate hash for {filename}")
                return False
            
            recipient_id = self.discovered_peers[target_ip]["peer_id"]
            
            # Register the send transaction on blockchain
            self.register_file_transaction(filename, file_hash, recipient_id, "send")
            
            # Connect and send
            s = socket.socket()
            s.settimeout(30)  # 30 second timeout
            s.connect((target_ip, target_port))
            
            # Send metadata
            metadata = {
                "filename": os.path.basename(filename),
                "file_hash": file_hash,
                "sender_id": self.peer_id,
                "timestamp": datetime.now().isoformat()
            }
            
            metadata_json = json.dumps(metadata)
            s.send(metadata_json.encode())
            
            # Wait for metadata acknowledgment
            ack = s.recv(1024).decode()
            if ack != 'METADATA_OK':
                print("[Sender] Metadata not acknowledged")
                return False
            
            # Send file in chunks
            bytes_sent = 0
            with open(filename, 'rb') as f:
                while True:
                    chunk = f.read(1024)
                    if not chunk:
                        break
                    s.send(chunk)
                    bytes_sent += len(chunk)
            
            print(f"[Sender] Sent {bytes_sent} bytes")
            
            # Wait for verification
            verification = s.recv(1024).decode()
            if verification == 'FILE_VERIFIED':
                print(f"[Sender] ✅ File '{filename}' successfully sent and verified!")
                return True
            else:
                print(f"[Sender] ❌ File transfer failed verification")
                return False
                
        except Exception as e:
            print(f"[Sender] Error: {e}")
            return False
        finally:
            try:
                s.close()
            except:
                pass
    
    def show_blockchain_status(self):
        """Display blockchain and network status"""
        print(f"\n{'='*50}")
        print(f"BLOCKCHAIN STATUS")
        print(f"{'='*50}")
        print(f"Peer ID: {self.peer_id}")
        print(f"Chain Length: {len(self.blockchain.chain)} blocks")
        print(f"Chain Valid: {'✅ Yes' if self.blockchain.is_chain_valid() else '❌ No'}")
        print(f"Pending Transactions: {len(self.blockchain.pending_transactions)}")
        
        # Show recent transactions
        print(f"\nRECENT TRANSACTIONS:")
        print(f"{'-'*50}")
        transaction_count = 0
        for block in reversed(self.blockchain.chain):
            if isinstance(block.data, dict) and "transactions" in block.data:
                for tx in block.data["transactions"]:
                    if tx["type"] == "file_transfer":
                        action_icon = "📤" if tx["action"] == "send" else "📥"
                        print(f"{action_icon} {tx['timestamp'][:19]}: {tx['action'].upper()} '{tx['filename']}'")
                        print(f"   From: {tx['sender_id'][:12]}... To: {tx['recipient_id'][:12]}...")
                        print(f"   Hash: {tx['file_hash'][:16]}... Size: {tx.get('file_size', 'unknown')} bytes")
                        transaction_count += 1
                        if transaction_count >= 5:  # Show last 5 transactions
                            break
            if transaction_count >= 5:
                break
        
        if transaction_count == 0:
            print("No file transfer transactions yet")
        
        print(f"\nNETWORK PEERS:")
        print(f"{'-'*50}")
        if not self.discovered_peers:
            print("No peers discovered yet")
        else:
            for ip, info in self.discovered_peers.items():
                print(f"🌐 {info['name']} ({ip})")
                print(f"   ID: {info['peer_id'][:16]}...")
                print(f"   Blockchain: {info['blockchain_length']} blocks")
    
    def run(self):
        """Main application loop"""
        print(f"\n{'='*60}")
        print(f"🔗 BLOCKCHAIN P2P FILE SHARING SYSTEM")
        print(f"{'='*60}")
        print(f"Peer ID: {self.peer_id}")
        print(f"Listening on port: {LISTEN_PORT}")
        print(f"Broadcasting on port: {BROADCAST_PORT}")
        
        # Start background threads
        threading.Thread(target=self.listen_for_incoming, daemon=True).start()
        threading.Thread(target=self.broadcast_presence, daemon=True).start()
        threading.Thread(target=self.listen_for_broadcasts, daemon=True).start()
        
        # Give threads time to start
        time.sleep(2)
        
        while True:
            print(f"\n{'='*40}")
            print("DISCOVERED PEERS:")
            print(f"{'='*40}")
            
            if not self.discovered_peers:
                print("🔍 Searching for peers...")
            else:
                for idx, (ip, info) in enumerate(self.discovered_peers.items(), start=1):
                    print(f"{idx}. 🖥️  {info['name']} ({ip})")
                    print(f"    ID: {info['peer_id'][:12]}...")
                    print(f"    Blockchain: {info['blockchain_length']} blocks")
            
            print(f"\n{'='*40}")
            print("COMMANDS:")
            print("• send <peer#> <filename>  - Send file to peer")
            print("• blockchain              - Show blockchain status")
            print("• exit                    - Exit application")
            print(f"{'='*40}")
            
            try:
                cmd = input("Enter command: ").strip()
                
                if cmd.lower() == 'exit':
                    print("🔒 Shutting down...")
                    break
                elif cmd.lower() == 'blockchain':
                    self.show_blockchain_status()
                elif cmd.startswith("send"):
                    parts = cmd.split()
                    if len(parts) != 3:
                        print("❌ Usage: send <peer_number> <filename>")
                        continue
                    
                    try:
                        peer_num = int(parts[1]) - 1
                        filename = parts[2]
                        
                        if peer_num < 0 or peer_num >= len(self.discovered_peers):
                            print("❌ Invalid peer number")
                            continue
                        
                        target_ip = list(self.discovered_peers.keys())[peer_num]
                        
                        print(f"📤 Sending {filename} to {self.discovered_peers[target_ip]['name']}...")
                        success = self.send_file(target_ip, LISTEN_PORT, filename)
                        
                        if success:
                            print("✅ Transfer completed successfully!")
                        else:
                            print("❌ Transfer failed!")
                            
                    except (ValueError, IndexError) as e:
                        print("❌ Invalid command format")
                else:
                    print("❌ Unknown command")
                    
            except KeyboardInterrupt:
                print("\n🔒 Shutting down...")
                break
            except Exception as e:
                print(f"❌ Error: {e}")

if __name__ == "__main__":
    try:
        peer = SecureP2PPeer()
        peer.run()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"💥 Fatal error: {e}")
