import socket

host = '0.0.0.0'
port = 5001

s = socket.socket()
s.bind((host, port))
s.listen(1)
print("Waiting for connection...")

conn, addr = s.accept()
print(f"Connected by {addr}")

with open('received_file.txt', 'wb') as f:
    while True:
        data = conn.recv(1024)
        if not data:
            break
        f.write(data)

conn.close()
