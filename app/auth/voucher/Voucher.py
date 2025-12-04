from abc import abstractmethod, ABCMeta
from typing import Any

class Voucher(metaclass=ABCMeta):
    """
    Abstract Class that handle voucher
    """
    def __init__(self) -> None:
        """
        It shouldn't raise any Exception as SOGo will instantiate the object but not necessarily use it right on spot
        """

    @abstractmethod
    def create_voucher(self, payload: dict) -> Any:
        """
        Create a unique voucher
        """

    @abstractmethod
    def read_voucher(self, voucher: Any) -> Any:
        """
        Create a unique voucher
        """
