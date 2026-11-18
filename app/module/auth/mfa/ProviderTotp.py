from __future__ import annotations
import hmac
import time

import pyotp

from app.module.auth.mfa.MfaProvider import MfaProvider
from app.utils import constants as cs


TOTP_PERIOD = 30         #RFC 6238 time step, in seconds
TOTP_DIGITS = 6
TOTP_VALID_WINDOW = 1    #Steps accepted before and after the current one (+-30 s)
TOTP_SECRET_LENGTH = 32  #base32 chars = 160 bits
#A used step must stay marked as long as it can be accepted
TTL_TOTP_USED = (2 * TOTP_VALID_WINDOW + 1) * TOTP_PERIOD


class ProviderTotp(MfaProvider):
    """
    TOTP (RFC 6238): SHA-1, 6 digits, 30 s period, +-1 step.

    Stored method: {"provider": "totp", "secret": <Fernet token of the base32 secret>, ...}
    """
    id = "totp"
    requires_enrollment = True

    def begin_enrollment(self) -> tuple[dict, dict]:
        """
        Generate a new secret and the otpauth:// URI the frontend turns into a QR code.
        The secret is returned in clear only here, for manual entry.
        """
        secret = pyotp.random_base32(TOTP_SECRET_LENGTH)
        issuer: str = getattr(self.ctx.auth_settings, "SOGO_D_LOGIN_MFA_TOTP_ISSUER", "SOGo") or "SOGo"
        uri = pyotp.TOTP(secret, digits=TOTP_DIGITS, interval=TOTP_PERIOD).provisioning_uri(
            name=self.ctx.mail or self.ctx.uid, issuer_name=issuer)
        pending = {"provider": self.id, "secret": self.crypto.encrypt(secret)}
        public = {"provider": self.id, "otpauth_uri": uri, "secret": secret}
        return public, pending

    def confirm_enrollment(self, pending: dict, code: str) -> dict | None:
        """
        One valid code confirms the secret. The step is marked as used, so the same code
        can't be used to log in.
        """
        if not self._verify_encrypted_secret(pending["secret"], code):
            return None
        return {"provider": self.id, "secret": pending["secret"]}

    def start_challenge(self, method: dict) -> dict:
        """
        Nothing to send for TOTP
        """
        return {}

    def verify(self, method: dict, challenge: dict, code: str) -> bool:
        """
        Check the code against the stored secret, with replay protection
        """
        return self._verify_encrypted_secret(method["secret"], code)

    def _verify_encrypted_secret(self, encrypted_secret: str, code: str) -> bool:
        """
        pyotp's verify(valid_window=1) doesn't say which step matched, which the replay
        protection needs: loop over the steps and use pyotp only to compute each code.

        The used step is marked in the cache with SET NX: if two requests send the same code
        at the same time, only one is accepted.
        The key includes a fingerprint of the encrypted secret so that a code of the current method
        and a code of a new method (being enrolled) at the same step don't collide.

        :param encrypted_secret: Fernet token of the base32 secret
        :type encrypted_secret: str
        :param code: code given by the user
        :type code: str
        :return: True if the code is valid and was never used
        :rtype: bool
        """
        if not isinstance(code, str) or len(code) != TOTP_DIGITS or not code.isdigit():
            return False

        secret = self.crypto.decrypt(encrypted_secret)
        totp = pyotp.TOTP(secret, digits=TOTP_DIGITS, interval=TOTP_PERIOD)
        current_step = int(time.time()) // TOTP_PERIOD
        for step in range(current_step - TOTP_VALID_WINDOW, current_step + TOTP_VALID_WINDOW + 1):
            if hmac.compare_digest(totp.at(step * TOTP_PERIOD), code):
                used_key = f"{cs.MFA_TOTP_USED_PREFIX}{self.ctx.uid}:{self.crypto.fingerprint(encrypted_secret)}:{step}"
                return self.cache.set(used_key, "1", TTL_TOTP_USED, nx=True)
        return False
