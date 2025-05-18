# receiver.py

import socket

host = '0.0.0.0'
port = 5001

try:
    s = socket.socket()
    s.bind((host, port))
    s.listen(1)
    print("[*] Waiting for connection...")

    conn, addr = s.accept()
    print(f"[+] Connected by {addr}")

    # Receive filename
    filename = conn.recv(1024).decode()
    print(f"[+] Receiving file: {filename}")
    conn.send(b'FILENAME_RECEIVED')

    # Receive and write file content
    with open(f'received_{filename}', 'wb') as f:
        while True:
            data = conn.recv(1024)
            if not data:
                break
            f.write(data)

    print(f"[+] File received and saved as: received_{filename}")
except Exception as e:
    print(f"[-] Error: {e}")
finally:
    conn.close()
    s.close()
