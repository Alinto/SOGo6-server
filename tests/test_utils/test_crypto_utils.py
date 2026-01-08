"""
Unit tests for crypto_utils module (AES-256 encryption/decryption)
"""
import os
import base64
import pytest
from unittest.mock import patch

import app.utils.maths.crypto_utils as crypto_utils
from app.utils.maths.crypto_utils import (
    encrypt_password,
    decrypt_password
)


@pytest.fixture
def mock_encryption_key():
    """Fixture to provide a valid 32-byte encryption key"""
    return base64.b64encode(os.urandom(32)).decode('utf-8')


@pytest.fixture
def setup_encryption_key(mock_encryption_key):
    """Fixture to set up encryption key in environment"""
    with patch.object(crypto_utils, 'SOGO_AES_ENC_KEY', mock_encryption_key):
        yield mock_encryption_key


class TestEncryptDecryptIntegration:
    """Integration tests for encrypt and decrypt functions"""

    def test_encrypt_decrypt(self, setup_encryption_key):
        """Test full encryption-decryption round trip"""
        passwords = [
            "simple",
            "Complex!P@ssw0rd#123",
            "Пароль",
            "日本語パスワード",
            "a" * 100,
            "!@#$%^&*()_+-=[]{}|;':\",./<>?",
            " leading",
            "trailing ",
            " both ",
            "middle   spaces",
            "\ttabs\t",
            "\nnewlines\n",
        ]

        for password in passwords:
            encrypted = encrypt_password(password)
            decrypted = decrypt_password(encrypted)
            assert decrypted == password, f"Failed for password: {password}"
