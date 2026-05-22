import base64
import hashlib
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding

_SECRET_KEY = "9meVE6j?G!u%Z?55vSb26zGGphWJQbG*"
_SECRET_IV = "9meVE6j?G!u%Z?55"

def test_decrypt(stored_b64, use_binary_key=False):
    try:
        if use_binary_key:
            # 32 bytes binary (direct hash)
            key = hashlib.sha256(_SECRET_KEY.encode()).digest()
            iv = hashlib.sha256(_SECRET_IV.encode()).digest()[:16]
        else:
            # 32 chars of the hex string
            key = hashlib.sha256(_SECRET_KEY.encode()).hexdigest().encode()[:32]
            iv = hashlib.sha256(_SECRET_IV.encode()).hexdigest().encode()[:16]
        
        raw = base64.b64decode(stored_b64)
        inner_str = raw.decode('ascii')
        ct = base64.b64decode(inner_str)
        
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        padded_data = decryptor.update(ct) + decryptor.finalize()
        unpadder = padding.PKCS7(128).unpadder()
        data = unpadder.update(padded_data) + unpadder.finalize()
        return data.decode()
    except Exception as e:
        return f"Error: {e}"

stored = "MUZMdFhGSTc3SUxmQWhPbHd6Ry9sQT09"
print(f"Hex Key Method: {test_decrypt(stored, False)}")
print(f"Binary Key Method: {test_decrypt(stored, True)}")
