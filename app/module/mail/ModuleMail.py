import email
from email.header import decode_header, make_header
from email.utils import parseaddr, getaddresses
import time

from typing import Any, Dict, Tuple, List

from app.manager.mail.ClientImap import ClientImap
# from app.manager.mail.ClientJmap import ClientJmap
from app.utils.exceptions import RequestException
from app.utils.module.importManager import import_and_instantiate_manager
from app.utils.logger.logger import logger_api
from app.module.mail.utils import convert_rights_to_imap, convert_imap_to_rights


class ModuleMail:
    """
    Module to handle mail operations using different mail client implementations.
    """

    def __init__(
        self,
        server: str | None = None,
        port: int = 143,
        client_registry: Dict[str, Tuple[str, str]] | None = None,
    ):
        self.server = server
        self.port = port
        self.client_registry: Dict[str, Tuple[str, str]] = (
            client_registry if client_registry is not None else {"imap": ("app.manager.mail", "ClientImap")}
        )

    def _validate_user_conf(self, user_conf: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure user_conf contains minimal required fields."""
        if not isinstance(user_conf, dict):
            raise RequestException("Invalid user configuration: expected dict")
        missing = [k for k in ("username", "password") if not user_conf.get(k)]
        if missing:
            raise RequestException(f"Missing required fields: {', '.join(missing)}")
        return user_conf

    def _resolve_client_impl(self, type_name: str) -> tuple[str, str]:
        """Resolve the appropriate client implementation."""
        if not type_name:
            raise RequestException("Mail type is required in user configuration")

        key = type_name.lower()
        impl = self.client_registry.get(key)
        if not impl:
            available = ", ".join(self.client_registry.keys())
            raise RequestException(f"Unsupported mail type '{type_name}', available: {available}")
        return impl

    def _open_client_for(self, user_conf: Dict[str, Any]) -> ClientImap:  # Union[ClientImap, ClientJmap]:
        """Open and login a mail client based on user_conf."""
        conf = self._validate_user_conf(user_conf)

        type_name = str(conf.get("type", "imap")).lower()
        module_path, class_name = self._resolve_client_impl(type_name)

        client = import_and_instantiate_manager(
            module_path=module_path,
            module_and_class_name=class_name,
            module_args={
                "server": conf.get("server", self.server),
                "port": int(conf.get("port", self.port)),
            },
        )
        if not client:
            raise RequestException(f"Failed to create {class_name} instance for type '{type_name}'")

        # Pass auth_mech if present in user_conf (ex: "SOGO_D_IMAP_AUTH_MECH")
        auth_mech = conf.get("auth_mech") or conf.get("auth") or conf.get("SOGO_D_IMAP_AUTH_MECH")  # TODO: revoir ça
        # Manager will handle connection exceptions and raise RequestException
        client.login(conf["username"], conf["password"], auth_mech)

        return client

    def _safe_logout(self, client: Any) -> None:
        """Safely logout from client, suppressing errors."""
        if client:
            try:
                client.logout()
            except RequestException:
                # Manager already logged the error
                pass

    def get_folder_list(self, user_conf: Dict[str, Any]) -> List[Dict[str, str]]:
        """Retrieve a list of folders in the user's mailbox.

        :param user_conf: The user configuration for mailbox access.
        :type user_conf: Dict[str, Any]
        :return: A list of folders (each folder is a dict with at least 'name' key).
        :rtype: List[Dict[str, str]]
        :raises RequestException: If connection or manager operations fail
        """
        conf = self._validate_user_conf(user_conf)

        client = self._open_client_for(conf)  # may raise RequestException
        try:
            raw_mailboxes = client.list_mailboxes()  # may raise RequestException
        finally:
            self._safe_logout(client)

        folder_names: List[Dict[str, str]] = []
        for raw in raw_mailboxes:
            try:
                if isinstance(raw, bytes):
                    decoded = raw.decode()
                else:
                    # some backends may already return str
                    decoded = str(raw)
                # Typical LIST response ends with the mailbox name possibly quoted
                name = decoded.split()[-1].strip('"')
                folder_names.append({"name": name})
            except (UnicodeDecodeError, AttributeError, IndexError) as e:
                logger_api.warning("Error decoding folder name: %s", e)
                continue

        return folder_names

    def create_folder(self, user_conf: Dict[str, Any], folder_name: str) -> Dict[str, Any]:
        """Create a new folder in the user's mailbox.

        :param user_conf: The user configuration for mailbox access.
        :type user_conf: Dict[str, Any]
        :param folder_name: The name of the folder to create.
        :type folder_name: str
        :return: A dict with created folder info
        :rtype: Dict[str, Any]
        :raises RequestException: If validation or manager operations fail
        """
        if not folder_name or not isinstance(folder_name, str):
            raise RequestException("folder name is required and must be a string")

        conf = self._validate_user_conf(user_conf)

        client = self._open_client_for(conf)  # may raise RequestException
        try:
            client.create_folder(folder_name)
        finally:
            self._safe_logout(client)

        return {"name": folder_name}

    def delete_folder(self, user_conf: Dict[str, Any], folder_name: str) -> None:
        """Delete a mail folder.

        :param user_conf: The user configuration for mailbox access.
        :type user_conf: Dict[str, Any]
        :param folder_name: The name of the folder to delete.
        :type folder_name: str
        :raises RequestException: If folder deletion fails
        :return: None
        :rtype: None
        """
        client = self._open_client_for(user_conf)
        try:
            client.delete_folder(folder_name)
        finally:
            self._safe_logout(client)

    def get_folder_mails(
        self, user_conf: Dict[str, Any], folder_name: str, first: int, last: int
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Retrieve a list of mails in a specific folder.

        :param user_conf: The user configuration for mailbox access.
        :type user_conf: Dict[str, Any]
        :param folder_name: The name of the folder to fetch mails from.
        :type folder_name: str
        :param first: The starting index for pagination (inclusive).
        :type first: int
        :param last: The ending index for pagination (exclusive).
        :type last: int
        :raises RequestException: If fetching mails fails
        :return: A tuple of (list of mail dicts, total mail count)
        :rtype: Tuple[List[Dict[str, Any]], int]
        """
        client = self._open_client_for(user_conf)
        try:
            # get all UIDs (this method selects mailbox internally)
            uids = client.get_mail_uids_before_date(folder_name, before_date=None, exclude_deleted=False)
            total_count = len(uids)
            # slice UIDs for pagination
            slice_uids = uids[first:last]
            # fetch only the mails we need
            mails_raw = client.fetch_mails_by_uids(folder_name, slice_uids)
        finally:
            self._safe_logout(client)

        mails = []
        for raw_entry in mails_raw:
            try:
                uid = raw_entry.get("uid")
                if not uid:
                    logger_api.warning("Mail without UID in folder %s, skipping", folder_name)
                    continue

                raw_email_bytes = raw_entry.get("mail_bytes")
                flags = raw_entry.get("flags", [])
                if not raw_email_bytes:
                    continue

                msg = email.message_from_bytes(raw_email_bytes)
            except (ValueError, TypeError) as e:
                logger_api.warning("Error parsing mail entry with UID %s: %s", raw_entry.get("uid", "unknown"), e)
                continue

            try:
                subject = str(make_header(decode_header(msg.get("Subject", ""))))
            except (UnicodeDecodeError, AttributeError) as e:
                logger_api.warning("Error decoding subject for UID %s: %s", uid, e)
                subject = ""

            try:
                from_name, from_email = parseaddr(msg.get("From", ""))
                to_addrs = getaddresses([msg.get("To", "")])
                to_list = [{"name": name, "email": addr} for name, addr in to_addrs]
            except (AttributeError, TypeError) as e:
                logger_api.warning("Error parsing addresses for UID %s: %s", uid, e)
                from_name, from_email = "", ""
                to_list = []

            date = msg.get("Date", "")

            has_attachment = False
            for part in msg.walk():
                content_disposition = part.get("Content-Disposition", "")
                if part.get_content_maintype() == "multipart":
                    continue
                if "attachment" in content_disposition.lower():
                    has_attachment = True
                    break

            mails.append({
                "uid": uid,
                "subject": subject,
                "from_": {"name": from_name, "email": from_email},
                "to": to_list,
                "date": date,
                "seen": "\\Seen" in flags,
                "flagged": "\\Flagged" in flags,
                "deleted": "\\Deleted" in flags,
                "flags": flags,
                "hasAttachment": has_attachment,
            })

        return mails, total_count

    def delete_mails(self, user_conf: Dict[str, Any], folder_name: str, mail_uids: List[int]) -> Dict[str, Any]:
        """Delete multiple mails by UIDs in a single client session.

        :param user_conf: The user configuration for mailbox access.
        :type user_conf: Dict[str, Any]
        :param folder_name: The name of the folder containing the mails.
        :type folder_name: str
        :param mail_uids: A list of mail UIDs to delete.
        :type mail_uids: List[int]
        :raises RequestException: If deletion fails for any mail
        :return: A dict with list of deleted mail UIDs
        :rtype: Dict[str, Any]
        """
        client = self._open_client_for(user_conf)
        deleted: List[int] = []
        failed_details: Dict[int, str] = {}

        try:
            # select mailbox once
            client.select_mailbox(folder_name)

            for uid in mail_uids:
                try:
                    client.uid_copy(uid, "Trash")
                    client.uid_store_flags(uid, ['\\Seen', '\\Deleted'])
                    deleted.append(uid)
                except RequestException as e:
                    logger_api.error("Error deleting mail UID %s in %s: %s", uid, folder_name, e)
                    failed_details[uid] = str(e)
        finally:
            self._safe_logout(client)

        if failed_details:
            detail_parts = [f"{k}: {v}" for k, v in failed_details.items()]
            error_msg = f"{len(failed_details)} mail(s) failed to be deleted - details: " + " ; ".join(detail_parts)
            raise RequestException(error_msg, error_code=400)

        return {"deleted_ids": deleted}

    def delete_all_mail_in_folder(self, user_conf: Dict[str, Any], folder_name: str, before_date: str | None = None) -> None:
        """Delete all mails in a specific folder.

        Optimized:
        - Get UIDs
        - Select mailbox once and operate per-UID using primitives
        """
        client = self._open_client_for(user_conf)
        try:
            mail_uids = client.get_mail_uids_before_date(folder_name, before_date)
            logger_api.debug("Found %d mails to delete in '%s'", len(mail_uids), folder_name)

            if not mail_uids:
                return

            client.select_mailbox(folder_name)
            for mail_uid in mail_uids:
                client.uid_copy(mail_uid, "Trash")
                client.uid_store_flags(mail_uid, ["\\Deleted"])
        finally:
            self._safe_logout(client)


    def expunge_folder(self, user_conf: Dict[str, Any], folder_name: str) -> Dict[str, int]:
        """Permanently remove deleted mails from the mailbox.

        :param user_conf: The user configuration for mailbox access.
        :type user_conf: Dict[str, Any]
        :param folder_name: The name of the folder to expunge.
        :type folder_name: str
        :raises RequestException: If expunge operation fails
        :return: Dictionary containing the number of mails deleted
        :rtype: Dict[str, int]
        """
        client = self._open_client_for(user_conf)
        try:
            mail_deleted = client.expunge_folder(folder_name)
        finally:
            self._safe_logout(client)

        return {"mail_deleted": mail_deleted}

    def move_mails(self, user_conf: Dict[str, Any], from_folder: str, mail_uids: List[int], to_folder: str) -> Dict[str, Any]:
        """Move multiple mails from one folder to another.

        :param user_conf: The user configuration for mailbox access.
        :type user_conf: Dict[str, Any]
        :param from_folder: The name of the source folder.
        :type from_folder: str
        :param mail_uids: A list of mail UIDs to move.
        :type mail_uids: List[int]
        :param to_folder: The name of the destination folder.
        :type to_folder: str
        :raises RequestException: If moving mails fails
        :return: A dict with list of moved mail UIDs
        :rtype: Dict[str, Any]
        """
        client = self._open_client_for(user_conf)
        moved_uids: List[int] = []

        try:
            client.select_mailbox(from_folder)
            for mail_uid in mail_uids:
                client.uid_copy(mail_uid, to_folder)
                client.uid_store_flags(mail_uid, ['\\Deleted'])
                moved_uids.append(mail_uid)
        finally:
            self._safe_logout(client)

        return {"moved_ids": moved_uids}

    def get_mail_detail(self, user_conf: Dict[str, Any], folder_name: str, mail_uid: int) -> Dict[str, Any]:
        """Fetch the details of a specific mail.

        :param user_conf: The user configuration for mailbox access.
        :type user_conf: Dict[str, Any]
        :param folder_name: The name of the folder containing the mail.
        :type folder_name: str
        :param mail_uid: The UID of the mail to fetch (int).
        :type mail_uid: int
        :raises RequestException: If fetching mail detail fails
        :return: A dictionary containing the mail details
        :rtype: Dict[str, Any]
        """
        client = self._open_client_for(user_conf)
        try:
            mail_bytes = client.fetch_mail(folder_name, mail_uid)
        finally:
            self._safe_logout(client)

        msg = email.message_from_bytes(mail_bytes)

        try:
            subject = str(make_header(decode_header(msg.get("Subject", ""))))
        except (UnicodeDecodeError, AttributeError) as e:
            logger_api.warning("Error decoding subject for UID %s: %s", mail_uid, e)
            subject = ""

        try:
            from_ = email.utils.formataddr(parseaddr(msg.get("From", "")))
            to = [email.utils.formataddr(x) for x in getaddresses([msg.get("To", "")])]
            cc = [email.utils.formataddr(x) for x in getaddresses([msg.get("Cc", "")])]
            bcc = [email.utils.formataddr(x) for x in getaddresses([msg.get("Bcc", "")])]
        except (AttributeError, TypeError) as e:
            logger_api.warning("Error parsing addresses for UID %s: %s", mail_uid, e)
            from_, to, cc, bcc = "", [], [], []

        date = msg.get("Date", "")
        size = len(mail_bytes)

        attachments = []
        has_attachment = False
        body = ""

        for i, part in enumerate(msg.walk(), 1):
            content_disposition = part.get("Content-Disposition", "")
            if part.get_content_maintype() == "multipart":
                continue

            if "attachment" in content_disposition.lower():
                has_attachment = True
                filename = part.get_filename()
                content_type = part.get_content_type()

                try:
                    attach_bytes = part.get_payload(decode=True)
                    attach_size = len(attach_bytes) if isinstance(attach_bytes, bytes) else 0
                except (ValueError, TypeError) as e:
                    logger_api.warning("Error decoding attachment %s for UID %s: %s", filename, mail_uid, e)
                    attach_size = 0

                attachments.append({
                    "partId": str(i),
                    "name": filename,
                    "contentType": content_type,
                    "size": attach_size,
                    "downloadUri": f"/attachments/{i}?dl=True",
                    "displayUri": "???" 
                })
            elif part.get_content_type() in ["text/plain", "text/html"]:
                try:
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or "utf-8"
                    if isinstance(payload, bytes):
                        decoded = payload.decode(charset, errors="replace")
                        body += decoded
                    elif isinstance(payload, str):
                        body += payload
                except (UnicodeDecodeError, LookupError, AttributeError) as e:
                    logger_api.warning("Error decoding body part for UID %s: %s", mail_uid, e)

        date_tuple = email.utils.parsedate(date)
        timestamp = int(time.mktime(date_tuple)) if date_tuple is not None else None

        return {
            "attachments": {
                "parts": attachments,
                "zipUri": "???",
                "count": len(attachments)
            },
            "uid": mail_uid,
            "contentUri": "???",
            "seen": False,
            "answered": False,
            "recent": False,
            "deleted": False,
            "hasAttachment": has_attachment,
            "important": False,
            "date": timestamp,
            "subject": subject,
            "isMailingList": False,
            "from": from_,
            "to": to,
            "cc": cc,
            "bcc": bcc,
            "size": size,
            "body": body
        }

    # ============================================================================
    # NEW METHODS - TO BE IMPLEMENTED
    # ============================================================================

    def list_mailboxes(self, user_conf: Any) -> List[Dict[str, Any]]:
        """List all configured mailboxes.
        
        :param user_conf: The user configuration (can be single dict or list of dicts)
        :type user_conf: Any
        :return: A list of mailboxes
        :rtype: List[Dict[str, Any]]
        """
        raise NotImplementedError("Message from ModuleMail.py: list_mailboxes is not implemented yet")

    def create_mailbox(self, user_conf: Any) -> Dict[str, Any]:
        """Create a new mailbox (add external account).
        
        :param user_conf: The user configuration
        :type user_conf: Any
        :return: Created mailbox data
        :rtype: Dict[str, Any]
        """
        raise NotImplementedError("Message from ModuleMail.py: create_mailbox is not implemented yet")

    def update_mailbox(self, user_conf: Dict[str, Any]) -> Dict[str, Any]:
        """Update mailbox settings.
        
        :param user_conf: The user configuration for mailbox access
        :type user_conf: Dict[str, Any]
        :return: Updated mailbox data
        :rtype: Dict[str, Any]
        """
        raise NotImplementedError("Message from ModuleMail.py: update_mailbox is not implemented yet")

    def delete_mailbox(self, user_conf: Dict[str, Any]) -> None:
        """Delete a mailbox (only external accounts).
        
        :param user_conf: The user configuration for mailbox access.
        :type user_conf: Dict[str, Any]
        :return: None
        :rtype: None
        """
        raise NotImplementedError("Message from ModuleMail.py: delete_mailbox is not implemented yet")

    def compose_email(self, user_conf: Dict[str, Any]) -> Dict[str, Any]:
        """Compose a new email from the specified mailbox.
        
        :param user_conf: The user configuration for mailbox access
        :type user_conf: Dict[str, Any]
        :return: Email composition data
        :rtype: Dict[str, Any]
        """
        raise NotImplementedError("Message from ModuleMail.py: compose_email is not implemented yet")

    def get_mailbox_delegates(self, user_conf: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get delegates for this mailbox.
        
        :param user_conf: The user configuration for mailbox access
        :type user_conf: Dict[str, Any]
        :return: A list of delegates
        :rtype: List[Dict[str, Any]]
        """
        raise NotImplementedError("Message from ModuleMail.py: get_mailbox_delegates is not implemented yet")

    def create_mailbox_delegate(self, user_conf: Dict[str, Any], data: dict) -> Dict[str, Any]:
        """Create a new delegate for this mailbox.
        
        :param user_conf: The user configuration for mailbox access
        :type user_conf: Dict[str, Any]
        :param data: Delegate data
        :type data: dict
        :return: Created delegate data
        :rtype: Dict[str, Any]
        """
        raise NotImplementedError("Message from ModuleMail.py: create_mailbox_delegate is not implemented yet")

    def purge_mailbox(self, user_conf: Dict[str, Any]) -> None:
        """Purge (all folders) from the specified mailbox.
        
        :param user_conf: The user configuration for mailbox access.
        :type user_conf: Dict[str, Any]
        :return: None
        :rtype: None
        """
        raise NotImplementedError("Message from ModuleMail.py: purge_mailbox is not implemented yet")

    def update_folder(self, user_conf: Dict[str, Any], folder_name: str, folder_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update name, type (junk, template...) and subscription status of a specific mail folder.
        
        :param user_conf: The user configuration for mailbox access.
        :type user_conf: Dict[str, Any]
        :param folder_name: The current name of the folder
        :type folder_name: str
        :param folder_data: Dictionary containing update data (name, subscribed, type)
        :type folder_data: Dict[str, Any]
        :return: Updated folder data
        :rtype: Dict[str, Any]
        :raises RequestException: If validation or manager operations fail
        """
        if not folder_name or not isinstance(folder_name, str):
            raise RequestException("folder_name is required and must be a string")

        if not folder_data or not isinstance(folder_data, dict):
            raise RequestException("folder_data is required and must be a dict")

        conf = self._validate_user_conf(user_conf)
        client = self._open_client_for(conf)

        try:
            new_name = folder_data.get("name")
            subscribed = folder_data.get("subscribed")
            folder_type = folder_data.get("type")

            # Rename folder if new name is provided and different
            final_folder_name = folder_name
            if new_name and new_name != folder_name:
                client.rename_folder(folder_name, new_name)
                final_folder_name = new_name
                logger_api.info("Renamed folder from '%s' to '%s'", folder_name, new_name)

            # Update subscription status if provided
            if subscribed is not None:
                if subscribed in (1, "1", True):
                    client.subscribe_folder(final_folder_name)
                    logger_api.info("Subscribed to folder '%s'", final_folder_name)
                else:
                    client.unsubscribe_folder(final_folder_name)
                    logger_api.info("Unsubscribed from folder '%s'", final_folder_name)

            # Get updated folder details
            updated_details = client.get_folder_details(final_folder_name)

            # Update folder type if provided
            if folder_type:
                updated_details["type"] = folder_type

            return updated_details

        finally:
            self._safe_logout(client)

    def get_folder_details(self, user_conf: Dict[str, Any], folder_name: str) -> Dict[str, Any]:
        """Retrieve details of a specific mail folder.
        
        :param user_conf: The user configuration for mailbox access.
        :type user_conf: Dict[str, Any]
        :param folder_name: The name of the folder
        :type folder_name: str
        :return: Folder details
        :rtype: Dict[str, Any]
        :raises RequestException: If validation or manager operations fail
        """
        if not folder_name or not isinstance(folder_name, str):
            raise RequestException("folder_name is required and must be a string")

        conf = self._validate_user_conf(user_conf)

        client = self._open_client_for(conf)
        try:
            folder_details = client.get_folder_details(folder_name)
        finally:
            self._safe_logout(client)

        return folder_details

    def _collect_subfolders(self, root_folder: str, client: Any) -> List[str]:
        """
        Iteratively collect all subfolder paths under root_folder using client's get_folder_details.

        Returns a flat list of subfolder paths (not including the root_folder itself).
        """
        subfolders: List[str] = []
        stack: List[str] = [root_folder]

        while stack:
            current = stack.pop()
            details = client.get_folder_details(current) or {}

            children = details.get("children", []) or []
            for child in children:
                child_path = child.get("path")
                if not child_path:
                    continue
                # Keep discovered child
                subfolders.append(child_path)
                # Push to stack to discover its children later
                stack.append(child_path)

        return subfolders

    def purge_folder_mails(self, user_conf: Dict[str, Any], folder_name: str, purge_data: Dict[str, Any]) -> Dict[str, int]:
        """Purge all mails in the specified folder.

        Mark mails as deleted (optionally before a specific date).
        If permanentlyDelete is True, also expunge the folder to permanently remove deleted mails.
        If applyToSubfolders is True, apply the purge recursively to all subfolders.

        Returns a dict with the number of mails that were marked as deleted:
            { "mails_deleted": int }

        :param user_conf: The user configuration for mailbox access
        :type user_conf: Dict[str, Any]
        :param folder_name: The name of the folder
        :type folder_name: str
        :param purge_data: Dictionary containing purge options:
            - applyToSubfolders (bool): Apply to subfolders recursively
            - permanentlyDelete (bool): Expunge after marking as deleted
            - date (str): Delete mails before this date (YYYY-MM-DD format)
        :type purge_data: Dict[str, Any]
        :return: Dict with count of mails marked as deleted
        :rtype: Dict[str, int]
        :raises RequestException: If validation or manager operations fail
        """
        if not folder_name or not isinstance(folder_name, str):
            raise RequestException("folder_name is required and must be a string")

        if not purge_data or not isinstance(purge_data, dict):
            raise RequestException("purge_data is required and must be a dict")

        conf = self._validate_user_conf(user_conf)
        client = self._open_client_for(conf)

        total_deleted = 0

        try:
            apply_to_subfolders = bool(purge_data.get("applyToSubfolders", False))
            permanently_delete = bool(purge_data.get("permanentlyDelete", False))
            before_date = purge_data.get("date")

            # Build the list of folders to purge: the main folder plus optionally all subfolders
            folders_to_purge: List[str] = [folder_name]
            if apply_to_subfolders:
                logger_api.debug("Collecting subfolders for '%s'", folder_name)
                # Let exceptions from subfolder enumeration bubble up (module decision point)
                subfolders = self._collect_subfolders(folder_name, client)
                if subfolders:
                    folders_to_purge.extend(subfolders)

            logger_api.info("Purging %d folder(s): %s", len(folders_to_purge), folders_to_purge)

            # Purge each folder
            for folder in folders_to_purge:
                logger_api.debug("Purging folder '%s' with date filter: %s", folder, before_date)

                # Try to estimate number of mails that will be marked as deleted before calling purge.
                estimated_count = 0
                if hasattr(client, "get_mail_uids_before_date"):
                    uids = client.get_mail_uids_before_date(folder, before_date, exclude_deleted=True)
                    if isinstance(uids, (list, tuple, set)):
                        estimated_count = len(uids)

                # Perform the purge (mark as deleted)
                actual_marked = None
                try:
                    res = client.purge_folder(folder, before_date)
                    # If client.purge_folder returns an int, use it as actual count
                    if isinstance(res, int):
                        actual_marked = res
                except RequestException as e:
                    logger_api.warning("Failed to purge folder '%s': %s", folder, e)
                    # Skip expunge for this folder if purge fails
                    actual_marked = 0

                count_for_folder = actual_marked if actual_marked is not None else estimated_count
                total_deleted += int(count_for_folder or 0)

                # If permanently delete is requested, try to expunge (does not change our "marked as deleted" count)
                if permanently_delete:
                    logger_api.debug("Expunging folder '%s' to permanently delete mails", folder)
                    try:
                        client.expunge_folder(folder)
                    except RequestException as e:
                        logger_api.warning("Failed to expunge folder '%s': %s", folder, e)

            logger_api.info("Successfully purged %d folder(s), mails marked as deleted: %d", len(folders_to_purge), total_deleted)
            return {"mails_deleted": total_deleted}

        finally:
            self._safe_logout(client)

    def export_folder_mails(self, user_conf: Dict[str, Any], folder_name: str) -> Dict[str, Any]:
        """Export all mails in the specified folder.
        
        :param user_conf: The user configuration for mailbox access
        :type user_conf: Dict[str, Any]
        :param folder_name: The name of the folder
        :type folder_name: str
        :return: Export data
        :rtype: Dict[str, Any]
        """
        raise NotImplementedError("Message from ModuleMail.py: export_folder_mails is not implemented yet")

    def get_folder_share(self, user_conf: Dict[str, Any], folder_name: str) -> Dict[str, Any]:
        """Get share information for the specified folder.
        
        Retrieves the ACL (Access Control List) from the IMAP server and formats it
        into the expected API response format with user information and their rights.
        
        :param user_conf: The user configuration for mailbox access.
        :type user_conf: Dict[str, Any]
        :param folder_name: The name of the folder
        :type folder_name: str
        :return: Share information with users and their permissions
        :rtype: Dict[str, Any]
        :raises RequestException: If validation or manager operations fail
        """
        if not folder_name or not isinstance(folder_name, str):
            raise RequestException("folder_name is required and must be a string")

        conf = self._validate_user_conf(user_conf)
        client = self._open_client_for(conf)

        try:
            # Get ACL from IMAP server
            acl_list = client.get_acl(folder_name)

            # Transform ACL list into the expected format
            users: Dict[str, Dict[str, Any]] = {}

            for identifier, imap_rights in acl_list:
                # Convert IMAP rights to SOGo rights format
                sogo_rights = convert_imap_to_rights(imap_rights)

                # Determine user class based on identifier
                if identifier == "anyone":
                    user_class = "public-user"
                    cn = "Tout utilisateur identifié"
                    uid = "anyone"
                    user_info: Dict[str, Any] = {
                        "userClass": user_class,
                        "cn": cn,
                        "uid": uid,
                        "rights": sogo_rights
                    }
                else:
                    user_class = "normal-user"
                    # TODO: In a real implementation, user database lookup?
                    email_parts = identifier.split('@')
                    cn = email_parts[0] if email_parts else identifier
                    user_info = {
                        "userClass": user_class,
                        "c_email": identifier,
                        "cn": cn,
                        "uid": identifier,
                        "rights": sogo_rights
                    }
                users[identifier] = user_info
            return {"users": users}
        finally:
            self._safe_logout(client)

    def share_folder(self, user_conf: Dict[str, Any], folder_name: str, share_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Share the specified folder with another user.
        
        :param user_conf: The user configuration for mailbox access.
        :type user_conf: Dict[str, Any]
        :param folder_name: The name of the folder
        :type folder_name: str
        :param share_data: List of users with their rights configuration
        :type share_data: List[Dict[str, Any]]
        :return: Share result data
        :rtype: Dict[str, Any]
        :raises RequestException: If validation or manager operations fail
        """
        if not folder_name or not isinstance(folder_name, str):
            raise RequestException("folder_name is required and must be a string")

        if not share_data or not isinstance(share_data, list):
            raise RequestException("share_data is required and must be a list")

        conf = self._validate_user_conf(user_conf)
        client = self._open_client_for(conf)

        try:
            # Step 1: Get current ACL to know which users currently have permissions
            current_acl = client.get_acl(folder_name)
            current_users = {identifier for identifier, _ in current_acl}

            # Step 2: Build list of users from the incoming share_data
            new_users_dict: Dict[str, str] = {}  # identifier -> imap_rights

            for user_entry in share_data:
                if not isinstance(user_entry, dict):
                    logger_api.warning("Invalid user entry in share_data, skipping: %s", user_entry)
                    continue

                # Extract user identifier (uid or c_email)
                identifier = user_entry.get("uid") or user_entry.get("c_email")
                if not identifier:
                    logger_api.warning("User entry missing 'uid' or 'c_email', skipping: %s", user_entry)
                    continue

                # Extract rights configuration
                rights_dict = user_entry.get("rights", {})
                if not isinstance(rights_dict, dict):
                    logger_api.warning("Invalid rights for user '%s', skipping", identifier)
                    continue

                # Convert rights dict to IMAP ACL string
                imap_rights = convert_rights_to_imap(rights_dict)
                logger_api.debug("Converted rights for user '%s': %s -> %s", identifier, rights_dict, imap_rights)

                # Store in new_users_dict (even if empty rights, we'll handle it below)
                new_users_dict[identifier] = imap_rights

            logger_api.info("New users dict from share_data: %s", new_users_dict)

            # Step 3: Determine which users need to be removed (present in current but not in new)
            users_to_remove = current_users - set(new_users_dict.keys())
            logger_api.info("Users to be removed: %s", users_to_remove)

            # Get the current authenticated username to avoid removing owner's rights
            owner_username = conf.get("username", "")

            # Step 4: Remove ACL for users not in the new list (except owner)
            removed_users: List[str] = []
            for user_to_remove in users_to_remove:
                # Skip owner to avoid locking them out
                if user_to_remove == owner_username:
                    logger_api.info("Skipping removal of ACL for owner '%s' on folder '%s'", user_to_remove, folder_name)
                    continue

                try:
                    client.delete_acl(folder_name, user_to_remove)
                    removed_users.append(user_to_remove)
                    logger_api.info("Removed ACL for folder '%s', user '%s'", folder_name, user_to_remove)
                except RequestException as e:
                    logger_api.warning("Failed to remove ACL for user '%s': %s", user_to_remove, e)

            # Step 5: Set/update ACL for users in the new list
            updated_users: List[str] = []
            for identifier, imap_rights in new_users_dict.items():
                if imap_rights:
                    # Set ACL for this user
                    try:
                        client.set_acl(folder_name, identifier, imap_rights)
                        updated_users.append(identifier)
                        logger_api.info("Set ACL for folder '%s', user '%s', rights '%s'", folder_name, identifier, imap_rights)
                    except RequestException as e:
                        logger_api.error("Failed to set ACL for user '%s': %s", identifier, e)
                else:
                    # If no rights specified, delete the ACL entry
                    try:
                        client.delete_acl(folder_name, identifier)
                        removed_users.append(identifier)
                        logger_api.info("Deleted ACL for folder '%s', user '%s' (no rights specified)", folder_name, identifier)
                    except RequestException as e:
                        logger_api.warning("Failed to delete ACL for user '%s': %s", identifier, e)

            return {
                "updated_users": updated_users,
                "removed_users": removed_users,
                "folder": folder_name
            }

        finally:
            self._safe_logout(client)

    def delete_mail(self, user_conf: Dict[str, Any], folder_name: str, mail_uid: int) -> None:
        """Delete a specific mail (mark as deleted).
        
        :param user_conf: The user configuration for mailbox access.
        :type user_conf: Dict[str, Any]
        :param folder_name: The name of the folder
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail
        :type mail_uid: int
        :return: None
        :rtype: None
        """
        raise NotImplementedError("Message from ModuleMail.py: delete_mail is not implemented yet")

    def reply_mail(self, user_conf: Dict[str, Any], folder_name: str, mail_uid: int) -> Dict[str, Any]:
        """Reply to a specific mail.
        
        :param user_conf: The user configuration for mailbox access.
        :type user_conf: Dict[str, Any]
        :param folder_name: The name of the folder
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail
        :type mail_uid: int
        :return: Reply data
        :rtype: Dict[str, Any]
        """
        raise NotImplementedError("Message from ModuleMail.py: reply_mail is not implemented yet")

    def forward_mail(self, user_conf: Dict[str, Any], folder_name: str, mail_uid: int) -> Dict[str, Any]:
        """Forward a specific mail.
        
        :param user_conf: The user configuration for mailbox access.
        :type user_conf: Dict[str, Any]
        :param folder_name: The name of the folder
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail
        :type mail_uid: int
        :return: Forward data
        :rtype: Dict[str, Any]
        """
        raise NotImplementedError("Message from ModuleMail.py: forward_mail is not implemented yet")

    def get_mail_raw(self, user_conf: Dict[str, Any], folder_name: str, mail_uid: int) -> Dict[str, Any]:
        """Retrieve the raw content of a specific mail.
        
        :param user_conf: The user configuration for mailbox access.
        :type user_conf: Dict[str, Any]
        :param folder_name: The name of the folder
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail
        :type mail_uid: int
        :return: Raw mail content as a dict with 'raw' key containing the string
        :rtype: Dict[str, Any]
        :raises RequestException: If validation or manager operations fail
        """
        if not folder_name or not isinstance(folder_name, str):
            raise RequestException("folder_name is required and must be a string")

        if not isinstance(mail_uid, int) or mail_uid <= 0:
            raise RequestException("mail_uid must be a positive integer")

        conf = self._validate_user_conf(user_conf)
        client = self._open_client_for(conf)
        try:
            mail_bytes = client.fetch_mail(folder_name, mail_uid)
            try:
                raw_content = mail_bytes.decode('utf-8')
            except UnicodeDecodeError:
                raw_content = mail_bytes.decode('latin-1')
            return {"raw": raw_content}
        finally:
            self._safe_logout(client)

    def get_mailbox_identities(self, user_conf: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get identities for this mailbox.
        
        :param user_conf: The user configuration for mailbox access
        :type user_conf: Dict[str, Any]
        :return: A list of identities
        :rtype: List[Dict[str, Any]]
        """
        raise NotImplementedError("Message from ModuleMail.py: get_mailbox_identities is not implemented yet")

    def create_mailbox_identity(self, user_conf: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new identity for this mailbox.
        
        :param user_conf: The user configuration for mailbox access
        :type user_conf: Dict[str, Any]
        :return: Created identity data
        :rtype: Dict[str, Any]
        """
        raise NotImplementedError("Message from ModuleMail.py: create_mailbox_identity is not implemented yet")

    def get_identity(self, user_conf: Dict[str, Any], identity_id: int) -> Dict[str, Any]:
        """Retrieve a specific mail identity.
        
        :param user_conf: The user configuration for mailbox access.
        :type user_conf: Dict[str, Any]
        :param identity_id: The identity identifier
        :type identity_id: int
        :return: Identity data
        :rtype: Dict[str, Any]
        """
        raise NotImplementedError("Message from ModuleMail.py: get_identity is not implemented yet")

    def delete_identity(self, user_conf: Dict[str, Any], identity_id: int) -> None:
        """Delete a specific mail identity.
        
        :param user_conf: The user configuration for mailbox access.
        :type user_conf: Dict[str, Any]
        :param identity_id: The identity identifier
        :type identity_id: int
        :return: None
        :rtype: None
        """
        raise NotImplementedError("Message from ModuleMail.py: delete_identity is not implemented yet")

    def update_identity(self, user_conf: Dict[str, Any], identity_id: int) -> Dict[str, Any]:
        """Update a specific mail identity.
        
        :param user_conf: The user configuration for mailbox access.
        :type user_conf: Dict[str, Any]
        :param identity_id: The identity identifier
        :type identity_id: int
        :return: Updated identity data
        :rtype: Dict[str, Any]
        """
        raise NotImplementedError("Message from ModuleMail.py: update_identity is not implemented yet")
