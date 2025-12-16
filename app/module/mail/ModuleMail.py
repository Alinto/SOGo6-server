import email
from email.header import decode_header, make_header
from email.utils import parseaddr, getaddresses
import time
import re

from typing import Any, Dict, Tuple, List, TYPE_CHECKING

if TYPE_CHECKING:
    from app.manager.mail.ClientImap import ClientImap as ClientImapType

from app.manager.mail.ClientImap import ClientImap
# from app.manager.mail.ClientJmap import ClientJmap
from app.utils.exceptions import RequestException
from app.utils.module.importManager import import_and_instantiate_manager
from app.utils.logger.logger import logger_mail_server


class ModuleMail:
    """
    Module to handle mail operations using different mail client implementations.
    """

    def __init__(
        self,
        user_conf: Dict[str, Any],
        server: str | None = None,
        port: int = 143,
        client_registry: Dict[str, Tuple[str, str]] | None = None,
    ):
        # user_conf est maintenant requis — l'appelant doit le fournir
        if not user_conf:
            raise RequestException("user_conf is required to initialize ModuleMail")

        self.server = server
        self.port = port
        self.client_registry: Dict[str, Tuple[str, str]] = (
            client_registry if client_registry is not None else {"imap": ("app.manager.mail", "ClientImap")}
        )

        # validate/create client dès l'init — plus besoin de vérifier self.client dans chaque méthode
        self.conf = self._validate_user_conf(user_conf)
        self.client = self._open_client_for(self.conf)

    def _validate_user_conf(self, user_conf: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure user_conf contains minimal required fields."""
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
        if client is not None:
            try:
                client.logout()
            except RequestException:
                # Manager already logged the error
                pass

    def get_folder_list(self) -> List[Dict[str, Any]]:
        """Retrieve a list of folders in the user's mailbox with detailed information.

        :return: A list of folders with complete details including name, path, type, counts, and children.
        :rtype: List[Dict[str, Any]]
        :raises RequestException: If connection or manager operations fail
        """
        return self.client.list_mailboxes_detailed()

    def create_folder(self, folder_name: str) -> Dict[str, Any]:
        """Create a new folder in the user's mailbox.

        :param folder_name: The name of the folder to create.
        :type folder_name: str
        :return: A dict with created folder info
        :rtype: Dict[str, Any]
        :raises RequestException: If validation or manager operations fail
        """
        self.client.create_folder(folder_name)
        return self.get_folder_details(folder_name)

    def delete_folder(self, folder_name: str) -> Dict[str, Any]:
        """Delete a mail folder.

        If the folder is NOT within Trash, it will be moved to Trash (along with subfolders).
        If the folder IS within Trash, it will be permanently deleted (along with subfolders).

        :param folder_name: The name of the folder to delete.
        :type folder_name: str
        :return: A dict with deletion status
        :rtype: Dict[str, Any]
        :raises RequestException: If validation or manager operations fail
        """
        # Check if folder is within Trash
        is_in_trash = self.client.is_folder_in_trash(folder_name)

        if is_in_trash:
            # Folder is in Trash -> permanently delete it and its subfolders
            logger_mail_server.info("Permanently deleting folder '%s' and its subfolders (already in Trash)", folder_name)

            # Collect all subfolders recursively
            subfolders = self._collect_subfolders(folder_name, self.client)

            # Delete subfolders first (bottom-up to avoid issues)
            for subfolder in reversed(subfolders):
                logger_mail_server.debug("Permanently deleting subfolder '%s'", subfolder)
                self.client.delete_folder(subfolder)

            # Finally delete the main folder
            self.client.delete_folder(folder_name)

            return {"folder_deleted": folder_name, "permanently": True}
        else:
            # Folder is NOT in Trash -> move it to Trash (along with subfolders)
            logger_mail_server.info("Moving folder '%s' and its subfolders to Trash", folder_name)

            # Ensure Trash folder exists
            trash_folder = "Trash"
            try:
                self.client.select_mailbox(trash_folder)
            except RequestException:
                logger_mail_server.info("Trash folder doesn't exist, creating it")
                self.client.create_folder(trash_folder)

            # Collect all subfolders recursively
            subfolders = self._collect_subfolders(folder_name, self.client)

            # Generate new folder name in Trash (avoid conflicts)
            timestamp = int(time.time())
            base_name = folder_name.split('/')[-1]  # Get last part of path
            new_folder_name = f"{trash_folder}/{base_name}_{timestamp}"

            # Rename/move the main folder to Trash
            self.client.rename_folder(folder_name, new_folder_name)
            logger_mail_server.info("Moved folder '%s' to '%s'", folder_name, new_folder_name)

            # Note: rename_folder in IMAP automatically moves subfolders
            # so we don't need to handle them separately

            return {"folder_deleted": folder_name, "moved_to": new_folder_name, "permanently": False}

    def get_folder_mails(
        self, folder_name: str, first: int, last: int
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Retrieve a list of mails in a specific folder with full details.

        :param folder_name: The name of the folder to fetch mails from.
        :type folder_name: str
        :param first: The starting index for pagination (inclusive).
        :type first: int
        :param last: The ending index for pagination (exclusive).
        :type last: int
        :raises RequestException: If fetching mails fails
        :return: A tuple of (list of mail dicts with full details, total mail count)
        :rtype: Tuple[List[Dict[str, Any]], int]
        """
        self.client.select_mailbox(folder_name)
        mails_raw, total_count = self.client.fetch_all_mails(folder_name, number_of_mails=last - first + 1)
        mails = []

        for raw_entry in mails_raw:
            try:
                uid = raw_entry.get("uid")
                if not uid:
                    logger_mail_server.warning("Mail without UID in folder %s, skipping", folder_name)
                    continue

                raw_email_bytes = raw_entry.get("mail_bytes")
                flags_dict = raw_entry.get("flags", {})
                size = raw_entry.get("size", 0)

                if not raw_email_bytes:
                    continue

                msg = email.message_from_bytes(raw_email_bytes)
            except (ValueError, TypeError) as e:
                logger_mail_server.warning("Error parsing mail entry with UID %s: %s", raw_entry.get("uid", "unknown"), e)
                continue

            # Parse subject
            try:
                subject = str(make_header(decode_header(msg.get("Subject", ""))))
            except (UnicodeDecodeError, AttributeError) as e:
                logger_mail_server.warning("Error decoding subject for UID %s: %s", uid, e)
                subject = ""

            # Parse addresses
            try:
                from_addr = parseaddr(msg.get("From", ""))
                from_ = {"name": from_addr[0], "email": from_addr[1]}

                to = [{"name": addr[0], "email": addr[1]} for addr in getaddresses([msg.get("To", "")])]
                cc = [{"name": addr[0], "email": addr[1]} for addr in getaddresses([msg.get("Cc", "")])]
                reply_to = [{"name": addr[0], "email": addr[1]} for addr in getaddresses([msg.get("Reply-To", "")])]
                return_path = msg.get("Return-Path", "")
            except (AttributeError, TypeError) as e:
                logger_mail_server.warning("Error parsing addresses for UID %s: %s", uid, e)
                from_, to, cc, reply_to = {"name": "", "email": ""}, [], [], []

            # Parse date
            date = msg.get("Date", "")

            # Parse priority
            priority_header = msg.get("X-Priority", None) 
            priority = 3  # default value

            if priority_header:
                # Extract the first integer from header
                m = re.search(r'(\d+)', str(priority_header))
                if m:
                    try:
                        p = int(m.group(1))
                        priority = p if 1 <= p <= 5 else 3
                    except ValueError:
                        priority = 3
                else:
                    raise ValueError("No numeric priority found") #TODO: handle this case

            # Check for read receipt
            should_ask_receipt = bool(msg.get("Disposition-Notification-To") or msg.get("Return-Receipt-To"))

            # Parse content, attachments, and encryption info
            contents = []
            attachments = []
            is_signed = False
            certificates: List[Dict[str, Any]] = []
            valid = None
            mail_type = "normal"
            mail_type_data: Dict[str, Any] = {}

            for part in msg.walk():
                content_disposition = str(part.get("Content-Disposition", ""))
                content_type = part.get_content_type()

                if part.get_content_maintype() == "multipart":
                    continue

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
                                "downloadUri": f"/api/v1/mailboxes/0/folders/{folder_name}/mails/{uid}/attachments/{filename}",
                                "displayUri": f"/api/v1/mailboxes/0/folders/{folder_name}/mails/{uid}/attachments/{filename}/display",
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
            mails.append({
                "uid": str(uid),
                "size": size,
                "seen": flags_dict.get('seen', False),
                "flagged": flags_dict.get('flagged', False),
                "answered": flags_dict.get('answered', False),
                "forwarded": flags_dict.get('forwarded', False),
                "deleted": flags_dict.get('deleted', False),
                "flags": flags_dict.get('all', []),
                "to": to,
                "from_": from_,
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
            })

        return mails, total_count

    def delete_mails(self, folder_name: str, mail_uids: List[int]) -> Dict[str, Any]:
        """Delete multiple mails by UIDs in a single client session.

        :param folder_name: The name of the folder containing the mails.
        :type folder_name: str
        :param mail_uids: A list of mail UIDs to delete.
        :type mail_uids: List[int]
        :raises RequestException: If deletion fails for any mail
        :return: A dict with list of deleted mail UIDs
        :rtype: Dict[str, Any]
        """
        deleted: List[int] = []
        failed_details: Dict[int, str] = {}
        self.client.select_mailbox(folder_name)
        for uid in mail_uids:
            try:
                self.client.uid_copy(uid, "Trash")
                self.client.uid_store_flags(uid, ['\\Seen', '\\Deleted'])
                deleted.append(uid)
            except RequestException as e:
                logger_mail_server.error("Error deleting mail UID %s in %s: %s", uid, folder_name, e)
                failed_details[uid] = str(e)

        if failed_details:
            detail_parts = [f"{k}: {v}" for k, v in failed_details.items()]
            error_msg = f"{len(failed_details)} mail(s) failed to be deleted - details: " + " ; ".join(detail_parts)
            raise RequestException(error_msg, error_code=400)

        return {"deleted_ids": deleted}

    def delete_all_mail_in_folder(self, folder_name: str, before_date: str | None = None) -> None:
        """Delete all mails in a specific folder.

        :param folder_name: The name of the folder to delete mails from.
        :type folder_name: str
        :param before_date: Optional date string (YYYY-MM-DD) to delete mails before this date.
        :type before_date: str | None
        :raises RequestException: If deletion fails
        :return: None
        """
        self.client.select_mailbox(folder_name)
        mail_uids = self.client.get_mail_uids_before_date(folder_name, before_date)
        logger_mail_server.debug("Found %d mails to delete in '%s'", len(mail_uids), folder_name)

        if not mail_uids:
            return

        for mail_uid in mail_uids:
            self.client.uid_copy(mail_uid, "Trash")
            self.client.uid_store_flags(mail_uid, ["\\Deleted"])

    def expunge_folder(self, folder_name: str) -> Dict[str, int]:
        """Permanently remove deleted mails from the mailbox.

        :param folder_name: The name of the folder to expunge.
        :type folder_name: str
        :raises RequestException: If expunge operation fails
        :return: Dictionary containing the number of mails deleted
        :rtype: Dict[str, int]
        """
        self.client.select_mailbox(folder_name)
        mail_deleted = self.client.expunge_folder(folder_name)
        return {"mail_deleted": mail_deleted}

    def move_mails(self, from_folder: str, mail_uids: List[int], to_folder: str) -> Dict[str, Any]:
        """Move multiple mails from one folder to another.

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
        moved_uids: List[int] = []
        self.client.select_mailbox(from_folder)
        self.client.select_mailbox(to_folder)
        for mail_uid in mail_uids:
            self.client.uid_copy(mail_uid, to_folder)
            self.client.uid_store_flags(mail_uid, ['\\Deleted'])
            moved_uids.append(mail_uid)

        return {"moved_ids": moved_uids}

    def get_mail_detail(self, folder_name: str, mail_uid: int) -> Dict[str, Any]:
        """Fetch the details of a specific mail.

        :param folder_name: The name of the folder containing the mail.
        :type folder_name: str
        :param mail_uid: The UID of the mail to fetch (int).
        :type mail_uid: int
        :raises RequestException: If fetching mail detail fails
        :return: A dictionary containing the mail details (following MailDetailSchema)
        :rtype: Dict[str, Any]
        """
        self.client.select_mailbox(folder_name)

        # Fetch mail data using IMAP
        mail_data = self.client.fetch_mail_detail(folder_name, mail_uid)

        # Parse the email message
        msg = email.message_from_bytes(mail_data['raw_message'])

        # Parse subject
        try:
            subject = str(make_header(decode_header(msg.get("Subject", ""))))
        except (UnicodeDecodeError, AttributeError) as e:
            logger_mail_server.warning("Error decoding subject for UID %s: %s", mail_uid, e)
            subject = ""

        # Parse addresses
        try:
            from_addr = parseaddr(msg.get("From", ""))
            from_ = {"name": from_addr[0], "email": from_addr[1]}
            to = [{"name": addr[0], "email": addr[1]} for addr in getaddresses([msg.get("To", "")])]
            cc = [{"name": addr[0], "email": addr[1]} for addr in getaddresses([msg.get("Cc", "")])]
            reply_to = [{"name": addr[0], "email": addr[1]} for addr in getaddresses([msg.get("Reply-To", "")])]
            return_path = msg.get("Return-Path", "")
        except (AttributeError, TypeError) as e:
            logger_mail_server.warning("Error parsing addresses for UID %s: %s", mail_uid, e)
            from_, to, cc, reply_to = {"name": "", "email": ""}, [], [], []

        # Parse date
        date = msg.get("Date", "")

        # Parse priority
        priority_header = msg.get("X-Priority", None) 
        priority = 3  # default value

        if priority_header:
            # Extract the first integer from header
            m = re.search(r'(\d+)', str(priority_header))
            if m:
                try:
                    p = int(m.group(1))
                    priority = p if 1 <= p <= 5 else 3
                except ValueError:
                    priority = 3
            else:
                raise ValueError("No numeric priority found") #TODO: handle this case

        # Check for read receipt
        should_ask_receipt = bool(msg.get("Disposition-Notification-To") or msg.get("Return-Receipt-To"))

        # Parse content (HTML and plain text), attachments, and encryption info
        contents = []
        attachments = []
        is_signed = False
        certificates: List[Dict[str, Any]] = []
        valid = None
        mail_type = "normal"
        mail_type_data: Dict[str, Any] = {}

        for part in msg.walk():
            content_disposition = str(part.get("Content-Disposition", ""))
            content_type = part.get_content_type()

            if part.get_content_maintype() == "multipart":
                continue

            # Check for S/MIME or PGP signatures
            if content_type in ("application/pkcs7-signature", "application/x-pkcs7-signature", "application/pgp-signature"):
                is_signed = True
                # TODO: Extract and validate certificates/signatures if needed
                continue
            # Check for encrypted content
            if content_type in ("application/pkcs7-mime", "application/x-pkcs7-mime") and "smime-type=enveloped-data" in str(part):
                # TODO: 
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
                            "downloadUri": f"/api/v1/mailboxes/0/folders/{folder_name}/mails/{mail_uid}/attachments/{filename}", #TODO: Implement
                            "displayUri": f"/api/v1/mailboxes/0/folders/{folder_name}/mails/{mail_uid}/attachments/{filename}/display", #TODO: Implement
                            "extension": extension
                        })
                except (AttributeError, TypeError) as e:
                    logger_mail_server.warning("Error parsing attachment for UID %s: %s", mail_uid, e)
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
                    logger_mail_server.warning("Error parsing text content for UID %s: %s", mail_uid, e)
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
                    logger_mail_server.warning("Error parsing ICS content for UID %s: %s", mail_uid, e)
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
                    logger_mail_server.warning("Error parsing vCard content for UID %s: %s", mail_uid, e)
                continue

        return {
            "uid": str(mail_uid),
            "size": mail_data['size'],
            "seen": mail_data['flags'].get('seen', False),
            "flagged": mail_data['flags'].get('flagged', False),
            "answered": mail_data['flags'].get('answered', False),
            "forwarded": mail_data['flags'].get('forwarded', False),
            "deleted": mail_data['flags'].get('deleted', False),
            "flags": mail_data['flags'].get('all', []),
            "to": to,
            "from_": from_,
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

    def list_mailboxes(self) -> List[Dict[str, Any]]:
        """List all configured mailboxes.
        
        :return: A list of mailboxes
        :rtype: List[Dict[str, Any]]
        """
        raise NotImplementedError("Message from ModuleMail.py: list_mailboxes is not implemented yet")

    def create_mailbox(self) -> Dict[str, Any]:
        """Create a new mailbox (add external account).
        
        :return: Created mailbox data
        :rtype: Dict[str, Any]
        """
        raise NotImplementedError("Message from ModuleMail.py: create_mailbox is not implemented yet")

    def update_mailbox(self) -> Dict[str, Any]:
        """Update mailbox settings.
        
        :return: Updated mailbox data
        :rtype: Dict[str, Any]
        """
        raise NotImplementedError("Message from ModuleMail.py: update_mailbox is not implemented yet")

    def delete_mailbox(self) -> None:
        """Delete a mailbox (only external accounts).
        
        :return: None
        :rtype: None
        """
        raise NotImplementedError("Message from ModuleMail.py: delete_mailbox is not implemented yet")

    def compose_email(self) -> Dict[str, Any]:
        """Compose a new email from the specified mailbox.
        
        :return: Email composition data
        :rtype: Dict[str, Any]
        """
        raise NotImplementedError("Message from ModuleMail.py: compose_email is not implemented yet")

    def get_mailbox_delegates(self) -> List[Dict[str, Any]]:
        """Get delegates for this mailbox.
        
        :return: A list of delegates
        :rtype: List[Dict[str, Any]]
        """
        raise NotImplementedError("Message from ModuleMail.py: get_mailbox_delegates is not implemented yet")

    def create_mailbox_delegate(self, data: dict) -> Dict[str, Any]:
        """Create a new delegate for this mailbox.
        
        :param data: Delegate data
        :type data: dict
        :return: Created delegate data
        :rtype: Dict[str, Any]
        """
        raise NotImplementedError("Message from ModuleMail.py: create_mailbox_delegate is not implemented yet")

    def purge_mailbox(self) -> None:
        """Purge (all folders) from the specified mailbox.
        
        :return: None
        :rtype: None
        """
        raise NotImplementedError("Message from ModuleMail.py: purge_mailbox is not implemented yet")

    def update_folder(self, folder_name: str, folder_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update name, type (junk, template...) and subscription status of a specific mail folder.
        
        :param folder_name: The current name of the folder
        :type folder_name: str
        :param folder_data: Dictionary containing update data (name, subscribed, type)
        :type folder_data: Dict[str, Any]
        :return: Updated folder data
        :rtype: Dict[str, Any]
        :raises RequestException: If validation or manager operations fail
        """
        self.client.select_mailbox(folder_name)
        new_name = folder_data.get("name")
        subscribed = folder_data.get("subscribed")
        folder_type = folder_data.get("type")

        # Rename folder if new name is provided and different
        final_folder_name = folder_name
        if new_name and new_name != folder_name:
            self.client.rename_folder(folder_name, new_name)
            final_folder_name = new_name
            logger_mail_server.info("Renamed folder from '%s' to '%s'", folder_name, new_name)

        # Update subscription status if provided
        if subscribed is not None:
            if subscribed in (1, "1", True):
                self.client.subscribe_folder(final_folder_name)
                logger_mail_server.info("Subscribed to folder '%s'", final_folder_name)
            else:
                self.client.unsubscribe_folder(final_folder_name)
                logger_mail_server.info("Unsubscribed from folder '%s'", final_folder_name)

        # Get updated folder details
        updated_details = self.client.get_folder_details(final_folder_name)

        # Update folder type if provided
        if folder_type:
            updated_details["type"] = folder_type
            #TODO: Manager BDD update quand on l'aura

        return updated_details

    def get_folder_details(self, folder_name: str) -> Dict[str, Any]:
        """Retrieve details of a specific mail folder.
        
        :param folder_name: The name of the folder
        :type folder_name: str
        :return: Folder details
        :rtype: Dict[str, Any]
        :raises RequestException: If validation or manager operations fail
        """
        self.client.select_mailbox(folder_name)
        folder_details = self.client.get_folder_details(folder_name)
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

    def purge_folder_mails(self, folder_name: str, purge_data: Dict[str, Any]) -> Dict[str, int]:
        """Purge all mails in the specified folder.

        Mark mails as deleted (optionally before a specific date).
        If permanentlyDelete is True, also expunge the folder to permanently remove deleted mails.
        If applyToSubfolders is True, apply the purge recursively to all subfolders.

        Returns a dict with the number of mails that were marked as deleted:
            { "mails_deleted": int }

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
        self.client.select_mailbox(folder_name)
        total_deleted = 0

        apply_to_subfolders = bool(purge_data.get("applyToSubfolders", False))
        permanently_delete = bool(purge_data.get("permanentlyDelete", False))
        before_date = purge_data.get("date")

        # Build the list of folders to purge: the main folder plus optionally all subfolders
        folders_to_purge: List[str] = [folder_name]
        if apply_to_subfolders:
            logger_mail_server.debug("Collecting subfolders for '%s'", folder_name)
            # Let exceptions from subfolder enumeration bubble up (module decision point)
            subfolders = self._collect_subfolders(folder_name, self.client)
            if subfolders:
                folders_to_purge.extend(subfolders)

        logger_mail_server.info("Purging %d folder(s): %s", len(folders_to_purge), folders_to_purge)

        # Purge each folder
        for folder in folders_to_purge:
            logger_mail_server.debug("Purging folder '%s' with date filter: %s", folder, before_date)

            # Try to estimate number of mails that will be marked as deleted before calling purge.
            estimated_count = 0
            if hasattr(self.client, "get_mail_uids_before_date"):
                uids = self.client.get_mail_uids_before_date(folder, before_date, exclude_deleted=True)
                if isinstance(uids, (list, tuple, set)):
                    estimated_count = len(uids)

            # Perform the purge (mark as deleted)
            actual_marked = None
            try:
                res = self.client.purge_folder(folder, before_date)
                # If client.purge_folder returns an int, use it as actual count
                if isinstance(res, int):
                    actual_marked = res
            except RequestException as e:
                logger_mail_server.warning("Failed to purge folder '%s': %s", folder, e)
                # Skip expunge for this folder if purge fails
                actual_marked = 0

            count_for_folder = actual_marked if actual_marked is not None else estimated_count
            total_deleted += int(count_for_folder or 0)

            # If permanently delete is requested, try to expunge (does not change our "marked as deleted" count)
            if permanently_delete:
                logger_mail_server.debug("Expunging folder '%s' to permanently delete mails", folder)
                try:
                    self.client.expunge_folder(folder)
                except RequestException as e:
                    logger_mail_server.warning("Failed to expunge folder '%s': %s", folder, e)

        logger_mail_server.info("Successfully purged %d folder(s), mails marked as deleted: %d", len(folders_to_purge), total_deleted)
        return {"mails_deleted": total_deleted}

    def export_folder_mails(self, folder_name: str) -> Dict[str, Any]:
        """Export all mails in the specified folder.
        
        :param folder_name: The name of the folder
        :type folder_name: str
        :return: Export data
        :rtype: Dict[str, Any]
        """
        raise NotImplementedError("Message from ModuleMail.py: export_folder_mails is not implemented yet")

    def get_folder_share(self, folder_name: str) -> Dict[str, Any]:
        """Get share information for the specified folder.
        
        Retrieves the ACL (Access Control List) from the IMAP server and formats it
        into the expected API response format with user information and their rights.
        
        :param folder_name: The name of the folder
        :type folder_name: str
        :return: Share information with users and their permissions
        :rtype: Dict[str, Any]
        :raises RequestException: If validation or manager operations fail
        """
        self.client.select_mailbox(folder_name)
        # Get ACL from client (already converted to SOGo rights format)
        acl_list = self.client.get_acl(folder_name)

        # Transform ACL list into the expected format
        users: Dict[str, Dict[str, Any]] = {}

        for identifier, sogo_rights in acl_list:
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

    def share_folder(self, folder_name: str, share_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Share the specified folder with another user.
        
        :param folder_name: The name of the folder
        :type folder_name: str
        :param share_data: List of users with their rights configuration
        :type share_data: List[Dict[str, Any]]
        :return: Share result data
        :rtype: Dict[str, Any]
        :raises RequestException: If validation or manager operations fail
        """
        self.client.select_mailbox(folder_name)

        # Step 1: Get current ACL to know which users currently have permissions
        current_acl = self.client.get_acl(folder_name)
        current_users = {identifier for identifier, _ in current_acl}

        # Step 2: Build list of users from the incoming share_data
        new_users_dict: Dict[str, Dict[str, Any]] = {}  # identifier -> rights_dict

        for user_entry in share_data:
            if not isinstance(user_entry, dict):
                logger_mail_server.warning("Invalid user entry in share_data, skipping: %s", user_entry)
                continue

            # Extract user identifier (uid or c_email)
            identifier = user_entry.get("c_email") or user_entry.get("uid")
            if not identifier:
                logger_mail_server.warning("User entry missing 'c_email' or 'uid', skipping: %s", user_entry)
                continue

            # Extract rights configuration
            rights_dict = user_entry.get("rights", {})
            if not isinstance(rights_dict, dict):
                logger_mail_server.warning("Invalid rights for user '%s', skipping", identifier)
                continue

            # Store rights dict directly (client will handle conversion)
            new_users_dict[identifier] = rights_dict
            logger_mail_server.debug("Rights for user '%s': %s", identifier, rights_dict)

        logger_mail_server.info("New users dict from share_data: %s", new_users_dict)

        # Step 3: Determine which users need to be removed (present in current but not in new)
        users_to_remove = current_users - set(new_users_dict.keys())
        logger_mail_server.info("Users to be removed: %s", users_to_remove)

        # Get the current authenticated username to avoid removing owner's rights
        owner_username = self.conf.get("username", "") if self.conf else ""

        # Step 4: Remove ACL for users not in the new list (except owner)
        removed_users: List[str] = []
        for user_to_remove in users_to_remove:
            # Skip owner to avoid locking them out
            if user_to_remove == owner_username:
                logger_mail_server.info("Skipping removal of ACL for owner '%s' on folder '%s'", user_to_remove, folder_name)
                continue

            try:
                self.client.delete_acl(folder_name, user_to_remove)
                removed_users.append(user_to_remove)
                logger_mail_server.info("Removed ACL for folder '%s', user '%s'", folder_name, user_to_remove)
            except RequestException as e:
                logger_mail_server.warning("Failed to remove ACL for user '%s': %s", user_to_remove, e)

        # Step 5: Set/update ACL for users in the new list
        updated_users: List[str] = []
        for identifier, rights_dict in new_users_dict.items():
            # Check if any rights are set (at least one truthy value)
            has_rights = any(rights_dict.values()) if rights_dict else False

            if has_rights:
                # Set ACL for this user (client handles conversion)
                try:
                    self.client.set_acl(folder_name, identifier, rights_dict)
                    updated_users.append(identifier)
                    logger_mail_server.info("Set ACL for folder '%s', user '%s', rights %s", folder_name, identifier, rights_dict)
                except RequestException as e:
                    logger_mail_server.error("Failed to set ACL for user '%s': %s", identifier, e)
            else:
                # If no rights specified, delete the ACL entry
                try:
                    self.client.delete_acl(folder_name, identifier)
                    removed_users.append(identifier)
                    logger_mail_server.info("Deleted ACL for folder '%s', user '%s' (no rights specified)", folder_name, identifier)
                except RequestException as e:
                    logger_mail_server.warning("Failed to delete ACL for user '%s': %s", identifier, e)

        # Return the complete current state of folder shares
        return self.get_folder_share(folder_name)

    def delete_mail(self, folder_name: str, mail_uid: int) -> Dict[str, int]:
        """Delete a specific mail (mark as deleted).
        
        :param folder_name: The name of the folder
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail
        :type mail_uid: int
        :return: Dictionary with the deleted mail UID
        :rtype: Dict[str, int]
        :raises RequestException: If validation or manager operations fail
        """
        self.client.select_mailbox(folder_name)
        self.client.delete_mail_by_uid(folder_name, mail_uid)
        return {"uid_deleted": mail_uid}

    def reply_mail(self, folder_name: str, mail_uid: int) -> Dict[str, Any]:
        """Reply to a specific mail.
        
        :param folder_name: The name of the folder
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail
        :type mail_uid: int
        :return: Reply data
        :rtype: Dict[str, Any]
        """
        raise NotImplementedError("Message from ModuleMail.py: reply_mail is not implemented yet")

    def forward_mail(self, folder_name: str, mail_uid: int) -> Dict[str, Any]:
        """Forward a specific mail.
        
        :param folder_name: The name of the folder
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail
        :type mail_uid: int
        :return: Forward data
        :rtype: Dict[str, Any]
        """
        raise NotImplementedError("Message from ModuleMail.py: forward_mail is not implemented yet")

    def get_mail_raw(self, folder_name: str, mail_uid: int) -> Dict[str, Any]:
        """Retrieve the raw content of a specific mail.
        
        :param folder_name: The name of the folder
        :type folder_name: str
        :param mail_uid: The unique identifier of the mail
        :type mail_uid: int
        :return: Raw mail content as a dict with 'raw' key containing the string
        :rtype: Dict[str, Any]
        :raises RequestException: If validation or manager operations fail
        """
        self.client.select_mailbox(folder_name)

        mail_bytes = self.client.fetch_mail(folder_name, mail_uid)
        try:
            raw_content = mail_bytes.decode('utf-8')
        except UnicodeDecodeError:
            raw_content = mail_bytes.decode('latin-1')
        return {"raw": raw_content}

    def get_mailbox_identities(self) -> List[Dict[str, Any]]:
        """Get identities for this mailbox.
        
        :return: A list of identities
        :rtype: List[Dict[str, Any]]
        """
        raise NotImplementedError("Message from ModuleMail.py: get_mailbox_identities is not implemented yet")

    def create_mailbox_identity(self) -> Dict[str, Any]:
        """Create a new identity for this mailbox.
        
        :return: Created identity data
        :rtype: Dict[str, Any]
        """
        raise NotImplementedError("Message from ModuleMail.py: create_mailbox_identity is not implemented yet")

    def get_identity(self, identity_id: int) -> Dict[str, Any]:
        """Retrieve a specific mail identity.
        
        :param identity_id: The identity identifier
        :type identity_id: int
        :return: Identity data
        :rtype: Dict[str, Any]
        """
        raise NotImplementedError("Message from ModuleMail.py: get_identity is not implemented yet")

    def delete_identity(self, identity_id: int) -> None:
        """Delete a specific mail identity.
        
        :param identity_id: The identity identifier
        :type identity_id: int
        :return: None
        :rtype: None
        """
        raise NotImplementedError("Message from ModuleMail.py: delete_identity is not implemented yet")

    def update_identity(self, identity_id: int) -> Dict[str, Any]:
        """Update a specific mail identity.
        
        :param identity_id: The identity identifier
        :type identity_id: int
        :return: Updated identity data
        :rtype: Dict[str, Any]
        """
        raise NotImplementedError("Message from ModuleMail.py: update_identity is not implemented yet")
