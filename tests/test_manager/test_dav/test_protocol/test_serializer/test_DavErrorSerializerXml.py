"""Unit tests for DavErrorSerializerXml - the body is compared to the expected XML."""

from app.manager.dav.protocol.model.DavError import DavError
from app.manager.dav.protocol.serializer.DavErrorSerializerXml import DavErrorSerializerXml

DECLARATION = b"<?xml version='1.0' encoding='utf-8'?>\n"

# ========== Tests for serialize ==========


def test_condition_in_error():
    body = DavErrorSerializerXml().serialize(DavError(condition="{DAV:}propfind-finite-depth"))
    assert body == DECLARATION + b'<D:error xmlns:D="DAV:"><D:propfind-finite-depth /></D:error>'
