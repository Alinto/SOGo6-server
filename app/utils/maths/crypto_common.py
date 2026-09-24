"""
check_password.py

Verify a plaintext password against an encrypted/hashed password, given the
name of the algorithm used to produce the hash.

Requires: passlib
    pip install passlib

Supported algo values (case-insensitive):
    'crypt'         - traditional Unix crypt(3) (DES)
    'md5'           - unsalted MD5, base64 encoded (LDAP {MD5})
    'md5-crypt'     - Unix $1$ crypt-style MD5
    'smd5'          - salted MD5, base64(digest || salt) (LDAP {SMD5})
    'cram-md5'      - CRAM-MD5 storage scheme, hex HMAC-MD5
    'ldap-md5'      - same as 'md5' (LDAP {MD5} alias)
    'sha'           - unsalted SHA1, base64 encoded (LDAP {SHA})
    'sha256'        - unsalted SHA256, base64 encoded
    'sha256-crypt'  - Unix $5$ crypt-style SHA256
    'ssha256'       - salted SHA256, base64(digest || salt) (LDAP {SSHA256})
    'sha512'        - unsalted SHA512, base64 encoded
    'sha512-crypt'  - Unix $6$ crypt-style SHA512
    'ssha512'       - salted SHA512, base64(digest || salt) (LDAP {SSHA512})
    'blf-crypt'     - bcrypt (Blowfish) crypt-style

Note: some databases store the hash with a leading "{SCHEME}" prefix
(e.g. "{SSHA}xxxxx"). If present, that prefix is stripped before verifying,
since the caller already tells us the algo via the `algo` argument.
"""

import base64
import hashlib
import hmac
import binascii
from typing import Callable

from passlib.hash import des_crypt, md5_crypt, sha256_crypt, sha512_crypt, bcrypt, argon2
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

PBKDF2_SALT_LEN = 16
PBKDF2_DEFAULT_ROUNDS = 5000  # only relevant if you ever need to *generate* a hash, not to verify one
PBKDF2_KEY_SIZE_SHA1 = 20

def _decode_b64(data: bytes) -> bytes:
    """Base64-decode, tolerating missing padding."""
    padding = (-len(data)) % 4
    return base64.b64decode(data + b"=" * padding)


def _check_plain_hash(password: str, encrypted_pwd: str, hash_func: Callable, is_hex: bool = False) -> bool:
    """Verify an unsalted {ALGO}-style digest: base64(digest)."""
    print(f"password = {encrypted_pwd}")
    if is_hex:
        computed = hash_func(password.encode()).hexdigest()
        return hmac.compare_digest(encrypted_pwd, computed)
    else:
        digest = _decode_b64(encrypted_pwd.encode())
        computed = hash_func(password.encode()).digest()
        return hmac.compare_digest(digest, computed)


def _check_salted_hash(password: str, encrypted_pwd: str, hash_func: Callable, digest_size: int) -> bool:
    """Verify a salted {SALGO}-style digest: base64(digest || salt)."""
    print(encrypted_pwd)
    raw = _decode_b64(encrypted_pwd.encode())
    digest, salt = raw[:digest_size], raw[digest_size:]
    computed = hash_func(password.encode() + salt).digest()
    return hmac.compare_digest(digest, computed)


def _check_cram_md5(password: str, encrypted_pwd: str) -> bool:
    """Verify CRAM-MD5 storage scheme: hex(HMAC-MD5(key=password, msg=b''))."""
    computed = hmac.new(password.encode(), b"", hashlib.md5).hexdigest()
    return hmac.compare_digest(computed, encrypted_pwd.strip().lower())

# def _check_sym_aes_128_cbc(password: str, encrypted_pwd: str, key_path: str) -> bool:
#     """Decrypt encrypted_pwd with the AES-128 key at key_path and compare."""
#     with open(key_path, "rb") as f:
#         key = f.read()  # expects a raw 16-byte key
#     raw = _decode_b64(encrypted_pwd.encode())
#     iv, ciphertext = raw[:16], raw[16:]  # assumes IV is prepended
#     decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
#     padded = decryptor.update(ciphertext) + decryptor.finalize()
#     unpadder = sym_padding.PKCS7(128).unpadder()
#     plaintext = unpadder.update(padded) + unpadder.finalize()
#     return hmac.compare_digest(plaintext.decode(), password)

def _check_sym_aes_128_cbc(password: str, encrypted_pwd: str, key_path: str) -> bool:
    """
    Verify the legacy `$AES-128-CBC$<iv_b64>$<ciphertext_b64>` scheme.

    Only the first 16-byte block of the (NUL-padded) password is ever
    compared, matching the original implementation, which truncated the
    ciphertext to 16 bytes before storing it.
    """
    parts = encrypted_pwd.split("$")
    if len(parts) != 4 or parts[1] != "AES-128-CBC":
        return False
    iv = _decode_b64(parts[2].encode())[:16]
    expected_ct = _decode_b64(parts[3].encode())

    with open(key_path, "rb") as f:
        key = f.read()[:16]

    pwd_bytes = password.encode()
    block_len = max(((len(pwd_bytes) + 15) // 16) * 16, 16)
    first_block = pwd_bytes.ljust(block_len, b"\x00")[:16]

    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    ciphertext = encryptor.update(first_block) + encryptor.finalize()

    return hmac.compare_digest(ciphertext, expected_ct)

def _check_pbkdf2_sha1(password: str, encrypted_pwd: str) -> bool:
    """
    Verify the legacy `$1$<salt>$<rounds>$<hex_hash>` PBKDF2-HMAC-SHA1 scheme.
    Only the first PBKDF2_SALT_LEN bytes of the salt string are actually
    used as the PBKDF2 salt, matching the original implementation.
    """
    parts = encrypted_pwd.split("$")
    if len(parts) != 4 or parts[0] != "" or parts[1] != "1":
        return False
    _, _, salt_str, rounds_str, hex_hash = parts
    try:
        rounds = int(rounds_str)
    except ValueError:
        return False

    salt = salt_str.encode("utf-8")[:PBKDF2_SALT_LEN]
    derived = hashlib.pbkdf2_hmac("sha1", password.encode(), salt, rounds, dklen=PBKDF2_KEY_SIZE_SHA1)
    return hmac.compare_digest(derived.hex(), hex_hash.lower())

# Dispatch table: algo name -> callable(password, encrypted_pwd) -> bool
# Built with functools.partial so every entry shares the same (password,
# encrypted_pwd) call signature, regardless of which helper backs it.
_ALGOS: dict[str, Callable[..., bool]] = {
    "crypt":           lambda p, e, **_: des_crypt.verify(p, e),
    "md5":             lambda p, e, is_hex=False, **_: _check_plain_hash(p, e, hashlib.md5, is_hex),
    "ldap-md5":        lambda p, e, is_hex=False, **_: _check_plain_hash(p, e, hashlib.md5, is_hex),
    "md5-crypt":       lambda p, e, **_: md5_crypt.verify(p, e),
    "smd5":            lambda p, e, **_: _check_salted_hash(p, e, hashlib.md5, 16),
    "cram-md5":        lambda p, e, **_: _check_cram_md5(p, e),
    "sha":             lambda p, e, is_hex=False, **_: _check_plain_hash(p, e, hashlib.sha1, is_hex),
    "sha256":          lambda p, e, is_hex=False, **_: _check_plain_hash(p, e, hashlib.sha256, is_hex),
    "sha256-crypt":    lambda p, e, **_: sha256_crypt.verify(p, e),
    "ssha256":         lambda p, e, **_: _check_salted_hash(p, e, hashlib.sha256, 32),
    "sha512":          lambda p, e, is_hex=False, **_: _check_plain_hash(p, e, hashlib.sha512, is_hex),
    "sha512-crypt":    lambda p, e, **_: sha512_crypt.verify(p, e),
    "ssha512":         lambda p, e, **_: _check_salted_hash(p, e, hashlib.sha512, 64),
    "blf-crypt":       lambda p, e, **_: bcrypt.verify(p, e),
    "plain":           lambda p, e, **_: hmac.compare_digest(p, e),
    "none":            lambda p, e, **_: hmac.compare_digest(p, e),
    "pbkdf2":          lambda p, e, **_: _check_pbkdf2_sha1(p, e),
    "argon2i":         lambda p, e, **_: argon2.verify(p, e),
    "argon2id":        lambda p, e, **_: argon2.verify(p, e),
    "sym-aes-128-cbc": lambda p, e, d, key_path=None, **_: _check_sym_aes_128_cbc(p, e, key_path),
}


def check_password(password: str, encrypted_pwd: str, default_algo: str, key_path: str | None = None) -> bool:
    """
    Return True if `password` matches `encrypted_pwd`. If the encrypted password
    prepend the algo, we use it, else we use the default_algo

    Raises ValueError if `algo` is not one of the supported schemes.
    Returns False (rather than raising) if the stored hash is malformed
    or otherwise can't be parsed/verified.
    """
    #Get algo
    is_hex = False
    if encrypted_pwd.startswith("{") and "}" in encrypted_pwd:
        split = encrypted_pwd.split("}", 2)
        print(split)
        algo = split[0][1:].lower()
        encrypted_pwd = split[1]
        if algo.endswith(".hex"):
            is_hex=True
            algo = algo[:-4]
    else:
        algo = default_algo.lower().strip()

    print(algo)
    verify_func = _ALGOS.get(algo)
    if verify_func is None:
        raise ValueError(f"Unsupported algorithm: {algo!r}")

    try:
        return verify_func(password, encrypted_pwd, is_hex=is_hex, key_path=key_path)
    except Exception:
        # Malformed/unparseable stored hash -> treat as no match, don't crash.
        return False
