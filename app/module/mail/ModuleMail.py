import email
from email.header import decode_header, make_header
from email.utils import parseaddr, getaddresses
import time

from typing import Optional, List, Any
from marshmallow import ValidationError

from app.utils.exceptions import RequestException
from app.utils.module.importManager import import_and_instantiate_manager
from app.utils.logger.logger import logger_api


class ModuleMail:
    """
    Module for mail-related operations.
    """
    def __init__(self, server: str, port: int = 143, imap_class: str = "ClientImap"):
        """
        Initialize the mail module with server and port information.
        :param server: The IMAP server address.
        :param port: The IMAP server port (default: 143).
        :param imap_class: Class name of the IMAP client to use.
        """
        self.server = server
        self.port = port
        self.imap_class = imap_class
        self.client = None

    def connect_imap(self, username: str, password: str) -> None:
        """
        Dynamically instantiate and connect the IMAP client.
        """
        client_args = {
            "server": self.server,
            "port": self.port
        }
        self.client = import_and_instantiate_manager(
            module_path="app.manager.mail",
            module_and_class_name=self.imap_class,
            module_args=client_args
        )
        if self.client is None:
            raise RequestException("ClientImap instance creation failed")
        self.client.login(username, password)

    def get_folder_list(self, username: str, password: str) -> dict:
        """
        Retourne la liste des dossiers (folders/mailboxes) pour l'utilisateur IMAP.

        :param username: Identifiant IMAP
        :type username: str
        :param password: Mot de passe IMAP
        :type password: str
        :return: Dictionnaire avec le statut, la liste des dossiers et les erreurs éventuelles
        :rtype: dict
        :raises RequestException: Si les dossiers ne peuvent pas être récupérés.
        """
        try:
            self.connect_imap(username, password)
            if self.client is None:
                raise RequestException("IMAP client not initialized")
            raw_mailboxes = self.client.list_mailboxes()
            self.client.logout()

            folder_names = []
            for raw in raw_mailboxes:
                decoded = raw.decode()
                name = decoded.split()[-1].strip('"')
                folder_names.append(name)
            return {"status": True, "folders": [{"name": name} for name in folder_names], "errors": None}
        except Exception as e:
            logger_api.error("Error fetching folder list: %s", e)
            if self.client:
                try:
                    self.client.logout()
                except Exception:
                    pass
            return {"status": False, "folders": [], "errors": str(e)}

    def create_folder(self, username: str, password: str, folder_name: str) -> tuple[bool, str]:
        """
        Connects to IMAP and creates a new mail folder.

        :param username: IMAP username
        :param password: IMAP password
        :param folder_name: IMAP folder to create
        :return: Tuple indicating success status and message
        :rtype: tuple[bool, str]
        """
        try:
            self.connect_imap(username, password)
            if self.client is None:
                raise RequestException("IMAP client not initialized")
            self.client.create_folder(folder_name)
            self.client.logout()
            return True, "OK"
        except ValidationError as e:
            logger_api.error("Validation error while creating folder: %s", e)
            if self.client:
                try:
                    self.client.logout()
                except Exception:
                    pass
            return False, str(e)
        except RequestException as e:
            logger_api.error("Request error: %s", e)
            if self.client:
                try:
                    self.client.logout()
                except Exception:
                    pass
            return False, str(e)
        except Exception as e: #TODO: qu'est ce qu'on fait dans ce cas la?
            logger_api.error("Unexpected error: %s", e)
            if self.client:
                try:
                    self.client.logout()
                except Exception:
                    pass
            return False, str(e)

    def delete_folder(self, username: str, password: str, folder_name: str) -> tuple[bool, str]:
        """
        Connects to IMAP and deletes the specified mail folder.

        :param username: IMAP username
        :param password: IMAP password
        :param folder_name: IMAP folder to delete
        :return: Tuple indicating success status and message
        :rtype: tuple[bool, str]
        """
        try:
            self.connect_imap(username, password)
            if self.client is None:
                raise RequestException("IMAP client not initialized")
            self.client.delete_folder(folder_name)
            self.client.logout()
            return True, "OK"
        except ValidationError as e:
            logger_api.error("Validation error while deleting folder: %s", e)
            if self.client:
                try:
                    self.client.logout()
                except Exception:
                    pass
            return False, str(e)
        except RequestException as e:
            logger_api.error("Request error: %s", e)
            if self.client:
                try:
                    self.client.logout()
                except Exception:
                    pass
            return False, str(e)
        except Exception as e:
            if self.client:
                try:
                    self.client.logout()
                except Exception:
                    pass
            logger_api.error("Unexpected error: %s", e)
            return False, str(e)

    def get_folder_mails(self, username: str, password: str, folder_name: str, page: int = 1, per_page: int = 20) -> dict:
        """
        Connects to IMAP and fetches mails from the specified folder with pagination.
        :param username: IMAP username
        :param password: IMAP password
        :param folder_name: IMAP folder to fetch mails from
        :param page: Page number for pagination (default: 1)
        :param per_page: Number of mails per page (default: 20)
        :return: Dict with status, list of mails with parsed headers and attachment info, and any errors
        :rtype: dict
        :raises RequestException: If the folder cannot be found or mails cannot be retrieved.
        """
        try:
            self.connect_imap(username, password)
            if self.client is None:
                raise RequestException("IMAP client not initialized")
            mails_raw = self.client.fetch_all_full_mails(folder_name)
            self.client.logout()
        except Exception as e:
            logger_api.error("Error fetching mails for folder %s: %s", folder_name, e)
            if self.client:
                try:
                    self.client.logout()
                except Exception:
                    pass
            return {
                "status": False,
                "mails": [],
                "errors": str(e)
            }

        mails = []
        for i, raw_entry in enumerate(mails_raw, 1):
            try:
                raw_email_bytes = raw_entry.get('mail_bytes')
                flags = raw_entry.get('flags', [])
                if not raw_email_bytes:
                    continue

                msg = email.message_from_bytes(raw_email_bytes)
                subject = str(make_header(decode_header(msg.get('Subject', ''))))
                from_name, from_email = parseaddr(msg.get('From', ''))
                to_addrs = getaddresses([msg.get('To', '')])
                to_list = [{"name": name, "email": addr} for name, addr in to_addrs]
                date = msg.get('Date', '')

                has_attachment = False
                for part in msg.walk():
                    content_disposition = part.get("Content-Disposition", "")
                    if part.get_content_maintype() == "multipart":
                        continue
                    if "attachment" in content_disposition.lower():
                        has_attachment = True
                        break

                mails.append({
                    "id": str(i),
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
            except Exception as e:
                logger_api.warning("Mail %d in folder %s could not be parsed: %s", i, folder_name, e)

        start = (page - 1) * per_page
        end = start + per_page
        return {
            "status": True,
            "mails": mails[start:end],
            "errors": None
        }

    def delete_all_mail_in_folder(self, username: str, password: str, folder_name: str, before_date: str | None) -> tuple[bool, str]:
        """
        Mark as deleted all mails in folder before the given date (YYYY-MM-DD).
        Returns number of mails marked as deleted.

        :param username: IMAP username
        :type username: str
        :param password: IMAP password
        :type password: str
        :param folder_name: Folder to delete mails from (e.g., "INBOX")
        :type folder_name: str
        :param before_date: Date string in format YYYY-MM-DD. If None, all mails
        before the current date are marked as deleted.
        :type before_date: str | None
        :return: Tuple indicating success status and message with count of mails marked as deleted
        :rtype: tuple[bool, str]
        """
        try:
            self.connect_imap(username, password)
            if self.client is None:
                raise RequestException("IMAP client not initialized")
            count = self.client.mark_all_mails_in_folder_deleted_and_copy_to_trash(folder_name, before_date)
            self.client.logout()
            return True, f"{count} mails marked as deleted"
        except ValidationError as e:
            logger_api.error("Validation error while deleting mails: %s", e)
            if self.client:
                try:
                    self.client.logout()
                except Exception:
                    pass
            return False, str(e)
        except RequestException as e:
            logger_api.error("Request error: %s", e)
            if self.client:
                try:
                    self.client.logout()
                except Exception:
                    pass
            return False, str(e)
        except Exception as e:
            if self.client:
                try:
                    self.client.logout()
                except Exception:
                    pass
            logger_api.error("Unexpected error: %s", e)
            return False, str(e)

    def expunge_mailbox(self, username: str, password: str, folder_name: str) -> tuple[bool, str]:
        """
        Connects to IMAP and expunges (permanently removes) mails marked as deleted from the specified mailbox.
        :param username: IMAP username
        :param password: IMAP password
        :param folder_name: IMAP folder to expunge
        :return: Tuple indicating success status and message
        :rtype: tuple[bool, str]
        """
        try:
            self.connect_imap(username, password)
            if self.client is None:
                raise RequestException("IMAP client not initialized")
            self.client.expunge_mailbox(folder_name)
            self.client.logout()
            return True, "OK"
        except ValidationError as e:
            logger_api.error("Validation error while expunging folder: %s", e)
            if self.client:
                try:
                    self.client.logout()
                except Exception:
                    pass
            return False, str(e)
        except RequestException as e:
            logger_api.error("Request error: %s", e)
            if self.client:
                try:
                    self.client.logout()
                except Exception:
                    pass
            return False, str(e)
        except Exception as e:
            if self.client:
                try:
                    self.client.logout()
                except Exception:
                    pass
            logger_api.error("Unexpected error: %s", e)
            return False, str(e)

    def get_mail_detail(self, username: str, password: str, folder_name: str, mail_id: str) -> dict:
        """
        Connects to IMAP and fetches a specific mail by id.

        :param username: IMAP username
        :param password: IMAP password
        :param folder_name: IMAP folder
        :param mail_id: IMAP mail id
        :return: Dict with status, detailed mail info including parsed headers, body, attachments, and any errors
        :rtype: dict
        """
        try:
            self.connect_imap(username, password)
            if self.client is None:
                raise RequestException("IMAP client not initialized")
            mail_bytes = self.client.fetch_mail(folder_name, mail_id)
            self.client.logout()

            msg = email.message_from_bytes(mail_bytes)
            subject = str(make_header(decode_header(msg.get('Subject', ''))))
            from_ = email.utils.formataddr(parseaddr(msg.get('From', '')))
            to = [email.utils.formataddr(x) for x in getaddresses([msg.get('To', '')])]
            cc = [email.utils.formataddr(x) for x in getaddresses([msg.get('Cc', '')])]
            bcc = [email.utils.formataddr(x) for x in getaddresses([msg.get('Bcc', '')])]
            date = msg.get('Date', '')
            size = len(mail_bytes)

            # TODO: Flags si tu veux les ajouter (via self.client)
            seen = False
            answered = False
            recent = False
            deleted = False
            important = False

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
                    attach_bytes = part.get_payload(decode=True)
                    attach_size = len(attach_bytes) if isinstance(attach_bytes, bytes) else 0
                    attachments.append({
                        "partId": str(i),
                        "name": filename,
                        "contentType": content_type,
                        "size": attach_size,
                        "downloadUri": f"/attachments/{i}?dl=True",
                        "displayUri": "???" #TODO: implement
                    })
                elif part.get_content_type() in ["text/plain", "text/html"]:
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or "utf-8"
                    if isinstance(payload, bytes):
                        try:
                            decoded = payload.decode(charset, errors="replace")
                            body += decoded
                        except Exception:
                            body += ""
                    elif isinstance(payload, str):
                        body += payload

            date_tuple = email.utils.parsedate(date)
            if date_tuple is not None:
                timestamp = int(time.mktime(date_tuple))
            else:
                timestamp = None

            return {
                "status": True,
                "errors": None,
                "mail": {
                    "attachments": {
                        "parts": attachments,
                        "zipUri": "???", #TODO: implement
                        "count": len(attachments)
                    },
                    "id": str(mail_id),
                    "contentUri": "???", #TODO: implement
                    "seen": seen,
                    "answered": answered,
                    "recent": recent,
                    "deleted": deleted,
                    "hasAttachment": has_attachment,
                    "important": important,
                    "date": timestamp,
                    "subject": subject,
                    "isMailingList": False,
                    "from_": from_,
                    "to": to,
                    "cc": cc,
                    "bcc": bcc,
                    "size": size,
                    "body": body
                }
            }
        except Exception as e:
            logger_api.error("Error fetching mail detail: %s", e)
            if self.client:
                try:
                    self.client.logout()
                except Exception:
                    pass
            return {
                "status": False,
                "mail": None,
                "errors": str(e)
            }

    def delete_mail_by_id(self, username: str, password: str, folder_name: str, mail_id: str) -> tuple[bool, str]:
        """
        Connects to IMAP and 'deletes' a specific mail by id (copy to Trash, flag deleted).

        :param username: IMAP username
        :param password: IMAP password
        :param folder_name: IMAP folder
        :param mail_id: IMAP mail id
        :return: Tuple indicating success status and message
        :rtype: tuple[bool, str]
        """
        try:
            self.connect_imap(username, password)
            if self.client is None:
                raise RequestException("IMAP client not initialized")
            self.client.copy_mail_to_mailbox(folder_name, mail_id, dest_mailbox="Trash")
            self.client.add_flags_to_mail(folder_name, mail_id, ['\\Seen', '\\Deleted'])
            self.client.logout()
            return True, "OK"
        except ValidationError as e:
            logger_api.error("Validation error while deleting mail: %s", e)
            if self.client:
                try:
                    self.client.logout()
                except Exception:
                    pass
            return False, str(e)
        except RequestException as e:
            logger_api.error("Request error: %s", e)
            if self.client:
                try:
                    self.client.logout()
                except Exception:
                    pass
            return False, str(e)
        except Exception as e:
            if self.client:
                try:
                    self.client.logout()
                except Exception:
                    pass
            logger_api.error("Unexpected error: %s", e)
            return False, str(e)

    def move_mail(self, username: str, password: str, from_folder: str, mail_id: str, to_folder: str) -> tuple[bool, str]:
        """
        Connects to IMAP and moves a mail from one folder to another.
        The mail is copied to the destination folder, flagged as deleted in the source, and expunged from the source.

        :param username: IMAP username
        :param password: IMAP password
        :param from_folder: Source folder
        :param mail_id: Mail id
        :param to_folder: Destination folder
        :return: Tuple indicating success status and message
        :rtype: tuple[bool, str]
        """
        try:
            self.connect_imap(username, password)
            if self.client is None:
                raise RequestException("IMAP client not initialized")
            self.client.copy_mail_to_mailbox(from_folder, mail_id, to_folder)
            self.client.add_flags_to_mail(from_folder, mail_id, ['\\Deleted'])
            #self.client.expunge_mailbox(from_folder) TODO: Est ce qu'on expunge direct apres le move?
            self.client.logout()
            return True, "OK"
        except ValidationError as e:
            logger_api.error("Validation error while moving mail: %s", e)
            if self.client:
                try:
                    self.client.logout()
                except Exception:
                    pass
            return False, str(e)
        except RequestException as e:
            logger_api.error("Request error: %s", e)
            if self.client:
                try:
                    self.client.logout()
                except Exception:
                    pass
            return False, str(e)
        except Exception as e:
            if self.client:
                try:
                    self.client.logout()
                except Exception:
                    pass
            logger_api.error("Unexpected error: %s", e)
            return False, str(e)
