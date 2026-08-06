from __future__ import annotations
from typing import TYPE_CHECKING, Any
from http import HTTPStatus

from app.auth.User import User
from app.factory.share.RepositoryAcl import AclEntry
from app.module.mail.ModuleMail import ModuleMail
from app.module.user.ModuleUserProfile import ModuleUserProfile
from app.module.auth.ModuleUserSource import ModuleUserSource
from app.module.mail.ModuleMail import ModuleMail
from app.factory.share.shareMailFolder import FOLDER_PERMISSION_CODE_TO_RIGHT, right_to_camel
from app.config.settings.DomainSettings import MailSettings, MailSettingsObj
from app.utils import constants as cs
from app.utils import errors as err
from app.utils.exceptions import RequestException
from app.utils.api.ApiBaseResponse import create_api_base_response
from app.utils.logger.logger import logger_api

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting


class InterfaceApiMailFolder:
    """
    Interface for folder-related mail operations.

    Handles mail folder operations for one or multiple configured IMAP accounts.
    """

    def __init__(self, process_setting: ProcessSetting, user_domain_settings: dict, user: User) -> None:
        self.process_setting = process_setting
        self.user_domain_settings = user_domain_settings
        self.mail_settings = MailSettingsObj(user_domain_settings[MailSettings.subparent])
        self.user = user

        self.mail_module = ModuleMail(self.user, self.mail_settings, process_setting=process_setting)
        self._user_source_module: ModuleUserSource = ModuleUserSource.init_from_domain_settings(user_domain_settings)
        self._share_targets: dict[str, User] = {}

    def get_folder_list(self, account_id: str) -> tuple[dict[str, Any], int]:
        """Retrieve the list of mail folders for a given account and return an ApiBaseResponse.

        Interface contract:
        - Catches module exceptions (RequestException, ValidationError)
        - Converts module data to API format
        - Returns tuple (response_dict, http_status_code)
        
        :param account_id: The account identifier
        :type account_id: str
        :return: tuple of (API response dict, HTTP status code)
        :rtype: tuple[dict[str, Any], int]
        """
        try:
            folder_list = self.mail_module.get_folder_list(account_id)
            return create_api_base_response(folder_list)
        except RequestException as ex:
            logger_api.error("Request exception in get_folder_list: %s", str(ex))
            return create_api_base_response(None, ex.error)

    def create_folder(self, account_id: str, folder_name: str, parent_path:str = "") -> tuple[dict[str, Any], int]:
        """Create a new mail folder for the configured account and return an ApiBaseResponse.

        Interface contract:
        - Catches module exceptions (RequestException, ValidationError)
        - Converts module data to API format
        - Returns tuple (response_dict, http_status_code)

        :param account_id: The account identifier
        :type account_id: str
        :param folder_name: Name of the folder to create
        :type folder_name: str
        :param parent_path: Path of the parent
        :type parent_path: str

        :return: tuple of (API response dict, HTTP status code)
        :rtype: tuple[dict[str, Any], int]
        """
        try:
            folder_data = self.mail_module.create_folder(account_id, folder_name, parent_path)
            return create_api_base_response(folder_data, code=HTTPStatus.CREATED)
        except RequestException as ex:
            logger_api.error("Request exception in create_folder: %s", str(ex))
            return create_api_base_response(None, ex.error)

    def get_one_folder(self, account_id: str, folder_name: str) -> tuple[dict[str, Any], int]:
        """Retrieve details of a specific mail folder.
        
        :param account_id: The ID of the account
        :type account_id: str
        :param folder_name: The ID of the folder
        :type folder_name: str
        :return: A tuple of (API response dict, status code)
        :rtype: tuple[dict[str, Any], int]
        """
        try:
            folder_details = self.mail_module.get_one_folder(account_id, folder_name)
            return create_api_base_response(folder_details)
        except RequestException as ex:
            logger_api.error("Request exception in get_one_folder: %s", str(ex))
            return create_api_base_response(None, ex.error)

    def delete_folder(self, account_id: str, folder_name: str) -> tuple[str|dict[str, Any], int]:
        """Delete a mail folder.
        
        :param account_id: The ID of the account
        :type account_id: str
        :param folder_name: The ID of the folder to delete
        :type folder_name: str
        :return: A tuple of (empty string or error dict, status code)
        :rtype: tuple[Union[str, dict[str, Any]], int]
        """
        try:
            self.mail_module.delete_folder(account_id, folder_name)
            return "", 204
        except RequestException as ex:
            logger_api.error("Request exception in delete_folder: %s", str(ex))
            return create_api_base_response(None, ex.error)

    def update_folder(self, account_id: str, folder_name: str, folder_data: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """Update name, type (junk, template...) and subscription status of a specific mail folder.
        
        :param account_id: The ID of the account
        :type account_id: str
        :param folder_name: The current name of the folder
        :type folder_name: str
        :param folder_data: dictionary containing update data (name, subscribed, type)
        :type folder_data: dict[str, Any]
        :return: A tuple of (API response dict, status code)
        :rtype: tuple[dict[str, Any], int]
        """
        try:
            updated_folder = self.mail_module.update_folder(folder_name, folder_data)
            return create_api_base_response(updated_folder)
        except RequestException as ex:
            logger_api.error("Request exception in update_folder: %s", str(ex))
            return create_api_base_response(None, ex.error)

    def rename_folder(self, account_id: str, folder_path: str, new_name: str) -> tuple[dict[str, Any], int]:
        """Rename a mail folder.
        
        :param account_id: The ID of the account
        :type account_id: str
        :param folder_path: The current path of the folder
        :type folder_path: str
        :param new_name: The new name for the folder
        :type new_name: str
        :return: A tuple of (API response dict, status code)
        :rtype: tuple[dict[str, Any], int]
        """
        try:
            renamed_folder = self.mail_module.rename_folder(account_id, folder_path, new_name)
            return create_api_base_response(renamed_folder)
        except RequestException as ex:
            logger_api.error("Request exception in rename_folder: %s", str(ex))
            return create_api_base_response(None, ex.error)

    def change_folder_type(self, account_id: str, folder_path: str, new_type: str) -> tuple[dict[str, Any], int]:
        """Change the type of a mail folder.
        
        :param account_id: The ID of the account
        :type account_id: str
        :param folder_path: The path of the folder
        :type folder_path: str
        :param new_type: The new type for the folder
        :type new_type: str
        :return: A tuple of (API response dict, status code)
        :rtype: tuple[dict[str, Any], int]
        """
        try:
            updated_folder = self.user_module.change_folder_type(self.user, self.mail_settings, folder_path, new_type)
            return create_api_base_response(updated_folder)
        except RequestException as ex:
            logger_api.error("Request exception in change_folder_type: %s", str(ex))
            return create_api_base_response(None, ex.error)

    def expunge_folder(self, account_id: str, folder_name: str, expunge_data:dict) -> tuple[dict[str, Any], int]:
        """Expunge all mails in the specified folder.
        
        :param account_id: The ID of the account
        :type account_id: str
        :param folder_name: The ID of the folder to expunge
        :type folder_name: str
        :return: A tuple of (API response dict with mail_deleted count, status code)
        :rtype: tuple[dict[str, Any], int]
        """
        do_subfolders = expunge_data["do_subfolders"]
        try:
            result = self.mail_module.expunge_folder(account_id, folder_name, do_subfolders)
            return create_api_base_response(result)
        except RequestException as ex:
            logger_api.error("Request exception in expunge_folder: %s", str(ex))
            return create_api_base_response(None, ex.error)

    def purge_folder_mails(self, account_id: str, folder_name: str, purge_data: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """Purge all mails in the specified folder.
        
        Mark mails as deleted (optionally before a specific date).
        If permanently_delete is True, also expunge the folder.
        
        :param account_id: The ID of the account
        :type account_id: str
        :param folder_name: The ID of the folder
        :type folder_name: str
        :param purge_data: dictionary containing purge options (do_subfolders, permanently_delete, date)
        :type purge_data: dict[str, Any]
        :return: A tuple of (empty string or error dict, status code)
        :rtype: tuple[Union[str, dict[str, Any]], int]
        """
        try:
            return create_api_base_response(self.mail_module.purge_folder_mails(account_id, folder_name, purge_data))
        except RequestException as ex:
            logger_api.error("Request exception in purge_folder_mails: %s", str(ex))
            return create_api_base_response(None, ex.error)

    def export_folder_mails(self, account_id: str, folder_name: str) -> tuple[dict[str, Any], int]:
        """Export all mails in the specified folder.
        
        :param account_id: The ID of the account
        :type account_id: str
        :param folder_name: The ID of the folder
        :type folder_name: str
        :return: A tuple of (API response dict, status code)
        :rtype: tuple[dict[str, Any], int]
        """
        try:
            export_data = self.mail_module.export_folder_mails(folder_name)
            return create_api_base_response(export_data)
        except RequestException as ex:
            logger_api.error("Request exception in export_folder_mails: %s", str(ex))
            return create_api_base_response(None, ex.error)

    def get_folder_share(self, account_id: str, folder_path: str) -> tuple[dict[str, Any], int]:
        """Get share information for the specified folder.

        :param account_id: The ID of the account
        :type account_id: str
        :param folder_path: The ID of the folder
        :type folder_path: str
        :return: A tuple of (API response dict, status code)
        :rtype: tuple[dict[str, Any], int]
        """
        try:
            entries: list[AclEntry] = self.mail_module.get_folder_share(account_id, folder_path)
        except RequestException as ex:
            logger_api.error("Request exception in get_folder_share: %s", str(ex))
            return create_api_base_response(None, ex.error)
        return create_api_base_response(self._serialize_share_entries(entries))

    def patch_folder_share(self, account_id: str, folder_path: str, share_data: list[dict[str, Any]]) -> tuple[dict[str, Any], int]:
        """Partially update sharing rights for the specified folder.

        Only the users specified in share_data are modified; other existing shares are
        left unchanged.

        :param account_id: The ID of the account
        :type account_id: str
        :param folder_path: The ID of the folder
        :type folder_path: str
        :param share_data: List of users with their rights configuration
        :type share_data: list[dict[str, Any]]
        :return: A tuple of (API response dict, status code)
        :rtype: tuple[dict[str, Any], int]
        """
        try:
            users = [{"uid": self._resolve_to_user(entry), "rights": self._resolve_rights(entry)} for entry in share_data]
            entries: list[AclEntry] = self.mail_module.patch_folder_share(account_id, folder_path, users)
        except RequestException as ex:
            logger_api.error("Request exception in patch_folder_share: %s", str(ex))
            return create_api_base_response(None, ex.error)
        return create_api_base_response(self._serialize_share_entries(entries))

    def put_folder_share(self, account_id: str, folder_path: str, share_data: list[dict[str, Any]]) -> tuple[dict[str, Any], int]:
        """Replace all sharing rights for the specified folder.

        Existing shares are entirely replaced by the users specified in share_data.

        :param account_id: The ID of the account
        :type account_id: str
        :param folder_path: The ID of the folder
        :type folder_path: str
        :param share_data: List of users with their rights configuration
        :type share_data: list[dict[str, Any]]
        :return: A tuple of (API response dict, status code)
        :rtype: tuple[dict[str, Any], int]
        """
        try:
            users = [{"uid": self._resolve_to_user(entry), "rights": self._resolve_rights(entry)} for entry in share_data]
            entries: list[AclEntry] = self.mail_module.put_folder_share(account_id, folder_path, users)
        except RequestException as ex:
            logger_api.error("Request exception in put_folder_share: %s", str(ex))
            return create_api_base_response(None, ex.error)
        return create_api_base_response(self._serialize_share_entries(entries))

    def post_folder_share(self, account_id: str, folder_path: str, share_data: list[dict[str, Any]]) -> tuple[dict[str, Any], int]:
        """Grant sharing rights on the specified folder to one or several users.

        :param account_id: The ID of the account
        :type account_id: str
        :param folder_path: The ID of the folder
        :type folder_path: str
        :param share_data: List of users with their rights configuration
        :type share_data: list[dict[str, Any]]
        :return: A tuple of (API response dict, status code)
        :rtype: tuple[dict[str, Any], int]
        """
        try:
            users = [{"uid": self._resolve_to_user(entry), "rights": self._resolve_rights(entry)} for entry in share_data]
            entries: list[AclEntry] = self.mail_module.post_folder_share(account_id, folder_path, users)
        except RequestException as ex:
            logger_api.error("Request exception in post_folder_share: %s", str(ex))
            return create_api_base_response(None, ex.error)
        return create_api_base_response(self._serialize_share_entries(entries))

    def _resolve_to_user(self, entry: dict[str, Any]) -> str:
        """Resolve the ACL to_user for a share entry.

        A "anyone" user_class always collapses to the SOGo pseudo-user "<default>" (mapped to
        the IMAP "anyone" identifier by ModuleMail), regardless of whatever uid the caller may
        have supplied. Any other uid is looked up in the user sources right away so the
        serialization of the response reuses the result. Unlike calendar/contact sharing, a uid
        unknown to every user source is still accepted (IMAP ACLs may target accounts the user
        sources do not expose): it is granted as is and reported with user_class ANON.
        """
        if entry.get("user_class") == cs.USER_CLASS_ANY:
            return cs.ANYONE_TO_USER
        return self._resolve_share_target(entry["uid"]).uid

    def _resolve_share_target(self, to_user: str) -> User:
        """Look up an ACL to_user in the user sources, memoized for the whole request.

        The returned User carries its user_class: USER when a user source knows it, ANON otherwise.
        """
        target: User | None = self._share_targets.get(to_user)
        if target is None:
            target = User(uid=to_user)
            self._user_source_module.get_contact_info_for_user(self.user, target)
            # source_id is only set by the user source when the uid was found.
            target.user_class = cs.USER_CLASS_USER if target.source_id else cs.USER_CLASS_ANON
            self._share_targets[to_user] = target
        return target

    @staticmethod
    def _resolve_rights(entry: dict[str, Any]) -> dict[str, int]:
        """Build the full rights dict (one 0/1 flag per IMAP ACL right) for a share entry.

        When ``permissions`` is provided, any right not listed is not granted (0) - it fully
        determines the entry's rights. When only ``rights`` is provided, any right it omits is
        likewise not granted (0). When both are provided, they must agree on every right
        ``permissions`` covers (i.e. every right, since an omitted code means "not granted").

        :raises RequestException: ERROR_SHARE_PERMISSIONS_RIGHTS_MISMATCH if permissions and
            rights disagree on a right they both cover.
        """
        permissions: list[str] | None = entry.get("permissions")
        rights_in: dict[str, int] = entry.get("rights") or {}

        if permissions is not None:
            derived = {right: (1 if code in permissions else 0) for code, right in FOLDER_PERMISSION_CODE_TO_RIGHT.items()}
            for right_name, value in rights_in.items():
                if derived.get(right_name) != value:
                    raise RequestException(error=err.ERROR_SHARE_PERMISSIONS_RIGHTS_MISMATCH)
            return derived

        resolved: dict[str, int] = dict.fromkeys(FOLDER_PERMISSION_CODE_TO_RIGHT.values(), 0)
        resolved.update(rights_in)
        return resolved

    def _serialize_share_entries(self, entries: list[AclEntry]) -> list[dict[str, Any]]:
        """Resolve ACL entries into the API's FolderShareResponseSchema shape.

        A to_user not known by any user source is still returned (user_class ANON) so the
        caller can see the raw grant instead of silently losing it. The "<default>" pseudo
        to_user is the "anyone" share and is never resolved through the user source.
        """
        users: list[dict[str, Any]] = []
        for entry in entries:
            granted_rights = {right_to_camel(right): 1 for right, value in entry.rights.items() if value}
            if entry.to_user == cs.ANYONE_TO_USER:
                users.append({
                    "user_class": cs.USER_CLASS_ANY,
                    "cn": "Tout utilisateur identifié",
                    "uid": cs.USER_CLASS_ANY,
                    "rights": granted_rights,
                })
                continue
            target: User = self._resolve_share_target(entry.to_user)
            users.append({
                "user_class": target.user_class,
                "c_email": target.uid,
                "cn": target.cn,
                "uid": entry.to_user,
                "rights": granted_rights,
            })
        return users

    def empty_folder(self, account_id: str, folder_path: str) -> tuple[dict[str, Any], int]:
        """Completely empty a folder by permanently deleting all mails.

        Only allowed for TRASH and JUNK folders.

        :param account_id: The ID of the account
        :type account_id: str
        :param folder_path: The path of the folder to empty
        :type folder_path: str
        :return: A tuple of (API response dict with mails_deleted count, status code)
        :rtype: tuple[dict[str, Any], int]
        """
        try:
            result = self.mail_module.empty_folder(account_id, folder_path)
            return create_api_base_response(result)
        except RequestException as ex:
            logger_api.error("Request exception in empty_folder: %s", str(ex))
            return create_api_base_response(None, ex.error)
