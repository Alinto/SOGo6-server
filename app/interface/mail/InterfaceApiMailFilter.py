from __future__ import annotations
from typing import TYPE_CHECKING, Any

from app.config.settings.DomainSettings import MailSettings, MailSettingsObj
from app.config.settings.UserSettings import UserGeneralSettings
from app.module.mail.ModuleFilter import ModuleFilter
from app.module.user.ModuleUserProfile import ModuleUserProfile
from app.utils.constants import (
    FILTER_SECTION_FILTERS,
    FILTER_SECTION_VACATION,
    FILTER_SECTION_FORWARD,
    FILTER_SECTION_NOTIFICATION,
)
from app.utils.exceptions import RequestException
from app.utils.api.ApiBaseResponse import create_api_base_response
from app.utils.logger.logger import logger_api

if TYPE_CHECKING:
    from app.auth.User import User
    from app.config.settings.ProcessSetting import ProcessSetting


class InterfaceApiMailFilter:
    """
    Interface for mail filter operations.

    Pass-through layer between the API and ModuleFilter.
    """

    def __init__(self, process_setting: ProcessSetting, user_domain_settings: dict, user: User) -> None:
        self.process_setting = process_setting
        self.user_domain_settings = user_domain_settings
        self.mail_settings = MailSettingsObj(user_domain_settings[MailSettings.subparent])
        self.user = user
        self.filter_module = ModuleFilter(user, self.mail_settings, process_setting)
        self.user_module = ModuleUserProfile(process_setting, user_domain_settings)

    def set_filters(self, filters: list[dict[str, Any]]) -> tuple[dict[str, Any], int]:
        """Replace the ``filters`` list for the current user.

        :param filters: Validated list of filter dicts.
        :type filters: list[dict[str, Any]]
        :return: Tuple of (API response dict, HTTP status code).
        :rtype: tuple[dict[str, Any], int]
        """
        try:
            saved = self.filter_module.set_section(FILTER_SECTION_FILTERS, filters)
        except RequestException as ex:
            logger_api.error("Request exception in set_filters: %s", str(ex))
            return create_api_base_response(None, ex.error)
        return create_api_base_response(saved)

    def set_vacation(self, vacation: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """Replace the ``Vacation`` section for the current user.

        Automatically adds the user's timezone to the vacation config if not specified,
        so that startDate/endDate without explicit timezone use the user's timezone.

        :param vacation: Validated vacation settings dict.
        :type vacation: dict[str, Any]
        :return: Tuple of (API response dict, HTTP status code).
        :rtype: tuple[dict[str, Any], int]
        """
        try:
            # Ensure timezone is set: if not provided, use user's timezone
            if not vacation.get("timezone"):
                vacation = dict(vacation)  # Make a copy to avoid modifying the original
                vacation["timezone"] = self._get_user_timezone()
            
            saved = self.filter_module.set_section(FILTER_SECTION_VACATION, vacation)
        except RequestException as ex:
            logger_api.error("Request exception in set_vacation: %s", str(ex))
            return create_api_base_response(None, ex.error)
        return create_api_base_response(saved)

    def _get_user_timezone(self) -> str:
        """Get the user's IANA timezone from preferences, defaulting to UTC.
        
        :return: IANA timezone string (e.g., 'Europe/Paris', 'UTC')
        :rtype: str
        """
        try:
            raw_gen: dict = self.user_module.get_partial_user_preferences(
                self.user.uid, UserGeneralSettings.subparent.lower()
            )
            return raw_gen.get(UserGeneralSettings.subparent, {}).get("SOGO_U_TIMEZONE", "UTC")
        except Exception as e:
            logger_api.warning("Failed to get user timezone for %s: %s. Defaulting to UTC.", self.user.uid, e)
            return "UTC"

    def set_forward(self, forward: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """Replace the ``Forward`` section for the current user.

        :param forward: Validated forward settings dict.
        :type forward: dict[str, Any]
        :return: Tuple of (API response dict, HTTP status code).
        :rtype: tuple[dict[str, Any], int]
        """
        try:
            saved = self.filter_module.set_section(FILTER_SECTION_FORWARD, forward)
        except RequestException as ex:
            logger_api.error("Request exception in set_forward: %s", str(ex))
            return create_api_base_response(None, ex.error)
        return create_api_base_response(saved)

    def set_notification(self, notification: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """Replace the ``Notification`` section for the current user.

        :param notification: Validated notification settings dict.
        :type notification: dict[str, Any]
        :return: Tuple of (API response dict, HTTP status code).
        :rtype: tuple[dict[str, Any], int]
        """
        try:
            saved = self.filter_module.set_section(FILTER_SECTION_NOTIFICATION, notification)
        except RequestException as ex:
            logger_api.error("Request exception in set_notification: %s", str(ex))
            return create_api_base_response(None, ex.error)
        return create_api_base_response(saved)

    # ------------------------------------------------------------------ #
    # GET methods                                                          #
    # ------------------------------------------------------------------ #

    def get_filters(self) -> tuple[dict[str, Any], int]:
        """Return the ``filters`` list for the current user.

        :return: Tuple of (API response dict, HTTP status code).
        :rtype: tuple[dict[str, Any], int]
        """
        try:
            value = self.filter_module.get_section(FILTER_SECTION_FILTERS)
        except RequestException as ex:
            logger_api.error("Request exception in get_filters: %s", str(ex))
            return create_api_base_response(None, ex.error)
        return create_api_base_response({"filters": value})

    def get_vacation(self) -> tuple[dict[str, Any], int]:
        """Return the ``Vacation`` section for the current user.

        :return: Tuple of (API response dict, HTTP status code).
        :rtype: tuple[dict[str, Any], int]
        """
        try:
            value = self.filter_module.get_section(FILTER_SECTION_VACATION)
        except RequestException as ex:
            logger_api.error("Request exception in get_vacation: %s", str(ex))
            return create_api_base_response(None, ex.error)
        return create_api_base_response({"vacation": value})

    def get_forward(self) -> tuple[dict[str, Any], int]:
        """Return the ``Forward`` section for the current user.

        :return: Tuple of (API response dict, HTTP status code).
        :rtype: tuple[dict[str, Any], int]
        """
        try:
            value = self.filter_module.get_section(FILTER_SECTION_FORWARD)
        except RequestException as ex:
            logger_api.error("Request exception in get_forward: %s", str(ex))
            return create_api_base_response(None, ex.error)
        return create_api_base_response({"forward": value})

    def get_notification(self) -> tuple[dict[str, Any], int]:
        """Return the ``Notification`` section for the current user.

        :return: Tuple of (API response dict, HTTP status code).
        :rtype: tuple[dict[str, Any], int]
        """
        try:
            value = self.filter_module.get_section(FILTER_SECTION_NOTIFICATION)
        except RequestException as ex:
            logger_api.error("Request exception in get_notification: %s", str(ex))
            return create_api_base_response(None, ex.error)
        return create_api_base_response({"notification": value})
