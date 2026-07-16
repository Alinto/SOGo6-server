"""
Admin authentication voucher service - simplified version without user data storage
"""

from typing import Type, Any
from base64 import urlsafe_b64encode
import time
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken

from app.auth.Admin import Admin, AdminAnonymous
from app.auth.voucher.Voucher import Voucher
from app.config.settings.ProcessSetting import ProcessSetting
from app.service import sogo_cache
from app.utils.dynamic_import import import_and_get_class
from app.utils.exceptions import RequestException, BugException
from app.utils import constants as cs
from app.utils.maths.sogo_hash import get_unique_token
from app.utils.logger.logger import logger_auth



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

        # Store minimal session info in Redis with 30 min TTL
        admin_session = {
            cs.USER_UID: admin_uid,
            cs.SESSION_LAST_SEEN: int(time.time())
        }

        cache = sogo_cache()
        cache.hashset(f"admin_session:{admin_session_id}", admin_session, 30 * 60)
        cache.close()

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
        voucher_data = voucher.create_voucher(voucher_payload, 30 * 60) #30 min validity

        return voucher_data

    def get_redis_session_key_from_voucher(self, voucher_data: Any) -> tuple[str, str]:
        """
        Extract the admin uid and Redis session key from admin voucher.

        :param voucher_data: The raw voucher data (JWT token string)
        :type voucher_data: Any
        :raises RequestException: If the voucher is invalid or expired
        :return: Admin uid and Redis key for the admin session (``admin_session:<session_id>``)
        :rtype: tuple[str, str]
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

        return payload[cs.USER_UID], f"admin_session:{session_id}"

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
            admin_uid, redis_key = self.get_redis_session_key_from_voucher(voucher_data)

            cache = sogo_cache()
            session_data = cache.hashget(redis_key)
            if not session_data:
                return AdminAnonymous()
            if not admin_uid == session_data[cs.USER_UID]:
                return AdminAnonymous()

            #Update ttl and lest seen
            cache.hashset(redis_key, {cs.SESSION_LAST_SEEN: int(time.time())}, ttl=30*60)
            cache.close()

            logger_auth.info("Admin authenticated with uid: %s", admin_uid)
            return Admin(uid=admin_uid)
        except RequestException as e:
            logger_auth.warning("RequestException while generating admin from voucher: %s", str(e))
            return AdminAnonymous()
