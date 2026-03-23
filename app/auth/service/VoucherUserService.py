
from typing import Any, Type
from cryptography.fernet import Fernet, InvalidToken
from base64 import urlsafe_b64decode, urlsafe_b64encode
from json import loads as js_loads, dumps as js_dumps, JSONDecodeError
from uuid import uuid4
import time

from app.auth.User import User, UserAnonymous
from app.auth.voucher.Voucher import Voucher
from app.config.settings.ProcessSetting import ProcessSetting
from app.config.settings.DomainSettings import AuthSettingsObj
from app.service import sogo_cache
from app.utils.dynamic_import import import_and_get_class
from app.utils.exceptions import RequestException, AggravatedException, BugException
from app.utils import constants as cs
from app.utils.logger.logger import logger, logger_auth
from app.utils.maths.sogo_hash import get_unique_token
from app.utils.strings import string_to_sort_score


class VoucherUserService:
    """
    Class that can genarte a user session and the associated user, ot get the user session from
    a voucher
    """

    def __init__(self, process_settings:ProcessSetting):
        self.process_settings = process_settings

        secret = self.process_settings.SOGO_P_VOUCHER_SECRET
        if len(secret) != 32:
            raise AggravatedException("SOGO_P_VOUCHER_SECRET is not 32 char long")
        key = urlsafe_b64encode(secret.encode("utf-8"))
        self.fernet_session = Fernet(key)

    def generate_voucher_from_user(self, user:User) -> Any:
        """
        Generate the user session and the voucher from a user

        :param user: _description_
        :type user: User
        :raises BugException: _description_
        :raises BugException: _description_
        :return: _description_
        :rtype: Any
        """

        #Generate, encrypt and store user_session in redis
        user_session_sensitive_data = js_dumps(user.get_user_session())
        user_session_id = str(uuid4())
        user_session_key = get_unique_token(32)
        try:
            session_fernet = Fernet(urlsafe_b64encode(user_session_key.encode("utf-8")))
            sensitive_data = session_fernet.encrypt(user_session_sensitive_data.encode("utf-8"))
        except (ValueError,InvalidToken) as e:
            raise BugException("Cannot encrypt user session") from e

        user_session = {
            cs.USER_UID: user.uid,
            cs.USER_DOMAIN: user.domain,
            cs.SESSION_SENSITIVE: sensitive_data,
            cs.SESSION_LAST_SEEN: int(time.time())
        }

        sogo_cache().hashset(f"user_session:{user_session_id}", user_session, cs.TTL_1D)
        # Index the session in the sorted set so that we can paginate / sort
        # active sessions by last-activity without scanning all keys.
        sogo_cache().zset_add(
            cs.ZSET_USER_SESSIONS_ACTIVITY,
            f"user_session:{user_session_id}",
            int(time.time()),
        )
        # Index the session by uid score so that sessions can be sorted / filtered by uid.
        sogo_cache().zset_add(
            cs.ZSET_USER_SESSIONS_UID,
            f"user_session:{user_session_id}",
            string_to_sort_score(user.uid),
        )
        # Index the session by domain score so that sessions can be sorted / filtered by domain.
        sogo_cache().zset_add(
            cs.ZSET_USER_SESSIONS_DOMAIN,
            f"user_session:{user_session_id}",
            string_to_sort_score(user.domain),
        )

        #Generate the voucher
        voucher_payload = user.get_voucher_payload()
        voucher_session_token_raw = f"{user_session_id}:{user_session_key}"
        try:
            voucher_session_token = self.fernet_session.encrypt(voucher_session_token_raw.encode("utf-8"))
        except (ValueError,InvalidToken) as e:
            raise BugException("Cannot encrypt vouhcer_session_token") from e 
        voucher_payload[cs.SESSION_KEY] = voucher_session_token.decode("utf-8")

        #If we were allowing different voucher type, here will be the settings
        voucher_type = "JWTVoucher"
        voucher_class: Type[Voucher] = import_and_get_class("app.auth.voucher", voucher_type)

        #Instantiate the voucher
        needed_data = voucher_class.get_needed_parameters_to_instantiate()
        kargs = {}
        for kind, (param_name, arg_name) in needed_data.items():
            if kind == "process_settings":
                kargs[arg_name] = self.process_settings[param_name]
        voucher = voucher_class(**kargs)
        voucher_data = voucher.create_voucher(voucher_payload, cs.TTL_1D)

        return voucher_data

    def generate_user_from_voucher(self,  data: Any) -> User:
        """
        Get a voucher instance and the expected data for it 

        :param user: _description_
        :type user: User
        """
        #If we were allowing different voucher type, here will be the settings
        voucher_type = "JWTVoucher"
        voucher_class: Type[Voucher] = import_and_get_class("app.auth.voucher", voucher_type)

        #Instantiate the voucher
        needed_data = voucher_class.get_needed_parameters_to_instantiate()
        kargs = {}
        for kind, (param_name, arg_name) in needed_data.items():
            if kind == "process_settings":
                kargs[arg_name] = self.process_settings[param_name]
        voucher = voucher_class(**kargs)

        #Check if the sessiondata is ok, then get the user session
        if voucher.check_voucher_data_type(data):
            payload = voucher.read_voucher(data)
            if not payload:
                raise RequestException("Voucher has expired or cannot be read")
            return self._get_user_session_from_payload(payload)

        raise RequestException("Wrong data type for voucher")


    def _get_user_session_from_payload(self, payload:dict) -> User:
        """
        The payload has the session_key encrypted to get the userSession
        and info about the user.
        
        :param payload: 
        :type payload: dict
        """

        # the plaintext is converted to ciphertext
        # token = self.fernet_session.encrypt(js_dumps(payload).encode("utf-8"))

        session_key_crypted: str = payload[cs.SESSION_KEY]
        voucher_user_uid: str = payload[cs.USER_UID]

        # decrypting the ciphertext
        session_key = self.fernet_session.decrypt(session_key_crypted.encode("utf-8")).decode("utf-8")

        try:
            #session_id to get the data from cache, session_secret to decrypt the encrypted part
            session_id, session_token = session_key.split(":")
        except ValueError as e:
            raise RequestException("Session key from Voucher is not valid") from e

        user_session_data = sogo_cache().hashget(f"user_session:{session_id}")
        if not user_session_data:
            logger_auth.info("User session for %s is expired or does not exist", voucher_user_uid)
            return UserAnonymous()

        if not voucher_user_uid == user_session_data[cs.USER_UID]:
            logger_auth.warning("Voucher user uid %s does not match the user session uid", voucher_user_uid)
            return UserAnonymous()

        #Get the sensitive data and try to decrypt it with session_token
        sensitive_data_encrypted = user_session_data[cs.SESSION_SENSITIVE]
        try:
            session_fernet = Fernet(urlsafe_b64encode(session_token.encode("utf-8")))
            sensitive_data = session_fernet.decrypt(sensitive_data_encrypted)
        except (ValueError,InvalidToken) as e:
            raise RequestException("Cannot decrypt usser session with session token given in Voucher") from e

        try:
            #sensitive data is supposed to be a json. At least check that
            user_data = js_loads(sensitive_data)
        except JSONDecodeError as e:
            raise BugException("sensitive data for user session is not a json") from e

        user = User.init_from_user_session(user_data)
        # Update the last activity timestamp in both the hash and the sorted set
        new_last_seen = int(time.time())
        logger.debug("Updating last_activity for session %s: %s -> %s", session_id, user_session_data.get(cs.SESSION_LAST_SEEN), new_last_seen)
        sogo_cache().hashset(
            f"user_session:{session_id}",
            {cs.SESSION_LAST_SEEN: new_last_seen},
            ttl=0
        )
        sogo_cache().zset_add(
            cs.ZSET_USER_SESSIONS_ACTIVITY,
            f"user_session:{session_id}",
            new_last_seen,
        )
        # Keep the uid score index in sync.
        sogo_cache().zset_add(
            cs.ZSET_USER_SESSIONS_UID,
            f"user_session:{session_id}",
            string_to_sort_score(user.uid),
        )
        # Keep the domain score index in sync.
        sogo_cache().zset_add(
            cs.ZSET_USER_SESSIONS_DOMAIN,
            f"user_session:{session_id}",
            string_to_sort_score(user.domain),
        )
        logger.info("From voucher get user: %s", user)

        return user
