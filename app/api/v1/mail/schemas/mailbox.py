from marshmallow import Schema, fields, validate, post_load
from app.utils.api.ApiBaseResponse import ApiBaseResponse
from app.utils import constants as cs


class MailServerSchema(Schema):
    """
    Schema for incoming mail server configuration (IMAP/POP3)
    """
    server = fields.String(required=True, validate=validate.Length(min=1))
    port = fields.Integer(required=True, validate=validate.Range(min=1, max=65535))
    encryption = fields.String(
        required=True,
        validate=validate.OneOf(cs.SOCK_ENC_LIST)
    )
    type_ = fields.String(
        load_default="imap",
        dump_default="imap",
        validate=validate.OneOf(["imap"]),
        data_key="type"
    )
    password = fields.String(required=True, validate=validate.Length(min=1))
    username = fields.String(required=True, validate=validate.Length(min=1))
    auth_mech = fields.String(
        required=False,
        allow_none=True,
        validate=validate.OneOf(["plain", "login", "xoauth2"])
    )

    @post_load
    def change_type(self, item: dict, many:bool, **kwargs: dict) -> dict:
        """
        Simply change the type name after a load
        """
        item["type"] = item.pop("type_")
        return item

    @classmethod
    def example(cls) -> dict:
        """Example data for mail server configuration.
        
        :return: Example mail server configuration
        :rtype: dict
        """
        return {
            "server": "imap.example.com",
            "port": 993,
            "encryption": "SSL/TLS",
            "type": "imap",
            "password": "secure_password",
            "username": "user@example.com",
            "auth_mech": "plain"
        }


class MailOutgoingSchema(Schema):
    """
    Schema for outgoing mail server configuration (SMTP)
    """
    server = fields.String(required=True, validate=validate.Length(min=1))
    port = fields.Integer(required=True, validate=validate.Range(min=1, max=65535))
    encryption = fields.String(
        required=True,
        validate=validate.OneOf(cs.SOCK_ENC_LIST)
    )
    password = fields.String(required=True, validate=validate.Length(min=1))
    username = fields.String(required=True, validate=validate.Length(min=1))
    auth_mech = fields.String(
        required=False,
        allow_none=True,
        validate=validate.OneOf(["plain", "login", "xoauth2"])
    )
    type_ = fields.String(
        required=True,
        validate=validate.OneOf(["smtp"]),
        data_key="type"
    )

    @post_load
    def change_type(self, item: dict, many:bool, **kwargs: dict) -> dict:
        """
        Simply change the type name after a load
        """
        item["type"] = item.pop("type_")
        return item

    @classmethod
    def example(cls) -> dict:
        """Example data for outgoing mail server configuration.
        
        :return: Example outgoing mail server configuration
        :rtype: dict
        """
        return {
            "server": "smtp.example.com",
            "port": 587,
            "encryption": "StartTLS",
            "password": "secure_password",
            "username": "user@example.com",
            "auth_mech": "plain",
            "type": "smtp"
        }


class IdentitySchema(Schema):
    """
    Schema for email identity
    """
    mail = fields.Email(required=True)
    name = fields.String(required=True, validate=validate.Length(min=1))
    replyTo = fields.Email(required=False, allow_none=True)
    isDefault = fields.Boolean(required=False, load_default=False)
    signatures = fields.Dict(fields.String(), required=False, load_default={})

    @classmethod
    def example(cls) -> dict:
        """Example data for identity.
        
        :return: Example identity
        :rtype: dict
        """
        return {
            "mail": "user@example.com",
            "name": "John Doe",
            "replyTo": "noreply@example.com",
            "isDefault": True,
            "signatures": {"default": "Best regards,\nJohn Doe"}
        }

class MailServerUpdateSchema(Schema):
    """
    Schema for incoming mail server configuration (IMAP/POP3)
    """
    server = fields.String(validate=validate.Length(min=1))
    port = fields.Integer(validate=validate.Range(min=1, max=65535))
    encryption = fields.String(validate=validate.OneOf(cs.SOCK_ENC_LIST))
    type_ = fields.String(
        validate=validate.OneOf(["imap"]),
        data_key="type"
    )
    password = fields.String(validate=validate.Length(min=1))
    username = fields.String(validate=validate.Length(min=1))
    auth_mech = fields.String(
        allow_none=True,
        validate=validate.OneOf(["plain", "login", "xoauth2"])
    )

    @post_load
    def change_type(self, item: dict, many:bool, **kwargs: dict) -> dict:
        """
        Simply change the type name after a load
        """
        if "type_" in item:
            item["type"] = item.pop("type_")
        return item

    @classmethod
    def example(cls) -> dict:
        """Example data for mail server configuration.
        
        :return: Example mail server configuration
        :rtype: dict
        """
        return {
            "server": "imap.example.com",
            "port": 993,
            "encryption": "SSL/TLS",
            "type": "imap",
            "password": "secure_password",
            "username": "user@example.com",
            "auth_mech": "plain"
        }


class MailOutgoingUpdateSchema(Schema):
    """
    Schema for outgoing mail server configuration (SMTP)
    """
    server = fields.String(validate=validate.Length(min=1))
    port = fields.Integer(validate=validate.Range(min=1, max=65535))
    encryption = fields.String(
        validate=validate.OneOf(cs.SOCK_ENC_LIST)
    )
    password = fields.String(validate=validate.Length(min=1))
    username = fields.String(validate=validate.Length(min=1))
    auth_mech = fields.String(
        allow_none=True,
        validate=validate.OneOf(["plain", "login", "xoauth2"])
    )
    type_ = fields.String(
        validate=validate.OneOf(["smtp"]),
        data_key="type"
    )

    @post_load
    def change_type(self, item: dict, many:bool, **kwargs: dict) -> dict:
        """
        Simply change the type name after a load
        """
        if "type_" in item:
            item["type"] = item.pop("type_")
        return item

    @classmethod
    def example(cls) -> dict:
        """Example data for outgoing mail server configuration.
        
        :return: Example outgoing mail server configuration
        :rtype: dict
        """
        return {
            "server": "smtp.example.com",
            "port": 587,
            "encryption": "StartTLS",
            "password": "secure_password",
            "username": "user@example.com",
            "auth_mech": "plain",
            "type": "smtp"
        }

class AttachmentSchema(Schema):
    """
    Schema for a mail attachment
    """
    filename = fields.String(required=False, load_default="file")
    data = fields.Raw(required=True, metadata={"description": "Raw binary data of the attachment"})


class SendMailSchema(Schema):
    """
    Schema for POST /mailboxes/<account_id>/send - Send an email
    """
    from_addr = fields.Email(required=True, data_key="from")
    to = fields.List(fields.Email(), required=True, validate=validate.Length(min=1))
    subject = fields.String(required=True, validate=validate.Length(min=1))
    body = fields.String(required=True)
    cc = fields.List(fields.Email(), required=False, load_default=[])
    bcc = fields.List(fields.Email(), required=False, load_default=[])
    return_receipt = fields.Email(required=False, allow_none=True, load_default=None)
    attachments = fields.List(fields.Nested(AttachmentSchema), required=False, load_default=[]) #TODO : à revoir

    @classmethod
    def example(cls) -> dict:
        return {
            "from": "sogo-tests1@example.org",
            "to": ["sogo-tests1@example.org"],
            "subject": "Hello",
            "body": "Hello world! commment ça va ?",
            "cc": [],
            "bcc": [],
            "return_receipt": None,
            "attachments": []
        }


class SendMailResponseSchema(ApiBaseResponse):
    """
    Schema for response when sending a mail
    """
    data = fields.Dict(required=False, allow_none=True)

    @classmethod
    def example(cls) -> dict:
        return {}


class QuotaSchema(Schema):
    """
    Schema for mailbox quota information
    """
    storage_used = fields.Integer(required=True, metadata={"description": "Storage used in KB"})
    storage_limit = fields.Integer(required=True, metadata={"description": "Storage limit in KB (0 if unlimited)"})
    soft_quota_value = fields.Integer(required=True, metadata={"description": "Soft quota value from domain settings (SOGO_D_SOFT_EMAIL_QUOTA)"})

    @classmethod
    def example(cls) -> dict:
        return {
            "storage_used": 1024,
            "storage_limit": 512000,
            "soft_quota_value": 10000,
        }


class MailboxCreateSchema(Schema):
    """
    Schema for POST /mailboxes - Create a new external mailbox account
    The server will generate the account hash and identity hashes
    Identities are provided as a list instead of a dict
    """
    name = fields.String(required=True, validate=validate.Length(min=1))
    mail_server = fields.Nested(MailServerSchema, required=True)
    receipts = fields.Dict(required=False, load_default={})
    identities = fields.List(
        fields.Nested(IdentitySchema),
        required=True
    )
    certificates = fields.Dict(required=False, load_default={})
    mail_outgoing = fields.Nested(MailOutgoingSchema, required=True)

    @classmethod
    def example(cls) -> dict:
        """Example data for creating a mailbox.
        
        :return: Example mailbox creation payload
        :rtype: dict
        """
        return {
            "name": "External Account",
            "mail_server": {
                "server": "imap.example.com",
                "port": 993,
                "encryption": "None",
                "type": "imap",
                "password": "secure_password",
                "username": "user@example.com",
                "auth_mech": "plain"
            },
            "receipts": {},
            "identities": [
                {
                    "mail": "user@example.com",
                    "name": "John Doe",
                    "replyTo": "noreply@example.com",
                    "isDefault": True,
                    "signatures": {"default": "Best regards,\nJohn Doe", "professional": "Sincerely,\nJohn Doe"}
                },
                {
                    "mail": "user2@example.com",
                    "name": "John Doe",
                    "replyTo": "noreply@example.com",
                    "isDefault": False,
                    "signatures": {}
                }
            ],
            "certificates": {},
            "mail_outgoing": {
                "server": "smtp.example.com",
                "port": 587,
                "encryption": "StartTLS",
                "password": "secure_password",
                "username": "user@example.com",
                "auth_mech": "plain",
                "type": "smtp"
            }
        }



class MailboxUpdateSchema(Schema):
    """
    Schema for PATCH /mailboxes/<account_id> - Update an existing mailbox
    Uses the same structure as MailboxCreateSchema (identities as a list)
    All fields are optional for partial updates
    """
    # Inherit all fields from MailboxCreateSchema but make them optional
    name = fields.String(required=False, validate=validate.Length(min=1))
    mail_server = fields.Nested(MailServerUpdateSchema, required=False)
    mail_outgoing = fields.Nested(MailOutgoingUpdateSchema, required=False)
    identities = fields.List(
        fields.Nested(IdentitySchema),
    )
    receipts = fields.Dict(required=False)
    certificates = fields.Dict(required=False)

    @classmethod
    def example(cls) -> dict:
        """Example data for updating a mailbox.
        
        :return: Example mailbox update payload
        :rtype: dict
        """
        return {
            "name": "Updated External Account",
            "mail_server": {
                "server": "imap.newserver.com",
                "port": 993,
                "encryption": "None",
                "type": "imap",
                "password": "new_secure_password",
                "username": "newuser@example.com",
                "auth_mech": "plain"
            },
            "receipts": {},
            "identities": [
                {
                    "mail": "newuser@example.com",
                    "name": "Jane Doe",
                    "replyTo": "noreply@example.com",
                    "isDefault": True,
                    "signatures": {"default": "Kind regards,\nJane"}
                }
            ],
            "certificates": {},
            "mail_outgoing": {
                "server": "smtp.newserver.com",
                "port": 465,
                "encryption": "None",
                "password": "new_secure_password",
                "username": "newuser@example.com",
                "auth_mech": "plain",
                "type": "smtp"
            }
        }


class MailboxResponseSchema(ApiBaseResponse):
    """
    Schema for response when getting or creating a mailbox
    """
    data = fields.Dict(required=False, allow_none=True)

    @classmethod
    def example(cls) -> dict:
        """Example response for mailbox operations.
        
        :return: Example mailbox response
        :rtype: dict
        """
        return {
            "error_code": 0,
            "error_msg": "",
            "data": {
                "name": "External Account",
                "mail_server": {
                    "server": "imap.example.com",
                    "port": 993,
                    "encryption": "None",
                    "type": "imap",
                    "password": "secure_password",
                    "username": "user@example.com",
                    "auth_mech": "plain"
                },
                "receipts": {},
                "identities": {
                    "0000": {
                        "mail": "user@example.com",
                        "name": "John Doe",
                        "replyTo": "noreply@example.com",
                        "isDefault": True,
                        "signatures": {"default": "Best regards,\nJohn Doe"}
                    }
                },
                "certificates": {},
                "mail_outgoing": {
                    "server": "smtp.example.com",
                    "port": 587,
                    "encryption": "None",
                    "password": "secure_password",
                    "username": "user@example.com",
                    "auth_mech": "plain",
                    "type": "smtp"
                },
                "quota": {
                    "storage_used": 1024,
                    "storage_limit": 512000,
                }
            }
        }


class MailboxListResponseSchema(ApiBaseResponse):
    """
    Schema for response when listing all mailboxes
    The 'data' field contains a list of accounts
    """
    data = fields.List(fields.Dict(), required=False, allow_none=True)

    @classmethod
    def example(cls) -> dict:
        """Example response for listing mailboxes.
        
        :return: Example mailbox list response
        :rtype: dict
        """
        return {
            "error_code": 0,
            "error_msg": "",
            "data": [
                {
                    "id": "0",
                    "name": "Main Account",
                    "mail_server": {
                        "server": "imap.main.com",
                        "port": 993,
                        "encryption": "None",
                        "type": "imap",
                        "username": "main@example.com",
                        "auth_mech": "plain"
                    },
                    "identities": {
                        "0000": {
                            "mail": "main@example.com",
                            "name": "Main User",
                            "isDefault": True
                        }
                    },
                    "mail_outgoing": {
                        "server": "smtp.main.com",
                        "port": 587,
                        "encryption": "None"
                    }
                },
                {
                    "id": "DRFK",
                    "name": "External Account 1",
                    "mail_server": {
                        "server": "imap.example.com",
                        "port": 993,
                        "encryption": "None",
                        "type": "imap",
                        "username": "user@example.com",
                        "auth_mech": "plain"
                    },
                    "identities": {
                        "0000": {
                            "mail": "user@example.com",
                            "name": "John Doe",
                            "isDefault": True
                        }
                    },
                    "mail_outgoing": {
                        "server": "smtp.example.com",
                        "port": 587,
                        "encryption": "None"
                    }
                }
            ]
        }


class DelegationSchema(Schema):
    """
    Schema for a single delegation entry
    """
    email = fields.String(required=True, validate=validate.Email())

    @classmethod
    def example(cls) -> dict:
        """Example data for a delegation.
        
        :return: Example delegation
        :rtype: dict
        """
        return {
            "email": "delegate@example.com"
        }


class DelegationCreateSchema(Schema):
    """
    Schema for POST /mailboxes/<account_id>/delegate - Add a delegation
    """
    email = fields.Email(required=True)

    @classmethod
    def example(cls) -> dict:
        """Example data for creating a delegation.
        
        :return: Example delegation creation payload
        :rtype: dict
        """
        return {
            "emails": ["delegate@example.com", "delegate2@example.com"]
        }


class DelegationListResponseSchema(ApiBaseResponse):
    """
    Schema for response when listing delegations
    The 'data' field contains a list of email addresses
    """
    data = fields.List(fields.String(), required=False, allow_none=True)

    @classmethod
    def example(cls) -> dict:
        """Example response for listing delegations.
        
        :return: Example delegation list response
        :rtype: dict
        """
        return {
            "error_code": 0,
            "error_msg": "",
            "data": [
                "delegate1@example.com",
                "delegate2@example.com"
            ]
        }


class DelegationResponseSchema(ApiBaseResponse):
    """
    Schema for response when creating a delegation
    """
    data = fields.String(required=False, allow_none=True)

    @classmethod
    def example(cls) -> dict:
        """Example response for creating a delegation.
        
        :return: Example delegation creation response
        :rtype: dict
        """
        return {
            "error_code": 0,
            "error_msg": "",
            "data": "delegate@example.com"
        }
