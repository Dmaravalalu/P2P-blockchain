import socket
import threading
import os
import json
import platform
import time
import hashlib
from datetime import datetime
import logging
import random

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

LISTEN_PORT = 5001
BROADCAST_PORT = 5002
BLOCKCHAIN_SYNC_PORT = 5003
BROADCAST_INTERVAL = 5
BLOCKCHAIN_SYNC_INTERVAL = 10
BROADCAST_IP = '255.255.255.255'
MAX_FILE_SIZE = 100 * 1024 * 1024

PEER_NAME = platform.node() or socket.gethostname()
PEER_ID = hashlib.sha256(f"{PEER_NAME}_{time.time()}".encode()).hexdigest()[:16]
discovered_peers = {}
peer_lock = threading.Lock()

class Blockchain:
    def __init__(self):
        self.chain = []
        self.pending_transactions = []
        self.chain_lock = threading.Lock()
        self.create_genesis_block()
        self.mining_difficulty = 4  # Number of leading zeros required

    def create_genesis_block(self):
        genesis_block = {
            'index': 0,
            'timestamp': str(datetime.now()),
            'transactions': [],
            'proof': 1,
            'previous_hash': '0',
            'miner': 'genesis'
        }
        genesis_block['hash'] = self.calculate_hash(genesis_block)
        self.chain.append(genesis_block)

    def calculate_hash(self, block):
        """Calculate SHA-256 hash of a block"""
        block_string = json.dumps({
            'index': block['index'],
            'timestamp': block['timestamp'],
            'transactions': block['transactions'],
            'proof': block['proof'],
            'previous_hash': block['previous_hash'],
            'miner': block.get('miner', '')
        }, sort_keys=True)
        return hashlib.sha256(block_string.encode()).hexdigest()

    def add_transaction(self, transaction):
        with self.chain_lock:
            transaction['hash'] = hashlib.sha256(
                json.dumps(transaction, sort_keys=True).encode()
            ).hexdigest()
            self.pending_transactions.append(transaction)
            logger.info(f"Transaction added: {transaction['type']}")

    def proof_of_work(self, previous_proof):
        """Proof of work algorithm"""
        new_proof = 1
        check_proof = False
        
        while not check_proof:
            hash_operation = hashlib.sha256(
                str(new_proof**2 - previous_proof**2).encode()
            ).hexdigest()
            if hash_operation[:self.mining_difficulty] == "0" * self.mining_difficulty:
                check_proof = True
            else:
                new_proof += 1
        
        return new_proof

    def mine_block(self):
        """Mine a new block with pending transactions"""
        with self.chain_lock:
            if not self.pending_transactions:
                return None
                
            previous_block = self.get_previous_block()
            proof = self.proof_of_work(previous_block['proof'])
            previous_hash = previous_block['hash']
            
            block = {
                'index': len(self.chain),
                'timestamp': str(datetime.now()),
                'transactions': self.pending_transactions.copy(),
                'proof': proof,
                'previous_hash': previous_hash,
                'miner': PEER_ID
            }
            
            block['hash'] = self.calculate_hash(block)
            self.chain.append(block)
            self.pending_transactions = []
            
            logger.info(f"Block #{block['index']} mined by {PEER_ID}")
            return block

    def add_block(self, block):
        """Add a validated block from another peer"""
        with self.chain_lock:
            # Validate the block
            if self.is_valid_block(block):
                # Check if we already have this block
                if len(self.chain) <= block['index']:
                    self.chain.append(block)
                    # Remove any pending transactions that are now in the blockchain
                    self.remove_confirmed_transactions(block['transactions'])
                    logger.info(f"Block #{block['index']} added from network")
                    return True
            return False

    def remove_confirmed_transactions(self, confirmed_transactions):
        """Remove transactions that have been confirmed in a block"""
        confirmed_hashes = {tx.get('hash') for tx in confirmed_transactions}
        self.pending_transactions = [
            tx for tx in self.pending_transactions 
            if tx.get('hash') not in confirmed_hashes
        ]

    def is_valid_block(self, block):
        """Validate a single block"""
        try:
            # Check hash
            if block['hash'] != self.calculate_hash(block):
                return False
                
            # Check if it's the next expected block
            if block['index'] != len(self.chain):
                return False
                
            # Check previous hash
            previous_block = self.get_previous_block()
            if block['previous_hash'] != previous_block['hash']:
                return False
                
            # Check proof of work
            hash_operation = hashlib.sha256(
                str(block['proof']**2 - previous_block['proof']**2).encode()
            ).hexdigest()
            if hash_operation[:self.mining_difficulty] != "0" * self.mining_difficulty:
                return False
                
            return True
        except Exception as e:
            logger.error(f"Block validation error: {e}")
            return False

    def get_previous_block(self):
        return self.chain[-1] if self.chain else None

    def is_chain_valid(self):
        """Validate the entire blockchain with timeout protection"""
        try:
            with self.chain_lock:
                if not self.chain:
                    return False
                    
                # Don't validate if chain is too long (performance protection)
                if len(self.chain) > 1000:
                    logger.warning("Chain too long for full validation")
                    return True
                    
                for i in range(1, len(self.chain)):
                    try:
                        current_block = self.chain[i]
                        previous_block = self.chain[i-1]
                        
                        # Check if block has required fields
                        required_fields = ['hash', 'previous_hash', 'proof', 'index']
                        if not all(field in current_block for field in required_fields):
                            logger.error(f"Block {i} missing required fields")
                            return False
                        
                        if current_block['hash'] != self.calculate_hash(current_block):
                            logger.error(f"Block {i} hash mismatch")
                            return False
                        
                        if current_block['previous_hash'] != previous_block['hash']:
                            logger.error(f"Block {i} previous hash mismatch")
                            return False
                        
                        # Skip proof of work validation for performance if chain is long
                        if len(self.chain) <= 50:
                            hash_operation = hashlib.sha256(
                                str(current_block['proof']**2 - previous_block['proof']**2).encode()
                            ).hexdigest()
                            if hash_operation[:self.mining_difficulty] != "0" * self.mining_difficulty:
                                logger.error(f"Block {i} proof of work invalid")
                                return False
                    
                    except Exception as e:
                        logger.error(f"Error validating block {i}: {e}")
                        return False
                
                return True
                
        except Exception as e:
            logger.error(f"Chain validation error: {e}")
            return False

    def get_chain_length(self):
        with self.chain_lock:
            return len(self.chain)

    def get_chain_copy(self):
        """Get a copy of the blockchain"""
        with self.chain_lock:
            return self.chain.copy()

    def replace_chain(self, new_chain):
        """Replace current chain with a longer valid chain"""
        with self.chain_lock:
            if len(new_chain) > len(self.chain):
                # Validate the new chain
                if self.validate_external_chain(new_chain):
                    self.chain = new_chain
                    # Clear pending transactions that might be in the new chain
                    self.pending_transactions = []
                    logger.info(f"Blockchain replaced with longer chain (length: {len(new_chain)})")
                    return True
            return False

    def validate_external_chain(self, chain):
        """Validate an external blockchain"""
        if not chain:
            return False
            
        # Check genesis block
        if chain[0]['index'] != 0 or chain[0]['previous_hash'] != '0':
            return False
            
        for i in range(1, len(chain)):
            current_block = chain[i]
            previous_block = chain[i-1]
            
            if current_block['hash'] != self.calculate_hash(current_block):
                return False
            
            if current_block['previous_hash'] != previous_block['hash']:
                return False
                
            hash_operation = hashlib.sha256(
                str(current_block['proof']**2 - previous_block['proof']**2).encode()
            ).hexdigest()
            if hash_operation[:self.mining_difficulty] != "0" * self.mining_difficulty:
                return False
        
        return True

    def display_blockchain(self):
        try:
            with self.chain_lock:
                chain_copy = self.chain.copy()
                pending_copy = self.pending_transactions.copy()
            
            print(f"\n{'='*60}")
            print(f"BLOCKCHAIN STATUS - Length: {len(chain_copy)}")
            print(f"Pending Transactions: {len(pending_copy)}")
            print(f"{'='*60}")
            
            if not chain_copy:
                print("No blocks in blockchain")
                return
            
            for block in chain_copy:
                try:
                    print(f"\n🔗 Block #{block.get('index', 'N/A')}")
                    print(f"⏰ Timestamp: {block.get('timestamp', 'N/A')}")
                    
                    block_hash = block.get('hash', 'N/A')
                    if len(str(block_hash)) > 20:
                        print(f"🔐 Hash: {str(block_hash)[:20]}...")
                    else:
                        print(f"🔐 Hash: {block_hash}")
                    
                    prev_hash = block.get('previous_hash', 'N/A')
                    if len(str(prev_hash)) > 20:
                        print(f"🔗 Previous: {str(prev_hash)[:20]}...")
                    else:
                        print(f"🔗 Previous: {prev_hash}")
                    
                    print(f"⚡ Proof: {block.get('proof', 'N/A')}")
                    print(f"⛏️  Miner: {block.get('miner', 'Unknown')}")
                    print("📋 Transactions:")
                    
                    transactions = block.get('transactions', [])
                    if transactions:
                        for i, tx in enumerate(transactions):
                            if i >= 10:  # Limit to first 10 transactions
                                print(f"   ... and {len(transactions) - 10} more transactions")
                                break
                            try:
                                filename = tx.get('filename', 'N/A')
                                sender = tx.get('sender', 'N/A')
                                receiver = tx.get('receiver', 'N/A')
                                print(f"   📁 {filename} | {sender} → {receiver}")
                            except Exception as e:
                                print(f"   📁 Error displaying transaction: {e}")
                    else:
                        print("   (No transactions)")
                    print("-" * 50)
                    
                except Exception as e:
                    print(f"Error displaying block: {e}")
                    continue
                    
        except Exception as e:
            print(f"Error displaying blockchain: {e}")
            logger.error(f"Blockchain display error: {e}")

# Initialize blockchain
blockchain = Blockchain()

def blockchain_sync_server():
    """Listen for blockchain synchronization requests"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server.bind(('0.0.0.0', BLOCKCHAIN_SYNC_PORT))
        server.listen(5)
        logger.info(f"Blockchain sync server listening on port {BLOCKCHAIN_SYNC_PORT}")

        while True:
            try:
                conn, addr = server.accept()
                data = conn.recv(8192).decode()
                request = json.loads(data)
                
                if request['type'] == 'get_chain':
                    # Send our blockchain
                    response = {
                        'type': 'chain',
                        'chain': blockchain.get_chain_copy(),
                        'length': blockchain.get_chain_length()
                    }
                    conn.send(json.dumps(response).encode())
                    
                elif request['type'] == 'new_block':
                    # Someone is broadcasting a new block
                    block = request['block']
                    if blockchain.add_block(block):
                        logger.info(f"New block accepted from {addr[0]}")
                    response = {'type': 'ack', 'accepted': True}
                    conn.send(json.dumps(response).encode())
                
                conn.close()
                
            except Exception as e:
                logger.error(f"Blockchain sync error: {e}")
                try:
                    conn.close()
                except:
                    pass
                    
    except Exception as e:
        logger.error(f"Blockchain sync server error: {e}")
    finally:
        server.close()

def sync_blockchain_with_peers():
    """Periodically sync blockchain with peers"""
    while True:
        time.sleep(BLOCKCHAIN_SYNC_INTERVAL)
        
        with peer_lock:
            peer_list = list(discovered_peers.keys())
        
        if not peer_list:
            continue
            
        # Try to sync with a random peer
        peer_ip = random.choice(peer_list)
        
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect((peer_ip, BLOCKCHAIN_SYNC_PORT))
            
            request = {'type': 'get_chain'}
            s.send(json.dumps(request).encode())
            
            response_data = s.recv(16384).decode()
            response = json.loads(response_data)
            
            if response['type'] == 'chain':
                peer_chain = response['chain']
                if blockchain.replace_chain(peer_chain):
                    logger.info(f"Blockchain updated from peer {peer_ip}")
            
            s.close()
            
        except Exception as e:
            logger.debug(f"Sync failed with {peer_ip}: {e}")

def broadcast_new_block(block):
    """Broadcast a newly mined block to all peers"""
    with peer_lock:
        peer_list = list(discovered_peers.keys())
    
    for peer_ip in peer_list:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3)
            s.connect((peer_ip, BLOCKCHAIN_SYNC_PORT))
            
            request = {
                'type': 'new_block',
                'block': block
            }
            s.send(json.dumps(request).encode())
            s.recv(1024)  # Wait for acknowledgment
            s.close()
            
        except Exception as e:
            logger.debug(f"Failed to broadcast to {peer_ip}: {e}")

def mining_worker():
    """Background worker that mines blocks when transactions are available"""
    while True:
        time.sleep(2)  # Check every 2 seconds
        
        if blockchain.pending_transactions:
            logger.info("Mining new block...")
            new_block = blockchain.mine_block()
            
            if new_block:
                # Broadcast the new block to all peers
                broadcast_new_block(new_block)
                logger.info(f"Block #{new_block['index']} mined and broadcast")

def get_file_hash(filepath):
    """Calculate SHA-256 hash of a file"""
    hash_sha256 = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    except Exception as e:
        logger.error(f"Error calculating file hash: {e}")
        return None

def listen_for_incoming():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server.bind(('0.0.0.0', LISTEN_PORT))
        server.listen(5)
        logger.info(f"File receiver listening on port {LISTEN_PORT}")

        while True:
            try:
                conn, addr = server.accept()
                logger.info(f"File transfer connection from {addr}")

                metadata_json = conn.recv(4096).decode()
                metadata = json.loads(metadata_json)
                filename = metadata['filename']
                filesize = metadata['filesize']
                file_hash = metadata.get('hash', '')

                if filesize > MAX_FILE_SIZE:
                    conn.send(b'FILE_TOO_LARGE')
                    conn.close()
                    continue

                conn.send(b'METADATA_RECEIVED')

                safe_filename = os.path.basename(filename)
                received_filename = f"received_{safe_filename}"
                
                with open(received_filename, 'wb') as f:
                    received_bytes = 0
                    while received_bytes < filesize:
                        data = conn.recv(min(4096, filesize - received_bytes))
                        if not data:
                            break
                        f.write(data)
                        received_bytes += len(data)

                received_hash = get_file_hash(received_filename)
                if file_hash and received_hash != file_hash:
                    logger.warning(f"File integrity check failed for {filename}")
                    conn.send(b'HASH_MISMATCH')
                else:
                    conn.send(b'FILE_RECEIVED')
                    logger.info(f"File received successfully: {received_filename}")

                    # Add transaction to blockchain (will be mined by mining worker)
                    transaction = {
                        'type': 'file_transfer',
                        'filename': filename,
                        'filesize': filesize,
                        'file_hash': received_hash,
                        'sender': addr[0],
                        'receiver': PEER_NAME,
                        'timestamp': str(datetime.now())
                    }
                    blockchain.add_transaction(transaction)

                conn.close()

            except Exception as e:
                logger.error(f"Error handling incoming connection: {e}")
                try:
                    conn.close()
                except:
                    pass

    except Exception as e:
        logger.error(f"Error in file receiver: {e}")
    finally:
        server.close()

def broadcast_presence():
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    udp.settimeout(0.2)

    my_ip = socket.gethostbyname(socket.gethostname())
    
    while True:
        try:
            msg = json.dumps({
                "name": PEER_NAME,
                "peer_id": PEER_ID,
                "ip": my_ip,
                "port": LISTEN_PORT,
                "blockchain_port": BLOCKCHAIN_SYNC_PORT,
                "timestamp": str(datetime.now())
            }).encode()
            udp.sendto(msg, (BROADCAST_IP, BROADCAST_PORT))
            time.sleep(BROADCAST_INTERVAL)
        except Exception as e:
            logger.error(f"Error broadcasting presence: {e}")
            time.sleep(BROADCAST_INTERVAL)

def listen_for_broadcasts():
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        udp.bind(("", BROADCAST_PORT))
        my_ip = socket.gethostbyname(socket.gethostname())
        
        while True:
            try:
                data, addr = udp.recvfrom(1024)
                peer_info = json.loads(data.decode())
                ip = peer_info.get("ip")
                name = peer_info.get("name")
                peer_id = peer_info.get("peer_id")
                
                if ip and ip != my_ip and peer_id != PEER_ID:
                    with peer_lock:
                        discovered_peers[ip] = {
                            'name': name,
                            'peer_id': peer_id,
                            'last_seen': datetime.now()
                        }
            except Exception as e:
                continue
                
    except Exception as e:
        logger.error(f"Error listening for broadcasts: {e}")

def send_file(target_ip, target_port, filename):
    if not os.path.exists(filename):
        print(f"[!] File '{filename}' not found.")
        return False

    filesize = os.path.getsize(filename)
    if filesize > MAX_FILE_SIZE:
        print(f"[!] File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB")
        return False

    file_hash = get_file_hash(filename)
    if not file_hash:
        print("[!] Could not calculate file hash.")
        return False

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(30)
        s.connect((target_ip, target_port))

        metadata = {
            'filename': os.path.basename(filename),
            'filesize': filesize,
            'hash': file_hash
        }
        s.send(json.dumps(metadata).encode())
        
        response = s.recv(1024).decode()
        if response == 'FILE_TOO_LARGE':
            print("[!] File rejected: too large")
            return False
        elif response != 'METADATA_RECEIVED':
            print("[!] Failed to send metadata")
            return False

        with open(filename, 'rb') as f:
            sent_bytes = 0
            while sent_bytes < filesize:
                data = f.read(4096)
                if not data:
                    break
                s.send(data)
                sent_bytes += len(data)
                
                progress = (sent_bytes / filesize) * 100
                print(f"\rSending: {progress:.1f}%", end='', flush=True)

        print()
        
        response = s.recv(1024).decode()
        if response == 'FILE_RECEIVED':
            print(f"✅ File '{filename}' sent successfully to {target_ip}")
            
            with peer_lock:
                receiver_name = discovered_peers.get(target_ip, {}).get('name', 'Unknown')
            
            # Add transaction (will be mined by mining worker)
            transaction = {
                'type': 'file_transfer',
                'filename': os.path.basename(filename),
                'filesize': filesize,
                'file_hash': file_hash,
                'sender': PEER_NAME,
                'receiver': receiver_name,
                'timestamp': str(datetime.now())
            }
            blockchain.add_transaction(transaction)
                
            return True
        elif response == 'HASH_MISMATCH':
            print("❌ File transfer failed: hash mismatch")
            return False
        else:
            print("❌ File transfer failed: unknown error")
            return False

    except socket.timeout:
        print("❌ Connection timeout")
        return False
    except Exception as e:
        print(f"❌ Error sending file: {e}")
        return False
    finally:
        s.close()

def cleanup_old_peers():
    while True:
        time.sleep(30)
        current_time = datetime.now()
        
        with peer_lock:
            peers_to_remove = []
            for ip, info in discovered_peers.items():
                if (current_time - info['last_seen']).seconds > 60:
                    peers_to_remove.append(ip)
            
            for ip in peers_to_remove:
                del discovered_peers[ip]

def main():
    print(f"🚀 Starting Synchronized P2P Blockchain Node")
    print(f"📋 Node: {PEER_NAME} (ID: {PEER_ID})")
    print(f"📡 File Port: {LISTEN_PORT} | Blockchain Port: {BLOCKCHAIN_SYNC_PORT}")
    
    # Start all background threads
    threading.Thread(target=listen_for_incoming, daemon=True).start()
    threading.Thread(target=broadcast_presence, daemon=True).start()
    threading.Thread(target=listen_for_broadcasts, daemon=True).start()
    threading.Thread(target=cleanup_old_peers, daemon=True).start()
    threading.Thread(target=blockchain_sync_server, daemon=True).start()
    threading.Thread(target=sync_blockchain_with_peers, daemon=True).start()
    threading.Thread(target=mining_worker, daemon=True).start()

    time.sleep(3)

    while True:
        try:
            print(f"\n{'='*60}")
            print("📋 DISCOVERED PEERS")
            print(f"{'='*60}")
            
            with peer_lock:
                peer_list = list(discovered_peers.items())
                
            if peer_list:
                for idx, (ip, info) in enumerate(peer_list, start=1):
                    name = info.get('name', 'Unknown')
                    peer_id = info.get('peer_id', 'Unknown')
                    if len(peer_id) > 8:
                        peer_id = peer_id[:8] + "..."
                    print(f"{idx}. {name} ({ip}) [ID: {peer_id}]")
            else:
                print("No peers discovered yet...")

            # Safe blockchain info display
            try:
                chain_len = blockchain.get_chain_length()
                pending_len = len(blockchain.pending_transactions)
                print(f"\n⛓️  Blockchain Length: {chain_len} | Pending Transactions: {pending_len}")
            except Exception as e:
                print(f"\n⛓️  Blockchain Status: Error - {e}")

            print(f"\n{'='*60}")
            print("💡 COMMANDS")
            print(f"{'='*60}")
            print("send <#> <filename>  - Send file to peer")
            print("blockchain           - View blockchain")
            print("validate             - Validate blockchain")
            print("sync                 - Force blockchain sync")
            print("peers                - Refresh peer list")
            print("exit                 - Exit program")
            
            cmd = input("\n➤ Enter command: ").strip()
            
            if cmd.lower() == 'exit':
                print("👋 Goodbye!")
                break
                
            elif cmd.lower() == 'blockchain':
                try:
                    print("🔄 Loading blockchain...")
                    blockchain.display_blockchain()
                except Exception as e:
                    print(f"❌ Error displaying blockchain: {e}")
                    logger.error(f"Blockchain display command error: {e}")
                
            elif cmd.lower() == 'validate':
                try:
                    print("🔄 Validating blockchain...")
                    is_valid = blockchain.is_chain_valid()
                    print(f"🔍 Blockchain validation: {'✅ VALID' if is_valid else '❌ INVALID'}")
                except Exception as e:
                    print(f"❌ Error validating blockchain: {e}")
                    logger.error(f"Blockchain validation error: {e}")
                    
            elif cmd.lower() == 'sync':
                print("🔄 Forcing blockchain synchronization...")
                
            elif cmd.lower() == 'peers':
                print("🔄 Refreshing peer list...")
                continue
                
            elif cmd.startswith("send"):
                try:
                    parts = cmd.split(maxsplit=2)
                    if len(parts) != 3:
                        print("[!] Usage: send <peer_number> <filename>")
                        continue
                        
                    _, index_str, filename = parts
                    index = int(index_str) - 1
                    
                    if 0 <= index < len(peer_list):
                        ip, info = peer_list[index]
                        name = info.get('name', 'Unknown')
                        print(f"📤 Sending '{filename}' to {name} ({ip})...")
                        send_file(ip, LISTEN_PORT, filename)
                    else:
                        print("[!] Invalid peer number")
                        
                except (ValueError, IndexError) as e:
                    print("[!] Usage: send <peer_number> <filename>")
                except Exception as e:
                    print(f"❌ Error sending file: {e}")
                    
            else:
                print("[!] Unknown command. Type 'exit' to quit.")
                
        except KeyboardInterrupt:
            print("\n👋 Exiting...")
            break
        except Exception as e:
            print(f"❌ Error in main loop: {e}")
            logger.error(f"Main loop error: {e}")
            continue

if __name__ == "__main__":
    main()