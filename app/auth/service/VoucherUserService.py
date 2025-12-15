
from typing import Any, Type

from app.auth.User import User
from app.auth.voucher.Voucher import Voucher
from app.config.settings.ProcessSetting import ProcessSetting
from app.utils.dynamic_import import import_and_get_class
from app.utils.exceptions import RequestException


class VoucherUserService:
    """
    Class that can genarte a user session and the associated user, ot get the user session from
    a voucher
    """

    def __init__(self, process_settings:ProcessSetting, auth_settings:dict):
        self.process_settings = process_settings
        self.auth_settings = auth_settings
        

    def generate_voucher_from_user(self, user: User):
        """
        Generate a voucher and the user session for this User

        :param user: _description_
        :type user: User
        """
    
    def generate_user_from_voucher(self,  data: Any):
        """
        Get a voucher instance and the expected data for it

        :param user: _description_
        :type user: User
        """
        #If we were allowing different coucher type, here will be the settings
        voucher_type = "JWTVoucher"
        voucher_class: Type[Voucher] = import_and_get_class("app.auth.voucher", voucher_type)

        needed_data = voucher_class.get_needed_parameters_to_instantiate()
        kargs = {}
        for kind, name in needed_data.items():
            if kind == "process_settings":
                kargs["secret"] = self.process_settings[name]
        voucher = voucher_class(**kargs)

        if voucher.check_voucher_data_type(data):
            payload = voucher.read_voucher(data)
            if not payload:
                raise RequestException("Voucher has expired or cannot be read")
            return self._get_user_session_from_payload(payload)

        else:
            raise RequestException("Wrong data type for voucher")


    def _get_user_session_from_payload(self, payload:dict):
        """
        The payload is encrypted and is supposed to have the
        session_key to get the userSession and decrypt it.
        
        :param payload: 
        :type payload: dict
        """

        




        

        