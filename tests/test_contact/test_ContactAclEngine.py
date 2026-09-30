"""Unit tests for ContactAclEngine: owner holds every right, a non-owner only the named rights of their share."""
from unittest.mock import MagicMock

import pytest

from app.factory.share.shareContact import RIGHT_CREATE, RIGHT_EDIT, RIGHT_ERASE, RIGHT_VIEW, ShareContact
from app.module.contact.acl.ContactAclEngine import ContactAclEngine
from app.module.contact.model.CardAddressBook import CardAddressBook
from app.utils import errors as err
from app.utils.exceptions import RequestException

_ALL_RIGHTS = (RIGHT_VIEW, RIGHT_CREATE, RIGHT_EDIT, RIGHT_ERASE)


def _user(uid):
    user = MagicMock()
    user.uid = uid
    return user


def _book(user_uid, key="book-1"):
    return CardAddressBook(user_uid=user_uid, name="Personal", key=key)


def _share_with_rights(rights):
    """Share resolver whose lookup returns an ACL entry carrying ``rights`` (None = no entry)."""
    share = ShareContact.__new__(ShareContact)
    entry = None if rights is None else MagicMock(rights=rights)
    share.get_user_or_anyone = MagicMock(return_value=entry)
    return share


def _engine_with_rights(rights):
    return ContactAclEngine(share=_share_with_rights(rights))


def test_owner_holds_every_right():
    engine = ContactAclEngine()
    for right in _ALL_RIGHTS:
        assert engine.has_right(_book("alice"), _user("alice"), right)
    engine.check_permission(_book("alice"), _user("alice"), *_ALL_RIGHTS)


def test_non_owner_without_resolver_is_denied():
    engine = ContactAclEngine()
    assert not engine.has_right(_book("alice"), _user("bob"), RIGHT_VIEW)
    with pytest.raises(RequestException) as exc:
        engine.check_permission(_book("alice"), _user("bob"), RIGHT_VIEW)
    assert exc.value.error == err.ERROR_CONTACT_ACCESS_DENIED


def test_non_owner_without_entry_is_denied():
    engine = _engine_with_rights(None)
    with pytest.raises(RequestException):
        engine.check_permission(_book("alice"), _user("bob"), RIGHT_VIEW)


def test_create_right_does_not_grant_edit_nor_erase():
    engine = _engine_with_rights({RIGHT_VIEW: True, RIGHT_CREATE: True, RIGHT_ERASE: False})
    book, bob = _book("alice"), _user("bob")
    engine.check_permission(book, bob, RIGHT_VIEW)
    engine.check_permission(book, bob, RIGHT_CREATE)
    for right in (RIGHT_EDIT, RIGHT_ERASE):
        with pytest.raises(RequestException) as exc:
            engine.check_permission(book, bob, right)
        assert exc.value.error == err.ERROR_CONTACT_ACCESS_DENIED


def test_check_permission_requires_every_right():
    engine = _engine_with_rights({RIGHT_VIEW: True, RIGHT_CREATE: True})
    with pytest.raises(RequestException):
        engine.check_permission(_book("alice"), _user("bob"), RIGHT_CREATE, RIGHT_EDIT)


def test_erase_right_alone_grants_erase_only():
    engine = _engine_with_rights({RIGHT_ERASE: True})
    engine.check_permission(_book("alice"), _user("bob"), RIGHT_ERASE)
    with pytest.raises(RequestException):
        engine.check_permission(_book("alice"), _user("bob"), RIGHT_VIEW)


def test_share_resolved_through_user_or_anyone():
    share = _share_with_rights({RIGHT_VIEW: True})
    ContactAclEngine(share=share).check_permission(_book("alice@x.org"), _user("bob@x.org"), RIGHT_VIEW)
    share.get_user_or_anyone.assert_called_once_with("bob@x.org", "alice@x.org", "book-1")
