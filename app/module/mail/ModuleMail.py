from __future__ import annotations
from typing import TYPE_CHECKING, Any, Iterator

from email.header import decode_header, make_header
from email.message import Message
from email.utils import parseaddr, getaddresses
from io import BytesIO
from re import search as reg_search
import zipfile

from app.config.settings.UserSettings import UserMailViewSettings, UserMailViewSettingsObj
from app.manager.mail.ClientMailServer import ClientMailServer
from app.utils import constants as cs
from app.utils import errors as err
from app.utils.exceptions import RequestException
from app.utils.maths.crypto_utils import decrypt_password
from app.utils.module.importManager import import_and_instantiate_manager
from app.utils.logger.logger import logger_mail_server
from app.utils.strings import get_imap_config_from_url


if TYPE_CHECKING:
    from app.auth.User import User
    from app.config.settings.DomainSettings import MailSettingsObj


REGISTRY_MANAGER : dict[str, str] = {
    "imap": "ClientImap",
    "jmap": "ClientJmap"
}

class ModuleMail:
    """
    Module to handle mail operations using different mail client implementations.
    """

    def __init__(self, user: User, mail_settings: MailSettingsObj):
        self.user = user
        self.mail_settings = mail_settings
        self.domain_mail_folder_name: dict = {}

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
            user_mail_conf["password"] = decrypt_password(ext_account_config["password"])
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
            else:
                raise ValueError("No numeric priority found") #TODO: handle this case

        # Check for read receipt
        should_ask_receipt = bool(email.get("Disposition-Notification-To") or email.get("Return-Receipt-To"))

        # Parse content, attachments, and encryption info
        contents = []
        attachments = []
        is_signed = False
        certificates: list[dict[str, Any]] = []
        valid = None
        mail_type = "normal"
        mail_type_data: dict[str, Any] = {}

        for part in email.walk():
            #The first part will be the full email, skip it
            if part.get_content_maintype() == "multipart":
                continue

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
                mail_type = "ics"
                try:
                    payload = part.get_payload(decode=True)
                    if payload and isinstance(payload, bytes):
                        charset = part.get_content_charset() or 'utf-8'
                        ics_content = payload.decode(charset, errors='replace')
                        mail_type_data = {"ics_content": ics_content}
                except (AttributeError, TypeError, UnicodeDecodeError) as e:
                    logger_mail_server.warning("Error parsing ICS content for UID %s: %s", uid, e)
                continue

            # Check for vCard
            if content_type in ("text/vcard", "text/x-vcard"):
                mail_type = "vcard"
                try:
                    payload = part.get_payload(decode=True)
                    if payload and isinstance(payload, bytes):
                        charset = part.get_content_charset() or 'utf-8'
                        vcard_content = payload.decode(charset, errors='replace')
                        mail_type_data = {"vcard_content": vcard_content}
                except (AttributeError, TypeError, UnicodeDecodeError) as e:
                    logger_mail_server.warning("Error parsing vCard content for UID %s: %s", uid, e)
                continue

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
            "has_attachment": len(attachments) > 0,
            "attachments": attachments,
            "is_signed": is_signed,
            "certificates": certificates,
            "valid": valid,
            "priority": priority,
            "should_ask_receipt": should_ask_receipt,
            "mail_type": mail_type,
            "mail_type_data": mail_type_data
        }

    def get_folder_mails(self, account_id: str, folder_name: str, first: int, last: int) -> tuple[list[dict[str, Any]], int]:
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
        mail_iter = client.fetch_all_mails(folder_name, number_of_mails=last - first + 1, offset=first)
        total_count = next(mail_iter)["nb_mails"]
        mails = []

        for raw_entry in mail_iter:
            mails.append(self._parse_mail(raw_entry))

        return mails, total_count

    def delete_mails(self, account_id:str, folder_path: str, mail_uids: str|list[str]) -> None:
        """Delete multiple mails by UIDs in a single client session.

        :param folder_name: The name of the folder containing the mails.
        :type folder_name: str
        :param mail_uids: A list of mail UIDs to delete.
        :type mail_uids: list[int]
        :raises RequestException: If deletion fails for any mail
        :return: A dict with list of deleted mail UIDs
        :rtype: dict[str, Any]
        """
        client = self._open_client_for(account_id)
        client.delete_mails_by_uid(folder_path, mail_uids)

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

    def list_mailboxes(self) -> list[dict[str, Any]]:
        """list all configured mailboxes.
        
        :return: A list of mailboxes
        :rtype: list[dict[str, Any]]
        """
        raise NotImplementedError("Message from ModuleMail.py: list_mailboxes is not implemented yet")

    def create_mailbox(self) -> dict[str, Any]:
        """Create a new mailbox (add external account).
        
        :return: Created mailbox data
        :rtype: dict[str, Any]
        """
        raise NotImplementedError("Message from ModuleMail.py: create_mailbox is not implemented yet")

    def update_mailbox(self) -> dict[str, Any]:
        """Update mailbox settings.
        
        :return: Updated mailbox data
        :rtype: dict[str, Any]
        """
        raise NotImplementedError("Message from ModuleMail.py: update_mailbox is not implemented yet")

    def delete_mailbox(self) -> None:
        """Delete a mailbox (only external accounts).
        
        :return: None
        :rtype: None
        """
        raise NotImplementedError("Message from ModuleMail.py: delete_mailbox is not implemented yet")

    def compose_email(self) -> dict[str, Any]:
        """Compose a new email from the specified mailbox.
        
        :return: Email composition data
        :rtype: dict[str, Any]
        """
        raise NotImplementedError("Message from ModuleMail.py: compose_email is not implemented yet")

    def get_mailbox_delegates(self) -> list[dict[str, Any]]:
        """Get delegates for this mailbox.
        
        :return: A list of delegates
        :rtype: list[dict[str, Any]]
        """
        raise NotImplementedError("Message from ModuleMail.py: get_mailbox_delegates is not implemented yet")

    def create_mailbox_delegate(self, data: dict) -> dict[str, Any]:
        """Create a new delegate for this mailbox.
        
        :param data: Delegate data
        :type data: dict
        :return: Created delegate data
        :rtype: dict[str, Any]
        """
        raise NotImplementedError("Message from ModuleMail.py: create_mailbox_delegate is not implemented yet")

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
        #TODO : action de l'admin pour activer une option qui enverra le mail à une adresse définie
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
