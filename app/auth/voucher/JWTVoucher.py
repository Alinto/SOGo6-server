import jwt

from app.utils.logger.logger import logger
from app.utils import exceptions as exc

from .Voucher import Voucher

class JWTVoucher(Voucher):
    """
    Voucher with is a JWT token

    :param Voucher: _description_
    :type Voucher: _type_
    """
    def __init__(self, secret:str, validity: int) -> None:
        super().__init__()
        self.secret = secret
        self.validity = validity

    def create_voucher(self, payload: dict) -> str:
        """
        Create a JWT token with the payload
        """
        token = jwt.encode(payload, self.secret, algorithm="HS256")
        return token

    def read_voucher(self, voucher:str) -> dict:
        """
        Get a JWT token and return the payload
        """
        try:
            payload = jwt.decode(voucher, self.secret, algorithms="HS256")
            return payload
        except jwt.ExpiredSignatureError as e:
            logger.error("JWT Token has expired: %s", str(e))
        return {}
