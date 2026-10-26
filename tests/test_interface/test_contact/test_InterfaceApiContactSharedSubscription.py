"""Unit tests for InterfaceApiContactContact - shared address book discovery, subscription and share-time subscribe."""
from unittest.mock import MagicMock, patch

from app.interface.contact.InterfaceApiContactContact import InterfaceApiContactContact
from app.module.contact.model.CardAddressBook import CardAddressBook
from app.module.contact.model.enums.CardSourceType import CardSourceType
from app.module.contact.serializer.CardAddressBookSerializerDict import CardAddressBookSerializerDict
from app.module.contact.serializer.CardAddressBooksSerializerList import CardAddressBooksSerializerList
from app.utils import constants as cs
from app.utils import errors as err
from app.utils.api.paginate_sort_filter import CollectionPaginateArgs
from app.utils.exceptions import RequestException

_ME = "bob@example.com"
_VIEW_RIGHTS = {"can_view": True, "can_create_objects": False, "can_edit_objects": False, "can_erase_objects": False}
_NO_VIEW_RIGHTS = {"can_view": False, "can_create_objects": True, "can_edit_objects": True, "can_erase_objects": True}


def _build_interface(subs=None):
    inter = object.__new__(InterfaceApiContactContact)
    inter.user = MagicMock()
    inter.user.uid = _ME
    inter.user.folders = {"ADDRESSBOOKS": {"OWNER": {"mine": True}, "SUBS": dict(subs or {})}}
    inter.module = MagicMock()
    inter.module.get_all_addressbooks.return_value = []
    inter.module.get_addressbook_share.return_value = []
    inter.module.get_contacts.return_value = ([], 0)
    inter.module.search_all_lists.return_value = []
    inter.module.get_rights_on.return_value = dict(_VIEW_RIGHTS)
    inter._addressbook_serializer = CardAddressBookSerializerDict()
    inter._addressbooks_serializer = CardAddressBooksSerializerList()
    inter._contacts_serializer = MagicMock(serialize=MagicMock(return_value=[]))
    inter._autocomplete_serializer = MagicMock(serialize=MagicMock(return_value=[]))
    inter._list_autocomplete_serializer = MagicMock(serialize=MagicMock(return_value=[]))
    inter._gab_autocomplete_serializer = MagicMock(serialize=MagicMock(return_value=[]))
    inter._user_source_module = MagicMock()
    inter._user_source_module.list_user_sources.return_value = []
    inter._user_source_module.get_user_source_by_uid.return_value = {}
    inter._user_module_settings = MagicMock(SOGO_D_AUTOCOMPLETION_MIN_LEN=2)
    inter._user_domain_settings = MagicMock()
    inter._user_module = MagicMock()
    inter._share_targets = {}
    # Every uid resolves to itself, "anyone" to the pseudo-user.
    inter._resolve_to_user = lambda entry: cs.ANYONE_TO_USER if entry.get("user_class") == cs.USER_CLASS_ANY else entry["uid"]
    inter._serialize_share_entries = MagicMock(return_value=[])
    return inter


def _book(key, owner="alice@example.com"):
    return CardAddressBook(user_uid=owner, name=key, key=key, source_type=CardSourceType.LOCAL)


def _subs_added(inter):
    return [c.args for c in inter._user_module.add_folder_key.call_args_list]


# ========== listings: passthrough, the module resolves subscriptions ==========

def test_get_all_addressbooks_only_passes_the_user():
    inter = _build_interface(subs={"a": True})
    inter.get_all_addressbooks()
    inter.module.get_all_addressbooks.assert_called_once_with(inter.user)


def test_get_contacts_does_not_pass_subscriptions():
    inter = _build_interface(subs={"a": True})
    inter.get_contacts(None, CollectionPaginateArgs(page=1, page_size=20))
    assert "listed_shared_keys" not in inter.module.get_contacts.call_args.kwargs


def test_autocomplete_does_not_pass_subscriptions():
    inter = _build_interface(subs={"a": True})
    with patch("app.interface.contact.InterfaceApiContactContact.ModuleUserSource") as module_us:
        module_us.init_from_domain_settings.return_value.search_for_all_us.return_value = []
        inter.autocomplete("ali")
    assert "listed_shared_keys" not in inter.module.get_contacts.call_args.kwargs
    assert "listed_shared_keys" not in inter.module.search_all_lists.call_args.kwargs


# ========== discovery ==========

def test_get_shared_addressbooks_serializes_module_result():
    inter = _build_interface()
    subscribed, offered = _book("a"), _book("b")
    subscribed.rights, subscribed.subscribed = dict(_VIEW_RIGHTS), True
    offered.rights, offered.subscribed = dict(_VIEW_RIGHTS), False
    inter.module.get_shared_addressbooks.return_value = [subscribed, offered]
    response, _ = inter.get_shared_addressbooks()
    books = response["data"]["addressbooks"]
    assert response["data"]["total_count"] == 2
    assert [(b["key"], b["subscribed"]) for b in books] == [("a", True), ("b", False)]
    assert books[0]["rights"] == _VIEW_RIGHTS


# ========== subscribe / unsubscribe ==========

def test_subscribe_writes_subs_without_overwriting_and_returns_module_book():
    inter = _build_interface()
    book = _book("a")
    book.rights, book.subscribed = dict(_VIEW_RIGHTS), True
    inter.module.require_subscribable.return_value = book
    response, _ = inter.set_addressbook_subscription("a", {"subscribe": True})
    assert response["error_code"] == "S000000"
    assert response["data"]["subscribed"] is True
    assert response["data"]["rights"] == _VIEW_RIGHTS
    inter._user_module.add_folder_key.assert_called_once_with(_ME, "ADDRESSBOOKS", "a", owner_key="SUBS", keep_existing=True)


def test_subscribe_refused_writes_nothing():
    inter = _build_interface()
    inter.module.require_subscribable.side_effect = RequestException(error=err.ERROR_CONTACT_ADDRESSBOOK_NOT_FOUND)
    response, _ = inter.set_addressbook_subscription("a", {"subscribe": True})
    assert response["error_code"] == err.ERROR_CONTACT_ADDRESSBOOK_NOT_FOUND.c
    inter._user_module.add_folder_key.assert_not_called()


def test_unsubscribe_removes_key_without_access_check():
    inter = _build_interface(subs={"a": True})
    response, _ = inter.set_addressbook_subscription("a", {"subscribe": False})
    assert response["error_code"] == "S000000"
    assert response["data"] == {"key": "a", "subscribed": False}
    inter._user_module.remove_folder_key.assert_called_once_with(_ME, "ADDRESSBOOKS", "a", owner_key="SUBS")
    inter.module.get_addressbook.assert_not_called()
    inter.module.require_subscribable.assert_not_called()


# ========== share-time subscription ==========

def test_patch_share_does_not_subscribe_by_default():
    inter = _build_interface()
    inter.patch_addressbook_share("k", [{"uid": "carol@example.com", "user_class": "user", "rights": _VIEW_RIGHTS}])
    inter._user_module.add_folder_key.assert_not_called()


def test_patch_share_subscribes_when_asked():
    inter = _build_interface()
    inter.patch_addressbook_share("k", [{"uid": "carol@example.com", "user_class": "user",
                                         "rights": _VIEW_RIGHTS, "subscribe": True}])
    assert _subs_added(inter) == [("carol@example.com", "ADDRESSBOOKS", "k")]


def test_patch_share_never_subscribes_anyone():
    inter = _build_interface()
    inter.patch_addressbook_share("k", [{"user_class": cs.USER_CLASS_ANY, "rights": _VIEW_RIGHTS, "subscribe": True}])
    inter._user_module.add_folder_key.assert_not_called()


def test_patch_share_does_not_subscribe_without_can_view():
    inter = _build_interface()
    inter.patch_addressbook_share("k", [{"uid": "carol@example.com", "user_class": "user",
                                         "rights": _NO_VIEW_RIGHTS, "subscribe": True}])
    inter._user_module.add_folder_key.assert_not_called()


def test_put_share_subscribes_only_flagged_users():
    inter = _build_interface()
    inter.put_addressbook_share("k", [
        {"uid": "carol@example.com", "user_class": "user", "rights": _VIEW_RIGHTS, "subscribe": True},
        {"uid": "dave@example.com", "user_class": "user", "rights": _VIEW_RIGHTS},
    ])
    assert _subs_added(inter) == [("carol@example.com", "ADDRESSBOOKS", "k")]


def test_post_share_grants_full_rights_and_honours_subscribe():
    inter = _build_interface()
    inter.post_addressbook_share("k", [{"uid": "carol@example.com", "user_class": "user",
                                        "rights": _NO_VIEW_RIGHTS, "subscribe": True}])
    inter.module.grant_addressbook_share.assert_called_once_with(inter.user, "k", ["carol@example.com"])
    assert _subs_added(inter) == [("carol@example.com", "ADDRESSBOOKS", "k")]
