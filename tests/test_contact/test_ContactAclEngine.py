"""Unit tests for ContactAclEngine (stubbed: owner -> MODIFY, non-owner -> denied)."""
from unittest.mock import MagicMock

import pytest

from app.module.contact.acl.ContactAclEngine import ContactAclEngine
from app.module.contact.model.CardAddressBook import CardAddressBook
from app.module.contact.model.enums.ContactShareLevel import ContactShareLevel
from app.utils import errors as err
from app.utils.exceptions import RequestException

_engine = ContactAclEngine()


def _user(uid):
    user = MagicMock()
    user.uid = uid
    return user


def _book(user_uid):
    return CardAddressBook(user_uid=user_uid, name="Personal")


def test_owner_gets_modify():
    assert _engine.get_share_level(_book("alice"), _user("alice")) == ContactShareLevel.MODIFY


def test_non_owner_is_denied():
    assert _engine.get_share_level(_book("alice"), _user("bob")) is None


def test_check_permission_allows_sufficient_level():
    _engine.check_permission(ContactShareLevel.VIEW, ContactShareLevel.VIEW)
    _engine.check_permission(ContactShareLevel.MODIFY, ContactShareLevel.VIEW)
    _engine.check_permission(ContactShareLevel.MODIFY, ContactShareLevel.MODIFY)


def test_check_permission_denies_insufficient_level():
    with pytest.raises(RequestException) as exc:
        _engine.check_permission(ContactShareLevel.VIEW, ContactShareLevel.MODIFY)
    assert exc.value.error == err.ERROR_CONTACT_ACCESS_DENIED


def test_check_permission_denies_none_level():
    with pytest.raises(RequestException) as exc:
        _engine.check_permission(None, ContactShareLevel.VIEW)
    assert exc.value.error == err.ERROR_CONTACT_ACCESS_DENIED
