from __future__ import annotations
from typing import TYPE_CHECKING, Any

from datetime import datetime
from logging import WARNING
import ldap #Warning! pylint and mypy are disabled on this lib as it's build on a C library; Therefore they are lost on liting.
import ldap.dn
import ldap.filter
import ldap.sasl
import ldap.controls.ppolicy
# python-ldap https://www.python-ldap.org/en/latest/
# ldap C https://git.openldap.org/rouzier/openldap

from app.manager.user_source.ClientUserSource import ClientUserSource
from app.utils import constants as cs
from app.utils import errors as err
from app.utils import exceptions as exc
from app.utils.db import Condition
from app.utils.logger.logger import logger_ldap
from app.utils.strings import SecretString


if TYPE_CHECKING:
    from ldap.ldapobject import LDAPObject
#MAP
scope_map = {
    cs.LDAP_SCOPE_BASE: ldap.SCOPE_BASE,  #Only search in current base
    cs.LDAP_SCOPE_ONE: ldap.SCOPE_ONELEVEL,    #Search in current base and one level below
    cs.LDAP_SCOPE_SUB: ldap.SCOPE_SUBTREE #Search in current base and all levels below
}


def ldap_escape(og_value:str|int|datetime, with_wildcard:bool = False) -> str|int:
    """
    Ldap escape to avoid injection but that allow wildcard char '*'

    :param og_str: string to escape
    :type og_str: str
    :return: escaped string but with '*' wildcard
    :rtype: str
    """
    if isinstance(og_value, int):
        return og_value
    if isinstance(og_value, datetime):
        return int(og_value.timestamp())
    s = ldap.filter.escape_filter_chars(og_value,escape_mode=0)
    if with_wildcard:
        s = s.replace(r"\2a", '*')
    return s

def condition_to_filter(condition: Condition.Condition) -> str:
    """
    Return the filter value for a ldap query
    """

    if isinstance(condition, Condition.EqualCondition):
        ldap_filter = f"({ldap_escape(condition.param_name, with_wildcard=True)}={ldap_escape(condition.param_value, with_wildcard=True)})"
    elif isinstance(condition, Condition.NotEqualCondition):
        ldap_filter = f"({ldap_escape(condition.param_name, with_wildcard=True)}!={ldap_escape(condition.param_value, with_wildcard=True)})"
    elif isinstance(condition, Condition.AndCondition):
        ldap_filter = "(&"
        for cond in condition.conditions:
            ldap_filter += f"{condition_to_filter(cond)}"
        ldap_filter += ")"
    elif isinstance(condition, Condition.OrCondition):
        ldap_filter = "(|"
        for cond in condition.conditions:
            ldap_filter += f"{condition_to_filter(cond)}"
        ldap_filter += ")"
    elif isinstance(condition, Condition.LessOrEqualCondition):
        ldap_filter = f"({ldap_escape(condition.param_name, with_wildcard=True)}<={ldap_escape(condition.param_value, with_wildcard=True)})"
    elif isinstance(condition, Condition.GreaterOrEqualCondition):
        ldap_filter = f"({ldap_escape(condition.param_name, with_wildcard=True)}>={ldap_escape(condition.param_value, with_wildcard=True)})"
    else:
        raise exc.BugException(f"Trying to convert a Condition not implemented for ldap: {condition}")

    return ldap_filter


class ClientLdap(ClientUserSource):
    """
    Manager for ldap server
    Doc: https://www.python-ldap.org/
    """

    def __init__(self,
                 ldap_host:str,
                 ldap_port:int,
                 ldap_enc:str,
                 ldap_bind_dn:str,
                 ldab_bind_pwd:str,
                 ldap_base_dn:str,
                 ldap_scope:str,
                 ldap_uid:str,
                 ldap_id:str,
                 ldap_cn:str,
                 ldap_mails:list[str],
                 ldap_bind_fields:list[str]|None = None,
                 ldap_bind_as_user:bool = False,
                 ldap_filter: Condition.Condition|None = None,
                 ldap_pwd_policy:bool = False
                 ) -> None:
        super().__init__()
        #Hostname
        self.host = ldap_host
        self.port = ldap_port
        self.enc = ldap_enc

        #bind
        self.bind_dn = ldap_bind_dn
        self.bind_pwd = ldab_bind_pwd
        self.bind_as_user = ldap_bind_as_user
        self.pwd_policy = ldap_pwd_policy
        self.bind_fields = ldap_bind_fields

        #Additional directive for query

        self.filter = condition_to_filter(ldap_filter) if ldap_filter else None

        self.binded = False

        #base
        self.base_dn = ldap_base_dn
        self.scope = scope_map[ldap_scope]

        #ldap field
        self.ldap_uid = ldap_uid
        self.ldap_id = ldap_id
        self.ldap_cn = ldap_cn
        self.ldap_main_mail = ldap_mails[0]

        #Client
        self.ldap_conn: LDAPObject|None = None

        #Search
        self.last_search: dict|None = None



    def _get_base_dn(self, username:str, domain:str) -> str:
        """
        _summary_

        :param username: _description_
        :type username: _type_
        :return: _description_
        :rtype: str
        """
        if self.ldap_conn is not None and self.connected:
            #If there is bind_fields, it means we have to fecth the base_dn directly from ldap

            new_base_dn = self.base_dn
            ##If there is "%d" in base dn replace it with the domain of the user
            if r"%d" in new_base_dn:
                new_base_dn = new_base_dn.replace(r"%d", domain)

            if self.bind_fields:
                # bind with admin creds
                self._bind(self.bind_dn, self.bind_pwd, use_admin=True)

                #init the filter with bind fields
                or_conds = []
                for field in self.bind_fields:
                    or_conds.append(Condition.EqualCondition(field, username))
                l_filter = condition_to_filter(Condition.OrCondition(*or_conds))

                #Add the others filters
                if self.filter:
                    l_filter = f"(&{l_filter}{self.filter})"
                new_base_dn = self._search_dn(new_base_dn, l_filter)
            else:
                
                ##Add the IDfield with username
                new_base_dn = f"{self.ldap_id}={ldap_escape(username)},{new_base_dn}"
            return new_base_dn
        else:
            raise exc.BugException("self.connection is still None, meaning self.connect() method didn't catch or raise correctly an error")


    def connect(self) -> None:
        """
        Connect to the ldap server
        """
        # Possible values for trace_level are 0 for no logging, 1 for only logging the method calls with arguments,
        # 2 for logging the method calls with arguments and the complete results
        # and 9 for also logging the traceback of method calls.
        trace_level = 0
        if logger_ldap.level < WARNING:
            trace_level = 2

        if self.enc == cs.SOCKET_ENC_IMPLICIT_TLS:
            uri_with_scheme = f"ldaps://{self.host}:{self.port}"
        else:
            uri_with_scheme = f"ldap://{self.host}:{self.port}"

        try:
            self.ldap_conn = ldap.initialize(uri_with_scheme, trace_level=trace_level)
        except ldap.LDAPError as e:
            logger_ldap.error("Cannot connect to the ldap server (%s) because %s", self.host, e)
            raise exc.RequestException(f"Cannot connect to the ldap server ({self.host})", error=err.ERROR_LDAP_CANNOT_CONNECT) from e

        # Not sur if mandatory. I don't know if some sogo users stiil used ldap2 version
        self.ldap_conn.protocol_version = ldap.VERSION3

        if self.enc != cs.SOCKET_ENC_PLAIN:
            self.ldap_conn.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_DEMAND)

        if self.enc == cs.SOCKET_ENC_EXPLICIT_TLS:
            self.ldap_conn.start_tls_s()


        self.connected = True

    def _bind(self, bind_dn:str, bind_pwd:str, use_admin:bool = True) -> Any:
        """
        Login to the ldap server.
        In this context it means a simple bind authentication.

        Username here is the bind dn (ex: 'cn=admin,dc=example,dc=org')
        and password is the bind password.

        :param username: the bind dn
        :type username: str
        :param password: the bind password
        :type password: str
        """
        #check that dn is correct
        if not ldap.dn.is_dn(bind_dn):
            logger_ldap.error("Cannot bind with bind dn: %s. Because it's not a valid dn", bind_dn)
            raise exc.RequestException(f"Cannot bind with bind dn: {bind_dn}. Because it's not a valid dn", error=err.ERROR_LDAP_BIND_WRONG_CRED)
        
        #Censored the password for the log
        h_password = SecretString(bind_pwd)

        #Add ppolicy if needed
        serverctrls: None|list[ldap.controls.RequestControl] = None
        if self.pwd_policy and not use_admin:
            serverctrls = [ldap.controls.ppolicy.PasswordPolicyControl(criticality=False)]

        if self.ldap_conn is not None:
            try:
                ret =self.ldap_conn.simple_bind_s(bind_dn, h_password, serverctrls=serverctrls)
                self.binded = True
                return ret
            except ldap.INVALID_CREDENTIALS as e:
                if isinstance(e, ldap.INVALID_CREDENTIALS):
                    logger_ldap.error("Invalid bind Credentials for bind dn: %s", bind_dn)
                    raise exc.RequestException(f"Invalid bind Credentials for bind {bind_dn}", error=err.ERROR_LDAP_BIND_WRONG_CRED)
            except ldap.LDAPError as e:
                logger_ldap.error("Cannot bind with bind dn: %s. Because: %s", bind_dn, e)
                raise exc.RequestException(f"Cannot bind with bind dn: {bind_dn}" , error=err.ERROR_LDAP_CANNOT_BIND) from e



    def check_login(self, username: str, password: str, domain:str) -> None:
        """Check the user credentials"""

        #Create the base dn
        base_dn = self._get_base_dn(username, domain)

        #bind
        ret = self._bind(base_dn, password)

        if self.last_search and (search := self.last_search.get(base_dn, False)):
            contact = search
        else:
            if not self.bind_as_user:
                self._bind(self.bind_dn, self.bind_pwd, use_admin=True)
            contact = self._search(base_dn, self.filter)


        print(type(ret))
        print(ret)
        print(contact)


    def _search_dn(self, base_dn:str, l_filter:str) -> Any:
        """
        Return the DN for a filter.

        Careful this query might return several entries. Only the first one is returned.

        :param filter: _description_
        :type filter: str
        :return: _description_
        :rtype: str
        """
        if self.ldap_conn is not None and self.connected:
            ret = self.ldap_conn.search_s(base_dn, self.scope, filterstr=l_filter, attrlist=["dn"])
            self.last_search = {base_dn: ret}
            return ret
        raise exc.BugException("self.connection is still None, meaning self.connect() method didn't catch or raise correctly an error")

    def _search(self, base_dn:str, l_filter:str|None = None, attributes: list|None = None) -> Any:
        """
        Return the DN for a filter.

        Careful this query might return several entries. Only the first one is returned.

        :param filter: _description_
        :type filter: str
        :return: _description_
        :rtype: str
        """
        if self.ldap_conn is not None and self.connected:
            #TODO search withouth attributes will fetch (including password, that will be lof in not encrypted)
            ret = self.ldap_conn.search_s(base_dn, self.scope, filterstr=l_filter, attrlist=attributes)
            self.last_search = {base_dn: ret}
            return ret
        raise exc.BugException("self.connection is still None, meaning self.connect() method didn't catch or raise correctly an error")


    def close(self) -> None:
        """
        Unbind the connection if needed
        """
        if self.ldap_conn is not None and self.binded:
            self.ldap_conn.unbind_s()
