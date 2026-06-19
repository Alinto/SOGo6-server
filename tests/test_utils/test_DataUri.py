"""Unit tests for DataUri (base64 RFC 2397 data URI parse/build)."""
from app.utils.uri.DataUri import DataUri


def test_build_then_parse_roundtrip():
    raw = b"\xff\xd8\xff\x00\x10"
    uri = DataUri.build("image/jpeg", raw)
    assert uri.startswith("data:image/jpeg;base64,")
    assert DataUri.parse(uri) == ("image/jpeg", raw)


def test_parse_rejects_non_data_uri():
    assert DataUri.parse("https://example.com/p.jpg") is None


def test_parse_rejects_non_base64_data_uri():
    assert DataUri.parse("data:text/plain,hello") is None


def test_parse_rejects_invalid_base64():
    assert DataUri.parse("data:image/png;base64,not valid !!") is None


def test_unwrap_then_wrap_roundtrip_keeps_payload():
    uri = DataUri.build("image/jpeg", b"\xff\xd8\xff")
    content_type, payload = DataUri.unwrap_base64(uri)
    assert content_type == "image/jpeg"
    assert DataUri.wrap_base64(content_type, payload) == uri  # no decode/re-encode drift


def test_unwrap_rejects_non_base64_data_uri():
    assert DataUri.unwrap_base64("data:text/plain,hello") is None
