from abc import abstractmethod, ABCMeta
from typing import Any

class Voucher(metaclass=ABCMeta):
    """
    Abstract Class that handle voucher
    A voucher is the data send to the API client to make authenticated request after.

    For now, SOGo 6 only used JWT Token. But abstract class is used to facilitate implementation of new methods
    in the future.
    """
    def __init__(self) -> None:
        """
        
        """
 

    @abstractmethod
    def create_voucher(self, payload: dict, validity: int) -> Any:
        """
        Create a unique voucher for this payload
        """
    
    @staticmethod
    @abstractmethod
    def get_needed_parameters_to_instantiate() -> dict[str, tuple[str, str]]:
        """
        Each type of voucher will need specific parameters for __init__
        This method, to use first, return a dict with then name of the parameters and where to find them.
        It laso give the argument name for **kwargs
        {
            "source": ("param_name", "arg_name"),
            ...
        }

        Example: JWT Voucher need the the SOGO_JWT_SECRET found in process settings
        and the validity time found in domain_settings.AUTH_SETTINGS

        This methods return:
        {
            "process_settings": ()"SOGO_JWT_SECRET", "secret")
        }
        """

    @abstractmethod
    def check_voucher_data_type(self, voucher_data: Any) -> bool:
        """
        Check if the data received is what the kind of the voucher expects

        example: JWT Voucher expect a string

        :return: _description_
        :rtype: bool
        """

    @abstractmethod
    def read_voucher(self, voucher_data: Any) -> dict|None:
        """
        Get the payload from the voucher
        """
