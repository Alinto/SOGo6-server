"""
Admin authentication voucher service - simplified version without user data storage
"""

from typing import Type, Any
from cryptography.fernet import Fernet, InvalidToken
from base64 import urlsafe_b64encode
from json import loads as js_loads, dumps as js_dumps
import time

from app.auth.Admin import Admin, AdminAnonymous
from app.auth.voucher.Voucher import Voucher
from app.config.settings.ProcessSetting import ProcessSetting
from app.service import sogo_cache
from app.utils.dynamic_import import import_and_get_class
from app.utils.exceptions import RequestException, BugException
from app.utils import constants as cs
from app.utils.maths.sogo_hash import get_unique_token
from app.utils.logger.logger import logger_auth
from uuid import uuid4


class VoucherAdminService:
    """
    Service for generating and validating admin session tokens.
    Admin sessions don't store sensitive user data,
    just a session key to verify token validity.
    """

    def __init__(self, process_settings: ProcessSetting):
        self.process_settings = process_settings

        secret = self.process_settings.SOGO_P_VOUCHER_SECRET
        if len(secret) != 32:
            raise BugException("SOGO_P_VOUCHER_SECRET is not 32 char long")
        key = urlsafe_b64encode(secret.encode("utf-8"))
        self.fernet_session = Fernet(key)

    def generate_voucher_from_admin(self, admin_uid: str) -> Any:
        """
        Generate admin session and voucher token.
        
        :param admin_uid: Admin username
        :type admin_uid: str
        :raises BugException: If encryption fails
        :return: JWT voucher token
        :rtype: Any
        """
        # Generate session key and ID
        admin_session_id = str(uuid4())
        admin_session_key = get_unique_token(32)
        
        try:
            session_fernet = Fernet(urlsafe_b64encode(admin_session_key.encode("utf-8")))
            session_key_crypted = session_fernet.encrypt(b"")  # No sensitive data for admin
        except (ValueError, InvalidToken) as e:
            raise BugException("Cannot encrypt admin session") from e

        # Store minimal session info in Redis with 30 min TTL
        admin_session = {
            cs.USER_UID: admin_uid,
            cs.SESSION_LAST_SEEN: int(time.time())
        }

        sogo_cache().hashset(f"admin_session:{admin_session_id}", admin_session, 30 * 60)

        # Generate the voucher
        voucher_payload = {
            cs.USER_UID: admin_uid,
            cs.SESSION_KEY: ""
        }
        voucher_session_token_raw = f"{admin_session_id}:{admin_session_key}"
        try:
            voucher_session_token = self.fernet_session.encrypt(voucher_session_token_raw.encode("utf-8"))
        except (ValueError, InvalidToken) as e:
            raise BugException("Cannot encrypt voucher_session_token") from e
        voucher_payload[cs.SESSION_KEY] = voucher_session_token.decode("utf-8")

        # Create JWT voucher
        voucher_type = "JWTVoucher"
        voucher_class: Type[Voucher] = import_and_get_class("app.auth.voucher", voucher_type)

        needed_data = voucher_class.get_needed_parameters_to_instantiate()
        kargs = {}
        for kind, (param_name, arg_name) in needed_data.items():
            if kind == "process_settings":
                kargs[arg_name] = self.process_settings[param_name]
        voucher = voucher_class(**kargs)
        # TTL
        voucher_data = voucher.create_voucher(voucher_payload, 30 * 60) #TODO:

        return voucher_data

    def get_redis_session_key_from_voucher(self, voucher_data: Any) -> str:
        """
        Extract the Redis session key from admin voucher.

        :param voucher_data: The raw voucher data (JWT token string)
        :type voucher_data: Any
        :raises RequestException: If the voucher is invalid or expired
        :return: Redis key for the admin session (``admin_session:<session_id>``)
        :rtype: str
        """
        voucher_type = "JWTVoucher"
        voucher_class: Type[Voucher] = import_and_get_class("app.auth.voucher", voucher_type)

        needed_data = voucher_class.get_needed_parameters_to_instantiate()
        kargs = {}
        for kind, (param_name, arg_name) in needed_data.items():
            if kind == "process_settings":
                kargs[arg_name] = self.process_settings[param_name]
        voucher = voucher_class(**kargs)

        if not voucher.check_voucher_data_type(voucher_data):
            raise RequestException("Wrong data type for voucher")

        payload = voucher.read_voucher(voucher_data)
        if not payload:
            raise RequestException("Voucher has expired or cannot be read")

        session_key_crypted: str = payload[cs.SESSION_KEY]
        try:
            session_key = self.fernet_session.decrypt(session_key_crypted.encode("utf-8")).decode("utf-8")
        except (ValueError, InvalidToken) as e:
            raise RequestException("Cannot decrypt session key from voucher") from e

        try:
            session_id, _ = session_key.split(":")
        except ValueError as e:
            raise RequestException("Session key from voucher is not valid") from e

        return f"admin_session:{session_id}"

    def is_admin_session_valid(self, redis_key: str) -> bool:
        """
        Check if an admin session is still valid in Redis.

        :param redis_key: The Redis key for the admin session
        :type redis_key: str
        :return: True if session exists and is valid
        :rtype: bool
        """
        try:
            session_data = sogo_cache().hashget(redis_key)
            return bool(session_data)
        except Exception as e:
            logger_auth.error("Error checking admin session validity: %s", str(e))
            return False

    def generate_admin_from_voucher(self, voucher_data: Any) -> Admin:
        """
        Generate an Admin instance from a valid voucher token.

        :param voucher_data: The raw voucher data (JWT token string)
        :type voucher_data: Any
        :raises RequestException: If the voucher is invalid, expired, or session is not valid
        :return: Admin instance if valid, AdminAnonymous otherwise
        :rtype: Admin
        """
        try:
            redis_key = self.get_redis_session_key_from_voucher(voucher_data)
            
            if not self.is_admin_session_valid(redis_key):
                logger_auth.warning("Admin session is not valid for key: %s", redis_key)
                return AdminAnonymous()

            session_data = sogo_cache().hashget(redis_key)
            admin_uid = session_data.get(cs.USER_UID, "anonymous")
            logger_auth.info("Admin authenticated with uid: %s", admin_uid)
            return Admin(uid=admin_uid)
        except RequestException as e:
            logger_auth.warning("RequestException while generating admin from voucher: %s", str(e))
            return AdminAnonymous()
