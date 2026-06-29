import pytest

from app.utils.strings import get_domain_from_mail, strip_accents, parse_url_str

def test_get_domain_from_mail():
    with pytest.raises(TypeError):
        get_domain_from_mail(1)
    assert get_domain_from_mail("aa") is None
    assert get_domain_from_mail("aa@bb.com") == "bb.com"
    assert get_domain_from_mail("aa@bb@cc") is None

def test_strip_accents_diacritics():
    assert strip_accents("Réunion Joël") == "reunion joel"
    assert strip_accents("naïve garçon Crêpe") == "naive garcon crepe"

def test_strip_accents_atomic_letters():
    assert strip_accents("Søren") == "soren"
    assert strip_accents("cœur Æther") == "coeur aether"
    assert strip_accents("Straße") == "strasse"
    assert strip_accents("Łódź") == "lodz"

def test_strip_accents_leaves_non_latin_untouched():
    assert strip_accents("Привет 你好 C++ jean@x.com") == "привет 你好 c++ jean@x.com"

def test_parse_url_str():
    ret1 = parse_url_str("https://username:password@example.com:8080/path?key1=value1&key1=value2&key2=value3")
    ret1_expected = {
        'protocol': 'https',
        'hostname': 'example.com',
        'port': 8080,
        'username': 'username',
        'password': 'password',
        'params': {'key1': ['value1', 'value2'], 'key2': 'value3'}
    }
    assert ret1 == ret1_expected

    ret1 = parse_url_str("https://example.com:8080/path?key1=value1&key1=value2&key2=value3")
    ret1_expected = {
        'protocol': 'https',
        'hostname': 'example.com',
        'port': 8080,
        'username': '',
        'password': '',
        'params': {'key1': ['value1', 'value2'], 'key2': 'value3'}
    }
    assert ret1 == ret1_expected
