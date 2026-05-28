"""PHP-compatible password encryption (shared by auth login and password reset)."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import re
import string

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

_SECRET_KEY = "9meVE6j?G!u%Z?55vSb26zGGphWJQbG*"
_SECRET_IV = "9meVE6j?G!u%Z?55"
_INNER_BYTE_FIX: dict[int, int] = {0x96: ord("V")}
_B64_CHARS = frozenset(string.ascii_letters + string.digits + "+/=")


def _aes_key_iv() -> tuple[bytes, bytes]:
    key = hashlib.sha256(_SECRET_KEY.encode()).hexdigest().encode()[:32]
    iv = hashlib.sha256(_SECRET_IV.encode()).hexdigest().encode()[:16]
    return key, iv


def _encrypt_plain_to_single_b64(plain: str) -> str:
    key, iv = _aes_key_iv()
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(plain.encode()) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ct = encryptor.update(padded_data) + encryptor.finalize()
    return base64.b64encode(ct).decode("ascii")


def php_password_for_db(plain: str) -> str:
    inner = _encrypt_plain_to_single_b64(plain)
    return base64.b64encode(inner.encode("ascii")).decode("ascii")


def stored_password_variants(plain: str) -> tuple[str, str]:
    inner = _encrypt_plain_to_single_b64(plain)
    outer = base64.b64encode(inner.encode("ascii")).decode("ascii")
    return inner, outer


def _inner_base64_string_from_outer_raw(raw: bytes) -> str:
    fixed = bytes(_INNER_BYTE_FIX.get(b, b) for b in raw)
    try:
        inner = fixed.decode("ascii")
    except UnicodeDecodeError:
        inner = fixed.decode("latin-1").translate(str.maketrans({"\x96": "V"}))
        inner = "".join(c for c in inner if c in _B64_CHARS)
    if not inner or not re.fullmatch(r"[A-Za-z0-9+/]+=*", inner):
        raise ValueError("invalid inner base64 layer")
    return inner


def _ciphertext_from_stored(stored_b64: str) -> bytes:
    raw = base64.b64decode(stored_b64)
    if len(raw) % 16 == 0:
        return raw
    inner = _inner_base64_string_from_outer_raw(raw)
    try:
        return base64.b64decode(inner, validate=True)
    except (ValueError, binascii.Error):
        return base64.b64decode(inner)


def _consteq(a: str, b: str) -> bool:
    if len(a) != len(b):
        return False
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def my_simple_crypt(string: str, action: str = "encrypt") -> str:
    if action == "encrypt":
        return php_password_for_db(string)
    key, iv = _aes_key_iv()
    ct = _ciphertext_from_stored(string)
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    padded_data = decryptor.update(ct) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    data = unpadder.update(padded_data) + unpadder.finalize()
    return data.decode()


def password_matches_stored(stored: str, plain: str) -> bool:
    stored = (stored or "").strip()
    plain = plain or ""
    if not stored:
        return False
    if _consteq(stored, plain):
        return True
    single_b64, double_b64 = stored_password_variants(plain)
    if _consteq(stored, single_b64):
        return True
    if _consteq(stored, double_b64):
        return True
    try:
        decrypted = my_simple_crypt(stored, "decrypt")
        return _consteq(decrypted, plain)
    except Exception:
        return False
