"""Unit tests for the low-level LDIF codec (FormatEngineLdif)."""
import base64

from app.module.contact.format.ldif.FormatEngineLdif import FormatEngineLdif


# ========== fold / unfold ==========

def test_fold_short_line_unchanged():
    assert FormatEngineLdif.fold("cn: John Doe") == "cn: John Doe"


def test_fold_unfold_round_trip():
    line = "description: " + "x" * 200
    folded = FormatEngineLdif.fold(line)
    assert "\n " in folded
    assert FormatEngineLdif.unfold(folded) == [line]


def test_fold_does_not_split_multibyte():
    line = "cn: " + "é" * 100
    assert FormatEngineLdif.unfold(FormatEngineLdif.fold(line)) == [line]


# ========== split_items drop logic ==========

def test_split_items_drops_header_comment_and_url():
    doc = ("version: 1\n\n"
           "dn: cn=A,ou=contacts\ncn: A\n# a comment\nmail:< file://somewhere\n\n"
           "dn: cn=B,ou=contacts\ncn: B\n")
    records = FormatEngineLdif.parse_records(doc)
    assert records[0] == [("dn", "cn=A,ou=contacts"), ("cn", "A")]   # header / comment / url dropped
    assert records[1] == [("dn", "cn=B,ou=contacts"), ("cn", "B")]


# ========== base64 (_is_safe) ==========

def test_emit_base64_for_non_ascii_and_unsafe_start():
    assert FormatEngineLdif.emit_attr("cn", "Joël").startswith("cn:: ")        # non-ASCII
    assert FormatEngineLdif.emit_attr("cn", " leading").startswith("cn:: ")    # leading space
    assert FormatEngineLdif.emit_attr("cn", ":colon").startswith("cn:: ")      # leading colon
    assert FormatEngineLdif.emit_attr("cn", "plain value") == "cn: plain value"
    assert base64.b64decode(FormatEngineLdif.emit_attr("cn", " x")[len("cn:: "):]).decode() == " x"


# ========== DN escaping (RFC 4514) ==========

def test_escape_dn_escapes_special_characters():
    assert FormatEngineLdif.escape_dn("Sales, Inc. + Co") == "Sales\\, Inc. \\+ Co"
    assert FormatEngineLdif.escape_dn("a;b<c>d") == "a\\;b\\<c\\>d"
    assert FormatEngineLdif.escape_dn(" leading") == "\\ leading"
    assert FormatEngineLdif.escape_dn("trailing ") == "trailing\\ "
