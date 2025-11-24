import pytest

from app.utils.dict import merge_patch, set_origin_from_settings


def test_merge_patch_rfc_7386_exemple():
    #https://datatracker.ietf.org/doc/html/rfc7386#section-3
    resource = {
        "title": "Goodbye!",
        "author":  {
            "givenName": "John",
            "familyName": "Doe"
        },
        "tags": ["example", "sample"],
        "content": "This will be unchanged"
    }

    patch = {
        "title": "Hello!",
        "phoneNumber": "+01-123-456-7890",
        "author": {
            "familyName": None
        },
        "tags": ["example"]
    }

    result = {
        "title": "Hello!",
        "author": {
            "givenName": "John"
        },
        "tags": ["example"],
        "content": "This will be unchanged",
        "phoneNumber": "+01-123-456-7890"
    }

    merge_patch(patch, resource)

    assert resource == result

def test_merge_patch_remove_dict_value():
    resource = {
        "title": "Goodbye!",
        "author":  {
            "givenName": "John",
            "familyName": "Doe"
        }
    }

    patch = {
        "title": "Hello!",
        "author": None,
    }

    result = {
        "title": "Hello!",
    }

    merge_patch(patch, resource)

    assert resource == result

def test_merge_patch_add_dict_value():
    resource = {
        "title": "Hello!",
    }

    patch = {
        "title": "Goodbye!",
        "author":  {
            "givenName": "John",
            "familyName": "Doe"
        }
    }

    result = {
        "title": "Goodbye!",
        "author":  {
            "givenName": "John",
            "familyName": "Doe"
        }
    }

    merge_patch(patch, resource)

    assert resource == result

def test_merge_patch_replace_none_with_dict_value():
    resource = {
        "title": "Hello!",
        "author": None
    }

    patch = {
        "title": "Goodbye!",
        "author":  {
            "givenName": "John",
            "familyName": "Doe"
        }
    }

    result = {
        "title": "Goodbye!",
        "author":  {
            "givenName": "John",
            "familyName": "Doe"
        }
    }

    merge_patch(patch, resource)

    assert resource == result

def test_merge_patch_replace_dict_with_not_dict():
    resource = {
        "title": "Goodbye!",
        "author":  {
            "givenName": "John",
            "familyName": "Doe"
        }
    }

    patch = {
        "title": "Hello!",
        "author": "not a dict",
    }

    with pytest.raises(ValueError):
        merge_patch(patch, resource)

def test_merge_patch_empty_resource():
    resource = {}

    patch = {
        "title": "Hello!",
        "phoneNumber": "+01-123-456-7890",
        "author": {
            "familyName": None
        },
        "author2": {
            "familyName": None,
            "Name": "John"
        },
        "author3": {
            "familyName": "Steward",
            "Name": "John"
        },
        "tags": ["example"],
        "isbn": None
    }

    result = {
        "title": "Hello!",
        "phoneNumber": "+01-123-456-7890",
        "author2": {
            "Name": "John"
        },
        "author3": {
            "familyName": "Steward",
            "Name": "John"
        },
        "tags": ["example"],
    }

    merge_patch(patch, resource)

    assert resource == result

def test_origin_from_settings():
    sogo_nu = {
        "param1": 1,
        "param2": "new",
        "param3": "idem"
    }

    default = {
        "param2": "old",
        "param3": "idem"
    }

    result = {
        "param1": "sogo.nu",
        "param2": "sogo.nu",
        "param3": "default"
    }

    assert result == set_origin_from_settings("sogo.nu", sogo_nu, default)
    
def test_origin_from_settings_with_inner_dict():
    sogo_nu = {
        "param1": {
            "subdict1": 1,
            "subdict2": "banane",
            "subdict3": {
                "deep1": 1,
                "deep2": "poire"
            }
        },
        "param2": "new",
        "param3": "idem"
    }

    default = {
        "param1": {
            "subdict1": 1,
            "subdict2": 2,
            "subdict3": {
                "deep1": 5,
                "deep2": "poire",
                "deep3": "ananas"
            }
        },
        "param2": "new",
        "param3": "idem"
    }

    result = {
        "param1": {
            "subdict1": "default",
            "subdict2": "sogo.nu",
            "subdict3": {
                "deep1": "sogo.nu",
                "deep2": "default",
                "deep3": "default"
            }
        },
        "param2": "default",
        "param3": "default"
    }

    assert result == set_origin_from_settings("sogo.nu", sogo_nu, default)