import pytest

from app.utils.strings import get_domain_from_mail, strip_accents

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
