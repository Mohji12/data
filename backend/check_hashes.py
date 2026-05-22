import base64
import hashlib
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding

_SECRET_KEY = "9meVE6j?G!u%Z?55vSb26zGGphWJQbG*"
_SECRET_IV = "9meVE6j?G!u%Z?55"

def encrypt(plain):
    key = hashlib.sha256(_SECRET_KEY.encode()).hexdigest().encode()[:32]
    iv = hashlib.sha256(_SECRET_IV.encode()).hexdigest().encode()[:16]
    
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(plain.encode()) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ct = encryptor.update(padded_data) + encryptor.finalize()
    
    inner = base64.b64encode(ct).decode('ascii')
    return inner

print(f"Admin@123: {encrypt('Admin@123')}")
print(f"admin123: {encrypt('admin123')}")
print(f"mohan: {encrypt('mohan')}")
