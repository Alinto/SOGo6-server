from __future__ import annotations
from typing import TYPE_CHECKING

from time import monotonic, sleep

from app.auth.User import UserAnonymous
from app.config.settings.SystemSettings import SystemSettingsObj, SystemSettings
from app.config.settings.DomainSettings import AuthSettingsObj, AuthSettings, UserSourceSettings, UserSourceSettingsObj, MailSettings, MailSettingsObj
from app.config.settings.UserSettings import UserGeneralSettings
from app.module.auth.ModuleAuth import ModuleAuth
from app.module.auth.ModuleUserSource import ModuleUserSource
from app.module.calendar.ModuleCalendar import ModuleCalendar
from app.module.contact.ModuleContact import ModuleContact
from app.module.mail.ModuleMail import ModuleMail
from app.module.user.ModuleUserProfile import ModuleUserProfile
from app.service import sogo_cache
from app.utils.api.ApiBaseResponse import create_api_base_response
from app.utils.exceptions import RequestException, BugException
from app.utils import errors as err
from app.utils.logger.logger import logger_api
from app.utils import constants as cs
from app.utils.maths.sogo_hash import generate_uuid


if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.auth.User import User
    from app.manager.cache.ClientRedis import ClientRedis
    from app.module.calendar.model.CalCalendar import CalCalendar
    from app.module.contact.model.CardAddressBook import CardAddressBook


class InterfaceAuthUser:
    """
    Interface for user authentication
    """

    def __init__(self, process: ProcessSetting, system: dict, default_domain: dict, user: User):
        system_settings = SystemSettingsObj(system[SystemSettings.subparent])
        default_auth = AuthSettingsObj(default_domain[AuthSettings.subparent])

        default_us_source_raw: dict = default_domain[UserSourceSettings.subparent]
        default_us_source: dict = {}
        for source_uid, source_settings in default_us_source_raw.items():
            default_us_source[source_uid] = UserSourceSettingsObj(source_settings)

        self.process = process
        self.default_domain = default_domain
        self.user = user
        self.module_auth = ModuleAuth(process, system_settings, default_auth, default_us_source)
        self.module_user_profile = ModuleUserProfile(process, default_domain)
        self._module_calendar: ModuleCalendar = ModuleCalendar(process)
        self._module_contact: ModuleContact = ModuleContact(process)

    def get_login_mech(self, user_uid:str, redirect:str) -> tuple[dict, int]:
        """
        Get the login mech from a uid

        :param user_uid: The user unique ID
        :type user_uid: str
        :param redirect: The redirect URL after authentication
        :type redirect: str
        :return: Tuple containing the API response dict and HTTP status code
        :rtype: tuple[dict, int]
        """
        try:
            ret = self.module_auth.get_login_mech(user_uid)
        except RequestException as e:
            return create_api_base_response(str(e), e.error)
        return create_api_base_response(ret)

    def _check_login(self, uid:str, password:str) -> tuple[bool, User, ModuleUserSource]:
        """
        Check credentials uid/password/token of a user
        #TODO get login auth with AuthSettingsObj

        :param uid: uid of the user
        :type username: str
        :param password: password or token or any equivalent
        :type password: str
        :return: True if success, instante of User, instande of Appropriate ModuleUserSource
        :rtype: tuple[bool, User, ModuleUserSource]
        """
        # Prepare the user object for authentication and get domain user sources
        user, domain_user_sources = self.module_auth.get_user_and_domain_user_sources(uid, password)

        # Check login using the user source module
        module_us = ModuleUserSource(domain_user_sources)
        return module_us.check_login(user), user, module_us

    def plain_login(self, data:dict, voucher_data:str = "") -> tuple[dict, int]:
        """
        Check a plain login uid/password.
        If the user is already authenticated as this uid, no new session is created
        and the current voucher is returned as is.

        :param data: Dictionary containing 'username' and 'password' keys
        :type data: dict
        :param voucher_data: The raw JWT token from the Authorization header, if any
        :type voucher_data: str
        :return: Tuple containing the API response dict and HTTP status code
        :rtype: tuple[dict, int]
        """
        uid = data["username"]
        password = data["password"]
        if voucher_data and self.user.authenticated and self.user.uid == uid:
            return create_api_base_response({"jwt_token": voucher_data})

        success, user, module_us = self._check_login(uid, password)

        if not success:
            return create_api_base_response(None, err.ERROR_LOGIN_FAILED)

        try:
            # Not closed: CPython frees the client once the onboarding is done, and the redis-py destructor
            # then closes its connection. A client shared by sogo_cache() stays open.
            self.onboard_user_and_fill_info(user=user, cache=sogo_cache())
        except RequestException as ex:
            logger_api.error("Request exception when onboarding user %s: %s", uid, str(ex))
            return create_api_base_response(None, ex.error)

        # Generate the voucher for the authenticated user, once onboarded: a failed onboarding leaves no session
        ret = self.module_auth.generate_voucher_from_user(user)

        return create_api_base_response(ret)

    def check_user_and_fill_info(self, user:User) -> tuple[bool, User]:
        """
        Directly used by the before_request at init.
        Check that the user credentials is still relevant and fill the user instance with infos needed

        :param user: _description_
        :type user: User
        :return: True if the user credentials are ok
        :rtype: bool
        """
        success, user_found = self.check_user(user)
        if success:
            self.module_user_profile.get_user_profile(user_found)
        return success, user_found

    def check_user(self, user: User) -> tuple[bool, User]:
        """
        Check the user credentials against the user sources, without loading the profile: a user who never
        signed in has none yet.

        :param user: The user with the credentials to check
        :type user: User
        :return: True and the user found if the credentials are ok, False and an anonymous user otherwise
        :rtype: tuple[bool, User]
        """
        success, user_found, _ = self._check_login(user.uid, user.password)
        if not success:
            return False, UserAnonymous()
        return True, user_found

    def onboard_user_and_fill_info(self, user: User, cache: ClientRedis) -> None:
        """
        Fill the user instance with its profile, after onboarding the user if it signs in for the first time.
        Called by the web sign-in and by every DAV request: DAV clients may connect before any web sign-in.

        The folders of the profile are set once the personal calendar and address book exist: the profile of
        an onboarded user is read once, without reading the onboarding lock.

        :param user: The authenticated user
        :type user: User
        :param cache: The cache client keeping the onboarding lock
        :type cache: ClientRedis
        :raises RequestException: When a step fails, or when the onboarding runs too long in another request
        """
        try:
            self.module_user_profile.get_user_profile(user)
            if user.folders:
                return
        except RequestException as ex:
            if ex.error is not err.ERROR_USER_PROFILE_NOT_FOUND:
                raise
        self._onboard_user(user=user, cache=cache)
        self.module_user_profile.get_user_profile(user)

    def _onboard_user(self, user: User, cache: ClientRedis) -> None:
        """
        Create the profile, the personal calendar and address book and the special mail folders of a user
        signing in for the first time. Clients adding an account often send several requests at once: the
        first one onboards the user under a lock, the others wait for it.
        """
        uid: str = user.uid
        lock_key: str = cs.ONBOARDING_LOCK_PREFIX + uid
        deadline: float = monotonic() + cs.ONBOARDING_WAIT_TIMEOUT
        InterfaceAuthUser._wait_onboarding_end(cache=cache, lock_key=lock_key, deadline=deadline)
        if self.module_user_profile.is_user_profile_present(uid):
            return
        lock_token: str = generate_uuid()
        if not cache.set(key=lock_key, value=lock_token, ttl=cs.ONBOARDING_LOCK_TTL, nx=True):
            InterfaceAuthUser._wait_onboarding_end(cache=cache, lock_key=lock_key, deadline=deadline)
            return
        try:
            # Another request may have onboarded the user between the check and the lock
            if self.module_user_profile.is_user_profile_present(uid):
                return
            self.module_user_profile.create_user_profile(user)
            raw_gen: dict = self.module_user_profile.get_partial_user_preferences(
                uid, UserGeneralSettings.subparent.lower()
            )
            user_tz: str = raw_gen.get(UserGeneralSettings.subparent, {}).get("SOGO_U_TIMEZONE", "UTC")
            personal_calendar: CalCalendar = self._module_calendar.create_personal_calendar(uid, tz=user_tz)
            personal_addressbook: CardAddressBook = self._module_contact.create_personal_addressbook(uid)
            # Update the folders column with the personal calendar and addressbook keys
            if personal_calendar.key and personal_addressbook.key:
                self.module_user_profile.update_user_folders(
                    uid=uid, calendar_key=personal_calendar.key, addressbook_key=personal_addressbook.key
                )
            mail_settings: MailSettingsObj = MailSettingsObj(self.default_domain[MailSettings.subparent])
            module_mail: ModuleMail = ModuleMail(user=user, mail_settings=mail_settings, process_setting=self.process)
            module_mail.create_special_folders_if_not_exist(cs.DEFAULT_IDENTITY_KEY_VALUE)
        finally:
            if cache.get(lock_key, expected_type=str) == lock_token:
                cache.delete(lock_key)

    @staticmethod
    def _wait_onboarding_end(cache: ClientRedis, lock_key: str, deadline: float) -> None:
        """Wait for the onboarding run by another request to release its lock, and raise
        ERROR_LOGIN_ONBOARDING_RUNNING if it still runs at the deadline (``monotonic()`` clock)."""
        while cache.get(lock_key, expected_type=str) is not None:
            if monotonic() >= deadline:
                raise RequestException(error=err.ERROR_LOGIN_ONBOARDING_RUNNING)
            sleep(cs.ONBOARDING_WAIT_STEP)

    def logout(self, voucher_data: str) -> tuple[dict, int]:
        """
        Revoke the session associated with the given voucher.

        :param voucher_data: The raw JWT token from the Authorization header
        :type voucher_data: str
        :return: Tuple containing the API response dict and HTTP status code
        :rtype: tuple[dict, int]
        """
        try:
            self.module_auth.logout_user(voucher_data)
        except RequestException as e:
            return create_api_base_response(None, e.error)
        return create_api_base_response(None)

