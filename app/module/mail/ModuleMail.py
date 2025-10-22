import email
from email.header import decode_header, make_header
from email.utils import parseaddr, getaddresses
import time
import imaplib
import socket
import ssl

from typing import Any, Dict, Tuple, List
from marshmallow import ValidationError

from app.manager.mail.ClientImap import ClientImap
#from app.manager.mail.ClientJmap import ClientJmap
from app.utils.exceptions import RequestException
from app.utils.module.importManager import import_and_instantiate_manager
from app.utils.logger.logger import logger_api


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

    def _open_client_for(self, user_conf: Dict[str, Any]) ->  ClientImap: #Union[ClientImap, ClientJmap]:
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
        auth_mech = conf.get("auth_mech") or conf.get("auth") or conf.get("SOGO_D_IMAP_AUTH_MECH") #TODO: revoir ça
        try:
            # client.login now supports optional auth_mech parameter (None, 'plain', 'xoauth2', ...)
            client.login(conf["username"], conf["password"], auth_mech)
        except (imaplib.IMAP4.error, socket.error, ssl.SSLError, ConnectionError, TimeoutError) as e:
            logger_api.error("Login failed for %s: %s", conf["username"], e)
            raise RequestException("Login failed") from e

        return client

    def _safe_logout(self, client: Any) -> None:
        """Safely logout from client, suppressing errors."""
        if client:
            try:
                client.logout()
            except (imaplib.IMAP4.error, AttributeError):
                pass

    def get_folder_list(self, user_conf: Dict[str, Any]) -> dict:
        """Retrieve a list of folders in the user's mailbox.

        :param user_conf: The user configuration for mailbox access.
        :type user_conf: Dict[str, Any]
        :return: A dictionary containing the status, data (list of folder names), and any errors.
        :rtype: dict
        """
        client = None
        try:
            client = self._open_client_for(user_conf)
        except RequestException as e:
            logger_api.error("Error opening client: %s", e)
            return {"status": False, "data": [], "errors": str(e)}

        try:
            raw_mailboxes = client.list_mailboxes()
        except (imaplib.IMAP4.error, socket.error, ssl.SSLError, AttributeError) as e:
            logger_api.error("Error fetching folder list: %s", e)
            return {"status": False, "data": [], "errors": str(e)}
        finally:
            self._safe_logout(client)

        folder_names: List[str] = []
        for raw in raw_mailboxes:
            try:
                decoded = raw.decode()
                name = decoded.split()[-1].strip('"')
                folder_names.append(name)
            except (UnicodeDecodeError, AttributeError) as e:
                logger_api.warning("Error decoding folder name: %s", e)
                continue

        return {"status": True, "data": [{"name": name} for name in folder_names], "errors": None}

    def create_folder(self, user_conf: Dict[str, Any], folder_name: str) -> dict:
        """Create a new folder in the user's mailbox.

        :param user_conf: The user configuration for mailbox access.
        :type user_conf: Dict[str, Any]
        :param folder_name: The name of the folder to create.
        :type folder_name: str
        :return: A dictionary containing the status, data (created folder info), and any errors.
        :rtype: dict
        """
        client = None
        try:
            client = self._open_client_for(user_conf)
        except RequestException as e:
            logger_api.error("Error opening client: %s", e)
            return {"status": False, "data": {}, "errors": str(e)}

        try:
            client.create_folder(folder_name)
            return {"status": True, "data": {"name": folder_name}, "errors": None}
        except ValidationError as e:
            logger_api.error("Validation error while creating folder: %s", e)
            return {"status": False, "data": {}, "errors": str(e)}
        except (imaplib.IMAP4.error, socket.error, ssl.SSLError, AttributeError, RequestException) as e:
            logger_api.error("Error creating folder: %s", e)
            return {"status": False, "data": {}, "errors": str(e)}
        finally:
            self._safe_logout(client)

    def delete_folder(self, user_conf: Dict[str, Any], folder_name: str) -> dict:
        """Delete a mail folder.

        :param user_conf: The user configuration for mailbox access.
        :type user_conf: Dict[str, Any]
        :param folder_name: The name of the folder to delete.
        :type folder_name: str
        :return: A dictionary containing the status, data (deleted folder info), and any errors.
        :rtype: dict
        """
        client = None
        try:
            client = self._open_client_for(user_conf)
        except RequestException as e:
            logger_api.error("Error opening client: %s", e)
            return {"status": False, "data": {}, "errors": str(e)}

        try:
            client.delete_folder(folder_name)
            return {"status": True, "data": {}, "errors": None}
        except (imaplib.IMAP4.error, socket.error, ssl.SSLError, AttributeError, RequestException) as e:
            logger_api.error("Error deleting folder: %s", e)
            return {"status": False, "data": {}, "errors": str(e)}
        finally:
            self._safe_logout(client)

    def get_folder_mails(self, user_conf: Dict[str, Any], folder_name: str, page: int = 1, per_page: int = 20) -> dict:
        """Retrieve a list of mails in a specific folder.

        :param user_conf: The user configuration for mailbox access.
        :type user_conf: Dict[str, Any]
        :param folder_name: The name of the folder to retrieve mails from.
        :type folder_name: str
        :param page: The page number to retrieve, defaults to 1
        :type page: int, optional
        :param per_page: The number of mails to retrieve per page, defaults to 20
        :type per_page: int, optional
        :return: A dictionary containing the status, data (list of mails), pagination info, and total count.
        :rtype: dict
        """
        client = None
        try:
            client = self._open_client_for(user_conf)
        except RequestException as e:
            logger_api.error("Error opening client: %s", e)
            return {"status": False, "data": [], "total": 0, "page": page, "per_page": per_page, "errors": str(e)}

        try:
            mails_raw = client.fetch_all_full_mails(folder_name)
        except (imaplib.IMAP4.error, socket.error, ssl.SSLError, AttributeError, RequestException) as e:
            logger_api.error("Error fetching mails for folder %s: %s", folder_name, e)
            return {"status": False, "data": [], "total": 0, "page": page, "per_page": per_page, "errors": str(e)}
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
                "from": {"name": from_name, "email": from_email},
                "to": to_list,
                "date": date,
                "seen": "\\Seen" in flags,
                "flagged": "\\Flagged" in flags,
                "deleted": "\\Deleted" in flags,
                "flags": flags,
                "hasAttachment": has_attachment,
            })

        total = len(mails)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_mails = mails[start_idx:end_idx]

        return {
            "status": True,
            "data": paginated_mails,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page,  # Ceiling division
            "errors": None
        }

    def delete_mails(self, user_conf: Dict[str, Any], folder_name: str, mail_uids: List[int]) -> dict:
        """Delete multiple mails by UIDs in a single client session.

        Now assumes mail_uids is a list of ints.

        :param user_conf: The user configuration for mailbox access.
        :type user_conf: Dict[str, Any]
        :param folder_name: The name of the folder containing the mails.
        :type folder_name: str
        :param mail_uids: The UIDs of the mails to delete (int).
        :type mail_uids: List[int]
        :return: A dictionary containing the status, data (deleted mail ids), and any errors.
        :rtype: dict
        """
        try:
            client = self._open_client_for(user_conf)
        except RequestException as e:
            logger_api.error("Error opening client for delete_mails: %s", e)
            return {"status": False, "data": {"deleted_ids": []}, "errors": str(e)}

        deleted: List[int] = []
        failed_details: Dict[int, str] = {}

        try:
            for uid in mail_uids:
                try:
                    # copy to Trash (client expects int uid)
                    client.copy_mail_to_mailbox(folder_name, uid, "Trash")
                    # add flags (Seen + Deleted)
                    client.add_flags_to_mail(folder_name, uid, ['\\Seen', '\\Deleted'])
                    deleted.append(uid)
                except RequestException as e:
                    logger_api.error("Error deleting mail UID %s in %s: %s", uid, folder_name, e)
                    failed_details[uid] = str(e)
                except (imaplib.IMAP4.error, socket.error, ssl.SSLError, AttributeError) as e:
                    logger_api.error("Error deleting mail UID %s in %s: %s", uid, folder_name, e)
                    failed_details[uid] = str(e)

            status = len(failed_details) == 0

            if status:
                errors_value = ""
            else:
                detail_parts = [f"{k}: {v}" for k, v in failed_details.items()]
                errors_value = f"{len(failed_details)} mail(s) failed to be deleted - details: " + " ; ".join(detail_parts)

            return {"status": status, "data": {"deleted_ids": deleted}, "errors": errors_value}
        finally:
            # Disconnect if client exists
            if client is not None:
                self._safe_logout(client)

    def delete_all_mail_in_folder(self, user_conf: Dict[str, Any], folder_name: str, before_date: str | None = None) -> dict:
        """Delete all mails in a specific folder.
        
        :param user_conf: The user configuration for mailbox access.
        :type user_conf: Dict[str, Any]
        :param folder_name: The name of the folder to delete mails from.
        :type folder_name: str
        :param before_date: Optional date string to delete mails before this date.
        :type before_date: str | None
        :return: A dictionary containing the status, data (count of deleted mails), and any errors.
        :rtype: dict
        """
        client = None
        try:
            try:
                client = self._open_client_for(user_conf)
            except RequestException as e:
                logger_api.error("Error opening client: %s", e)
                return {"status": False, "data": {}, "errors": str(e)}

            # Get UIDs
            try:
                mail_uids = client.get_mail_uids_before_date(folder_name, before_date)
                logger_api.debug("Found %d mails to delete in '%s'", len(mail_uids), folder_name)
            except (imaplib.IMAP4.error, socket.error, ssl.SSLError, AttributeError, RequestException) as e:
                logger_api.error("Error fetching mail UIDs in folder %s: %s", folder_name, e)
                return {"status": False, "data": {}, "errors": str(e)}

            # Delete mails one by one
            deleted_count = 0
            for mail_uid in mail_uids:
                try:
                    client.copy_mail_to_mailbox(folder_name, mail_uid, "Trash")
                    client.add_flags_to_mail(folder_name, mail_uid, ["\\Deleted"])
                    deleted_count += 1
                except (imaplib.IMAP4.error, AttributeError) as e:
                    logger_api.warning("Failed to delete mail UID %s in %s: %s", mail_uid, folder_name, e)
                    return {"status": False, "data": {}, "errors": f"error with mail UID {mail_uid}: {e}"}

            return {"status": True, "data": {"mails deleted": deleted_count}, "errors": None}

        finally:
            # Disconnect if client exists
            if client is not None:
                self._safe_logout(client)


    def expunge_mailbox(self, user_conf: Dict[str, Any], folder_name: str) -> dict:
        """Permanently remove deleted mails from the mailbox.

        :param user_conf: The user configuration for mailbox access.
        :type user_conf: Dict[str, Any]
        :param folder_name: The name of the folder to expunge.
        :type folder_name: str
        :return: A dictionary containing the status, data (count of expunged mails), and any errors.
        :rtype: dict
        """
        client = None
        try:
            client = self._open_client_for(user_conf)
        except RequestException as e:
            logger_api.error("Error opening client: %s", e)
            return {"status": False, "data": {}, "errors": str(e)}
        try:
            client.expunge_mailbox(folder_name)
            return {"status": True, "data": {}, "errors": None}
        except (imaplib.IMAP4.error, socket.error, ssl.SSLError, AttributeError, RequestException) as e:
            logger_api.error("Error expunging mailbox %s: %s", folder_name, e)
            return {"status": False, "data": {}, "errors": str(e)}
        finally:
            self._safe_logout(client)

    def move_mails(self, user_conf: Dict[str, Any], from_folder: str, mail_uids: List[int], to_folder: str) -> dict:
        """Move multiple mails from one folder to another.
        
        :param user_conf: The user configuration for mailbox access.
        :type user_conf: Dict[str, Any]
        :param from_folder: The name of the source folder.
        :type from_folder: str
        :param mail_uids: List of UIDs of mails to move.
        :type mail_uids: List[int]
        :param to_folder: The name of the destination folder.
        :type to_folder: str
        :return: A dictionary containing the status, data, and any errors.
        :rtype: dict
        """
        client = None
        try:
            client = self._open_client_for(user_conf)
        except RequestException as e:
            logger_api.error("Error opening client: %s", e)
            return {"status": False, "data": {}, "errors": str(e)}

        try:
            for mail_uid in mail_uids:
                try:
                    # client expects int mail_uid
                    client.copy_mail_to_mailbox(from_folder, mail_uid, to_folder)
                    client.add_flags_to_mail(from_folder, mail_uid, ['\\Deleted'])
                except (imaplib.IMAP4.error, socket.error, ssl.SSLError, AttributeError, RequestException) as e:
                    logger_api.error(
                        "Error moving mail UID %s from %s to %s: %s",
                        mail_uid, from_folder, to_folder, e
                    )
                    return {"status": False, "data": {}, "errors": f"error with mail UID {mail_uid}: {e}"}
            return {"status": True, "data": {}, "errors": None}

        finally:
            self._safe_logout(client)

    def get_mail_detail(self, user_conf: Dict[str, Any], folder_name: str, mail_uid: int) -> dict:
        """Fetch the details of a specific mail.

        :param user_conf: The user configuration for mailbox access.
        :type user_conf: Dict[str, Any]
        :param folder_name: The name of the folder containing the mail.
        :type folder_name: str
        :param mail_uid: The UID of the mail to fetch (int).
        :type mail_uid: int
        :return: A dictionary containing the status, data (mail details), and any errors.
        :rtype: dict
        """
        client = None
        try:
            client = self._open_client_for(user_conf)
        except RequestException as e:
            logger_api.error("Error opening client: %s", e)
            return {"status": False, "data": None, "errors": str(e)}

        try:
            mail_bytes = client.fetch_mail(folder_name, mail_uid)
        except (imaplib.IMAP4.error, socket.error, ssl.SSLError, AttributeError, RequestException) as e:
            logger_api.error("Error fetching mail detail for UID %s: %s", mail_uid, e)
            return {"status": False, "data": None, "errors": str(e)}
        finally:
            self._safe_logout(client)

        try:
            msg = email.message_from_bytes(mail_bytes)
        except (ValueError, TypeError) as e:
            logger_api.error("Error parsing mail bytes for UID %s: %s", mail_uid, e)
            return {"status": False, "data": None, "errors": str(e)}

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
            "status": True,
            "errors": None,
            "data": {
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
        }