"""Unit tests for MediaType (content-type detection from magic bytes / markup)."""
from app.utils.media.MediaType import MediaType


def test_sniff_known_signatures():
    assert MediaType.get_content_type(b"\xff\xd8\xff\xe0rest") == "image/jpeg"
    assert MediaType.get_content_type(b"\x89PNG\r\n\x1a\nrest") == "image/png"
    assert MediaType.get_content_type(b"GIF89arest") == "image/gif"
    assert MediaType.get_content_type(b"RIFF\x00\x00\x00\x00WEBPrest") == "image/webp"
    assert MediaType.get_content_type(b"BMrest") == "image/bmp"
    assert MediaType.get_content_type(b"%PDF-1.7\nrest") == "application/pdf"


def test_sniff_svg():
    assert MediaType.get_content_type(b"<svg xmlns='http://www.w3.org/2000/svg'></svg>") == "image/svg+xml"
    assert MediaType.get_content_type(b"<?xml version='1.0'?>\n<svg></svg>") == "image/svg+xml"
    assert MediaType.get_content_type(b"\xef\xbb\xbf  <svg></svg>") == "image/svg+xml"  # BOM + whitespace
    assert MediaType.get_content_type(b"<?xml version='1.0'?><rss></rss>") is None       # XML but not SVG


def test_sniff_unknown_returns_none():
    assert MediaType.get_content_type(b"not an image at all") is None
    assert MediaType.get_content_type(b"") is None
