"""
Utility module for AES-256 encryption/decryption of sensitive data
"""
import os
import base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding

SOGO_AES_ENC_KEY = os.environ.get('SOGO_AES_ENC_KEY', None)

def get_encryption_key() -> bytes:
    """
    Get the AES encryption key from environment or generate a default one
    
    :return: 32 bytes key for AES-256
    :rtype: bytes
    """
    if SOGO_AES_ENC_KEY:
        try:
            return base64.b64decode(SOGO_AES_ENC_KEY)
        except Exception:
            # If it's a raw string, convert it
            return SOGO_AES_ENC_KEY.encode('utf-8').ljust(32)[:32]
    else:
        raise ValueError("Encryption key not set in environment variable 'SOGO_AES_ENC_KEY'")


def encrypt_password(password: str) -> str:
    """
    Encrypt a password using AES-256-CBC
    
    :param password: Plain text password
    :type password: str
    :return: Base64 encoded encrypted password with IV prepended
    :rtype: str
    """
    if not password:
        return ""

    # Generate a random 16-byte IV
    iv = os.urandom(16)

    # Get encryption key
    key = get_encryption_key()

    # Create cipher
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()

    # PKCS7 padding to align with AES block size (128 bits = 16 bytes)
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(password.encode('utf-8')) + padder.finalize()

    # Encrypt
    encrypted = encryptor.update(padded_data) + encryptor.finalize()

    # Return IV + encrypted data in base64
    return base64.b64encode(iv + encrypted).decode('utf-8')


def decrypt_password(encrypted_password: str) -> str:
    """
    Decrypt a password using AES-256-CBC

    :param encrypted_password: Base64 encoded encrypted password with IV prepended
    :type encrypted_password: str
    :return: Plain text password
    :rtype: str
    """
    if not encrypted_password:
        return ""

    try:
        # Decode from base64
        encrypted_data = base64.b64decode(encrypted_password)

        # Extract IV (first 16 bytes)
        iv = encrypted_data[:16]
        encrypted = encrypted_data[16:]

        # Get encryption key
        key = get_encryption_key()

        # Create cipher
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()

        # Decrypt
        decrypted_padded = decryptor.update(encrypted) + decryptor.finalize()

        # Remove padding
        unpadder = padding.PKCS7(128).unpadder()
        decrypted = unpadder.update(decrypted_padded) + unpadder.finalize()

        return decrypted.decode('utf-8')
    except Exception as e:
        # In case of decryption error, we can log but not return the password
        raise ValueError(f"Failed to decrypt password: {e}") from e
