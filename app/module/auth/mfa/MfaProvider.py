from __future__ import annotations
from typing import TYPE_CHECKING, ClassVar
from abc import ABC, abstractmethod
from dataclasses import dataclass

if TYPE_CHECKING:
    from app.config.settings.DomainSettings import AuthSettingsObj
    from app.manager.cache.ClientRedis import ClientRedis
    from app.module.auth.mfa.MfaCrypto import MfaCrypto


@dataclass
class MfaContext:
    """
    Everything a provider needs to know about the user and the domain.
    The context is built either from a user session or from an MFA session.

    :param uid: uid of the user, same as in sogo_user_profiles
    :param mail: mail of the user (used e.g. as the TOTP account name)
    :param auth_settings: effective auth settings of the user's domain
    """
    uid: str
    mail: str
    auth_settings: AuthSettingsObj | None


class MfaProvider(ABC):
    """
    Base class of every MFA method.

    A provider is stateless: what must be kept between two requests is returned
    to ModuleMfa, which stores it (pending enrollment in the cache, method in the user profile,
    challenge in the MFA session).

    Adding a method = one subclass + its registration in registry.py (+ its settings).

    The `method` dict is what is stored in the column mfa_method of the user profile.
    It always has the key "provider" (= id), the rest is provider specific.
    """
    #Stable id of the method, used in settings (SOGO_D_LOGIN_MFA_METHOD) and in the stored method
    id: ClassVar[str] = ""
    #True if the method must be set up (and confirmed) before being usable at login
    requires_enrollment: ClassVar[bool] = True

    def __init__(self, ctx: MfaContext, cache: ClientRedis, crypto: MfaCrypto):
        self.ctx = ctx
        self.cache = cache
        self.crypto = crypto

    @abstractmethod
    def begin_enrollment(self) -> tuple[dict, dict]:
        """
        Start the setup of the method for the user.

        :return: (data sent back to the user, pending enrollment data kept in the cache until confirmation).
                 The pending data must be json serializable and must not contain any secret in clear.
        :rtype: tuple[dict, dict]
        """

    @abstractmethod
    def confirm_enrollment(self, pending: dict, code: str) -> dict | None:
        """
        Check the code against the pending enrollment.

        :param pending: pending data returned by begin_enrollment
        :type pending: dict
        :param code: code given by the user
        :type code: str
        :return: the method dict to store in the user profile, None if the code is wrong
        :rtype: dict | None
        """

    @abstractmethod
    def start_challenge(self, method: dict) -> dict:
        """
        Called at login, after the password check, before asking the code
        (e.g. External OTP sends the code). Nothing to do for TOTP.

        :param method: the stored method of the user
        :type method: dict
        :return: the challenge state kept in the MFA session (json serializable, no code in clear)
        :rtype: dict
        """

    @abstractmethod
    def verify(self, method: dict, challenge: dict, code: str) -> bool:
        """
        Check a code given by the user for the stored method.

        :param method: the stored method of the user
        :type method: dict
        :param challenge: the challenge state returned by start_challenge ({} outside of the login)
        :type challenge: dict
        :param code: code given by the user
        :type code: str
        :return: True if the code is valid
        :rtype: bool
        """
