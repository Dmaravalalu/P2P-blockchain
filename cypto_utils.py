# crypto_utils.py

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend
import os

def generate_aes_key_iv():
    key = os.urandom(32)  # AES-256
    iv = os.urandom(16)
    return key, iv

def encrypt_file(input_path, output_path, key, iv):
    with open(input_path, 'rb') as f:
        data = f.read()

    padder = padding.PKCS7(128).padder()
    padded = padder.update(data) + padder.finalize()

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    encrypted = encryptor.update(padded) + encryptor.finalize()

    with open(output_path, 'wb') as f:
        f.write(iv + encrypted)  # prepend IV for decryption

def decrypt_file(input_path, output_path, key):
    with open(input_path, 'rb') as f:
        iv = f.read(16)
        encrypted = f.read()

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    padded_data = decryptor.update(encrypted) + decryptor.finalize()

    unpadder = padding.PKCS7(128).unpadder()
    data = unpadder.update(padded_data) + unpadder.finalize()

    with open(output_path, 'wb') as f:
        f.write(data)
