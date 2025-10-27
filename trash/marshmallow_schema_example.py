import marshmallow as ma

class Item(ma.Schema):
    name = ma.fields.String()
    mail = ma.fields.Email()
    id = ma.fields.Integer()

class ItemRequired(ma.Schema):
    name = ma.fields.String()
    mail = ma.fields.Email(required=True)
    id = ma.fields.Integer()

    @ma.validates_schema
    def validate_lower_bound(self, data: dict, **kwargs: dict) -> None:
        errors = {}
        if data["id"] == 2 and "mail" not in data:
            errors["mail"] = ["mail is required when id = 2"]
        if errors:
            raise ma.ValidationError(errors)


class ItemUrl(ma.Schema):
    url = ma.fields.Url(schemes={"ldap"})

class ListItem(ma.Schema):
    accounts = ma.fields.List(ma.fields.Nested(Item))

class ItemFrom(ma.Schema):
    from_ = ma.fields.String(required=True, data_key="from", attribute="from")

item1 = {
    "name": "dude",
    "mail": "dude@test.com",
    "id": 0
}
item2 = {
    "name": "hewill",
    "mail": "hewill@test.com",
    "id": 1
}
item3 = {
    "name": "hewill",
    "id": 1
}

item4 = {
    "name": "hewill",
    "id": 2
}

item_url = {
    "url": "ldap://localhost:5000"
}
list_items = {"accounts": [item1, item2]}

item_from = {
    "from": "banane"
}

# schema_item = Item()
# ret = schema_item.load(item3)
# print(ret)

# schema_item2 = ItemRequired()
# ret = schema_item2.load(item3, partial=True)
# print(ret)

# ret = schema_item2.load(item4, partial=True)
# print(ret)


# schema = ListItem()
# ret = schema.load(list_items)

# schema = ItemUrl()
# ret = schema.load(item_url)

schema = ItemFrom()
ret = schema.load(item_from)

print(ret)
