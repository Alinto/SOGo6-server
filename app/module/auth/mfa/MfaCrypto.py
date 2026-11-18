from __future__ import annotations
from typing import TYPE_CHECKING
from base64 import urlsafe_b64encode
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.utils import errors as err
from app.utils.exceptions import AggravatedException, BugException
from app.utils.logger.logger import logger_mfa

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting


#Changing this value makes every stored MFA secret unreadable
_HKDF_INFO = b"sogo6-mfa-secret-v1"


class MfaCrypto:
    """
    Encrypt/decrypt the MFA secrets stored in the database or in the cache.

    The Fernet key is derived (HKDF-SHA256) from SOGO_P_VOUCHER_SECRET with its own `info`,
    so it is never the same key as the one used for the sessions.
    Changing SOGO_P_VOUCHER_SECRET makes every stored secret unreadable: users must enroll again.
    """

    def __init__(self, process_settings: ProcessSetting):
        secret: str = process_settings.SOGO_P_VOUCHER_SECRET
        if not secret:
            raise AggravatedException("SOGO_P_VOUCHER_SECRET is empty, cannot derive the MFA key")
        hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=_HKDF_INFO)
        key = hkdf.derive(secret.encode("utf-8"))
        self._fernet = Fernet(urlsafe_b64encode(key))

    def encrypt(self, clear: str) -> str:
        """
        Encrypt a string

        :param clear: value to encrypt
        :type clear: str
        :return: Fernet token
        :rtype: str
        """
        return self._fernet.encrypt(clear.encode("utf-8")).decode("utf-8")

    def decrypt(self, token: str) -> str:
        """
        Decrypt a Fernet token

        :param token: Fernet token created by encrypt()
        :type token: str
        :raises BugException: the token can't be decrypted (key changed or data corrupted)
        :return: the clear value
        :rtype: str
        """
        try:
            return self._fernet.decrypt(token.encode("utf-8")).decode("utf-8")
        except (InvalidToken, ValueError, AttributeError) as e:
            logger_mfa.error("Cannot decrypt an MFA secret. Has SOGO_P_VOUCHER_SECRET changed?")
            raise BugException(err.ERROR_MFA_SECRET_UNREADABLE.m, err.ERROR_MFA_SECRET_UNREADABLE) from e

    @staticmethod
    def fingerprint(value: str) -> str:
        """
        Short, non reversible identifier of a value (e.g. an encrypted secret), usable in a cache key.

        :param value: value to fingerprint
        :type value: str
        :return: 16 hex chars
        :rtype: str
        """
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
