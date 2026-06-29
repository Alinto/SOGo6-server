"""Unit tests for the low-level vCard content-line codec (FormatEngineVcard)."""
from app.module.contact.format.ContentLine import ContentLine
from app.module.contact.format.vcard.FormatEngineVcard import FormatEngineVcard


# ========== unfold ==========

def test_unfold_joins_continuation_lines():
    text = "NOTE:line one\r\n  still one\r\nFN:John"
    assert FormatEngineVcard.unfold(text) == ["NOTE:line one still one", "FN:John"]


def test_unfold_accepts_bare_lf():
    assert FormatEngineVcard.unfold("A:1\nB:2") == ["A:1", "B:2"]


# ========== fold ==========

def test_fold_short_line_unchanged():
    assert FormatEngineVcard.fold("FN:John Doe") == "FN:John Doe"


def test_fold_unfold_round_trip_ascii():
    line = "NOTE:" + "x" * 300
    assert FormatEngineVcard.unfold(FormatEngineVcard.fold(line)) == [line]


def test_fold_does_not_split_multibyte_and_round_trips():
    line = "NOTE:" + "é" * 100  # 2 octets each, crosses several 75-octet boundaries
    folded = FormatEngineVcard.fold(line)
    assert "\r\n " in folded
    assert FormatEngineVcard.unfold(folded) == [line]


# ========== parse_line ==========

def test_parse_simple():
    cl = FormatEngineVcard.parse_line("FN:John Doe")
    assert cl.name == "FN" and cl.value == "John Doe" and cl.params == {} and cl.group is None


def test_parse_type_comma_list_and_repeated():
    assert FormatEngineVcard.parse_line("TEL;TYPE=work,voice:+33").param_values("type") == ["work", "voice"]
    assert FormatEngineVcard.parse_line("TEL;TYPE=work;TYPE=home:+1").param_values("TYPE") == ["work", "home"]


def test_parse_bare_type_shorthand():
    # vCard 2.1 / 3.0 style: a bare parameter is a TYPE value.
    assert FormatEngineVcard.parse_line("TEL;WORK:+1").param_values("type") == ["WORK"]


def test_parse_quoted_param_keeps_inner_comma():
    cl = FormatEngineVcard.parse_line('X-FOO;LABEL="a,b":v')
    assert cl.param_values("label") == ["a,b"]


def test_parse_value_with_colon():
    assert FormatEngineVcard.parse_line("URL:https://example.com").value == "https://example.com"


def test_parse_group_prefix():
    cl = FormatEngineVcard.parse_line("item1.X-ABLabel:Home")
    assert cl.group == "item1" and cl.name == "X-ABLABEL" and cl.value == "Home"


# ========== emit_line ==========

def test_emit_with_params():
    cl = ContentLine(name="TEL", value="+33", params={"TYPE": ["work", "voice"]})
    assert FormatEngineVcard.emit_line(cl) == "TEL;TYPE=work,voice:+33"


def test_emit_quotes_param_with_special_char():
    cl = ContentLine(name="X-FOO", value="v", params={"LABEL": ["a,b"]})
    assert FormatEngineVcard.emit_line(cl) == 'X-FOO;LABEL="a,b":v'


def test_emit_with_group():
    cl = ContentLine(name="X-ABLABEL", value="Home", group="item1")
    assert FormatEngineVcard.emit_line(cl) == "item1.X-ABLABEL:Home"


def test_emit_then_parse_round_trip():
    cl = ContentLine(name="EMAIL", value="a@x.com", params={"TYPE": ["work"], "PREF": ["1"]})
    parsed = FormatEngineVcard.parse_line(FormatEngineVcard.emit_line(cl))
    assert parsed.name == "EMAIL" and parsed.value == "a@x.com"
    assert parsed.param_values("type") == ["work"] and parsed.first_param("pref") == "1"


# ========== escaping ==========

def test_escape_unescape_round_trip():
    raw = "a,b;c\nd\\e"
    assert FormatEngineVcard.escape_text(raw) == "a\\,b\\;c\\nd\\\\e"
    assert FormatEngineVcard.unescape_text(FormatEngineVcard.escape_text(raw)) == raw


# ========== structured / multi value ==========

def test_split_components_respects_escaped_semicolon():
    assert FormatEngineVcard.split_components("a;b\\;c;d") == ["a", "b\\;c", "d"]


def test_split_values_respects_escaped_comma():
    assert FormatEngineVcard.split_values("x\\,y,z") == ["x\\,y", "z"]


# ========== split_cards ==========

def test_split_cards_returns_each_body_without_delimiters():
    doc = ("BEGIN:VCARD\r\nVERSION:4.0\r\nFN:Alice\r\nEND:VCARD\r\n"
           "BEGIN:VCARD\r\nVERSION:3.0\r\nFN:Bob\r\nEND:VCARD\r\n")
    cards = FormatEngineVcard.split_items(doc)
    assert len(cards) == 2
    assert FormatEngineVcard.parse_item(cards[0])[0].name == "VERSION"
    assert any(cl.name == "FN" and cl.value == "Alice" for cl in FormatEngineVcard.parse_item(cards[0]))
    assert any(cl.value == "Bob" for cl in FormatEngineVcard.parse_item(cards[1]))
