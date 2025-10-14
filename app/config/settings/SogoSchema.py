from marshmallow import Schema

class SogoSchema(Schema):
    """
    Fake Schema for hint typing
    """
    subparent = ""
    dependencies: dict = {}
    is_secret: set = set()