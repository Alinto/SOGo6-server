"""Names for MIME parts the webmail can download.

Regular attachments keep their filename. Inline images referenced from the HTML
body (``src="cid:…"``) often have no filename, only a ``Content-ID``. Both the
mail parser and the attachment download must derive the same name from that id,
otherwise the browser asks for a file the server cannot find.
"""
from __future__ import annotations

from email.header import decode_header, make_header
from email.message import Message
from typing import Iterator

_SIGNATURE_TYPES = (
    "application/pkcs7-signature",
    "application/x-pkcs7-signature",
    "application/pgp-signature",
)
_ENCRYPTED_TYPES = ("application/pkcs7-mime", "application/x-pkcs7-mime")


def content_id_value(part: Message) -> str | None:
    """Return the Content-ID without the surrounding angle brackets.

    :param part: A MIME part.
    :return: The identifier, or None when the part has no Content-ID.
    """
    raw = part.get("Content-ID")
    if not raw:
        return None
    value = str(raw).strip()
    if value.startswith("<") and value.endswith(">"):
        value = value[1:-1].strip()
    return value or None


def content_id_filename(content_id: str) -> str:
    """Turn a Content-ID into a single path segment.

    ``logo.png@mail.example`` becomes ``logo.png``, which is what HTML refers to
    as ``cid:logo.png``. Slashes are stripped so the value can be one URL segment.

    :param content_id: Content-ID without angle brackets.
    :return: A filename safe to put in an attachment URL.
    """
    local = content_id.split("@", 1)[0].strip()
    name = local.replace("\\", "_").replace("/", "_").replace("\x00", "").strip()
    return name or "inline-image"


def unique_filename(filename: str, used: list[str]) -> str:
    """Return *filename*, or ``name(n).ext`` when it is already used.

    :param filename: Desired filename.
    :param used: Filenames already assigned in this message.
    :return: A filename that is not in *used*.
    """
    if filename not in used:
        return filename
    if "." in filename:
        dot_idx = filename.rfind(".")
        stem = filename[:dot_idx]
        ext = filename[dot_idx:]
    else:
        stem = filename
        ext = ""
    index = 1
    while True:
        candidate = f"{stem}({index}){ext}"
        if candidate not in used:
            return candidate
        index += 1


def decoded_filename(part: Message) -> str | None:
    """Return the part filename with RFC 2047 words decoded.

    :param part: A MIME part.
    :return: The filename, or None when the part has none.
    """
    filename = part.get_filename()
    if not filename:
        return None
    try:
        return str(make_header(decode_header(filename)))
    except (UnicodeDecodeError, AttributeError):
        return str(filename)


def iter_named_parts(message: Message) -> Iterator[tuple[Message, str, str | None]]:
    """Yield each downloadable part with the name the API will expose.

    A part is downloadable when it is a classic attachment (disposition
    ``attachment`` or a filename) or an inline image identified only by its
    Content-ID. Signature and encrypted parts are skipped, as they are in the
    mail parser.

    :param message: The parsed mail.
    :return: ``(part, filename, content_id)`` in walk order.
    """
    used: list[str] = []
    for part in message.walk():
        if part.get_content_maintype() == "multipart":
            continue
        content_type = part.get_content_type()
        if content_type in _SIGNATURE_TYPES:
            continue
        if content_type in _ENCRYPTED_TYPES and "smime-type=enveloped-data" in str(part):
            continue

        content_disposition = str(part.get("Content-Disposition", ""))
        filename = None
        if "attachment" in content_disposition.lower() or part.get_filename():
            filename = decoded_filename(part)
        elif part.get_content_maintype() == "image":
            content_id = content_id_value(part)
            if content_id:
                filename = content_id_filename(content_id)
        if not filename:
            continue

        filename = unique_filename(filename, used)
        used.append(filename)
        yield part, filename, content_id_value(part)


def find_named_part(message: Message, filename: str) -> Message | None:
    """Return the part whose download name is *filename*.

    :param message: The parsed mail.
    :param filename: Name requested by the client.
    :return: The matching part, or None.
    """
    for part, name, _content_id in iter_named_parts(message):
        if name == filename:
            return part
    return None
