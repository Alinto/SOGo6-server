"""Unit tests for DavResourceResolver."""

import pytest

from app.auth.User import User
from app.dav.resource.DavAddressBookHomeResource import DavAddressBookHomeResource
from app.dav.resource.DavCalendarHomeResource import DavCalendarHomeResource
from app.dav.resource.DavPrincipalResource import DavPrincipalResource
from app.dav.resource.DavResourceResolver import DavResourceResolver
from app.dav.resource.DavRootResource import DavRootResource
from app.utils import errors as err
from app.utils.exceptions import RequestException

USER = User("alice@example.org", "secret")

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
    assert isinstance(DavResourceResolver.resolve(path=path, user=USER), resource_class)


@pytest.mark.parametrize(
    "path",
    [
        "bob@example.org/",
        "Alice@example.org/",
        "alice@example.org/Tasks/",
        "alice@example.org/Calendar/personal/",
    ],
)
def test_resolve_not_found(path):
    with pytest.raises(RequestException) as ex:
        DavResourceResolver.resolve(path=path, user=USER)
    assert ex.value.error is err.ERROR_DAV_RESOURCE_NOT_FOUND
