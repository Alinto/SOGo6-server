from app.utils.strings import parse_url_str

a = "https://127.0.0.0.1:8080/path?key1=value1&key1=value2&key2=value3"

print(parse_url_str(a))