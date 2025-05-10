# -*- coding: utf-8 -*-

old_usersource = { "SOGoUserSources": [
    {
        "type": "ldap",
        "CNFieldName": "cn",
        "IDFieldName":"uid",
        "UIDFieldName": "uid",
        "IMAPHostFieldName": "mailHost",
        "baseDN": "ou=users,dc=acme,dc=com",
        "bindDN": "uid=sogo,ou=users,dc=acme,dc=com",
        "bindPassword": "qwerty",
        "canAuthenticate": True,
        "displayName": "Shared Addresses",
        "hostname": "ldap://127.0.0.1:389",
        "id": "public",
        "isAddressBook": True
    }
]}