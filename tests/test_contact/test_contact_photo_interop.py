"""PHOTO interop across formats (vCard 3.0/4.0, LDIF) and the inline -> storage -> inline chain."""
from app.utils.file.FileAdapter import FileAdapter
from app.module.contact.model.CardContact import CardContact
from app.module.contact.serializer.ContactDeserializerLdif import ContactDeserializerLdif
from app.module.contact.serializer.ContactDeserializerVcard3 import ContactDeserializerVcard3
from app.module.contact.serializer.ContactDeserializerVcard4 import ContactDeserializerVcard4
from app.module.contact.serializer.ContactSerializerLdif import ContactSerializerLdif
from app.module.contact.serializer.ContactSerializerVcard3 import ContactSerializerVcard3
from app.module.contact.serializer.ContactSerializerVcard4 import ContactSerializerVcard4
from app.utils.uri.DataUri import DataUri

# Real binary bytes (invalid UTF-8) so the LDIF binary path is genuinely exercised.
_JPEG = bytes([0xFF, 0xD8, 0xFF, 0xE0]) + b"JFIF\x00" + bytes([0x01, 0x02, 0xFE, 0xFF])
_JPEG_URI = DataUri.build("image/jpeg", _JPEG)
_PNG = b"\x89PNG\r\n\x1a\n" + bytes([0x00, 0x01, 0x02, 0xFE, 0xFF])
_PNG_URI = DataUri.build("image/png", _PNG)
_MAX = 10 * 1024 * 1024
_ALLOWED = frozenset({"image/jpeg", "image/png"})


class FakeFileAdapter(FileAdapter):
    """In-memory FileAdapter for the storage round-trip."""

    def __init__(self):
        self.blobs = {}
        self._counter = 0

    def save(self, data, content_type):
        self._counter += 1
        key = f"k{self._counter}"
        self.blobs[key] = (data, content_type)
        return self._make_reference(key)

    def load(self, ref):
        return self.blobs.get(self._reference_key(ref)) if self.is_reference(ref) else None

    def matches(self, ref, data):
        payload = self.load(ref)
        return payload is not None and payload[0] == data

    def delete(self, ref):
        if self.is_reference(ref):
            self.blobs.pop(self._reference_key(ref), None)

    def _all_references(self):
        return {self._make_reference(key) for key in self.blobs}


def _photo_contact():
    return CardContact(display_name="Pic Holder", photos=[_JPEG_URI])


# ========== vCard 4.0 ==========

def test_vcard4_inline_photo_roundtrip():
    card = ContactSerializerVcard4().serialize(_photo_contact())
    assert "PHOTO:data:image/jpeg;base64," in card  # 4.0 carries the data: URI directly
    assert ContactDeserializerVcard4().deserialize(card).photos == [_JPEG_URI]


# ========== vCard 3.0 ==========

def test_vcard3_inline_photo_roundtrip():
    card = ContactSerializerVcard3().serialize(_photo_contact())
    assert "PHOTO;ENCODING=b;TYPE=JPEG:" in card  # 3.0 uses ENCODING=b;TYPE=, not a data: URI
    assert "data:image/jpeg" not in card
    assert ContactDeserializerVcard3().deserialize(card).photos == [_JPEG_URI]


def test_vcard3_external_photo_uri_roundtrip():
    contact = CardContact(display_name="X", photos=["https://example.com/p.jpg"])
    card = ContactSerializerVcard3().serialize(contact)
    assert "PHOTO;VALUE=uri:https://example.com/p.jpg" in card
    assert ContactDeserializerVcard3().deserialize(card).photos == ["https://example.com/p.jpg"]


# ========== LDIF ==========

def test_ldif_inline_photo_roundtrip():
    record = ContactSerializerLdif().serialize(_photo_contact())
    assert "jpegPhoto:: " in record  # binary attribute (double colon)
    assert ContactDeserializerLdif().deserialize(record).photos == [_JPEG_URI]


# ========== type carried by the format (vCard) or recovered by the file layer (LDIF) ==========

def test_vcard4_png_type_preserved():
    # 4.0 carries the type in the data: URI, so a plain round-trip keeps it.
    card = ContactSerializerVcard4().serialize(CardContact(display_name="X", photos=[_PNG_URI]))
    assert ContactDeserializerVcard4().deserialize(card).photos == [_PNG_URI]


def test_vcard3_png_type_preserved():
    # 3.0 carries the type in the TYPE token.
    card = ContactSerializerVcard3().serialize(CardContact(display_name="X", photos=[_PNG_URI]))
    assert "TYPE=PNG" in card
    assert ContactDeserializerVcard3().deserialize(card).photos == [_PNG_URI]


def test_ldif_png_type_recovered_when_saved():
    # LDIF jpegPhoto carries no type; the file layer recovers image/png from the bytes when saved.
    record = ContactSerializerLdif().serialize(CardContact(display_name="X", photos=[_PNG_URI]))
    imported = ContactDeserializerLdif().deserialize(record)
    adapter = FakeFileAdapter()
    imported.photos = adapter.save_all([], imported.photos, _MAX, _ALLOWED)
    assert adapter.load_all(imported.photos) == [_PNG_URI]


# ========== inline -> storage -> inline (Point 3) ==========

def test_vcard4_inline_survives_storage_roundtrip():
    _assert_storage_roundtrip(ContactSerializerVcard4(), ContactDeserializerVcard4().deserialize)


def test_vcard3_inline_survives_storage_roundtrip():
    _assert_storage_roundtrip(ContactSerializerVcard3(), ContactDeserializerVcard3().deserialize)


def test_ldif_inline_survives_storage_roundtrip():
    _assert_storage_roundtrip(ContactSerializerLdif(), ContactDeserializerLdif().deserialize)


def _assert_storage_roundtrip(serializer, deserialize):
    """Import an inline photo, offload it to storage, resolve it back, and re-export it inline."""
    adapter = FakeFileAdapter()
    imported = deserialize(serializer.serialize(_photo_contact()))
    imported.photos = adapter.save_all([], imported.photos, _MAX, _ALLOWED)   # validate + offload
    assert FileAdapter.is_reference(imported.photos[0])             # stored as a reference
    assert len(adapter.blobs) == 1
    imported.photos = adapter.load_all(imported.photos)          # back to inline for export
    assert imported.photos == [_JPEG_URI]
    payload: str = DataUri.unwrap_base64(_JPEG_URI)[1]
    assert payload in serializer.serialize(imported)               # re-exported inline (any format)
