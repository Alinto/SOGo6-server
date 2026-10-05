from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config.settings.DomainSettings import UserSourceSettingsObj

def mail_serializer(mail:str) -> dict:
    """
    _summary_

    :param mail: _description_
    :type mail: str
    """
    return {"value": mail, "types": ["work"], "pref": 1}

class CardGABContact:
    """
    Class to convert data from user sources to Card element
    """

    @staticmethod
    def serializer(contact:dict[str, list[str]|str], us_setting:UserSourceSettingsObj) -> dict:
        """
        Mapping comes from US_MAPPING

        :param contact: _description_
        :type contact: dict
        :param mapping: _description_
        :type mapping: dict
        """
        mapping = us_setting.US_MAPPING
        mails: list[str] = []
        for email_field in us_setting.US_MAIL:
            if email_field in contact:
                mails.extend(contact[email_field])
        return {
            "key": contact[us_setting.US_FIELD_UID][0],
            "addressbook_key": us_setting.US_UID,
            "uid": contact[us_setting.US_FIELD_UID][0],
            "kind": "individual",
            "first_name": contact[us_setting.US_FIELD_CN][0],
            "emails": [mail_serializer(e) for e in mails]
        }
