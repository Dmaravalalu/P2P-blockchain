import socket
import threading
import os
import json
import platform
import time
import hashlib
from datetime import datetime
import uuid
import secrets
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Configuration
LISTEN_PORT = 5001
BROADCAST_PORT = 5002
BROADCAST_INTERVAL = 5
BROADCAST_IP = '255.255.255.255'
PEER_NAME = platform.node() or socket.gethostname()

# Encryption utilities
class SimpleEncryption:
    @staticmethod
    def generate_key():
        """Generate a random encryption key"""
        return Fernet.generate_key()
    
    @staticmethod
    def derive_key_from_password(password, salt=None):
        """Derive encryption key from password"""
        if salt is None:
            salt = os.urandom(16)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key, salt
    
    @staticmethod
    def encrypt_data(data, key):
        """Encrypt data with given key"""
        f = Fernet(key)
        return f.encrypt(data)
    
    @staticmethod
    def decrypt_data(encrypted_data, key):
        """Decrypt data with given key"""
        f = Fernet(key)
        return f.decrypt(encrypted_data)
    
    @staticmethod
    def encrypt_file(filepath, key):
        """Encrypt a file and return encrypted data"""
        with open(filepath, 'rb') as file:
            file_data = file.read()
        return SimpleEncryption.encrypt_data(file_data, key)
    
    @staticmethod
    def decrypt_file(encrypted_data, key, output_path):
        """Decrypt data and save to file"""
        decrypted_data = SimpleEncryption.decrypt_data(encrypted_data, key)
        with open(output_path, 'wb') as file:
            file.write(decrypted_data)
        return True

# Blockchain Components
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

class SecureBlockchain:
    def __init__(self):
        self.chain = [self.create_genesis_block()]
        self.difficulty = 2
        self.pending_transactions = []
    
    def create_genesis_block(self):
        return Block({
            "type": "genesis", 
            "message": "Encrypted P2P File Sharing Genesis Block",
            "peer_name": PEER_NAME,
            "encryption_enabled": True
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

class EncryptedP2PPeer:
    def __init__(self):
        self.blockchain = SecureBlockchain()
        self.discovered_peers = {}
        self.peer_id = self.generate_peer_id()
        self.session_key = str(uuid.uuid4())
        self.master_password = None
        self.peer_keys = {}  # Store encryption keys for each peer
        
    def generate_peer_id(self):
        unique_string = f"{PEER_NAME}-{socket.gethostname()}-{time.time()}"
        return hashlib.sha256(unique_string.encode()).hexdigest()[:16]
    
    def set_master_password(self, password):
        """Set the master password for this peer"""
        self.master_password = password
        print(f"🔐 Master password set for peer {self.peer_id[:8]}...")
    
    def generate_session_key(self, peer_id):
        """Generate a session key for communication with a specific peer"""
        if not self.master_password:
            # Generate random key if no master password
            return SimpleEncryption.generate_key()
        
        # Derive key from master password + peer IDs
        combined_string = f"{self.master_password}{self.peer_id}{peer_id}"
        key, _ = SimpleEncryption.derive_key_from_password(combined_string)
        return key
    
    def get_peer_key(self, peer_id):
        """Get or generate encryption key for a peer"""
        if peer_id not in self.peer_keys:
            self.peer_keys[peer_id] = self.generate_session_key(peer_id)
        return self.peer_keys[peer_id]
    
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
    
    def register_file_transaction(self, filename, file_hash, recipient_id, action="send", encrypted=True):
        """Register a file transfer transaction on the blockchain"""
        transaction = {
            "id": str(uuid.uuid4()),
            "type": "encrypted_file_transfer" if encrypted else "file_transfer",
            "timestamp": datetime.now().isoformat(),
            "filename": filename,
            "file_hash": file_hash,
            "sender_id": self.peer_id,
            "recipient_id": recipient_id,
            "action": action,
            "encrypted": encrypted,
            "file_size": os.path.getsize(filename) if os.path.exists(filename) else 0
        }
        
        transaction["signature"] = self.create_transaction_signature(transaction)
        self.blockchain.add_transaction(transaction)
        mined_txs = self.blockchain.mine_pending_transactions()
        
        encryption_status = "🔐 ENCRYPTED" if encrypted else "🔓 PLAIN"
        print(f"[Blockchain] Registered {action} ({encryption_status}): {filename} -> {recipient_id[:8]}...")
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
        """Enhanced receiver with encryption support"""
        server = socket.socket()
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('0.0.0.0', LISTEN_PORT))
        server.listen(5)
        print(f"[Receiver] 🔐 Encrypted listener on port {LISTEN_PORT}...")
        
        while True:
            try:
                conn, addr = server.accept()
                print(f"[Receiver] Connection from {addr}")
                
                # Receive metadata
                metadata_size = int.from_bytes(conn.recv(4), byteorder='big')
                metadata_json = conn.recv(metadata_size).decode()
                metadata = json.loads(metadata_json)
                
                filename = metadata['filename']
                expected_hash = metadata['file_hash']
                sender_id = metadata['sender_id']
                is_encrypted = metadata.get('encrypted', False)
                
                conn.send(b'METADATA_OK')
                
                # Receive encrypted file data
                encrypted_data = b''
                while True:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    encrypted_data += chunk
                
                print(f"[Receiver] Received {len(encrypted_data)} bytes (encrypted: {is_encrypted})")
                
                # Decrypt and save file
                received_filename = f"received_{int(time.time())}_{filename}"
                
                if is_encrypted:
                    try:
                        # Get decryption key for this sender
                        decryption_key = self.get_peer_key(sender_id)
                        
                        # Decrypt the file data
                        print(f"[Receiver] 🔓 Decrypting file...")
                        SimpleEncryption.decrypt_file(encrypted_data, decryption_key, received_filename)
                        
                        print(f"[Receiver] ✅ File decrypted successfully")
                    except Exception as e:
                        print(f"[Receiver] ❌ Decryption failed: {e}")
                        conn.send(b'DECRYPTION_FAILED')
                        continue
                else:
                    # Save unencrypted file
                    with open(received_filename, 'wb') as f:
                        f.write(encrypted_data)
                
                # Verify file integrity
                if self.verify_file_integrity(received_filename, expected_hash):
                    self.register_file_transaction(
                        filename, expected_hash, sender_id, "receive", is_encrypted
                    )
                    conn.send(b'FILE_VERIFIED')
                    print(f"[Receiver] 💾 File saved as: {received_filename}")
                else:
                    os.remove(received_filename)
                    conn.send(b'FILE_CORRUPTED')
                    print(f"[Receiver] ❌ Corrupted file removed")
                
            except Exception as e:
                print(f"[Receiver] Error: {e}")
            finally:
                try:
                    conn.close()
                except:
                    pass
    
    def broadcast_presence(self):
        """Broadcast peer presence with encryption capability"""
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
                    "encryption_enabled": True,
                    "has_master_password": self.master_password is not None
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
                
                if ip != socket.gethostbyname(socket.gethostname()):
                    self.discovered_peers[ip] = {
                        "name": peer_info.get("name"),
                        "peer_id": peer_info.get("peer_id"),
                        "blockchain_length": peer_info.get("blockchain_length", 0),
                        "encryption_enabled": peer_info.get("encryption_enabled", False),
                        "has_master_password": peer_info.get("has_master_password", False),
                        "last_seen": datetime.now().isoformat()
                    }
            except Exception as e:
                continue
    
    def send_file(self, target_ip, target_port, filename, encrypt=True):
        """Enhanced file sender with encryption"""
        try:
            if not os.path.exists(filename):
                print(f"[Sender] File not found: {filename}")
                return False
            
            # Calculate original file hash
            file_hash = self.calculate_file_hash(filename)
            if not file_hash:
                print(f"[Sender] Cannot calculate hash for {filename}")
                return False
            
            recipient_id = self.discovered_peers[target_ip]["peer_id"]
            
            # Register the send transaction
            self.register_file_transaction(filename, file_hash, recipient_id, "send", encrypt)
            
            # Prepare file data
            if encrypt:
                print(f"[Sender] 🔐 Encrypting file...")
                encryption_key = self.get_peer_key(recipient_id)
                file_data = SimpleEncryption.encrypt_file(filename, encryption_key)
                print(f"[Sender] ✅ File encrypted ({len(file_data)} bytes)")
            else:
                with open(filename, 'rb') as f:
                    file_data = f.read()
                print(f"[Sender] 🔓 Sending unencrypted ({len(file_data)} bytes)")
            
            # Connect and send
            s = socket.socket()
            s.settimeout(30)
            s.connect((target_ip, target_port))
            
            # Send metadata
            metadata = {
                "filename": os.path.basename(filename),
                "file_hash": file_hash,
                "sender_id": self.peer_id,
                "encrypted": encrypt,
                "timestamp": datetime.now().isoformat()
            }
            
            metadata_json = json.dumps(metadata).encode()
            s.send(len(metadata_json).to_bytes(4, byteorder='big'))
            s.send(metadata_json)
            
            # Wait for metadata acknowledgment
            ack = s.recv(1024).decode()
            if ack != 'METADATA_OK':
                print("[Sender] Metadata not acknowledged")
                return False
            
            # Send encrypted/unencrypted file data
            s.sendall(file_data)
            print(f"[Sender] 📤 Sent {len(file_data)} bytes")
            
            # Wait for verification
            verification = s.recv(1024).decode()
            if verification == 'FILE_VERIFIED':
                encryption_status = "🔐 ENCRYPTED" if encrypt else "🔓 UNENCRYPTED"
                print(f"[Sender] ✅ File '{filename}' successfully sent and verified! ({encryption_status})")
                return True
            elif verification == 'DECRYPTION_FAILED':
                print(f"[Sender] ❌ Recipient failed to decrypt file (key mismatch?)")
                return False
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
        print(f"\n{'='*60}")
        print(f"🔐 ENCRYPTED BLOCKCHAIN STATUS")
        print(f"{'='*60}")
        print(f"Peer ID: {self.peer_id}")
        print(f"Master Password: {'✅ Set' if self.master_password else '❌ Not Set'}")
        print(f"Chain Length: {len(self.blockchain.chain)} blocks")
        print(f"Chain Valid: {'✅ Yes' if self.blockchain.is_chain_valid() else '❌ No'}")
        print(f"Pending Transactions: {len(self.blockchain.pending_transactions)}")
        print(f"Peer Keys Cached: {len(self.peer_keys)}")
        
        # Show recent transactions
        print(f"\nRECENT TRANSACTIONS:")
        print(f"{'-'*60}")
        transaction_count = 0
        for block in reversed(self.blockchain.chain):
            if isinstance(block.data, dict) and "transactions" in block.data:
                for tx in block.data["transactions"]:
                    if "file_transfer" in tx["type"]:
                        action_icon = "📤" if tx["action"] == "send" else "📥"
                        encryption_icon = "🔐" if tx.get("encrypted", False) else "🔓"
                        print(f"{action_icon}{encryption_icon} {tx['timestamp'][:19]}: {tx['action'].upper()} '{tx['filename']}'")
                        print(f"   From: {tx['sender_id'][:12]}... To: {tx['recipient_id'][:12]}...")
                        print(f"   Hash: {tx['file_hash'][:16]}... Size: {tx.get('file_size', 'unknown')} bytes")
                        transaction_count += 1
                        if transaction_count >= 5:
                            break
            if transaction_count >= 5:
                break
        
        if transaction_count == 0:
            print("No file transfer transactions yet")
        
        print(f"\nNETWORK PEERS:")
        print(f"{'-'*60}")
        if not self.discovered_peers:
            print("No peers discovered yet")
        else:
            for ip, info in self.discovered_peers.items():
                encryption_status = "🔐" if info.get("encryption_enabled") else "🔓"
                password_status = "🔑" if info.get("has_master_password") else "🆔"
                print(f"🌐 {info['name']} ({ip}) {encryption_status}{password_status}")
                print(f"   ID: {info['peer_id'][:16]}...")
                print(f"   Blockchain: {info['blockchain_length']} blocks")
    
    def run(self):
        """Main application loop"""
        print(f"\n{'='*70}")
        print(f"🔐 ENCRYPTED BLOCKCHAIN P2P FILE SHARING SYSTEM")
        print(f"{'='*70}")
        print(f"Peer ID: {self.peer_id}")
        print(f"Listening on port: {LISTEN_PORT}")
        print(f"Broadcasting on port: {BROADCAST_PORT}")
        
        # Ask for master password (optional)
        password = input("\n🔑 Enter master password (optional, press Enter to skip): ").strip()
        if password:
            self.set_master_password(password)
        else:
            print("🆔 Using random session keys for each peer")
        
        # Start background threads
        threading.Thread(target=self.listen_for_incoming, daemon=True).start()
        threading.Thread(target=self.broadcast_presence, daemon=True).start()
        threading.Thread(target=self.listen_for_broadcasts, daemon=True).start()
        
        time.sleep(2)
        
        while True:
            print(f"\n{'='*50}")
            print("DISCOVERED PEERS:")
            print(f"{'='*50}")
            
            if not self.discovered_peers:
                print("🔍 Searching for peers...")
            else:
                for idx, (ip, info) in enumerate(self.discovered_peers.items(), start=1):
                    encryption_icon = "🔐" if info.get("encryption_enabled") else "🔓"
                    password_icon = "🔑" if info.get("has_master_password") else "🆔"
                    print(f"{idx}. 🖥️  {info['name']} ({ip}) {encryption_icon}{password_icon}")
                    print(f"    ID: {info['peer_id'][:12]}...")
                    print(f"    Blockchain: {info['blockchain_length']} blocks")
            
            print(f"\n{'='*50}")
            print("COMMANDS:")
            print("• send <peer#> <filename>        - Send encrypted file")
            print("• send_plain <peer#> <filename>  - Send unencrypted file")
            print("• blockchain                     - Show blockchain status")
            print("• password <new_password>        - Change master password")
            print("• exit                          - Exit application")
            print(f"{'='*50}")
            
            try:
                cmd = input("Enter command: ").strip()
                
                if cmd.lower() == 'exit':
                    print("🔒 Shutting down...")
                    break
                elif cmd.lower() == 'blockchain':
                    self.show_blockchain_status()
                elif cmd.startswith("password "):
                    new_password = cmd[9:]
                    self.set_master_password(new_password)
                    self.peer_keys = {}  # Clear cached keys
                elif cmd.startswith("send_plain "):
                    parts = cmd.split()
                    if len(parts) != 3:
                        print("❌ Usage: send_plain <peer_number> <filename>")
                        continue
                    
                    try:
                        peer_num = int(parts[1]) - 1
                        filename = parts[2]
                        
                        if peer_num < 0 or peer_num >= len(self.discovered_peers):
                            print("❌ Invalid peer number")
                            continue
                        
                        target_ip = list(self.discovered_peers.keys())[peer_num]
                        
                        print(f"📤🔓 Sending {filename} UNENCRYPTED to {self.discovered_peers[target_ip]['name']}...")
                        success = self.send_file(target_ip, LISTEN_PORT, filename, encrypt=False)
                        
                        if success:
                            print("✅ Transfer completed successfully!")
                        else:
                            print("❌ Transfer failed!")
                            
                    except (ValueError, IndexError):
                        print("❌ Invalid command format")
                elif cmd.startswith("send "):
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
                        
                        print(f"📤🔐 Sending {filename} ENCRYPTED to {self.discovered_peers[target_ip]['name']}...")
                        success = self.send_file(target_ip, LISTEN_PORT, filename, encrypt=True)
                        
                        if success:
                            print("✅ Transfer completed successfully!")
                        else:
                            print("❌ Transfer failed!")
                            
                    except (ValueError, IndexError):
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
        peer = EncryptedP2PPeer()
        peer.run()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"💥 Fatal error: {e}")
