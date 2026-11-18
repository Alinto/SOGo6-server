from __future__ import annotations

from app.module.auth.mfa.MfaProvider import MfaProvider


class ProviderExternalOtp(MfaProvider):
    """
    External OTP: SOGo talks to an outside service over HTTP. Two modes (see spec_mfa.md):

    - send: SOGo generates the code (secrets), sends it through `send_request` (e.g. SMS gateway),
      keeps an HMAC of it in the challenge and checks it locally.
    - validate: SOGo optionally calls `send_request` as a trigger, then sends the typed code
      to `validate_request`; the `success` rule decides.

    NOT IMPLEMENTED YET. It is not registered in registry.py and 'external_otp' is not
    accepted by SOGO_D_LOGIN_MFA_METHOD, so it can't be selected.
    To do when implementing it:
    - settings block (mode, timeout, send_request, validate_request, success rule) in AuthSettings,
      with the cross check of the placeholders against US_MAPPING
    - request builder (placeholders substituted in parsed values, encoded by requests),
      success rule, fail closed on timeout/network error
    - register it in registry.py and add 'external_otp' to SOGO_D_LOGIN_MFA_METHOD
    - admin endpoint POST /config/mfa/test
    """
    id = "external_otp"
    requires_enrollment = True

    def begin_enrollment(self) -> tuple[dict, dict]:
        raise NotImplementedError("External OTP is not implemented yet")

    def confirm_enrollment(self, pending: dict, code: str) -> dict | None:
        raise NotImplementedError("External OTP is not implemented yet")

    def start_challenge(self, method: dict) -> dict:
        raise NotImplementedError("External OTP is not implemented yet")

    def verify(self, method: dict, challenge: dict, code: str) -> bool:
        raise NotImplementedError("External OTP is not implemented yet")
