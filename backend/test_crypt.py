import base64
import hashlib
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend

def my_simple_crypt(string, action='encrypt'):
    secret_key = '9meVE6j?G!u%Z?55vSb26zGGphWJQbG*'
    secret_iv = '9meVE6j?G!u%Z?55'
    encrypt_method = "AES-256-CBC"
    
    # Hash the key and IV using SHA256 as PHP does
    key = hashlib.sha256(secret_key.encode()).hexdigest().encode()
    # PHP's hash('sha256', ...) returns a hex string. 
    # But wait, AES-256 needs a 32-byte key. 
    # hexdigest() is 64 characters. 
    # PHP's openssl_encrypt will truncate or use the raw bytes?
    # Let's check: $key = hash( 'sha256', $secret_key ); -> this is a 64 char hex string.
    # PHP openssl_encrypt will take the first 32 bytes of this string as the key for AES-256.
    
    key_bytes = key[:32]
    iv_bytes = hashlib.sha256(secret_iv.encode()).hexdigest()[:16].encode()
    
    if action == 'encrypt':
        # Padding
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(string.encode()) + padder.finalize()
        
        cipher = Cipher(algorithms.AES(key_bytes), modes.CBC(iv_bytes), backend=default_backend())
        encryptor = cipher.encryptor()
        ct = encryptor.update(padded_data) + encryptor.finalize()
        return base64.b64encode(ct).decode()
    else:
        ct = base64.b64decode(string)
        cipher = Cipher(algorithms.AES(key_bytes), modes.CBC(iv_bytes), backend=default_backend())
        decryptor = cipher.decryptor()
        padded_data = decryptor.update(ct) + decryptor.finalize()
        
        unpadder = padding.PKCS7(128).unpadder()
        data = unpadder.update(padded_data) + unpadder.finalize()
        return data.decode()

# Test with the password from screenshot and DB
test_pass = "6YHNNHY6"
encrypted = my_simple_crypt(test_pass)
print(f"Test Password: {test_pass}")
print(f"Encrypted in Python: {encrypted}")

db_pass = "SUNMallZSHF1Ybm5WUT09"
try:
    decrypted = my_simple_crypt(db_pass, action='decrypt')
    print(f"Decrypted from DB: {decrypted}")
except Exception as e:
    print(f"Decryption failed: {e}")
