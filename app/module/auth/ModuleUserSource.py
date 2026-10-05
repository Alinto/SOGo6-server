from __future__ import annotations
from typing import TYPE_CHECKING

from app.config.settings.DomainSettings import UserSourceSettingsObj, UserSourceSettings
from app.module.auth.model.CardGABContact import CardGABContact
from app.utils import exceptions as exc
from app.utils.db import Condition
from app.utils import errors as err
from app.utils.module.importManager import import_and_instantiate_manager
from app.utils.logger.logger import logger
from app.utils.strings import get_domain_from_mail

if TYPE_CHECKING:
    from app.auth.User import User
    from app.manager.user_source.ClientUserSource import ClientUserSource

MAP_KEY_CLASS = {
    "ldap": "ClientLdap",
    "db": "ClientSQLUserSource"
}

MAP_KEY_PATH = {
    "ldap": "app.manager.ldap",
    "db": "app.manager.db"

}

class ModuleUserSource:
    """
    Module to handle UserSources. Plural because they may be several users sources.
    There are rules between the differents users sources about visibility.

    """

    @staticmethod
    def init_from_domain_settings(domain_settings:dict) -> ModuleUserSource:
        """
        Init the Module User Source from the domain settings

        :param domain_settings: Domain settings
        :type domain_settings: dict
        :return: self
        :rtype: ModuleUserSource
        """
        all_user_sources: dict = {}
        domain_user_sources: dict = domain_settings[UserSourceSettings.subparent]
        for user_source_id, user_source in domain_user_sources.items():
            all_user_sources[user_source_id] = UserSourceSettingsObj(user_source)
        return ModuleUserSource(all_user_sources)

    def __init__(self, all_user_sources: dict[str, UserSourceSettingsObj]):
        """
        list_user_source is a dict where the keys are the soruce uid
        """
        self.all_user_sources = all_user_sources

    def _get_manager_for_user_source(self, source_settings: UserSourceSettingsObj) -> ClientUserSource:
        """
        Instantiate and connect the user source manager

        :param source_settings: _description_
        :type source_settings: UserSourceSettingsObj
        :return: _description_
        :rtype: ClientUserSource
        """
        us_config = source_settings.get_user_source_settings(source_settings.US_TYPE)
        
        if source_settings.US_TYPE == "db" and not source_settings.US_PWD_ALGO:
            raise exc.AggravatedException("US_PWD_ALGO not given for db user source")

        client_us: ClientUserSource = import_and_instantiate_manager(
            module_path=MAP_KEY_PATH[source_settings.US_TYPE],
            module_and_class_name=MAP_KEY_CLASS[source_settings.US_TYPE],
            module_args=us_config
        )
        client_us.connect()
        return client_us

    def list_user_sources(self) -> list[dict]:
        """
        Return a dict with all the user sources bisible for the user
        """
        books: list[dict] = []
        for us_uid, us_settings in self.all_user_sources.items():
            if us_settings.US_IS_ADDRESSBOOK:
                books.append({
                        "key": us_uid,
                        "name": us_settings.US_DISPLAY_NAME or us_settings.US_NAME,
                        "description": us_settings.US_DESCRIPTION,
                        "is_default": False,
                        "source_type": "ldap",
                        "ctag": 0,
                        "owner": "",
                    })
        return books

    def get_user_source_by_uid(self, uid:str|None) -> dict:
        """
        Return a dict with all the user sources bisible for the user
        """
        if uid is None:
            return {}
        us_settings = self.all_user_sources.get(uid, None)
        if us_settings is not None and us_settings.US_IS_ADDRESSBOOK:
            return {
                        "key": us_settings.US_UID,
                        "name": us_settings.US_DISPLAY_NAME or us_settings.US_NAME,
                        "description": us_settings.US_DESCRIPTION,
                        "is_default": False,
                        "source_type": "ldap",
                        "ctag": 0,
                        "owner": "",
                    }
        return {}


    def _make_us_check_login(self, source_settings: UserSourceSettingsObj, user: User) -> tuple[bool, dict, dict[str, list[str]]]:
        """
        _summary_

        :param source_settings: _description_
        :type source_settings: UserSourceSettingsObj
        :param user: _description_
        :type user: User
        :return: _description_
        :rtype: tuple[bool, dict, dict]
        """
        client_us = self._get_manager_for_user_source(source_settings)

        return client_us.check_login(user.uid, user.password, user.domain)

    def check_login(self, user:User) -> bool:
        """
        Check the login in the user source

        :param user: User object containing authentication information
        :type user: User
        :return: True if the user is correctly authenticated
        :rtype: bool
        """
        auth = False
        raw_policy: dict = {}
        raw_content: dict[str, list[str]] = {}

        #If we check for a user already authenticated (jwt token) directly get the proper user source
        if user.source_id and user.source_id in self.all_user_sources:
            source_settings = self.all_user_sources[user.source_id]
            if source_settings.US_CAN_AUTH:
                logger.warning("Registered user source %s for user %s forbid authentication." \
                "Might happend if the user source US_CAN_AUTH has changed", user.source_id, user.uid)
            else:
                auth, raw_policy, raw_contact = self._make_us_check_login(source_settings, user)
                if not auth:
                    return False
                user.authenticated = True

        #If first login chekc in all user sources until first match
        if not user.authenticated:
            for source_uid, source_settings in self.all_user_sources.items():
                if source_settings.US_CAN_AUTH:
                    auth, raw_policy, raw_contact = self._make_us_check_login(source_settings, user)
                    if not auth:
                        #User not found in this user source, check the next one
                        continue
                    user.source_id = source_uid
                    user.authenticated = True
                    break

        if not user.authenticated:
            # Creds false or user missing from user source
            return False

        #Get user info
        self.fill_user_with_contact_info(user, raw_contact)
        self.fill_user_with_source_info(user, raw_contact)
        return auth


    def _build_condition_for_search(self, search:str, user:User, us:UserSourceSettingsObj) -> Condition.Condition|None:
        """
        _summary_

        :param user: _description_
        :type user: User
        :param us: _description_
        :type us: UserSourceSettingsObj
        :return: _description_
        :rtype: Condition
        """
        wildcard = '*'
        if us.US_TYPE == "db":
            wildcard = "%"

        search_cond: Condition.Condition
        if search == "":
            #Means we're looking for everyone
            search_cond = Condition.LikeCondition(us.US_FIELD_CN,wildcard)
        else:
            #Build condition, US_FILTER is already given to the user source
            list_cond: list[Condition.Condition] = []

            #Add default condition
            criteria = f"{wildcard}{search}{wildcard}"
            list_cond.append(Condition.LikeCondition(us.US_FIELD_UID, criteria))
            list_cond.append(Condition.LikeCondition(us.US_FIELD_CN, criteria))
            list_cond.append(Condition.LikeCondition(us.US_MAIL[0], criteria))

            #Add admin condition
            for field in us.US_SEARCH_FIELD:
                list_cond.append(Condition.LikeCondition(field, criteria))

            search_cond = Condition.OrCondition(*list_cond)

        #Add hidden users
        list_hidden = []
        for hidden in us.US_HIDDEN_USER:
            list_hidden.append(Condition.NotEqualCondition(us.US_FIELD_UID, hidden))
        if size := len(list_hidden):
            if size == 1:
                search_cond = Condition.AndCondition(search_cond, list_hidden[0])
            else:
                search_cond = Condition.AndCondition(search_cond, Condition.OrCondition(*list_hidden))

        #Add UNIT condition
        if us.US_UNIT_FIELD:
            if not user.unit:
                return None
            search_cond = Condition.AndCondition(search_cond, Condition.EqualCondition(us.US_UNIT_FIELD, user.unit))
        #OR Add Domain Partition
        elif us.US_DOMAIN_PARTITION:
            if us.US_DOMAIN_PARTITION == 1:
                #User can only see user with the same mail domain
                mail_criteria = f"{wildcard}{user.domain}"
                list_cond = [Condition.LikeCondition(us.US_MAIL[0], mail_criteria)]
                for domain in us.US_DOMAIN_VISIBLE:
                    mail_criteria = f"{wildcard}{domain}"
                    list_cond.append(Condition.LikeCondition(us.US_MAIL[0], mail_criteria))
                if len(list_cond) == 1:
                    search_cond = Condition.AndCondition(search_cond, list_cond[0])
                else:
                    search_cond = Condition.AndCondition(search_cond, Condition.OrCondition(*list_cond))
            if us.US_DOMAIN_PARTITION == -1:
                #User can't see anybody except the one set in US_DOMAIN_VISIBLE
                list_cond = []
                for domain in us.US_DOMAIN_VISIBLE:
                    mail_criteria = f"{wildcard}{domain}"
                    list_cond.append(Condition.LikeCondition(us.US_MAIL[0], mail_criteria))
                if len(list_cond) == 0:
                    #Cannot see anybody with no whitelist, return empty list
                    return None
                elif len(list_cond) == 1:
                    search_cond = Condition.AndCondition(search_cond, list_cond[0])
                else:
                    search_cond = Condition.AndCondition(search_cond, Condition.OrCondition(*list_cond))
        else:
            #means US_DOMAIN_PARTITION == 0, means everyone see everyone except for US_DOMAIN_NOT_VISIBLE
            list_cond = []
            for domain in us.US_DOMAIN_NOT_VISIBLE:
                mail_criteria = f"{wildcard}{domain}"
                list_cond.append(Condition.NotLikeCondition(us.US_MAIL[0], mail_criteria))
            if len(list_cond) == 1:
                search_cond = Condition.AndCondition(search_cond, list_cond[0])
            elif len(list_cond) > 1:
                search_cond = Condition.AndCondition(search_cond, Condition.OrCondition(*list_cond))

        logger.debug("Conditions for autocomplete: %s", search_cond)
        return search_cond

    def _build_condition_for_match(self, uid_to_find:str, user:User, us:UserSourceSettingsObj) -> Condition.Condition|None:
        """
        _summary_

        :param user: _description_
        :type user: User
        :param us: _description_
        :type us: UserSourceSettingsObj
        :return: _description_
        :rtype: Condition
        """

        #Check if uid_to_find is hidden
        if uid_to_find in us.US_HIDDEN_USER:
            return None

        #Build condition, US_FILTER is already given to the user source
        list_cond: list[Condition.Condition] = []

        #Add default condition
        search_cond: Condition.Condition = Condition.EqualCondition(us.US_FIELD_UID, uid_to_find)

        wildcard = '*'
        if us.US_TYPE == "db":
            wildcard = "%"

        #Add UNIT condition
        if us.US_UNIT_FIELD:
            if not user.unit:
                return None
            search_cond = Condition.AndCondition(search_cond, Condition.EqualCondition(us.US_UNIT_FIELD, user.unit))
        #OR Add Domain Partition
        elif us.US_DOMAIN_PARTITION:
            if us.US_DOMAIN_PARTITION == 1:
                #User can only see user with the same mail domain
                mail_criteria = f"{wildcard}{user.domain}"
                list_cond = [Condition.LikeCondition(us.US_MAIL[0], mail_criteria)]
                for domain in us.US_DOMAIN_VISIBLE:
                    mail_criteria = f"{wildcard}{domain}"
                    list_cond.append(Condition.LikeCondition(us.US_MAIL[0], mail_criteria))
                if len(list_cond) == 1:
                    search_cond = Condition.AndCondition(search_cond, list_cond[0])
                else:
                    search_cond = Condition.AndCondition(search_cond, Condition.OrCondition(*list_cond))
            if us.US_DOMAIN_PARTITION == -1:
                #User can't see anybody except the one set in US_DOMAIN_VISIBLE
                list_cond = []
                for domain in us.US_DOMAIN_VISIBLE:
                    mail_criteria = f"{wildcard}{domain}"
                    list_cond.append(Condition.LikeCondition(us.US_MAIL[0], mail_criteria))
                if len(list_cond) == 0:
                    #Cannot see anybody with no whitelist, return empty list
                    return None
                elif len(list_cond) == 1:
                    search_cond = Condition.AndCondition(search_cond, list_cond[0])
                else:
                    search_cond = Condition.AndCondition(search_cond, Condition.OrCondition(*list_cond))
        else:
            #means US_DOMAIN_PARTITION == 0, means everyone see everyone except for US_DOMAIN_NOT_VISIBLE
            list_cond = []
            for domain in us.US_DOMAIN_NOT_VISIBLE:
                mail_criteria = f"{wildcard}{domain}"
                list_cond.append(Condition.NotLikeCondition(us.US_MAIL[0], mail_criteria))
            if len(list_cond) == 1:
                search_cond = Condition.AndCondition(search_cond, list_cond[0])
            elif len(list_cond) > 1:
                search_cond = Condition.AndCondition(search_cond, Condition.OrCondition(*list_cond))

        logger.debug("Conditions for autocomplete: %s", search_cond)
        return search_cond


    def fill_user_with_contact_info(self, user:User, user_info:dict) -> None:
        """
        Fill user with the contact info

        :param uid: The user unique ID
        :type uid: str
        :return: Dictionary containing user contact information (uid, cn, email)
        :rtype: dict
        """

        #At this stage, the user must have a source_id as it already has been logged in.
        if not user.source_id or user.source_id not in self.all_user_sources:
            raise exc.AggravatedException("User with no source_id")

        user_source_settings = self.all_user_sources[user.source_id]
        user.cn =   user_info[user_source_settings.US_FIELD_CN][0]
        user.mail = user_info[user_source_settings.US_MAIL[0]][0]
        user.domain = get_domain_from_mail(user.mail) or ""
        if user_source_settings.US_UNIT_FIELD:
            try:
                user.unit = user_info[user_source_settings.US_UNIT_FIELD][0]
            except KeyError as e:
                logger.error("US_UNIT_FIELD is set (%s) but there is no value for user %s", user_source_settings.US_UNIT_FIELD, user.uid)
                raise exc.RequestException(error=err.ERROR_US_USER_UNIT_MISSING) from e

        #Check for others mails address
        for key_mail in user_source_settings.US_MAIL:
            for new_mail in user_info.get(key_mail, []):
                if new_mail != user.mail:
                    user.extra_mail.append(new_mail)

        #Check if we have extra info in the user_info
        if user_source_settings.US_MAPPING:
            for key_sogo, key_user_source in user_source_settings.US_MAPPING.items():
                if info := user_info.get(key_user_source):
                    #TODO parse into contactCard, beware that each user_info is a list and may need to be a single value
                    user.extra_info[key_sogo] = info


    def fill_user_with_source_info(self, user:User, user_info:dict) -> None:
        """
        WIll fecth the user source for extra info required by user source config.
        Mainly there is the US_MAPPING wich are contact info.
        Secondly there is some mails parameters, and module access.

        :param user: _description_
        :type user: User
        """
        #At this stage, the user mus have a source_id as it already has been logged in.
        if not user.source_id or user.source_id not in self.all_user_sources:
            raise exc.AggravatedException("User with no source_id")

        user_source_settings = self.all_user_sources[user.source_id]

        # Get, if needed, the proper login for mail
        user.login_mail_server = user.mail
        user.login_mail_outgoing = user.mail
        user.login_mail_filtering = user.mail
        if user_source_settings.US_MAIL_SERVER_LOGIN:
            user.login_mail_server = user_info.get(user_source_settings.US_MAIL_SERVER_LOGIN, user.mail)
        if user_source_settings.US_MAIL_OUTGOING_LOGIN:
            user.login_mail_outgoing = user_info.get(user_source_settings.US_MAIL_OUTGOING_LOGIN, user.mail)
        if user_source_settings.US_MAIL_FILTERING_LOGIN:
            user.login_mail_filtering = user_info.get(user_source_settings.US_MAIL_FILTERING_LOGIN, user.mail)

        # Get, if needed, the proper imap DEPRECATED
        if user_source_settings.US_IMAP_HOST_FIELDNAME:
            user.imap_host = user_info.get(user_source_settings.US_IMAP_HOST_FIELDNAME, "")

        if user_source_settings.US_MODULE_ACCESS:
            for module_name, conditions in user_source_settings.US_MODULE_ACCESS.items():
                for cond_name, cond_value in conditions.items():
                    if user_info.get(cond_name, None) == cond_value:
                        setattr(user.access, module_name.lower(), False)


    def get_contact_info_for_user(self, user_auth:User, user_to_find:User) -> None:
        """
        Try to find the user_to_dinf amonf user_auth user source configuration
        Doesn't return anything but change user_to_find instance

        :param user: _description_
        :type user: _type_
        :return: _description_
        :rtype: dict
        """
        for us_uid, us_settings in self.all_user_sources.items():

            if not us_settings.US_IS_ADDRESSBOOK:
                continue

            search_cond = self._build_condition_for_match(user_to_find.uid, user_auth, us_settings)
            if search_cond is None:
                #It happends if the conf for domains visibility says the user can't see anything.
                continue

            #Get client
            client_us = self._get_manager_for_user_source(us_settings)
            record =  client_us.get_user_info(user_to_find.uid, search_cond, user_auth.uid, user_auth.domain, user_auth.password)
            if not record:
                continue
            else:
                user_to_find.source_id = us_uid
                self.fill_user_with_contact_info(user_to_find, record)
                self.fill_user_with_source_info(user_to_find, record)


    def search_for_all_us(self, search: str, user: User, limit:int = 100) -> list[dict]:
        """
        _summary_

        :param search: _description_
        :type search: str
        :param user: _description_
        :type user: User
        :return: _description_
        :rtype: dict
        """
        tmp_limit = limit
        results: list[dict] = []
        for _, us_settings in self.all_user_sources.items():
            if tmp_limit <= 0:
                break

            if not us_settings.US_IS_ADDRESSBOOK:
                continue

            search_cond = self._build_condition_for_search(search, user, us_settings)
            if search_cond is None:
                #It happends if the conf for domains visibility says the user can't see anything.
                continue

            #Get client
            client_us = self._get_manager_for_user_source(us_settings)
            search_iter = client_us.search_user(search, search_cond,
                                                        limit, offset=0, sort="", order="",
                                                        username=user.uid, domain=user.domain, password=user.password)
            total = next(search_iter)
            for record in search_iter:
                #TODO it's the interface that should do this not the module
                tmp_user: dict = {}
                tmp_user["us_uid"] = us_settings.US_UID
                tmp_user["us_name"] = us_settings.US_DISPLAY_NAME or us_settings.US_NAME
                tmp_user["uid"] = record[us_settings.US_FIELD_UID][0]
                tmp_user["emails"] = []
                for email_field in us_settings.US_MAIL:
                    tmp_user["emails"].extend(record[email_field])
                #TODO: add config for admin to syntax the name returned, here it was SOGo 5 behavior getting display name, if not fall back on cn
                if "displayname" in record:
                    tmp_user["name"] =  record["displayname"][0]
                else:
                    tmp_user["name"] =  record[us_settings.US_FIELD_CN][0]
                results.append(tmp_user)
                tmp_limit -= 1

        return results

    def search_for_one_us(self, us_uid: str, search: str, user: User, limit:int = 100, offset:int=0) -> tuple[int, list[dict]]:
        """
        _summary_

        :param search: _description_
        :type search: str
        :param user: _description_
        :type user: User
        :return: _description_
        :rtype: dict
        """
        results: list[dict] = []

        us_settings = self.all_user_sources.get(us_uid)
        if not us_settings:
            return 0, []

        if not us_settings.US_IS_ADDRESSBOOK:
            return 0, []

        search_cond = self._build_condition_for_search(search, user, us_settings)
        if search_cond is None:
            #It happends if the conf for domains visibility says the user can't see anything.
            return 0, []

        #Get client
        client_us = self._get_manager_for_user_source(us_settings)
        search_iter = client_us.search_user(search, search_cond,
                                            limit, offset=offset, sort="", order="",
                                            username=user.uid, domain=user.domain, password=user.password)
        total = next(search_iter)
        for record in search_iter:
            results.append(CardGABContact.serializer(record, us_settings))

        return total["total"], results
