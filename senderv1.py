import socket

host = 'receiver_ip_here'
port = 5001

s = socket.socket()
s.connect((host, port))

with open('file_to_send.txt', 'rb') as f:
    data = f.read(1024)
    while data:
        s.send(data)
        data = f.read(1024)

s.close()
