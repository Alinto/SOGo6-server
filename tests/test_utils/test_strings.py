import pytest

from app.utils.strings import get_domain_from_mail, strip_accents, parse_url_str, quote, unquote, get_invitation_filename

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

def test_unquote():
    assert unquote('"Junk"') == "Junk"
    assert unquote("Junk") == "Junk"
    assert unquote('"') == '"'
    for value in ("My Folder", 'With "quotes"', "Back\\slash"):
        assert unquote(quote(value)) == value


class TestGetInvitationFilename:
    def test_uses_event_uid(self):
        assert get_invitation_filename(b"BEGIN:VEVENT\r\nUID:e34b3139-0bc6\r\nEND:VEVENT\r\n") == "e34b3139-0bc6.ics"

    def test_keeps_email_like_uid(self):
        assert get_invitation_filename(b"UID:abc123@google.com\n") == "abc123@google.com.ics"

    def test_unfolds_long_uid(self):
        assert get_invitation_filename(b"UID:e34b\r\n 3139\r\nEND:VEVENT\r\n") == "e34b3139.ics"

    def test_ignores_other_properties_ending_in_uid(self):
        assert get_invitation_filename(b"X-UID:wrong\r\nUID:right\r\n") == "right.ics"

    def test_sanitizes_path_characters(self):
        filename = get_invitation_filename(b'UID:../../etc/pa"ss\r\n')
        assert "/" not in filename and '"' not in filename

    def test_caps_length(self):
        assert len(get_invitation_filename(b"UID:" + b"a" * 5000 + b"\r\n")) == 204

    def test_falls_back_without_uid(self):
        assert get_invitation_filename(b"BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n") == "invitation.ics"
