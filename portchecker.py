import socket

def is_port_available(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) != 0

for port in range(5000, 5010):  # Adjust range as needed
    if is_port_available(port):
        print(f"Port {port} is available.")
    else:
        print(f"Port {port} is in use.")
