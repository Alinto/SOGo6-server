import base64
import os
import hashlib


from passlib.hash import (
    md5_crypt,
    sha1 as passlib_sha1,
    sha256_crypt,
    sha512_crypt,
    pbkdf2_sha256,
    argon2,
    ldap_salted_md5 as ldap_md5,
    cram_md5 as passlib_cram_md5,
    bcrypt as blf_crypt,
    unix_disabled as unix_crypt,  # For Unix crypt (may require system support)
)
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend


# --- Helper for symmetric encryption ---
def generate_key(salt: bytes) -> bytes:
    """Generate a key for AES-128-CBC using a salt."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=16,
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    return kdf.derive(b"fixed_password_for_key_derivation")  # Replace with a secure method in production

def encrypt_aes_128_cbc(plain_password: str, key: bytes) -> str:
    """Encrypt using AES-128-CBC (symmetric)."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    iv = os.urandom(16)
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    padded_password = plain_password.encode().ljust(16, b"\0")  # Simple padding
    encrypted = encryptor.update(padded_password) + encryptor.finalize()
    return base64.b64encode(iv + encrypted).decode()

def decrypt_aes_128_cbc(encrypted_password: str, key: bytes) -> str:
    """Decrypt using AES-128-CBC (symmetric)."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    data = base64.b64decode(encrypted_password)
    iv = data[:16]
    ciphertext = data[16:]
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    decrypted = decryptor.update(ciphertext) + decryptor.finalize()
    return decrypted.decode().rstrip("\0")

# --- Encryption Functions ---
def encrypt_crypt(plain_password: str) -> str:
    return passlib_crypt.hash(plain_password)

def encrypt_md5(plain_password: str) -> str:
    return hashlib.md5(plain_password.encode()).hexdigest()

def encrypt_md5_crypt(plain_password: str) -> str:
    return md5_crypt.hash(plain_password)

def encrypt_smd5(plain_password: str) -> str:
    return smd5.hash(plain_password)

def encrypt_cram_md5(plain_password: str) -> str:
    return cram_md5.hash(plain_password)

def encrypt_ldap_md5(plain_password: str) -> str:
    return ldap_md5.hash(plain_password)

def encrypt_sha(plain_password: str) -> str:
    return passlib_sha.hash(plain_password)

def encrypt_sha256(plain_password: str) -> str:
    return hashlib.sha256(plain_password.encode()).hexdigest()

def encrypt_sha256_crypt(plain_password: str) -> str:
    return sha256_crypt.hash(plain_password)

def encrypt_ssha256(plain_password: str) -> str:
    salt = os.urandom(16)
    return f"{{SSHA256}}{base64.b64encode(hashlib.sha256(plain_password.encode() + salt).digest() + salt).decode()}"

def encrypt_sha512(plain_password: str) -> str:
    return hashlib.sha512(plain_password.encode()).hexdigest()

def encrypt_sha512_crypt(plain_password: str) -> str:
    return sha512_crypt.hash(plain_password)

def encrypt_ssha512(plain_password: str) -> str:
    salt = os.urandom(16)
    return f"{{SSHA512}}{base64.b64encode(hashlib.sha512(plain_password.encode() + salt).digest() + salt).decode()}"

def encrypt_blf_crypt(plain_password: str) -> str:
    return blf_crypt.hash(plain_password)

def encrypt_pbkdf2(plain_password: str) -> str:
    return pbkdf2_sha256.hash(plain_password)

def encrypt_sym_aes_128_cbc(plain_password: str) -> str:
    salt = os.urandom(16)
    key = generate_key(salt)
    return encrypt_aes_128_cbc(plain_password, key)

def encrypt_argon2i(plain_password: str) -> str:
    return argon2.hash(plain_password, algorithm="argon2i")

def encrypt_argon2id(plain_password: str) -> str:
    return argon2.hash(plain_password, algorithm="argon2id")

# --- Mapping of algorithm names to functions ---
PWD_ALGO_FUNCTIONS = {
    'crypt': encrypt_crypt,
    'md5': encrypt_md5,
    'md5-crypt': encrypt_md5_crypt,
    'smd5': encrypt_smd5,
    'cram-md5': encrypt_cram_md5,
    'ldap-md5': encrypt_ldap_md5,
    'sha': encrypt_sha,
    'sha256': encrypt_sha256,
    'sha256-crypt': encrypt_sha256_crypt,
    'ssha256': encrypt_ssha256,
    'sha512': encrypt_sha512,
    'sha512-crypt': encrypt_sha512_crypt,
    'ssha512': encrypt_ssha512,
    'blf-crypt': encrypt_blf_crypt,
    'PBKDF2': encrypt_pbkdf2,
    'sym-aes-128-cbc': encrypt_sym_aes_128_cbc,
    'argon2i': encrypt_argon2i,
    'argon2id': encrypt_argon2id,
}

def encrypt_password(plain_password: str, algo: str) -> str:
    """Encrypt a password using the specified algorithm."""
    if algo not in PWD_ALGO_FUNCTIONS:
        raise ValueError(f"Unsupported algorithm: {algo}")
    return PWD_ALGO_FUNCTIONS[algo](plain_password)