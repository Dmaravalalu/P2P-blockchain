# sender.py

import socket
import os

host = '192.168.0.144'  # Replace with receiver's IP
port = 5001
filename = 'testforv1.txt'

try:
    s = socket.socket()
    s.connect((host, port))

    # Send the filename
    s.send(filename.encode())
    ack = s.recv(1024).decode()
    if ack != 'FILENAME_RECEIVED':
        print("[-] Failed to send filename.")
        s.close()
        exit()

    # Send file content
    with open(filename, 'rb') as f:
        data = f.read(1024)
        while data:
            s.send(data)
            data = f.read(1024)

    print("[+] File sent successfully.")
except Exception as e:
    print(f"[-] Error: {e}")
finally:
    s.close()
