from __future__ import annotations

from typing import Any

from marshmallow import Schema, fields, validate, validates_schema, ValidationError

from app.utils.api.ApiBaseResponse import ApiBaseResponse


class AddressBookCreateSchema(Schema):
    """Request body for creating an address book."""

    name        = fields.String(required=True, validate=validate.Length(min=1, max=255),
                                metadata={"example": "Personal contacts"})
    description = fields.String(load_default=None, allow_none=True,
                                metadata={"example": "My personal address book"})


class AddressBookUpdateSchema(Schema):
    """Request body for updating an address book (all fields optional)."""

    name        = fields.String(validate=validate.Length(min=1, max=255), metadata={"example": "Friends"})
    description = fields.String(allow_none=True)
    is_default  = fields.Boolean(metadata={"description": "Mark this book as the user's default address book."})


class AddressBookSchema(Schema):
    """Representation of an address book in API responses."""

    key         = fields.String()
    name        = fields.String()
    description = fields.String(allow_none=True)
    is_default  = fields.Boolean()
    source_type = fields.String()
    ctag        = fields.Integer(metadata={"description": "CardDAV change tag, bumped on every contact mutation."})


class AddressBookListDataSchema(Schema):
    """Data payload for the address book list response."""

    addressbooks = fields.List(fields.Nested(AddressBookSchema))
    total_count  = fields.Integer()


class AddressBookListResponseSchema(ApiBaseResponse):
    """Response schema for a list of address books."""

    data = fields.Nested(AddressBookListDataSchema, allow_none=True)


class AddressBookResponseSchema(ApiBaseResponse):
    """Response schema for a single address book."""

    data = fields.Nested(AddressBookSchema, allow_none=True)


class ContactImportQueryArgsSchema(Schema):
    """Query arguments for the import endpoints."""

    format = fields.String(load_default="json", validate=validate.OneOf(["json", "vcard3", "vcard4", "ldif"]),
                           metadata={"description": "Source format of the uploaded document (default json)."})


class ContactJobDataSchema(Schema):
    """Payload returned when an import or export is enqueued as an Agent job."""

    job_id = fields.String(required=True, metadata={"description": "Id of the enqueued Agent job. Poll GET /jobs/<job_id> until SUCCESS; import counters are in the job result, export document via GET /jobs/<job_id>/result."})


class ContactJobResponseSchema(ApiBaseResponse):
    """Response schema for the async import/export endpoints (returns a job_id)."""

    data = fields.Nested(ContactJobDataSchema, allow_none=True)


class ContactImportUploadSchema(Schema):
    """Multipart file upload schema for the import endpoint.

    Declares the ``file`` part so Swagger renders an upload widget. The actual binary read happens in
    the view since Marshmallow does not deserialize the FileStorage object.
    """

    file = fields.Raw(
        required=True,
        metadata={"type": "string", "format": "binary",
                  "description": "The JSON (.json), vCard (.vcf) or LDIF (.ldif) file to import."},
    )


class ContactShareRightsSchema(Schema):
    """Permission rights for an address book share."""

    can_view = fields.Boolean(required=True, metadata={"description": "Can view contacts and lists", "example": True})
    can_create_objects = fields.Boolean(required=True, metadata={"description": "Can create contacts and lists", "example": True})
    can_edit_objects = fields.Boolean(required=True, metadata={"description": "Can edit contacts and lists", "example": True})
    can_erase_objects = fields.Boolean(required=True, metadata={"description": "Can delete contacts and lists", "example": False})


class ContactShareUserSchema(Schema):
    """User permission entry in address book sharing.

    ``c_email`` and ``uid`` are required unless ``user_class`` is ``"anyone"``, in which case
    they are ignored (the share applies to any authenticated user, not a specific one).
    """

    c_email = fields.String(required=False, allow_none=True, metadata={"description": "User email address", "example": "jdoe@example.org"})
    uid = fields.String(required=False, allow_none=True, metadata={"description": "User UID", "example": "jdoe"})
    user_class = fields.String(
        required=True,
        validate=validate.OneOf(["user", "anyone"]),
    )
    rights = fields.Nested(ContactShareRightsSchema, required=True, metadata={"description": "Permission rights for this user"})

    @validates_schema
    def validate_user_identity(self, data: dict[str, Any], **kwargs: Any) -> None:  # pylint: disable=unused-argument
        """Require c_email and uid unless user_class is 'anyone'."""
        if data.get("user_class") == "anyone":
            return
        errors: dict[str, list[str]] = {}
        if not data.get("c_email"):
            errors["c_email"] = ["Missing data for required field."]
        if not data.get("uid"):
            errors["uid"] = ["Missing data for required field."]
        if errors:
            raise ValidationError(errors)


class ContactSharePatchSchema(ContactShareUserSchema):
    """Request body item for PATCH /addressbooks/{key}/share - partial update of user permissions.

    The endpoint expects a JSON list of these objects (use with ``many=True``).
    Only the users specified in the request are modified. Other existing permissions remain unchanged.
    """

    class Meta:
        ordered = True

    @staticmethod
    def example() -> list[dict[str, Any]]:
        """Example data for Swagger documentation."""
        return [
            {
                "c_email": "jdoe@example.org",
                "uid": "jdoe",
                "user_class": "user",
                "rights": {
                    "can_view": True,
                    "can_create_objects": True,
                    "can_edit_objects": True,
                    "can_erase_objects": False
                }
            }
        ]


class ContactSharePutSchema(ContactShareUserSchema):
    """Request body item for PUT /addressbooks/{key}/share - replace all user permissions.

    The endpoint expects a JSON list of these objects (use with ``many=True``).
    All existing permissions are replaced by the users specified in the request.
    """

    class Meta:
        ordered = True

    @staticmethod
    def example() -> list[dict[str, Any]]:
        """Example data for Swagger documentation."""
        return [
            {
                "c_email": "jdoe@example.org",
                "uid": "jdoe",
                "user_class": "user",
                "rights": {
                    "can_view": True,
                    "can_create_objects": True,
                    "can_edit_objects": True,
                    "can_erase_objects": False
                }
            },
            {
                "c_email": "alice@example.org",
                "uid": "alice",
                "user_class": "user",
                "rights": {
                    "can_view": True,
                    "can_create_objects": True,
                    "can_edit_objects": True,
                    "can_erase_objects": True
                }
            }
        ]


class ContactSharePostSchema(ContactShareUserSchema):
    """Request body item for POST /addressbooks/{key}/share - grant full permissions to users.

    The endpoint expects a JSON list of these objects (use with ``many=True``).
    Grants full view/create/edit/erase rights to the specified users, regardless of the rights
    carried in the request body.
    """

    class Meta:
        ordered = True

    @staticmethod
    def example() -> list[dict[str, Any]]:
        """Example data for Swagger documentation."""
        return [
            {
                "c_email": "jdoe@example.org",
                "uid": "jdoe",
                "user_class": "user",
                "rights": {
                    "can_view": True,
                    "can_create_objects": True,
                    "can_edit_objects": True,
                    "can_erase_objects": True
                }
            }
        ]


class ContactShareResponseSchema(ApiBaseResponse):
    """Response schema for address book sharing endpoints. ``data`` is a plain list of users."""

    data = fields.List(fields.Nested(ContactShareUserSchema), allow_none=True)

    @staticmethod
    def example() -> dict[str, Any]:
        """Example full envelope for Swagger documentation."""
        return {
            "data": [
                {
                    "c_email": "jdoe@example.org",
                    "uid": "jdoe",
                    "user_class": "user",
                    "rights": {
                        "can_view": True,
                        "can_create_objects": True,
                        "can_edit_objects": True,
                        "can_erase_objects": False
                    }
                }
            ],
            "error_code": "S000000",
            "error_msg": "No Error"
        }
