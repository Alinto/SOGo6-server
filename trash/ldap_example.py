import ldap

LOGIN_DN = "cn=admin,dc=example,dc=org"
LOGIN_PW = "password"


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

#Beware that the constants are not found by Pylint because they come from the C library and not the python module
l = ldap.initialize("ldap://openldap:390")

#Si il y a encryption (ldaps)
l.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_HARD) # pylint: disable=no-member

l.simple_bind(LOGIN_DN, LOGIN_PW)
ret = l.search_s("ou=users,dc=example,dc=org", ldap.SCOPE_SUBTREE, "objectclass=*") # pylint: disable=no-member
print(ret)

#Beware of ret param are str but value are bytes
