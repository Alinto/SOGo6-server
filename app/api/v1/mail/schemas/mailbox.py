from typing import Any
from marshmallow import Schema, fields, validate
from app.utils.api.ApiBaseResponse import ApiBaseResponse


def validate_email_or_empty(value: Any) -> None:
    """
    Validate that the value is either an empty string or a valid email address.
    
    :param value: The value to validate
    :raises ValidationError: If value is not empty and not a valid email
    """
    if value and value.strip():  # If not empty or only whitespace
        email_validator = validate.Email()
        email_validator(value)
    # If empty or None, validation passes


class MailServerSchema(Schema):
    """
    Schema for incoming mail server configuration (IMAP/POP3)
    """
    server = fields.String(required=True, validate=validate.Length(min=1))
    port = fields.Integer(required=True, validate=validate.Range(min=1, max=65535))
    encryption = fields.String(
        required=True,
        validate=validate.OneOf(["none", "ssl", "tls", "starttls"])
    )
    type_ = fields.String(
        required=True,
        validate=validate.OneOf(["imap", "jmap"]),
        data_key="type"
    )
    password = fields.String(required=True, validate=validate.Length(min=1))
    username = fields.String(required=True, validate=validate.Length(min=1))
    authMech = fields.String(
        required=False,
        allow_none=True,
        validate=validate.OneOf(["plain", "login", "xoauth2"])
    )

    @classmethod
    def example(cls) -> dict:
        """Example data for mail server configuration.
        
        :return: Example mail server configuration
        :rtype: dict
        """
        return {
            "server": "imap.example.com",
            "port": 993,
            "encryption": "ssl",
            "type": "imap",
            "password": "secure_password",
            "username": "user@example.com",
            "authMech": "plain"
        }


class MailOutgoingSchema(Schema):
    """
    Schema for outgoing mail server configuration (SMTP)
    """
    server = fields.String(required=True, validate=validate.Length(min=1))
    port = fields.Integer(required=True, validate=validate.Range(min=1, max=65535))
    encryption = fields.String(
        required=True,
        validate=validate.OneOf(["none", "ssl", "tls", "starttls"])
    )
    password = fields.String(required=True, validate=validate.Length(min=1))
    username = fields.String(required=True, validate=validate.Length(min=1))
    authMech = fields.String(
        required=False,
        allow_none=True,
        validate=validate.OneOf(["plain", "login", "xoauth2"])
    )
    type_ = fields.String(
        required=True,
        validate=validate.OneOf(["smtp"]),
        data_key="type"
    )

    @classmethod
    def example(cls) -> dict:
        """Example data for outgoing mail server configuration.
        
        :return: Example outgoing mail server configuration
        :rtype: dict
        """
        return {
            "server": "smtp.example.com",
            "port": 587,
            "encryption": "starttls",
            "password": "secure_password",
            "username": "user@example.com",
            "authMech": "plain",
            "type": "smtp"
        }


class IdentitySchema(Schema):
    """
    Schema for email identity
    """
    mail = fields.String(required=True, validate=validate.Email())
    name = fields.String(required=True, validate=validate.Length(min=1))
    replyTo = fields.String(required=False, allow_none=True, validate=validate_email_or_empty)
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
        required=True,
        load_default=[]
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
                "encryption": "ssl",
                "type": "imap",
                "password": "secure_password",
                "username": "user@example.com",
                "authMech": "plain"
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
                "encryption": "starttls",
                "password": "secure_password",
                "username": "user@example.com",
                "authMech": "plain",
                "type": "smtp"
            }
        }


class MailboxUpdateSchema(MailboxCreateSchema):
    """
    Schema for PATCH /mailboxes/<account_id> - Update an existing mailbox
    Uses the same structure as MailboxCreateSchema (identities as a list)
    All fields are optional for partial updates
    """
    # Inherit all fields from MailboxCreateSchema but make them optional
    name = fields.String(required=False, validate=validate.Length(min=1))
    mail_server = fields.Nested(MailServerSchema, required=False)
    mail_outgoing = fields.Nested(MailOutgoingSchema, required=False)
    identities = fields.List(
        fields.Nested(IdentitySchema),
        required=False,
        load_default=[]
    )

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
                "encryption": "ssl",
                "type": "imap",
                "password": "new_secure_password",
                "username": "newuser@example.com",
                "authMech": "plain"
            },
            "receipts": {},
            "identities": [
                {
                    "mail": "newuser@example.com",
                    "name": "Jane Doe",
                    "replyTo": "",
                    "isDefault": True,
                    "signatures": {"default": "Kind regards,\nJane"}
                }
            ],
            "certificates": {},
            "mail_outgoing": {
                "server": "smtp.newserver.com",
                "port": 465,
                "encryption": "ssl",
                "password": "new_secure_password",
                "username": "newuser@example.com",
                "authMech": "plain",
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
                    "encryption": "ssl",
                    "type": "imap",
                    "password": "secure_password",
                    "username": "user@example.com",
                    "authMech": "plain"
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
                    "encryption": "starttls",
                    "password": "secure_password",
                    "username": "user@example.com",
                    "authMech": "plain",
                    "type": "smtp"
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
                        "encryption": "ssl",
                        "type": "imap",
                        "username": "main@example.com",
                        "authMech": "plain"
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
                        "encryption": "starttls"
                    }
                },
                {
                    "id": "DRFK",
                    "name": "External Account 1",
                    "mail_server": {
                        "server": "imap.example.com",
                        "port": 993,
                        "encryption": "ssl",
                        "type": "imap",
                        "username": "user@example.com",
                        "authMech": "plain"
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
                        "encryption": "starttls"
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
    email = fields.String(required=True, validate=validate.Email())

    @classmethod
    def example(cls) -> dict:
        """Example data for creating a delegation.
        
        :return: Example delegation creation payload
        :rtype: dict
        """
        return {
            "email": "delegate@example.com"
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
