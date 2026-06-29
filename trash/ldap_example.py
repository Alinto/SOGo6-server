import ldap
import ldap.controls.ppolicy
import ldap.filter
from ldap import LDAPError
from app.manager.ldap.ClientLdap import ClientLdap


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

dev_ldap_conf = {
    "ldap_host"         : "openldap",
    "ldap_port"         : 390,
    "ldap_enc"          : "None",
    "ldap_bind_dn"      : LOGIN_DN,
    "ldab_bind_pwd"     : LOGIN_PW,
    "ldap_base_dn"      : "ou=users,dc=example,dc=org",
    "ldap_scope"        : "SUB",
    "ldap_uid"          : "uid",
    "ldap_id"           : "uid",
    "ldap_cn"           : "cn",
    "ldap_mails"        : ["mail"],
    "ldap_bind_fields"  : None,
    "ldap_bind_as_user" : False,
    "ldap_filter"       : None,
    "ldap_pwd_policy"   : False
}

USE_MANAGER = False

################
#LDAP LIB ALONE#
################

if USE_MANAGER:
    #Beware that the constants are not found by Pylint because they come from the C library and not the python module
    l = ldap.initialize("ldap://openldap:390", trace_level=0)

    # #Si il y a encryption (ldaps)
    # l.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_DEMAND) # pylint: disable=no-member

    # class SecretString(str):
    #     """
    #     A class that override the __repr__ to censor secrets/passwords
    #     """

    #     def set_censored(self, censored_value:str="SecretString('***')") -> None:
    #         """
    #         :param censored_value: Value to show in the log instead of the true value
    #         :type censored_value: str
    #         """
    #         self._censored = censored_value # pylint: disable=attribute-defined-outside-init

    #     def __repr__(self) -> str:
    #         if self.__getattribute__("_censored"):
    #             return self._censored
    #         return "SecretString('***')"
        
    # LOGIN_PW = SecretString("hdsjkqh")
    # LOGIN_PW.set_censored("BANANE")

    pwd_control = ldap.controls.ppolicy.PasswordPolicyControl(criticality=False)
    serverctrls = [pwd_control]

    # try:
    #     ret = l.simple_bind_s(LOGIN_DN, LOGIN_PW, serverctrls=serverctrls)
    #     print(ret
    #     ret = l.simple_bind_s(LOGIN_DN, LOGIN_PW, serverctrls=serverctrls)
    #     print(ret)
    # except LDAPError as e:
    #     print("Hey j'ai catch")
    #     print(type(e))
    #     print(e)

    # ret = l.search_)
    # except LDAPError as e:
    #     print("Hey j'ai catch")
    #     print(type(e))
    #     print(e)

    # ret = l.search_s("ou=users,dc=example,dc=org", ldap.SCOPE_SUBTREE, "objectclass=*") # pylint: disable=no-member
    # print(ret)

    # #Beware of ret param are str but value are bytes

    s="Joe*"
    print(s)
    s = ldap.filter.escape_filter_chars(s,escape_mode=0)
    print(s)
    s = s.replace(r"\2a", '*')
    print(s)

else:
    manager = ClientLdap(**dev_ldap_conf)
    manager.connect()
    manager.check_login("sogo-tests1@example.org", "sogo", "example.org")
# (
#     101,
#      [
#         (
#            'uid=sogo-tests1@example.org,ou=users,dc=example,dc=org',
#             {
#               'cn': [b'Didy'],
#               'gidNumber': [b'1000'],
#               'givenName': [b'Didy'],
#               'homeDirectory': [b'/home/sogo-tests1'],
#               'homePhone': [b'+1 (123) 456-7890'],
#               'homePostalAddress': [b'dude@sogo.alinto', b'dude2@sogo.alinto'],
#               'l': [b'Vladivostok'],
#               'mail': [b'sogo-tests1@example.org'],
#               'objectClass': [b'inetOrgPerson', b'posixAccount', b'shadowAccount'],
#               'sn': [b'Love'],
#               'telephoneNumber': [b'+1 (120) 987-6543'],
#               'uid': [b'sogo-tests1@example.org'],
#               'uidNumber': [b'1000'],
#               'userPassword': [b'sogo']
#             }
#         )
#     ],
#     2,
#     []
# )