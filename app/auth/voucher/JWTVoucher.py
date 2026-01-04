from typing import Any
from time import time

import jwt

from app.utils.logger.logger import logger
from app.utils import constants as cs
from app.utils import exceptions as exc
from app.utils import errors as err

from .Voucher import Voucher

class JWTVoucher(Voucher):
    """
    Voucher with is a JWT token

    :param Voucher: _description_
    :type Voucher: _type_
    """

    @staticmethod
    def get_needed_parameters_to_instantiate() -> dict[str, tuple[str, str]]:
        """
        JWT token only needs a secret to encode and decode the payload
        """
        return {"process_settings": ("SOGO_P_VOUCHER_SECRET", "secret")}

    def __init__(self, secret:str) -> None:
        super().__init__()
        self.secret = secret

    def create_voucher(self, payload: dict, validity: int) -> str:
        """
        Create a JWT token with the payload and a validity
        """
        if validity <= 0:
            raise exc.BugException(f"Validity time invalid {validity}", err.ERROR_VALIDITY_TIME_BELOW_0)

        payload[cs.JWT_ISS] = "SOGo6" #Issuer
        payload[cs.JWT_EXP] = int(time()) + validity #Expiration

        token = jwt.encode(payload, self.secret, algorithm="HS256")
        return token

    def check_voucher_data_type(self, voucher_data:Any) -> bool:
        """
        check

        :return: _description_
        :rtype: bool
        """
        return isinstance(voucher_data, str)

    def read_voucher(self, voucher_data:str) -> dict|None:
        """
        Get a JWT token and return the payload
        """
        payload = None
        try:
            payload = jwt.decode(voucher_data, self.secret, algorithms="HS256")
            return payload
        except jwt.ExpiredSignatureError as e:
            logger.error("JWT Token has expired: %s", str(e))

        return payload
