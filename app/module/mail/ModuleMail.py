from __future__ import annotations
from typing import TYPE_CHECKING, Any, Iterator

from email.header import decode_header, make_header
from email.message import Message
from email.utils import parseaddr, getaddresses
from io import BytesIO
from re import search as reg_search
import zipfile
from email.message import EmailMessage

from app.config.settings.UserSettings import UserMailViewSettings, UserMailViewSettingsObj, UserMailGeneralSettings
from app.module.mail.model.TmpDraftManager import TmpDraftManager
from app.manager.mail.ClientMailServer import ClientMailServer
from app.utils import constants as cs
from app.utils import errors as err
from app.utils.exceptions import RequestException
from app.utils.maths.crypto_utils import decrypt_password
from app.utils.module.importManager import import_and_instantiate_manager
from app.utils.logger.logger import logger_mail_server
from app.utils.strings import get_imap_config_from_url
from app.utils.constants import DELETE_MAIL_BEHAVIOR_MAP

if TYPE_CHECKING:
    from app.auth.User import User
    from app.config.settings.DomainSettings import MailSettingsObj
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.manager.db.ClientSQL import ClientSQL
    from app.utils.api.paginate_sort_filter import CollectionPaginateArgs


REGISTRY_MANAGER : dict[str, str] = {
    "imap": "ClientImap",
    "jmap": "ClientJmap"
}

class ModuleMail:
    """
    Module to handle mail operations using different mail client implementations.
    """

    def __init__(self, user: User, mail_settings: MailSettingsObj, process_setting: ProcessSetting | None = None):
        self.user = user
        self.mail_settings = mail_settings
        self.domain_mail_folder_name: dict = {}
        self._process_setting: ProcessSetting | None = process_setting
        self._db: ClientSQL | None = None

    def _get_db(self) -> ClientSQL:
        """Return the DB client, lazily initialising it on first call.

        :raises BugException: If the module was instantiated without a process_setting.
        :raises RequestException: If the DB connection fails.
        """
        from app.utils.exceptions import BugException
        if self._process_setting is None:
            raise BugException("ModuleMail was instantiated without a process_setting but a DB operation was requested")
        if self._db is None:
            sogo_db_type = f"Client{self._process_setting.SOGO_P_DB_TYPE}"
            self._db = import_and_instantiate_manager(
                module_path="app.manager.db",
                module_and_class_name=sogo_db_type,
                module_args=self._process_setting.get_db_settings(),
            )
            self._db.connect()
        return self._db

    def _get_user_conf(self, account_id: str) -> dict:
        user_mail_conf: dict = {}
        if account_id == cs.DEFAULT_IDENTITY_KEY_VALUE:
            #Get info of the main account
            user_mail_conf["username"] = self.user.login_mail_server
            user_mail_conf["password"] = self.user.password
            user_mail_conf["type"] = self.mail_settings.SOGO_D_MAIL_SERVER_TYPE
            user_mail_conf["args"] = self.mail_settings.get_mail_server_settings_for_type(self.mail_settings.SOGO_D_MAIL_SERVER_TYPE)
            #Update folder name defined by user
            user_mail_view_settings = UserMailViewSettingsObj(self.user.profile.preferences.get(UserMailViewSettings.subparent, {}))
            user_mail_folder_name = user_mail_view_settings.get_user_mail_folder_map()
            domain_mail_folder_name: dict = user_mail_conf["args"]["folders_map"]
            domain_mail_folder_name.update(user_mail_folder_name)

            self.domain_mail_folder_name = domain_mail_folder_name

            #DEPRECATED but legacy
            if self.mail_settings.SOGO_D_MAIL_SERVER_TYPE == "imap" and self.user.imap_host:
                #extract host from user source
                new_config = get_imap_config_from_url(self.user.imap_host)
                user_mail_conf["args"].update(new_config)
        else:
            if not self.user.profile.external_accounts or account_id not in self.user.profile.external_accounts:
                raise RequestException(err.ERROR_EXTERNAL_ACCOUNT_NOT_FOUND.m, error=err.ERROR_EXTERNAL_ACCOUNT_NOT_FOUND)
            ext_account_config: dict = self.user.profile.external_accounts[account_id]["mail_server"]
            user_mail_conf["username"] = ext_account_config["username"]
            user_mail_conf["password"] = decrypt_password(ext_account_config["password"], account_id=account_id)
            user_mail_conf["type"] = ext_account_config["type"]
            user_mail_conf["args"] = {
                "server": ext_account_config["server"],
                "port": ext_account_config["port"],
                "encryption": ext_account_config["encryption"],
                "auth_mech": ext_account_config["auth_mech"]
            }
            #TODO How to handle folder type for external account ?? By name?
            user_mail_conf["args"]["folders_map"] = self.mail_settings.get_mail_server_settings_for_type("imap")["folders_map"]

        return user_mail_conf

    def _open_client_for(self, account_id: str, do_login: bool = True) -> ClientMailServer:
        """
        Open a mail client based on user_conf
        Connect it, and do login except if it is not asked.
        """
        conf = self._get_user_conf(account_id)

        client: ClientMailServer = import_and_instantiate_manager(
            module_path="app.manager.mail",
            module_and_class_name=REGISTRY_MANAGER[conf["type"]],
            module_args=conf["args"])
        client.connect()
        if do_login:
            client.login(conf["username"], conf["password"])
        return client


#########
#FOLDERS#
#########

    def get_folder_list(self, account_id:str) -> list[dict[str, Any]]:
        """Retrieve a list of folders in the user's mailbox with detailed information.

        :return: A list of folders with complete details including name, path, type, counts, and children.
        :rtype: list[dict[str, Any]]
        :raises RequestException: If connection or manager operations fail
        """
        client = self._open_client_for(account_id)

        return client.list_folders()

    def get_one_folder(self, account_id:str, folder_path: str) -> dict[str, Any]:
        """Retrieve details of a specific mail folder.
        
        :param folder_path: The name of the folder
        :type folder_path: str
        :return: Folder details
        :rtype: dict[str, Any]
        :raises RequestException: If validation or manager operations fail
        """
        client = self._open_client_for(account_id)
        folder_details = client.get_one_folder(folder_path)
        return folder_details

    def create_folder(self, account_id:str, folder_name: str, parent_path: str) -> dict[str, Any]:
        """Create a new folder in the user's mailbox.

        :param folder_path: The name of the folder to create.
        :type folder_path: str
        :return: A dict with created folder info
        :rtype: dict[str, Any]
        :raises RequestException: If validation or manager operations fail
        """
        client = self._open_client_for(account_id)
        new_folder_path = client.create_folder(folder_name, parent_path)
        return client.get_one_folder(new_folder_path)

    def delete_folder(self, account_id: str, folder_path: str, do_children:bool = True) -> None:
        """Delete a mail folder.

        If the folder is NOT within Trash, it will be moved to Trash (along with subfolders).
        If the folder IS within Trash, it will be permanently deleted (along with subfolders).

        :param folder_path: The name of the folder to delete.
        :type folder_path: str
        :return: A dict with deletion status
        :rtype: dict[str, Any]
        :raises RequestException: If validation or manager operations fail
        """
        client = self._open_client_for(account_id)
        client.delete_folder(folder_path, do_children)

    def expunge_folder(self, account_id:str, folder_path: str, do_subfolders: bool = True) -> dict[str, int]:
        """Permanently remove deleted mails from the mailbox.

        :param folder_path: The name of the folder to expunge.
        :type folder_path: str
        :raises RequestException: If expunge operation fails
        :return: dictionary containing the number of mails deleted
        :rtype: dict[str, int]
        """
        client = self._open_client_for(account_id)
        mail_deleted = client.expunge_folder(folder_path, do_subfolders)
        return {"mail_deleted": mail_deleted}


    def update_folder(self, folder_name: str, folder_data: dict[str, Any]) -> dict[str, Any]:
        """Update name, type (junk, template...) and subscription status of a specific mail folder.
        
        :param folder_name: The current name of the folder
        :type folder_name: str
        :param folder_data: dictionary containing update data (name, subscribed, type)
        :type folder_data: dict[str, Any]
        :return: Updated folder data
        :rtype: dict[str, Any]
        :raises RequestException: If validation or manager operations fail
        """
        raise NotImplementedError()
        # self.client.select_mailbox(folder_name)
        # new_name = folder_data.get("name")
        # subscribed = folder_data.get("subscribed")
        # folder_type = folder_data.get("type")

        # # Rename folder if new name is provided and different
        # final_folder_name = folder_name
        # if new_name and new_name != folder_name:
        #     self.client.rename_folder(folder_name, new_name)
        #     final_folder_name = new_name
        #     logger_mail_server.info("Renamed folder from '%s' to '%s'", folder_name, new_name)

        # # Update subscription status if provided
        # if subscribed is not None:
        #     if subscribed in (1, "1", True):
        #         self.client.subscribe_folder(final_folder_name)
        #         logger_mail_server.info("Subscribed to folder '%s'", final_folder_name)
        #     else:
        #         self.client.unsubscribe_folder(final_folder_name)
        #         logger_mail_server.info("Unsubscribed from folder '%s'", final_folder_name)

        # # Get updated folder details
        # updated_details = self.client.get_one_folder(final_folder_name)

        # # Update folder type if provided
        # if folder_type:
        #     updated_details["type"] = folder_type
        #     #TODO: Manager BDD update quand on l'aura

        # return updated_details


    def purge_folder_mails(self, account_id:str, folder_path: str, purge_data: dict[str, Any]) -> dict[str, int]:
        """Purge all mails in the specified folder.

        Mark mails as deleted (optionally before a specific date).
        If permanently_delete is True, also expunge the folder to permanently remove deleted mails.
        If do_subfolders is True, apply the purge recursively to all subfolders.

        Returns a dict with the number of mails that were marked as deleted:
            { "mails_deleted": int }

        :param folder_path: The name of the folder
        :type folder_path: str
        :param purge_data: dictionary containing purge options:
            - do_subfolders (bool): Apply to subfolders recursively
            - permanently_delete (bool): Expunge after marking as deleted
            - date (str): Delete mails before this date (YYYY-MM-DD format)
        :type purge_data: dict[str, Any]
        :return: dict with count of mails marked as deleted
        :rtype: dict[str, int]
        :raises RequestException: If validation or manager operations fail
        """
        client = self._open_client_for(account_id)

        apply_to_subfolders = purge_data["do_subfolders"]
        permanently_delete = purge_data["permanently_delete"]
        before_date = purge_data["date"]

        res = client.purge_folder(folder_path, before_date, apply_to_subfolders, permanently_delete)

        logger_mail_server.info("Successfully purged %d folder(s), mails marked as deleted: %d", folder_path, res)
        return {"mails_deleted": res}

    def purge_all_folders(self, account_id: str, purge_data: dict[str, Any]) -> dict[str, int]:
        """Purge all mails in all folders of the specified account.

        Opens a single client connection, lists all top-level folders,
        and purges each one (with its subfolders).

        :param account_id: The account identifier ("0" for main, hash for external)
        :type account_id: str
        :param purge_data: dictionary containing purge options:
            - permanently_delete (bool): Expunge after marking as deleted
            - date (str): Delete mails before this date (YYYY-MM-DD format)
        :type purge_data: dict[str, Any]
        :return: dict with total count of mails marked as deleted
        :rtype: dict[str, int]
        :raises RequestException: If connection or manager operations fail
        """
        client = self._open_client_for(account_id)

        permanently_delete = purge_data["permanently_delete"]
        before_date = purge_data["date"]

        folders = client.list_folders()
        total_deleted = 0

        for folder in folders:
            folder_path = folder["path"]
            total_deleted += client.purge_folder(folder_path, before_date, do_children=True, permanently=permanently_delete)

        logger_mail_server.info(
            "Successfully purged all folders for account '%s', total mails marked as deleted: %d",
            account_id, total_deleted
        )
        return {"mails_deleted": total_deleted}

    def get_folder_share(self, account_id: str, folder_path: str) -> Iterator[tuple[str, dict[str, int]]]:
        """
        Yield the acl for a folder.
        (identifier, {right1: 1, right2: 0, ...})

        :param account_id: _description_
        :type account_id: str
        :param folder_path: _description_
        :type folder_path: str
        :yield: _description_
        :rtype: Iterator[tuple[str, dict[str, int]]]
        """
        client = self._open_client_for(account_id)
        # Get ACL from client (already converted to SOGo rights format)
        yield from client.get_acl(folder_path)



    def share_folder(self, account_id:str, folder_path: str, share_data: list[dict[str, Any]]) -> Iterator[tuple[str, dict[str, int]]]:
        """Share the specified folder with another user.
        
        :param folder_name: The name of the folder
        :type folder_name: str
        :param share_data: list of users with their rights configuration
        :type share_data: list[dict[str, Any]]
        :return: Share result data
        :rtype: dict[str, Any]
        :raises RequestException: If validation or manager operations fail
        """
        client = self._open_client_for(account_id)

        # Step 1: Get current ACL to know which users currently have permissions
        current_acl = client.get_acl(folder_path)
        current_users = {identifier for identifier, _ in current_acl}

        # Step 2: Build list of users from the incoming share_data
        new_users_dict: dict[str, dict[str, Any]] = {}  # identifier -> rights_dict

        for user_entry in share_data:
            # Extract user identifier (uid or c_email)
            #TODO in fact, we need the user.login_mail_server
            identifier = user_entry["c_email"]
            rights_dict = user_entry.get("rights", {})

            # Store rights dict directly (client will handle conversion)
            new_users_dict[identifier] = rights_dict

        logger_mail_server.info("New users dict from share_data: %s", new_users_dict)

        # Step 3: Determine which users need to be removed (present in current but not in new)
        users_to_remove = current_users - set(new_users_dict.keys())
        logger_mail_server.info("Users to be removed: %s", users_to_remove)

        # Step 4: Remove ACL for users not in the new list (except owner)
        for user_to_remove in users_to_remove:
            # Skip owner to avoid locking them out
            if user_to_remove == self.user.login_mail_server:
                continue
            try:
                client.delete_acl(folder_path, user_to_remove)
                logger_mail_server.info("Removed ACL for folder '%s', user '%s'", folder_path, user_to_remove)
            except RequestException as e:
                logger_mail_server.warning("Failed to remove ACL for user '%s': %s", user_to_remove, e)

        # Step 5: Set/update ACL for users in the new list
        for identifier, rights_dict in new_users_dict.items():
            # Check if any rights are set (at least one truthy value)
            has_rights = any(rights_dict.values()) if rights_dict else False

            if has_rights:
                # Set ACL for this user (client handles conversion)
                try:
                    client.set_acl(folder_path, identifier, rights_dict)
                    logger_mail_server.info("Set ACL for folder '%s', user '%s', rights %s", folder_path, identifier, rights_dict)
                except RequestException as e:
                    logger_mail_server.error("Failed to set ACL for user '%s': %s", identifier, e)
            else:
                # If no rights specified, delete the ACL entry
                try:
                    client.delete_acl(folder_path, identifier)
                    logger_mail_server.info("Deleted ACL for folder '%s', user '%s' (no rights specified)", folder_path, identifier)
                except RequestException as e:
                    logger_mail_server.warning("Failed to delete ACL for user '%s': %s", identifier, e)
        
        yield from client.get_acl(folder_path)

#######
#MAILS#
#######

    def _parse_mail(self, mail_dict:dict) -> dict:
        """
        Parse a mail and return a dict with all the infos

        {
            "uid": str, uid of the mail
            "size": int, sizeof the mail in bytes
            "seen": bool, is the mail already seen
            "flagged": bool, is the mail flagged as important
            "answered": bool, has the mail been answered
            "forwarded": bool, has the mail been forwarded
            "deleted": bool, the mail is flagged as deleted (will be gone after expunge)
            "flags": list[str], all the flags of the mail
            "to": list[dict], [{
                "mail": str, email of the recipient
                "name": str, name of the recipient
                }, ...]
            "from_": dict, {
                "mail": str, email of the sender
                "name": str, name of the sender
                },
            "cc": list[dict],  [{
                "mail": str, email of the copy recipient
                "name": str, name of the rcopy ecipient
                }, ...],
            "reply_to": dict, {
                "mail": str, email of the reply-to
                "name": str, name of the reply-to
                },
            "return_path": str, return_path,
            "subject": str, subject,
            "date": str, date,
            "contents": list[dict], [{
                "content": str, actual content,
                "contentType": str, type of content,
                "shouldDisplayAttachment": bool, False if we can't display the attachment
                },....]
            "has_attachment": boool, True  if has attachment
            "attachments": list(dict], [{
                            "filename": str, name of the file,
                            "contentType": str, content type,
                            "size": int,  attachment_size,
                            "downloadUri": str, url to download the attachment
                            "displayUri": str, url to preview the attachment
                            "extension": str, extension of the file
                        },..]
            "is_signed": bool, true if signed,
            "certificates": certificates,
            "valid": valid,
            "priority": int, priority of the mail
            "should_ask_receipt": bool, should_ask_receipt,
            "mail_type": str, mailtype,
            "mail_type_data": dict, data related to the type
        }

        :param mail_dict: _description_
        :type mail_dict: dict
        :raises ValueError: _description_
        :return: _description_
        :rtype: dict
        """
        uid = mail_dict["uid"]
        email: Message = mail_dict["mail"]
        flags_dict: dict = mail_dict["flags"]
        size = mail_dict["size"]

        # Parse subject
        try:
            subject = str(make_header(decode_header(email.get("Subject", ""))))
        except (UnicodeDecodeError, AttributeError) as e:
            logger_mail_server.warning("Error decoding subject for UID %s: %s", uid, e)
            subject = ""

        # Parse addresses
        try:
            from_addr = parseaddr(email.get("From", ""))
            from_ = {"name": from_addr[0], "email": from_addr[1]}
            to = [{"name": addr[0], "email": addr[1]} for addr in getaddresses([email.get("To", "")])]
            cc = [{"name": addr[0], "email": addr[1]} for addr in getaddresses([email.get("Cc", "")])]
            reply_to = [{"name": addr[0], "email": addr[1]} for addr in getaddresses([email.get("Reply-To", "")])]
            return_path = email.get("Return-Path", "")
        except (AttributeError, TypeError) as e:
            logger_mail_server.warning("Error parsing addresses for UID %s: %s", uid, e)
            from_, to, cc, reply_to = {"name": "", "email": ""}, [], [], []

        # Parse date
        date = email.get("Date", "")

        # Parse priority
        priority_header = email.get("X-Priority", None)
        priority = 3  # default value

        if priority_header:
            # Extract the first integer from header
            m = reg_search(r'(\d+)', str(priority_header))
            if m:
                try:
                    p = int(m.group(1))
                    priority = p if 1 <= p <= 5 else 3
                except ValueError:
                    priority = 3

        # Check for read receipt
        should_ask_receipt = bool(email.get("Disposition-Notification-To") or email.get("Return-Receipt-To"))

        # Parse content, attachments, and encryption info
        contents = []
        attachments = []
        is_signed = False
        certificates: list[dict[str, Any]] = []
        mail_type = []
        mail_type_data: list[dict[str, Any]] = []
        has_walked = False

        for part in email.walk():
            #The first part will be the full email, skip it
            if part.get_content_maintype() == "multipart":
                continue
            has_walked = True

            content_disposition = str(part.get("Content-Disposition", ""))
            content_type = part.get_content_type()

            # Check for S/MIME or PGP signatures
            if content_type in ("application/pkcs7-signature", "application/x-pkcs7-signature", "application/pgp-signature"):
                is_signed = True
                continue

            # Check for encrypted content
            if content_type in ("application/pkcs7-mime", "application/x-pkcs7-mime") and "smime-type=enveloped-data" in str(part):
                continue

            # Check for attachments
            if "attachment" in content_disposition.lower() or part.get_filename():
                try:
                    filename = part.get_filename()
                    if filename:
                        # Decode filename if encoded
                        try:
                            filename = str(make_header(decode_header(filename)))
                        except (UnicodeDecodeError, AttributeError):
                            pass

                        attachment_size = len(part.get_payload(decode=True) or b"")
                        extension = filename.rsplit('.', 1)[-1] if '.' in filename else ""

                        attachments.append({
                            "filename": filename,
                            "contentType": content_type,
                            "size": attachment_size,
                            "downloadUri": f"/api/v1/mailboxes/0/folders/INBOX/mails/{uid}/attachments/{filename}",
                            "displayUri": f"/api/v1/mailboxes/0/folders/INOX/mails/{uid}/attachments/{filename}/display",
                            "extension": extension
                        })
                except (AttributeError, TypeError) as e:
                    logger_mail_server.warning("Error parsing attachment for UID %s: %s", uid, e)
                continue

            # Parse text content
            if content_type == "text/plain" or content_type == "text/html":
                try:
                    payload = part.get_payload(decode=True)
                    if payload and isinstance(payload, bytes):
                        charset = part.get_content_charset() or 'utf-8'
                        try:
                            content_text = payload.decode(charset, errors='replace')
                        except (UnicodeDecodeError, LookupError):
                            content_text = payload.decode('utf-8', errors='replace')

                        contents.append({
                            "content": content_text,
                            "contentType": content_type,
                            "shouldDisplayAttachment": False
                        })
                except (AttributeError, TypeError) as e:
                    logger_mail_server.warning("Error parsing text content for UID %s: %s", uid, e)
                continue

            # Check for calendar events (ICS)
            if content_type in ("text/calendar", "application/ics"):
                mail_type.append("event")
                try:
                    payload = part.get_payload(decode=True)
                    if payload and isinstance(payload, bytes):
                        charset = part.get_content_charset() or 'utf-8'
                        ics_content = payload.decode(charset, errors='replace')
                        mail_type_data.append({"ics_content": ics_content})
                except (AttributeError, TypeError, UnicodeDecodeError) as e:
                    logger_mail_server.warning("Error parsing ICS content for UID %s: %s", uid, e)
                continue

            # Check for vCard
            if content_type in ("text/vcard", "text/x-vcard"):
                mail_type.append("contact")
                try:
                    payload = part.get_payload(decode=True)
                    if payload and isinstance(payload, bytes):
                        charset = part.get_content_charset() or 'utf-8'
                        vcard_content = payload.decode(charset, errors='replace')
                        mail_type_data.append({"vcard_content": vcard_content})
                except (AttributeError, TypeError, UnicodeDecodeError) as e:
                    logger_mail_server.warning("Error parsing vCard content for UID %s: %s", uid, e)
                continue

        # Check if mail has extra info
        has_attachment = len(attachments) > 0
        if not has_walked:
            has_attachment = mail_dict["has_attachment"] if mail_dict.get("has_attachment", None) is not None else has_attachment
            is_signed = mail_dict["is_signed"] if mail_dict.get("is_signed", None) is not None else is_signed
            if mail_dict.get("has_event", False):
                mail_type.append("event")
            if mail_dict.get("has_contact", False):
                mail_type.append("contact")

        
        # Build mail entry with full details
        return {
            "uid": str(uid),
            "size": size,
            "seen": flags_dict.get('seen', False),
            "flagged": flags_dict.get('flagged', False),
            "answered": flags_dict.get('answered', False),
            "forwarded": flags_dict.get('forwarded', False),
            "deleted": flags_dict.get('deleted', False),
            "flags": flags_dict.get('all', []),
            "to": to,
            "from": from_,
            "cc": cc,
            "reply_to": reply_to,
            "return_path": return_path,
            "subject": subject,
            "date": date,
            "contents": contents,
            "has_attachment": has_attachment,
            "attachments": attachments,
            "is_signed": is_signed,
            "certificates": certificates,
            "priority": priority,
            "should_ask_receipt": should_ask_receipt,
            "mail_type": mail_type,
            "mail_type_data": mail_type_data
        }

    def get_folder_mails(self, account_id: str, folder_name: str, collection_param: CollectionPaginateArgs) -> tuple[list[dict[str, Any]], int]:
        """Retrieve a list of mails in a specific folder with full details.

        :param folder_name: The name of the folder to fetch mails from.
        :type folder_name: str
        :param first: The starting index for pagination (inclusive).
        :type first: int
        :param last: The ending index for pagination (exclusive).
        :type last: int
        :raises RequestException: If fetching mails fails
        :return: A tuple of (list of mail dicts with full details, total mail count)
        :rtype: tuple[list[dict[str, Any]], int]
        """
        client = self._open_client_for(account_id)
        offset = collection_param.first_item + 1 #First mail is index 1 not zero
        nb_mails = collection_param.last_item - collection_param.first_item + 1
        logger_mail_server.info("Try to fetch %s mails with offset %s", nb_mails, offset)
        mail_iter: Iterator|None = None
        without_content = False
        if collection_param.fields:
            requested = collection_param.fields.split(",")
            if collection_param.fields_action == "include" and "contents" not in requested:
                without_content = True
                mail_iter = client.fetch_all_mails_without_content(folder_name, number_of_mails=nb_mails, offset=offset)
            if collection_param.fields_action == "exclude" and "contents" in requested:
                without_content = True
                mail_iter = client.fetch_all_mails_without_content(folder_name, number_of_mails=nb_mails, offset=offset)
        if mail_iter is None:
            mail_iter = client.fetch_all_mails_with_content(folder_name, number_of_mails=nb_mails, offset=offset)
        total_count = next(mail_iter)["nb_mails"]
        mails = []

        for raw_entry in mail_iter:
            parsed_mail = self._parse_mail(raw_entry)
            if without_content:
                parsed_mail.pop("contents", None)
                parsed_mail.pop("attachments", None)
                parsed_mail.pop("certificates", None)
                parsed_mail.pop("mail_type_data", None)
            mails.append(parsed_mail)

        return mails, total_count

    def delete_mails(self, account_id:str, folder_path: str, mail_uids: str|list[str]) -> None:
        """Delete multiple mails by UIDs in a single client session.

        The deletion behaviour is driven by the user preference
        ``SOGO_U_MAIL_DELETE_BEHAVIOR`` stored in the user's mail general settings:

        * ``MOVE_TO_TRASH_AND_EXPUNGE`` (default): copy to Trash + flag Deleted + expunge.
        * ``FLAG_DELETED_ONLY``: flag Deleted only (mail appears struck-through/greyed in UI).
        * ``EXPUNGE_ONLY``: flag Deleted + expunge, no copy to Trash.
        * ``MOVE_TO_TRASH_ONLY``: copy to Trash + flag Deleted, no expunge.

        :param account_id: The account identifier.
        :type account_id: str
        :param folder_path: The name of the folder containing the mails.
        :type folder_path: str
        :param mail_uids: A mail UID or a list of mail UIDs to delete.
        :type mail_uids: str or list[str]
        :raises RequestException: If deletion fails for any mail
        """
        # Get raw dict from user preferences (may be empty or missing keys)
        raw_mail_general_prefs: dict = self.user.profile.preferences.get(UserMailGeneralSettings.subparent, {})
        # Load through schema to apply default values for missing keys
        mail_general_prefs: dict = UserMailGeneralSettings().load(raw_mail_general_prefs)

        delete_behavior: str = mail_general_prefs["SOGO_U_MAIL_DELETE_BEHAVIOR"]
        move_to_trash, permanently = DELETE_MAIL_BEHAVIOR_MAP.get(delete_behavior, (True, True))

        client = self._open_client_for(account_id)
        client.delete_mails_by_uid(folder_path, mail_uids, move_to_trash=move_to_trash, permanently=permanently)

    def delete_draft_mail(self, account_id: str, draft_uid: str) -> None:
        """Permanently delete a draft mail without moving it to Trash.

        :param account_id: The account identifier.
        :type account_id: str
        :param draft_uid: The UID of the draft mail to delete.
        :type draft_uid: str
        :raises RequestException: If deletion fails
        """
        client = self._open_client_for(account_id)
        client.delete_mail_permanently_from_folder_type(cs.MAIL_FOLDER_DRAFT, draft_uid)

    def move_mails(self, from_folder: str, mail_uids: list[int], to_folder: str) -> dict[str, Any]:
        """Move multiple mails from one folder to another.

        :param from_folder: The name of the source folder.
        :type from_folder: str
        :param mail_uids: A list of mail UIDs to move.
        :type mail_uids: list[int]
        :param to_folder: The name of the destination folder.
        :type to_folder: str
        :raises RequestException: If moving mails fails
        :return: A dict with list of moved mail UIDs
        :rtype: dict[str, Any]
        """
        raise NotImplementedError()
        # moved_uids: list[int] = []
        # self.client.select_mailbox(from_folder)
        # self.client.select_mailbox(to_folder)
        # for mail_uid in mail_uids:
        #     self.client.uid_copy(mail_uid, to_folder)
        #     self.client.uid_store_flags(mail_uid, ['\\Deleted'])
        #     moved_uids.append(mail_uid)

        # return {"moved_ids": moved_uids}

    def get_mail_detail(self, account_id: str, folder_name: str, mail_uid: str) -> dict[str, Any]:
        """Fetch the details of a specific mail.

        :param folder_name: The name of the folder containing the mail.
        :type folder_name: str
        :param mail_uid: The UID of the mail to fetch (int).total_count
        :type mail_uid: str
        :raises RequestException: If fetching mail detail fails
        :return: A dictionary containing the mail details (following MailDetailSchema)
        :rtype: dict[str, Any]
        """
        client = self._open_client_for(account_id)

        # Fetch mail data using IMAP
        mail_data = client.fetch_mail(folder_name, mail_uid)

        return self._parse_mail(mail_data)

    def get_mailbox_quota(self, account_id: str) -> dict[str, Any] | None:
        """Get the quota information for a mailbox.

        Opens a mail client for the given account, retrieves the quota using
        GETQUOTAROOT on INBOX, and returns the quota data.
        Returns None if the server does not support quota for this configuration.

        :param account_id: The account identifier (cs.DEFAULT_IDENTITY_KEY_VALUE for main account)
        :type account_id: str
        :return: Dictionary containing quota info, or None if unavailable:
            {
                "storage_used": int,        # storage used in KB
                "storage_limit": int,       # storage limit in KB (0 if unlimited)
                "soft_quota_value": int,    # soft quota value from domain settings (SOGO_D_SOFT_EMAIL_QUOTA)
            }
        :rtype: dict[str, Any] | None
        """
        client = self._open_client_for(account_id)
        quota = client.get_quota()
        if quota is not None:
            quota["soft_quota_value"] = self.mail_settings.SOGO_D_SOFT_EMAIL_QUOTA
        return quota

    def compose_email(self) -> dict[str, Any]:
        """Compose a new email from the specified mailbox.
        
        :return: Email composition data
        :rtype: dict[str, Any]
        """
        raise NotImplementedError("Message from ModuleMail.py: compose_email is not implemented yet")


    def export_folder_mails(self, folder_name: str) -> dict[str, Any]:
        """Export all mails in the specified folder.
        
        :param folder_name: The name of the folder
        :type folder_name: str
        :return: Export data
        :rtype: dict[str, Any]
        """
        raise NotImplementedError("Message from ModuleMail.py: export_folder_mails is not implemented yet")


    def reply_mail(self, account_id: str, folder_name: str, mail_uid: str) -> dict[str, Any]:
        """Reply to a specific mail.
        
        :param folder_name: The name of the folder
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail
        :type mail_uid: str
        :return: Reply data
        :rtype: dict[str, Any]
        """
        raise NotImplementedError("Message from ModuleMail.py: reply_mail is not implemented yet")

    def forward_mail(self, account_id: str, folder_name: str, mail_uid: str) -> dict[str, Any]:
        """Forward a specific mail.
        
        :param folder_name: The name of the folder
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail
        :type mail_uid: str
        :return: Forward data
        :rtype: dict[str, Any]
        """
        raise NotImplementedError("Message from ModuleMail.py: forward_mail is not implemented yet")

    def get_mail_raw(self, account_id: str, folder_name: str, mail_uid: str) -> dict[str, Any]:
        """Retrieve the raw content of a specific mail.
        
        :param folder_name: The name of the folder
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail
        :type mail_uid: str
        :return: Raw mail content as a dict with 'raw' key containing the string
        :rtype: dict[str, Any]
        :raises RequestException: If validation or manager operations fail
        """
        client = self._open_client_for(account_id)

        raw_content = client.fetch_mail_raw(folder_name, mail_uid)
        return {"raw": raw_content}


    def save_draft(self, account_id: str, mail_data: dict, key: str | None = None) -> dict[str, Any]:
        """Save a mail as a draft in the account's Drafts folder, managing the tmp_draft table.

        If *key* is provided, the corresponding tmp_draft row is looked up, the owner is verified,
        the lock state is checked (409 if locked), and the existing IMAP draft is replaced.
        If *key* is absent, a new tmp_draft entry is created (after checking the per-user limit).

        The tmp_draft row is locked around the IMAP operation and unlocked afterwards.

        :param account_id: The account identifier
        :type account_id: str
        :param mail_data: Dict with draft fields (from_addr, to, subject, body, cc, bcc, return_receipt)
        :type mail_data: dict
        :param key: Optional tmp_draft key; if None a new tmp_draft is created
        :type key: str | None
        :return: Dict with the tmp_draft key and the saved draft data
        :rtype: dict[str, Any]
        :raises RequestException: If any validation or operation fails
        """
        tmpdraftmngr = TmpDraftManager(self._get_db(), self.user.uid)

        with tmpdraftmngr.locked(key, wait_if_locked=False) as (resolved_key, mail_server_uid):
            # --- Build and save the IMAP draft ---
            message = EmailMessage()
            if from_addr := mail_data.get("from_addr"):
                message["From"] = from_addr
            if to_list := mail_data.get("to"):
                message["To"] = ", ".join(to_list)
            if subject := mail_data.get("subject"):
                message["Subject"] = subject
            if cc := mail_data.get("cc"):
                message["Cc"] = ", ".join(cc)
            if bcc := mail_data.get("bcc"):
                message["Bcc"] = ", ".join(bcc)
            if return_receipt := mail_data.get("return_receipt"):
                message["Disposition-Notification-To"] = return_receipt
            message.set_content(mail_data.get("body") or "")

            client = self._open_client_for(account_id)
            raw_draft = client.save_draft(message, mail_server_uid)
            new_mail_server_uid: str = raw_draft.get("uid", "")

            tmpdraftmngr.release(resolved_key, new_mail_server_uid)

        parsed = self._parse_mail(raw_draft)
        parsed["key"] = resolved_key
        return parsed

    def upload_attachment(self, account_id: str, filename: str, content_type: str, file_data: bytes, key: str | None = None) -> dict[str, Any]:
        """Add an attachment to the "mail in progress" draft, managing the tmp_draft table.

        If *key* is provided, the corresponding tmp_draft row is looked up, the owner is verified,
        the lock state is checked with a short polling wait (up to 2s every 100ms) before giving up (409).
        If *key* is absent, a new tmp_draft entry is created (after checking the per-user limit).

        The existing IMAP draft is fetched, the attachment is added to it, and the draft is replaced.

        :param account_id: The account identifier
        :type account_id: str
        :param filename: The attachment filename
        :type filename: str
        :param content_type: The MIME content type of the attachment (e.g. "application/pdf")
        :type content_type: str
        :param file_data: Raw bytes of the attachment
        :type file_data: bytes
        :param key: Optional tmp_draft key; if None a new tmp_draft is created
        :type key: str | None
        :return: Dict with the tmp_draft key
        :rtype: dict[str, Any]
        :raises RequestException: If any validation or operation fails
        """
        import email as email_existing

        tmpdraftmngr = TmpDraftManager(self._get_db(), self.user.uid)

        with tmpdraftmngr.locked(key, wait_if_locked=True) as (resolved_key, mail_server_uid):
            try:
                client = self._open_client_for(account_id)

                # --- Fetch existing draft or start with an empty message ---
                if mail_server_uid is not None:
                    folder_path = client.folders_map_type_to_name[cs.MAIL_FOLDER_DRAFT]
                    raw_eml = client.fetch_mail_raw(folder_path, mail_server_uid)
                    existing = email_existing.message_from_string(raw_eml)
                    new_message = EmailMessage()
                    for header, value in existing.items():
                        new_message[header] = value
                    if existing.is_multipart():
                        for part in existing.walk():
                            if part.get_content_maintype() == "multipart":
                                continue
                            payload = part.get_payload(decode=True)
                            if payload is None:
                                continue
                            ctype = part.get_content_type()
                            disposition = part.get_content_disposition()
                            part_filename = part.get_filename()
                            if disposition == "attachment" and part_filename:
                                mt, st = ctype.split("/", 1)
                                new_message.add_attachment(payload, maintype=mt, subtype=st, filename=part_filename)
                            else:
                                charset = part.get_content_charset() or "utf-8"
                                try:
                                    new_message.set_content(payload.decode(charset))
                                except (UnicodeDecodeError, LookupError):
                                    new_message.set_content(payload.decode("utf-8", errors="replace"))
                    else:
                        payload = existing.get_payload(decode=True)
                        charset = existing.get_content_charset() or "utf-8"
                        if payload:
                            try:
                                new_message.set_content(payload.decode(charset))
                            except (UnicodeDecodeError, LookupError):
                                new_message.set_content(payload.decode("utf-8", errors="replace"))
                else:
                    new_message = EmailMessage()

                # --- Add the new attachment ---
                maintype, subtype = content_type.split("/", 1) if "/" in content_type else ("application", "octet-stream")
                new_message.add_attachment(file_data, maintype=maintype, subtype=subtype, filename=filename)

                raw_draft = client.save_draft(new_message, mail_server_uid)
                new_mail_server_uid: str = raw_draft.get("uid", "")
            except Exception as ex:
                if not isinstance(ex, RequestException):
                    raise RequestException(err.ERROR_TMP_DRAFT_ATTACHMENT_FAILED.m, error=err.ERROR_TMP_DRAFT_ATTACHMENT_FAILED) from ex
                raise

            tmpdraftmngr.release(resolved_key, new_mail_server_uid)

        return {"key": resolved_key}

    def validate_tmp_draft_key(self, key: str) -> None:
        """Validate that a tmp_draft key exists and belongs to the current user, and is not locked.

        :param key: The tmp_draft key to validate.
        :type key: str
        :raises RequestException: 404 if key not found, 401 if owner mismatch, 409 if locked.
        """
        tmpdraftmngr = TmpDraftManager(self._get_db(), self.user.uid)
        _key, row_owner, _uid, row_locked = tmpdraftmngr.fetch_row(key)
        tmpdraftmngr.check_owner(row_owner)
        if row_locked:
            raise RequestException(err.ERROR_TMP_DRAFT_LOCKED.m, error=err.ERROR_TMP_DRAFT_LOCKED)

    def delete_tmp_draft(self, key: str, account_id: str | None = None) -> None:
        """Delete a tmp_draft row by key, and remove the associated IMAP draft if present.

        If *account_id* is provided and the tmp_draft row contains a mail_server_uid,
        the corresponding draft is deleted from the IMAP Drafts folder before the DB row
        is removed.

        :param key: The tmp_draft key to delete.
        :type key: str
        :param account_id: Optional account identifier used to open the IMAP client and
            delete the draft from the Drafts folder.
        :type account_id: str | None
        :raises RequestException: If deletion fails.
        """
        tmpdraftmngr = TmpDraftManager(self._get_db(), self.user.uid)

        if account_id is not None:
            try:
                _key, _owner, mail_server_uid, _locked = tmpdraftmngr.fetch_row(key)
                if mail_server_uid:
                    client = self._open_client_for(account_id)
                    client.delete_mail_permanently_from_folder_type(cs.MAIL_FOLDER_DRAFT, mail_server_uid)
            except RequestException:
                logger_mail_server.warning("Failed to delete IMAP draft for uid %s", mail_server_uid)

        tmpdraftmngr.delete(key)

    def save_mail_to_folder(self, account_id: str, message: EmailMessage, folder_type: str) -> None:
        """Append an already-built email message to a folder identified by its type.

        :param account_id: The account identifier
        :type account_id: str
        :param message: The email message to save.
        :type message: EmailMessage
        :param folder_type: The folder type constant to save into (e.g. cs.MAIL_FOLDER_SENT).
        :type folder_type: str
        :raises RequestException: If the operation fails.
        """
        client = self._open_client_for(account_id)
        client.save_mail_to_folder(message, folder_type)

    def perform_mail_action(self, account_id:str, folder_name: str, mail_uid: str, action_data: dict) -> dict[str, Any]:
        """Perform an action on a specific mail.
        
        :param folder_name: The name of the folder
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail
        :type mail_uid: str
        :param action_data: dictionary containing 'action' and optional 'data' fields
        :type action_data: dict[str, Any]
        :return: Result of the action
        :rtype: dict[str, Any]
        :raises RequestException: If validation or manager operations fail
        """
        action: str = action_data["action"]
        # null if not provided
        data = action_data.get("data")

        client = self._open_client_for(account_id)

        if action == "tag":
            return self._action_tag(client, folder_name, mail_uid, data)
        elif action == "untag":
            return self._action_untag(client, folder_name, mail_uid, data)
        elif action == "move":
            return self._action_move(client, folder_name, mail_uid, data)
        elif action == "spam":
            return self._action_spam(client, folder_name, mail_uid)
        elif action == "ham":
            return self._action_ham(client, folder_name, mail_uid)
        elif action == "copy":
            return self._action_copy(client, folder_name, mail_uid, data)
        else:
            raise RequestException(f"Invalid action: {action}", err.ERROR_INVALID_ACTION)

    def download_mail(self, account_id: str, folder_name: str, mail_uid: str, download_format: str) -> BytesIO:
        """Download a specific mail as .eml or .zip.

        :param account_id: The account identifier
        :type account_id: str
        :param folder_name: The name of the folder containing the mail
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail
        :type mail_uid: str
        :param download_format: The download format ('eml' or 'zip')
        :type download_format: str
        :return: A BytesIO buffer containing the mail file
        :rtype: BytesIO
        :raises RequestException: If fetching the mail fails
        """
        client = self._open_client_for(account_id)

        if download_format == "zip":
            return self._action_zip(client, folder_name, mail_uid)
        else:
            return self._action_download(client, folder_name, mail_uid)

    def _action_tag(self, client: ClientMailServer, folder_name: str, mail_uid: str, tags: Any) -> dict[str, Any]:
        """Add custom flags/tags to a mail.
        
        :param folder_name: The name of the folder
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail
        :type mail_uid: str
        :param tags: List of tags to add or a single tag string
        :type tags: Any
        :return: Result with added tags
        :rtype: dict[str, Any]
        :raises RequestException: If tags data is missing or invalid
        """
        if not tags:
            raise RequestException("Missing tags data for tag action", err.ERROR_MISSING_ACTION_DATA)

        # Normalize tags to list
        if isinstance(tags, str):
            tag_list = [tags]
        elif isinstance(tags, list):
            tag_list = tags
        else:
            raise RequestException("Tags must be a string or list of strings", err.ERROR_MISSING_ACTION_DATA)

        client.add_flags_to_mail(folder_name, mail_uid, tag_list)

        return {"action": "tag", "mail_uid": mail_uid, "tags_added": tag_list}

    def _action_untag(self, client: ClientMailServer, folder_name: str, mail_uid: str, tags: Any) -> dict[str, Any]:
        """Remove custom flags/tags from a mail.
        
        :param folder_name: The name of the folder
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail
        :type mail_uid: str
        :param tags: List of tags to remove or a single tag string
        :type tags: Any
        :return: Result with removed tags
        :rtype: dict[str, Any]
        :raises RequestException: If tags data is missing or invalid
        """
        if not tags:
            raise RequestException("Missing tags data for untag action", err.ERROR_MISSING_ACTION_DATA)

        # Normalize tags to list
        if isinstance(tags, str):
            tag_list = [tags]
        elif isinstance(tags, list):
            tag_list = tags
        else:
            raise RequestException("Tags must be a string or list of strings", err.ERROR_MISSING_ACTION_DATA)

        client.remove_flags_to_mail(folder_name, mail_uid, tag_list)

        return {"action": "untag", "mail_uid": mail_uid, "tags_removed": tag_list}

    def _action_move(self, client: ClientMailServer, folder_name: str, mail_uid: str, destination: Any) -> dict[str, Any]:
        """Move a mail to another folder.
        
        :param folder_name: The name of the source folder
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail
        :type mail_uid: str
        :param destination: The destination folder name
        :type destination: Any
        :return: Result with moved mail info
        :rtype: s[str, Any]
        :raises RequestException: If destination is missing or invalid
        """
        if not destination or not isinstance(destination, str):
            raise RequestException("Missing or invalid destination folder for move action", err.ERROR_MISSING_ACTION_DATA)

        client.copy_mail_to_mailbox(folder_name, mail_uid, destination)
        client.add_flags_to_mail(folder_name, mail_uid, ['\\Deleted'])

        return {"action": "move", "mail_uid": mail_uid, "from_folder": folder_name, "to_folder": destination}

    def _action_spam(self, client: ClientMailServer, folder_name: str, mail_uid: str) -> dict[str, Any]:
        """Mark a mail as spam and move it to Junk folder.
        
        :param folder_name: The name of the folder
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail
        :type mail_uid: str
        :return: Result with spam action info
        :rtype: dict[str, Any]
        :raises RequestException: If operation fails
        """
        #TODO mechanism to store the origin folder in the tag so when set as ham
        junk_folder = self.domain_mail_folder_name.get(cs.MAIL_FOLDER_JUNK, "Junk")
        client.copy_mail_to_mailbox(folder_name, mail_uid, junk_folder, create_dest=True)
        client.add_flags_to_mail(folder_name, mail_uid, ['\\Deleted'])
        return {"action": "spam", "mail_uid": mail_uid, "moved_to": junk_folder}

    def _action_ham(self, client: ClientMailServer, folder_name: str, mail_uid: str) -> dict[str, Any]:
        """Mark a mail as ham (not spam) and move it to INBOX.
        
        :param folder_name: The name of the folder
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail
        :type mail_uid: str
        :return: Result with ham action info
        :rtype: dict[str, Any]
        :raises RequestException: If operation fails
        """
        inbox_folder = self.domain_mail_folder_name.get(cs.MAIL_FOLDER_INBOX, "INBOX")
        junk_folder = self.domain_mail_folder_name.get(cs.MAIL_FOLDER_JUNK, "Junk")
        client.copy_mail_to_mailbox(junk_folder, mail_uid, inbox_folder)
        client.add_flags_to_mail(folder_name, mail_uid, ['\\Deleted'])

        return {"action": "ham", "mail_uid": mail_uid, "moved_to": inbox_folder}

    def _action_copy(self, client: ClientMailServer, folder_name: str, mail_uid: str, destination: Any) -> dict[str, Any]:
        """Copy a mail to another folder.
        
        :param folder_name: The name of the source folder
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail
        :type mail_uid: str
        :param destination: The destination folder name
        :type destination: Any
        :return: Result with copied mail info
        :rtype: dict[str, Any]
        :raises RequestException: If destination is missing or invalid
        """
        if not destination or not isinstance(destination, str):
            raise RequestException("Missing or invalid destination folder for copy action", err.ERROR_MISSING_ACTION_DATA)

        client.copy_mail_to_mailbox(folder_name, mail_uid, destination)

        return {"action": "copy", "mail_uid": mail_uid, "from_folder": folder_name, "to_folder": destination}

    def _action_download(self, client: ClientMailServer, folder_name: str, mail_uid: str) -> BytesIO:
        """Download a mail as raw .eml bytes.

        :param folder_name: The name of the folder containing the mail.
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail.
        :type mail_uid: str
        :return: A tuple of (raw .eml bytes, suggested filename).
        :rtype: Tuple[bytes, str]
        :raises RequestException: If fetching the mail fails.
        """
        mail_str = client.fetch_mail_raw(folder_name, mail_uid)
        return BytesIO(mail_str.encode())

    def _action_zip(self, client: ClientMailServer, folder_name: str, mail_uid: str) -> BytesIO:
        """Download a mail as a .zip archive containing the .eml file.

        :param folder_name: The name of the folder containing the mail.
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail.
        :type mail_uid: str
        :return: A Flask send_file response with the zip archive.
        :rtype: Any
        :raises RequestException: If fetching or zipping the mail fails.
        """
        mail_str = client.fetch_mail_raw(folder_name, mail_uid)

        eml_filename = f"mail_{mail_uid}.eml"
        try:
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr(eml_filename, mail_str)
            zip_buffer.seek(0)
        except (OSError, zipfile.BadZipFile) as e:
            raise RequestException(f"Failed to create zip archive for mail UID {mail_uid}: {e}", err.ERROR_MAIL_ZIP_FAILED) from e

        return zip_buffer