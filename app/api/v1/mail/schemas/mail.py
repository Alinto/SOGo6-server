from marshmallow import Schema, fields, validate
from app.utils.api.ApiBaseResponse import ApiBaseResponse


class MailDeleteSchema(Schema):
    """
    Schema for deleting multiple emails.
    """
    mail_uids = fields.List(fields.Integer(), required=True)

    @classmethod
    def example(cls) -> dict:
        """Example data for mail deletion.
        
        :return: Example mail deletion payload
        :rtype: dict
        """
        return {
            "mail_uids": [1, 2, 3, 4, 5]
        }


class MailMoveSchema(Schema):
    """
    Schema for moving multiple emails to another folder.
    """
    mail_uids = fields.List(fields.Integer(), required=True)
    to_folder_name = fields.String(required=True)

    @classmethod
    def example(cls) -> dict:
        """Example data for moving mails.
        
        :return: Example mail move payload
        :rtype: dict
        """
        return {
            "mail_uids": [1, 2, 3],
            "to_folder_name": "Archive"
        }


class MailFolderQueryArgsSchema(Schema):
    """
    Schema for query parameters when deleting emails in a folder.
    """
    before_date = fields.String(required=False, allow_none=True)



class AttachmentPartSchema(Schema):
    """
    Schema for an attachment part in an email
    """
    partId = fields.String()
    name = fields.String()
    contentType = fields.String()
    size = fields.Integer()
    downloadUri = fields.String()
    displayUri = fields.String()


class AttachmentsSchema(Schema):
    """
    Schema for the attachments group in a mail
    """
    parts = fields.List(fields.Nested(AttachmentPartSchema))
    zipUri = fields.String()
    count = fields.Integer()


class AddressSchema(Schema):
    """
    Schema for an email address
    """
    name = fields.String()
    email = fields.String()


class AttachmentSchema(Schema):
    """
    Schema for an email attachment
    """
    filename = fields.String()
    contentType = fields.String()
    size = fields.Integer()
    downloadUri = fields.String()
    displayUri = fields.String()
    extension = fields.String()

class ContentSchema(Schema):
    """
    Schema for mail content
    """
    content = fields.String()
    contentType = fields.String()
    shouldDisplayAttachment = fields.Boolean()


class CertificateSchema(Schema):
    """Schema for email certificates
    """
    emails = fields.List(fields.String())


class MetaDataMailSchema(Schema):
    """
    Schema for mail metadata
    """
    mail_type = fields.String()
    mail_type_data = fields.Dict()

class MailDetailSchema(Schema):
    """
    Schema for detailed mail information
    """
    uid = fields.String(required=True)
    size = fields.Integer()

    # system flags (https://datatracker.ietf.org/doc/html/rfc9051#name-flags-message-attribute)
    seen = fields.Boolean() # match flag \SEEN
    flagged = fields.Boolean() # match flag \FLAGGED
    answered = fields.Boolean() # match flag \ANSWERED
    forwarded = fields.Boolean() # match flag $FORWARDED
    flags = fields.List(fields.String())
    deleted = fields.Boolean() # match flag \DELETED ?? est ce qu'on l'envoie?

    # header
    to = fields.List(fields.Nested(AddressSchema))  # header To
    from_ = fields.Nested(AddressSchema, data_key="from") #header From
    cc = fields.List(fields.Nested(AddressSchema))  # header Cc
    reply_to = fields.List(fields.Nested(AddressSchema))  # header Reply-To
    subject = fields.String() # header Subject
    date = fields.String() # match header Date
    return_path = fields.String() # match header Return-Path

    # body
    contents = fields.List(fields.Nested(ContentSchema))
    has_attachment = fields.Boolean()
    attachments = fields.List(fields.Nested(AttachmentSchema))

    # encryption
    is_signed = fields.Boolean() # whether the mail is signed (S/MIME or PGP)
    certificates = fields.List(fields.Nested(CertificateSchema)) # list of certificates if signed
    valid = fields.Boolean() # whether the signature is valid

    # others
    priority = fields.Integer() # custom header X-Priority in sogo 5
    should_ask_receipt = fields.Boolean() # header return-receipt-to/Disposition-Notification-To present

    # isImageSafe = fields.Boolean() # whether images are safe to display TODO: geré coté front?

    # mail type
    metadatas = fields.List(fields.Nested(MetaDataMailSchema))

class MailDetailResponseSchema(ApiBaseResponse):
    """
    Schema for GET /mailboxes/<account_id>/folders/<path:folder_name>/mails/<mail_uid> response
    """
    data = fields.Nested(MailDetailSchema, required=True)

    @classmethod
    def example(cls) -> dict:
        """Example response for mail detail.
        
        :return: Example mail detail response
        :rtype: dict
        """
        return {
            "error_code": 0,
            "error_msg": "",
            "data": {
                "uid": "42",
                "size": 12543,
                "seen": False,
                "flagged": False,
                "answered": False,
                "forwarded": False,
                "flags": ["\\Recent"],
                "deleted": False,
                "to": [{"name": "Bob Jones", "email": "bob@example.com"}],
                "from": {"name": "Alice Smith", "email": "alice@example.com"},
                "cc": [{"name": "David", "email": "david@example.com"}],
                "reply_to": [],
                "subject": "Important Meeting Tomorrow",
                "date": "Tue, 17 Dec 2024 14:30:00 +0100",
                "return_path": "<alice@example.com>",
                "contents": [
                    {"content": "Hello,\n\nThis is the body of the email...\n\nBest regards,\nAlice", "contentType": "text/plain", "shouldDisplayAttachment": False},
                    {"content": "<p>Hello,<br><br>This is the body of the email...</p><p>Best regards,<br>Alice</p>", "contentType": "text/html", "shouldDisplayAttachment": False}
                ],
                "has_attachment": True,
                "attachments": [
                    {
                        "filename": "document.pdf",
                        "contentType": "application/pdf",
                        "size": 45678,
                        "downloadUri": "/attachments/1?dl=True",
                        "displayUri": "???",
                        "extension": "pdf"
                    }
                ],
                "is_signed": True,
                "certificates": [],
                "valid": True,
                "priority": 1,
                "should_ask_receipt": False,
                "metadatas": [
                    {
                        "mail_type": "normal",
                        "mail_type_data": {}
                    }
                ]
            }
        }



class MailListResponseSchema(ApiBaseResponse):
    """
    Schema for GET /mailboxes/<account_id>/folders/<path:folder_name>/mails response
    """
    data = fields.List(
        fields.Nested(MailDetailSchema),
        required=True
    )

    @classmethod
    def example(cls) -> dict:
        """Example response for mail list.
        
        :return: Example mail list response
        :rtype: dict
        """
        return {
            "error_code": 0,
            "error_msg": "",
            "data": [
                {
                    "uid": "42",
                    "size": 12543,
                    "seen": False,
                    "flagged": False,
                    "answered": False,
                    "forwarded": False,
                    "flags": ["\\Recent"],
                    "deleted": False,
                    "to": [{"name": "Bob Jones", "email": "bob@example.com"}],
                    "from": {"name": "Alice Smith", "email": "alice@example.com"},
                    "cc": [{"name": "David", "email": "david@example.com"}],
                    "reply_to": [],
                    "subject": "Important Meeting Tomorrow",
                    "date": "Tue, 17 Dec 2024 14:30:00 +0100",
                    "return_path": "<alice@example.com>",
                    "contents": [
                        {"content": "Hello,\n\nThis is the body of the email...\n\nBest regards,\nAlice", "contentType": "text/plain", "shouldDisplayAttachment": False}
                    ],
                    "has_attachment": True,
                    "attachments": [
                        {
                            "filename": "document.pdf",
                            "contentType": "application/pdf",
                            "size": 45678,
                            "downloadUri": "/attachments/1?dl=True",
                            "displayUri": "???",
                            "extension": "pdf"
                        }
                    ],
                    "is_signed": True,
                    "certificates": [],
                    "valid": True,
                    "priority": 1,
                    "should_ask_receipt": False,
                    "metadatas": [
                        {
                            "mail_type": "normal",
                            "mail_type_data": {}
                        }
                    ]
                }
            ]
        }


class MailDeleteResponseSchema(ApiBaseResponse):
    """
    Schema for DELETE /mailboxes/<account_id>/folders/<path:folder_name>/mails/<mail_uid> response
    """
    data = fields.Dict(keys=fields.String(), values=fields.Integer())

    @classmethod
    def example(cls) -> dict:
        """Example response for mail deletion.
        
        :return: Example mail deletion response
        :rtype: dict
        """
        return {
            "error_code": 0,
            "error_msg": "",
            "data": {
                "uid_deleted": 42
            }
        }


class MailBulkDeleteResponseSchema(ApiBaseResponse):
    """
    Schema for deleting multiple mails response
    """
    data = fields.Dict(keys=fields.String(), values=fields.List(fields.Integer()))

    @classmethod
    def example(cls) -> dict:
        """Example response for bulk mail deletion.
        
        :return: Example bulk deletion response
        :rtype: dict
        """
        return {
            "error_code": 0,
            "error_msg": "",
            "data": {
                "deleted_ids": [1, 2, 3, 4, 5]
            }
        }


class MailMoveResponseSchema(ApiBaseResponse):
    """
    Schema for moving mails response
    """
    data = fields.Dict(keys=fields.String(), values=fields.List(fields.Integer()))

    @classmethod
    def example(cls) -> dict:
        """Example response for moving mails.
        
        :return: Example mail move response
        :rtype: dict
        """
        return {
            "error_code": 0,
            "error_msg": "",
            "data": {
                "moved_ids": [1, 2, 3]
            }
        }


class MailRawResponseSchema(ApiBaseResponse):
    """
    Schema for GET /mailboxes/<account_id>/folders/<path:folder_name>/mails/<mail_uid>/raw response
    """
    data = fields.Dict(keys=fields.String(), values=fields.String())

    @classmethod
    def example(cls) -> dict:
        """Example response for raw mail content.
        
        :return: Example raw mail response
        :rtype: dict
        """
        return {
            "error_code": 0,
            "error_msg": "",
            "data": {
                "raw": "Return-Path: <alice@example.com>\nReceived: from mail.example.com...\nDate: Tue, 17 Dec 2024 14:30:00 +0100\nFrom: Alice Smith <alice@example.com>\nTo: Bob Jones <bob@example.com>\nSubject: Meeting Tomorrow\n\nHello Bob,\n\nLet's meet tomorrow at 10am.\n\nBest regards,\nAlice"
            }
        }


# ===== Deprecated/Legacy Schemas =====

class MailListQuerySchema(Schema):
    """Schema for mail list query parameters."""

    page = fields.Int(
        validate=validate.Range(min=1),
        load_default=1,
    )
    per_page = fields.Int(
        validate=validate.Range(min=1, max=100),
        load_default=20,
    )
