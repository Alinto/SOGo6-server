
from app.auth.User import User
from app.config.settings.ProcessSetting import ProcessSetting


class VoucherUserService:
    """
    Class that can genarte a user session and the associated user, ot get the user session from
    a voucher
    """

    def __init__(self, process_settings:ProcessSetting, auth_settings:dict):
        self.process_settings = process_settings
        self.auth_settings = auth_settings
        

    def generate_from_user(user: User):
        """
        Generate a voucher and the user session for this User

        :param user: _description_
        :type user: User
        """
        