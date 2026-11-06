"""Inline images referenced by Content-ID are exposed as downloadable parts."""
from email.message import EmailMessage
from unittest.mock import MagicMock

from app.module.mail.ModuleMail import ModuleMail
from app.module.mail.mime_cid import find_named_part, iter_named_parts


def _quarantine_message() -> EmailMessage:
    """HTML body plus two inline PNGs, the same shape as a Cleanmail report."""
    message = EmailMessage()
    message["Subject"] = "Rapport de quarantaine"
    message["From"] = "noreply@alinto.net"
    message["To"] = "retd@dev.alinto.org"
    message.set_content("plain report")
    message.add_alternative(
        '<img src="cid:logo.png" width="70"><img src="cid:show.png">',
        subtype="html",
    )
    related = message.get_payload()[-1]
    related.add_related(
        b"\x89PNG-logo",
        maintype="image",
        subtype="png",
        cid="<logo.png>",
        disposition="inline",
    )
    related.add_related(
        b"\x89PNG-show",
        maintype="image",
        subtype="png",
        cid="<show.png@cleanmail.eu>",
        disposition="inline",
    )
    return message


def test_iter_named_parts_names_inline_images_from_content_id():
    names = [(name, content_id) for _part, name, content_id in iter_named_parts(_quarantine_message())]

    assert ("logo.png", "logo.png") in names
    assert ("show.png", "show.png@cleanmail.eu") in names


def test_find_named_part_returns_the_inline_bytes():
    part = find_named_part(_quarantine_message(), "logo.png")

    assert part is not None
    assert part.get_payload(decode=True) == b"\x89PNG-logo"


def test_parse_mail_lists_inline_images_with_content_id():
    module = ModuleMail(MagicMock(), MagicMock())
    parsed = module._parse_mail({
        "uid": "42",
        "mail": _quarantine_message(),
        "flags": {},
        "size": 100,
    })

    by_name = {item["filename"]: item for item in parsed["attachments"]}
    assert by_name["logo.png"]["contentId"] == "logo.png"
    assert by_name["logo.png"]["contentType"] == "image/png"
    assert by_name["show.png"]["contentId"] == "show.png@cleanmail.eu"
    html = next(item["content"] for item in parsed["contents"] if item["contentType"] == "text/html")
    assert "cid:logo.png" in html
