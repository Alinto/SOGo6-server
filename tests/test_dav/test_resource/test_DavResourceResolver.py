"""Unit tests for DavResourceResolver."""

from types import SimpleNamespace

import pytest

from app.auth.User import User
from app.dav.model.DavContext import DavContext
from app.dav.resource.DavAddressBookHomeResource import DavAddressBookHomeResource
from app.dav.resource.DavCalendarHomeResource import DavCalendarHomeResource
from app.dav.resource.DavPrincipalResource import DavPrincipalResource
from app.dav.resource.DavResourceResolver import DavResourceResolver
from app.dav.resource.DavRootResource import DavRootResource
from app.utils import errors as err
from app.utils.exceptions import RequestException


def _context(account_alias=None):
    return DavContext(
        process_settings=SimpleNamespace(),
        system_settings={},
        user_domain_settings={},
        user=User("alice@example.org", "secret"),
        cache=SimpleNamespace(),
        account_alias=account_alias,
    )


CONTEXT = _context()
ALIAS_CONTEXT = _context(account_alias="Work")

# ========== Tests for resolve ==========


@pytest.mark.parametrize(
    "path, resource_class",
    [
        ("", DavRootResource),
        ("alice@example.org/", DavPrincipalResource),
        ("alice@example.org", DavPrincipalResource),
        ("alice@EXAMPLE.org/", DavPrincipalResource),
        ("alice@example.org/Calendar/", DavCalendarHomeResource),
        ("alice@example.org/Contacts", DavAddressBookHomeResource),
    ],
)
def test_resolve(path, resource_class):
    assert isinstance(DavResourceResolver.resolve(path=path, context=CONTEXT), resource_class)


@pytest.mark.parametrize(
    "path",
    [
        "bob@example.org/",
        "Alice@example.org/",
        "alice@example.org/Tasks/",
        "alice@example.org/Calendar/personal/",
        "alice@example.org!Work/",
    ],
)
def test_resolve_not_found(path):
    with pytest.raises(RequestException) as ex:
        DavResourceResolver.resolve(path=path, context=CONTEXT)
    assert ex.value.error is err.ERROR_DAV_RESOURCE_NOT_FOUND


# ========== Tests for the account alias ==========


@pytest.mark.parametrize(
    "path, resource_class",
    [
        ("", DavRootResource),
        ("alice@EXAMPLE.org!Work/", DavPrincipalResource),
        ("alice@example.org!Work/Contacts/", DavAddressBookHomeResource),
    ],
)
def test_resolve_alias(path, resource_class):
    assert isinstance(DavResourceResolver.resolve(path=path, context=ALIAS_CONTEXT), resource_class)


@pytest.mark.parametrize("path", ["alice@example.org/", "alice@example.org!work/", "alice@example.org!Other/"])
def test_resolve_alias_not_found(path):
    with pytest.raises(RequestException) as ex:
        DavResourceResolver.resolve(path=path, context=ALIAS_CONTEXT)
    assert ex.value.error is err.ERROR_DAV_RESOURCE_NOT_FOUND
