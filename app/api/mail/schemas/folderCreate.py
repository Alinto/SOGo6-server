from marshmallow import Schema, fields

class FolderCreateSchema(Schema):
    """
    Schema for creating a new mail folder.
    """
    name = fields.String(required=True)

    @classmethod
    def example(cls) -> dict:
        """
        Example data for folder creation.

        :return: Example folder creation payload.
        :rtype: dict
        """
        return {
            "name": "NewFolder"
        }
