"""Unit tests for FileAdapter: save_all (validate + offload), load_all, purge_orphans."""
import pytest

from app.utils.file.FileAdapter import FileAdapter
from app.utils import errors as err
from app.utils.exceptions import RequestException
from app.utils.uri.DataUri import DataUri

_MAX = 10 * 1024 * 1024
_ALLOWED = frozenset({"image/png", "image/jpeg", "image/gif"})


def _png(suffix=b""):
    return b"\x89PNG\r\n\x1a\n" + suffix


class FakeFileAdapter(FileAdapter):
    """In-memory FileAdapter tracking stored blobs and deletions."""

    def __init__(self):
        self.blobs = {}
        self.deleted = []
        self._counter = 0

    def save(self, data, content_type):
        self._counter += 1
        key = f"k{self._counter}"
        self.blobs[key] = (data, content_type)
        return self._make_reference(key)

    def load(self, ref):
        if not self.is_reference(ref):
            return None
        return self.blobs.get(self._reference_key(ref))

    def matches(self, ref, data):
        payload = self.load(ref)
        return payload is not None and payload[0] == data

    def delete(self, ref):
        if self.is_reference(ref):
            self.deleted.append(ref)
            self.blobs.pop(self._reference_key(ref), None)

    def _all_references(self):
        return {self._make_reference(key) for key in self.blobs}


def _save_all(fa, previous, incoming):
    return fa.save_all(previous, incoming, _MAX, _ALLOWED)


# ========== load_all ==========

def test_load_all_turns_reference_into_data_uri():
    fa = FakeFileAdapter()
    ref = fa.save(b"\xff\xd8\xff", "image/jpeg")
    result = fa.load_all([ref, "https://example.com/p.png"])
    assert result == [DataUri.build("image/jpeg", b"\xff\xd8\xff"), "https://example.com/p.png"]


def test_load_all_drops_dangling_reference():
    fa = FakeFileAdapter()
    assert fa.load_all([f"{FileAdapter.REFERENCE_PREFIX}ghost"]) == []


# ========== save_all: validation ==========

def test_save_all_rejects_oversized_payload():
    fa = FakeFileAdapter()
    big = DataUri.build("image/png", _png(b"\x00" * _MAX))
    with pytest.raises(RequestException) as exc:
        _save_all(fa, [], [big])
    assert exc.value.error == err.ERROR_FILE_TOO_LARGE
    assert fa.blobs == {}  # nothing stored on rejection


def test_save_all_rejects_disallowed_type():
    fa = FakeFileAdapter()
    pdf = DataUri.build("image/png", b"%PDF-1.7\nbody")  # sniffs as application/pdf
    with pytest.raises(RequestException) as exc:
        _save_all(fa, [], [pdf])
    assert exc.value.error == err.ERROR_FILE_TYPE_NOT_ALLOWED


def test_save_all_rejects_unrecognised_bytes():
    fa = FakeFileAdapter()
    with pytest.raises(RequestException) as exc:
        _save_all(fa, [], [DataUri.build("image/png", b"not an image")])
    assert exc.value.error == err.ERROR_FILE_TYPE_NOT_ALLOWED


def test_save_all_rejects_non_base64_data_uri():
    fa = FakeFileAdapter()
    with pytest.raises(RequestException) as exc:
        _save_all(fa, [], ["data:text/html,<script>alert(1)</script>"])  # no ;base64 -> never stored
    assert exc.value.error == err.ERROR_FILE_TYPE_NOT_ALLOWED


def test_save_all_rejects_non_http_scheme():
    fa = FakeFileAdapter()
    with pytest.raises(RequestException) as exc:
        _save_all(fa, [], ["javascript:alert(1)"])
    assert exc.value.error == err.ERROR_FILE_TYPE_NOT_ALLOWED


def test_save_all_allows_http_external_uri():
    fa = FakeFileAdapter()
    assert _save_all(fa, [], ["https://example.com/p.png"]) == ["https://example.com/p.png"]


# ========== save_all: typing ==========

def test_save_all_stores_sniffed_type_not_declared_one():
    # A polyglot: GIF bytes declared text/html are accepted (gif is allowed) and stored as image/gif.
    fa = FakeFileAdapter()
    _save_all(fa, [], [DataUri.build("text/html", b"GIF89a<script>alert(1)</script>")])
    (_, content_type), = fa.blobs.values()
    assert content_type == "image/gif"


def test_save_all_corrects_mislabeled_type():
    fa = FakeFileAdapter()
    _save_all(fa, [], [DataUri.build("image/png", b"\xff\xd8\xff jpeg bytes")])  # declared png, really jpeg
    (_, content_type), = fa.blobs.values()
    assert content_type == "image/jpeg"


# ========== save_all: offload / dedup / orphans ==========

def test_save_all_first_write_offloads_inline_and_keeps_uri():
    fa = FakeFileAdapter()
    result = _save_all(fa, [], [DataUri.build("image/png", _png()), "https://example.com/p.png"])
    assert len(fa.blobs) == 1
    assert FileAdapter.is_reference(result[0])
    assert result[1] == "https://example.com/p.png"


def test_save_all_roundtrip_reuses_blob():
    fa = FakeFileAdapter()
    ref = fa.save(_png(b"a"), "image/png")
    result = _save_all(fa, [ref], [DataUri.build("image/png", _png(b"a"))])  # same bytes round-tripped
    assert result == [ref]
    assert fa.deleted == [] and len(fa.blobs) == 1


def test_save_all_replace_leaves_old_blob_as_orphan():
    # save_all never deletes: the replaced blob is left for the orphan sweep, not removed in-place.
    fa = FakeFileAdapter()
    ref = fa.save(_png(b"old"), "image/png")
    result = _save_all(fa, [ref], [DataUri.build("image/png", _png(b"new"))])
    assert FileAdapter.is_reference(result[0]) and result[0] != ref
    assert ref not in fa.deleted
    assert fa.purge_orphans(set(result)) == 1  # reclaimed later by clean()/purge_orphans


def test_save_all_removal_leaves_old_blob_as_orphan():
    fa = FakeFileAdapter()
    ref = fa.save(_png(), "image/png")
    assert _save_all(fa, [ref], []) == []
    assert ref not in fa.deleted
    assert fa.purge_orphans(set()) == 1


def test_save_all_keeps_own_reference_passthrough():
    fa = FakeFileAdapter()
    ref = fa.save(_png(), "image/png")
    result = _save_all(fa, [ref], [ref])  # raw reference (e.g. a PATCH merge from the stored form)
    assert result == [ref] and ref not in fa.deleted


def test_save_all_drops_foreign_reference():
    fa = FakeFileAdapter()
    result = _save_all(fa, [], [f"{FileAdapter.REFERENCE_PREFIX}foreign"])  # a reference never owned
    assert result == [] and fa.deleted == []


# ========== purge_orphans ==========

def test_purge_orphans_deletes_unreferenced_blobs():
    fa = FakeFileAdapter()
    kept = fa.save(b"keep", "image/png")
    orphan = fa.save(b"drop", "image/png")
    removed = fa.purge_orphans({kept})
    assert removed == 1
    assert orphan in fa.deleted and kept not in fa.deleted
    assert list(fa.blobs) == [fa._reference_key(kept)]


def test_purge_orphans_keeps_everything_when_all_referenced():
    fa = FakeFileAdapter()
    refs = {fa.save(b"a", "image/png"), fa.save(b"b", "image/png")}
    assert fa.purge_orphans(refs) == 0 and fa.deleted == []
