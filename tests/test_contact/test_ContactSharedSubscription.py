"""Unit tests for shared address book subscriptions: listing vs access resolution, discovery and subscribe checks."""
from unittest.mock import MagicMock

import pytest

from app.factory.share.RepositoryAcl import AclEntry
from app.factory.share.shareContact import FULL_MODIFY_RIGHTS, ShareContact
from app.module.contact.ModuleContact import ModuleContact
from app.module.contact.acl.ContactAclEngine import ContactAclEngine
from app.module.contact.model.CardAddressBook import CardAddressBook
from app.module.contact.model.enums.CardSourceType import CardSourceType
from app.module.contact.source.ContactSources import ContactSources
from app.utils import constants as cs
from app.utils import errors as err
from app.utils.exceptions import RequestException

_ME = "bob@example.com"
_OWNER = "alice@example.com"

_VIEW_RIGHTS = {"can_view": True, "can_create_objects": False, "can_edit_objects": False, "can_erase_objects": False}
_NO_VIEW_RIGHTS = {"can_view": False, "can_create_objects": True, "can_edit_objects": True, "can_erase_objects": True}


def _book(key, owner=_OWNER):
    return CardAddressBook(user_uid=owner, name=key, key=key, source_type=CardSourceType.LOCAL)


def _entry(key, to_user=_ME, owner=_OWNER, rights=None):
    return AclEntry(resource_type="addressbook", key=key, owner=owner, to_user=to_user, rights=rights or _VIEW_RIGHTS)


def _user(uid=_ME, subs=None):
    """Acting user whose folders.ADDRESSBOOKS.SUBS holds ``subs`` (key -> display toggle)."""
    user = MagicMock()
    user.uid = uid
    user.mail = uid
    user.folders = {"ADDRESSBOOKS": {"OWNER": {}, "SUBS": dict(subs or {})}}
    return user


def _build_sources(owned=(), by_key=None, direct=(), anyone=()):
    """ContactSources over mocked repositories and a ShareContact resolving rights from the given entries.

    by_key maps a key to its book (find_by_key_only); direct / anyone are the ACL entries returned for
    the user and for the "anyone" pseudo-user of the user's domain.
    """
    by_key = dict(by_key or {})
    sources = object.__new__(ContactSources)
    sources._db = MagicMock()
    sources._repo_addressbook = MagicMock()
    sources._repo_addressbook.find_all.return_value = list(owned)
    sources._repo_addressbook.find_by_key.return_value = None
    sources._repo_addressbook.find_by_key_only.side_effect = by_key.get
    acl: dict[str, AclEntry] = {e.key: e for e in (*direct, *anyone)}
    share = MagicMock()
    share.get_keys_shared_with.return_value = list(direct)
    share.get_keys_shared_with_anyone_in_domain.return_value = list(anyone)
    share.get_user_or_anyone.side_effect = lambda uid, owner, key: acl.get(key)
    share.has_right.side_effect = lambda uid, owner, key, right: key in acl and bool(acl[key].rights.get(right))
    sources._share = share
    return sources


# ========== ContactSources.get_listed ==========

def test_get_listed_returns_owned_and_subscribed_shared():
    sources = _build_sources(owned=[_book("mine", _ME)], by_key={"shared": _book("shared")}, direct=[_entry("shared")])
    assert [s.addressbook.key for s in sources.get_listed(_ME, ["shared"])] == ["mine", "shared"]


def test_get_listed_skips_unsubscribed_shared():
    sources = _build_sources(owned=[_book("mine", _ME)], by_key={"shared": _book("shared")}, direct=[_entry("shared")])
    assert [s.addressbook.key for s in sources.get_listed(_ME, [])] == ["mine"]


def test_get_listed_drops_orphan_subscriptions_silently():
    """A subscription whose share was revoked, or whose book was deleted, is not listed."""
    sources = _build_sources(by_key={"revoked": _book("revoked")})
    assert not sources.get_listed(_ME, ["revoked", "deleted"])


def test_get_listed_drops_subscription_without_can_view():
    sources = _build_sources(by_key={"a": _book("a")}, direct=[_entry("a", rights=_NO_VIEW_RIGHTS)])
    assert not sources.get_listed(_ME, ["a"])


def test_get_listed_does_not_duplicate_owned_key():
    sources = _build_sources(owned=[_book("mine", _ME)])
    assert [s.addressbook.key for s in sources.get_listed(_ME, ["mine"])] == ["mine"]


def test_get_all_still_returns_every_accessible_book():
    """Access resolution ignores subscriptions."""
    sources = _build_sources(owned=[_book("mine", _ME)], by_key={"shared": _book("shared")}, direct=[_entry("shared")])
    assert [s.addressbook.key for s in sources.get_all(_ME)] == ["mine", "shared"]


def test_get_contacts_transverse_with_listed_keys_only_spans_listed_books():
    sources = _build_sources()
    listed = MagicMock()
    listed.get_contacts.return_value = []
    sources.get_listed = MagicMock(return_value=[listed])
    sources.get_all = MagicMock()
    sources.get_contacts(_ME, listed_shared_keys=["shared"])
    sources.get_listed.assert_called_once_with(_ME, ["shared"], None)
    sources.get_all.assert_not_called()


def test_get_contacts_scoped_to_one_book_ignores_subscriptions():
    sources = _build_sources()
    book_source = MagicMock()
    book_source.get_contacts.return_value = []
    book_source.count_contacts.return_value = 0
    sources.get_by_key = MagicMock(return_value=book_source)
    sources.get_listed = MagicMock()
    sources.get_contacts(_ME, addressbook_key="shared", listed_shared_keys=[])
    sources.get_listed.assert_not_called()


def test_search_all_lists_with_listed_keys_only_spans_listed_books():
    sources = _build_sources()
    sources.get_listed = MagicMock(return_value=[])
    sources.get_all = MagicMock()
    sources.search_all_lists(_ME, search="te", listed_shared_keys=["shared"])
    sources.get_listed.assert_called_once_with(_ME, ["shared"], None)
    sources.get_all.assert_not_called()


# ========== ContactSources.get_shared_addressbooks ==========

def test_get_shared_addressbooks_queries_anyone_shares_of_user_domain_only():
    sources = _build_sources()
    sources.get_shared_addressbooks(_ME)
    sources._share.get_keys_shared_with_anyone_in_domain.assert_called_once_with("example.com")


def test_get_shared_addressbooks_rechecks_exact_owner_domain():
    """The SQL LIKE is only a prefilter: an owner of another domain is still rejected."""
    sources = _build_sources(by_key={"other": _book("other", owner="eve@exampleXcom")},
                             anyone=[_entry("other", to_user=cs.ANYONE_TO_USER, owner="eve@exampleXcom")])
    assert not sources.get_shared_addressbooks(_ME)


def test_get_shared_addressbooks_merges_direct_and_anyone_without_duplicates():
    sources = _build_sources(
        by_key={"a": _book("a"), "b": _book("b")},
        direct=[_entry("a")],
        anyone=[_entry("a", to_user=cs.ANYONE_TO_USER), _entry("b", to_user=cs.ANYONE_TO_USER)],
    )
    assert [b.key for b in sources.get_shared_addressbooks(_ME)] == ["a", "b"]


# ========== ShareContact.grants_view ==========

@pytest.mark.parametrize("rights, expected", [
    (_VIEW_RIGHTS, True),
    (_NO_VIEW_RIGHTS, False),
    (FULL_MODIFY_RIGHTS, True),
    ({}, False),
])
def test_grants_view(rights, expected):
    assert ShareContact.grants_view(rights) is expected


# ========== ModuleContact ==========

def _build_module(sources):
    module = object.__new__(ModuleContact)
    module._db = MagicMock()
    module._sources = sources
    module._share = sources._share
    module._acl = ContactAclEngine(share=sources._share)
    return module


def test_get_all_addressbooks_lists_owned_and_subscribed_shared():
    sources = _build_sources(owned=[_book("mine", _ME)], by_key={"a": _book("a"), "b": _book("b")},
                             direct=[_entry("a"), _entry("b")])
    books = _build_module(sources).get_all_addressbooks(_user(subs={"b": True}))
    assert [b.key for b in books] == ["mine", "b"]


def test_get_all_addressbooks_keeps_hidden_subscription():
    """Presence in SUBS is the subscription; False is only the display toggle."""
    sources = _build_sources(by_key={"a": _book("a")}, direct=[_entry("a")])
    assert [b.key for b in _build_module(sources).get_all_addressbooks(_user(subs={"a": False}))] == ["a"]


def test_get_all_addressbooks_without_subs_section_lists_owned_only():
    sources = _build_sources(owned=[_book("mine", _ME)], by_key={"a": _book("a")}, direct=[_entry("a")])
    user = _user()
    user.folders = {}
    assert [b.key for b in _build_module(sources).get_all_addressbooks(user)] == ["mine"]


def test_get_shared_addressbooks_flags_subscription_and_rights():
    sources = _build_sources(by_key={"a": _book("a"), "b": _book("b")}, direct=[_entry("a"), _entry("b")])
    books = _build_module(sources).get_shared_addressbooks(_user(subs={"a": False}))
    assert [(b.key, b.subscribed) for b in books] == [("a", True), ("b", False)]
    assert books[0].rights == _VIEW_RIGHTS


def _build_listing_module():
    """ModuleContact over a mocked ContactSources, to inspect what the listings pass down."""
    module = object.__new__(ModuleContact)
    module._sources = MagicMock()
    module._sources.get_contacts.return_value = ([], 0)
    module._sources.search_all_lists.return_value = []
    module._acl = MagicMock()
    module._file = MagicMock()
    return module


def test_get_contacts_transverse_spans_subscribed_books():
    module = _build_listing_module()
    module.get_contacts(_user(subs={"a": True}), search="ali")
    assert module._sources.get_contacts.call_args.kwargs["listed_shared_keys"] == ["a"]


def test_get_contacts_of_one_book_relies_on_acl_only():
    module = _build_listing_module()
    module.get_addressbook = MagicMock()
    module.get_contacts(_user(subs={"a": True}), addressbook_key="unsubscribed")
    assert module._sources.get_contacts.call_args.kwargs["listed_shared_keys"] is None


def test_search_all_lists_spans_subscribed_books():
    module = _build_listing_module()
    module.search_all_lists(_user(subs={"a": True}), search="te")
    assert module._sources.search_all_lists.call_args.kwargs["listed_shared_keys"] == ["a"]


def test_get_shared_addressbooks_keeps_only_viewable_shares():
    sources = _build_sources(by_key={"a": _book("a"), "b": _book("b")},
                             direct=[_entry("a"), _entry("b", rights=_NO_VIEW_RIGHTS)])
    assert [b.key for b in _build_module(sources).get_shared_addressbooks(_user())] == ["a"]


def test_get_shared_addressbooks_includes_anyone_shares():
    sources = _build_sources(by_key={"a": _book("a")}, anyone=[_entry("a", to_user=cs.ANYONE_TO_USER)])
    assert [b.key for b in _build_module(sources).get_shared_addressbooks(_user())] == ["a"]


def test_get_rights_on_returns_sharee_rights():
    sources = _build_sources(by_key={"a": _book("a")}, direct=[_entry("a")])
    assert _build_module(sources).get_rights_on(_user(), _book("a")) == _VIEW_RIGHTS


def test_get_rights_on_owner_has_full_rights():
    sources = _build_sources()
    assert _build_module(sources).get_rights_on(_user(), _book("mine", _ME)) == FULL_MODIFY_RIGHTS


def test_require_subscribable_accepts_anyone_share_with_rights_and_subscribed():
    sources = _build_sources(by_key={"a": _book("a")}, anyone=[_entry("a", to_user=cs.ANYONE_TO_USER)])
    book = _build_module(sources).require_subscribable(_user(), "a")
    assert book.key == "a"
    assert book.rights == _VIEW_RIGHTS
    assert book.subscribed is True


def test_require_subscribable_refuses_own_addressbook():
    sources = _build_sources()
    sources._repo_addressbook.find_by_key.return_value = _book("mine", _ME)
    with pytest.raises(RequestException) as exc:
        _build_module(sources).require_subscribable(_user(), "mine")
    assert exc.value.error == err.ERROR_CONTACT_CANNOT_SUBSCRIBE_OWN


def test_require_subscribable_hides_book_without_can_view():
    sources = _build_sources(by_key={"a": _book("a")}, direct=[_entry("a", rights=_NO_VIEW_RIGHTS)])
    with pytest.raises(RequestException) as exc:
        _build_module(sources).require_subscribable(_user(), "a")
    assert exc.value.error == err.ERROR_CONTACT_ADDRESSBOOK_NOT_FOUND


def test_require_subscribable_refuses_unshared_book():
    sources = _build_sources(by_key={"a": _book("a")})
    with pytest.raises(RequestException) as exc:
        _build_module(sources).require_subscribable(_user(), "a")
    assert exc.value.error == err.ERROR_CONTACT_ADDRESSBOOK_NOT_FOUND
