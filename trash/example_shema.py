import marshmallow as ma

class Item(ma.Schema):
    name = ma.fields.String()
    mail = ma.fields.Email()
    id = ma.fields.Integer()

class ListItem(ma.Schema):
    accounts = ma.fields.List(ma.fields.Nested(Item))


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

list_items = {"accounts": [item1, item2]}

schema_item = Item()
ret = schema_item.load(item1)
print(ret)

schema = ListItem()
ret = schema.load(list_items)

print(ret)
