"""
MFA settings of AuthSettings: invalid values are refused on save.
"""
import pytest
from marshmallow import ValidationError, EXCLUDE

from app.config.settings.DomainSettings import AuthSettings


def load(data: dict) -> dict:
    return AuthSettings().load(data, unknown=EXCLUDE)


def test_defaults():
    ret = load({})
    assert ret["SOGO_D_LOGIN_MFA"] is True
    assert ret["SOGO_D_LOGIN_MFA_FORCE"] is False
    assert ret["SOGO_D_LOGIN_MFA_TOTP_ISSUER"] == "SOGo"


def test_force_without_method_refused():
    with pytest.raises(ValidationError) as exc:
        load({"SOGO_D_LOGIN_MFA": True, "SOGO_D_LOGIN_MFA_FORCE": True, "SOGO_D_LOGIN_MFA_METHOD": []})
    assert "SOGO_D_LOGIN_MFA_FORCE" in exc.value.messages


def test_force_with_method_ok():
    ret = load({"SOGO_D_LOGIN_MFA_FORCE": True, "SOGO_D_LOGIN_MFA_METHOD": ["totp"]})
    assert ret["SOGO_D_LOGIN_MFA_FORCE"] is True


def test_force_ignored_when_mfa_disabled():
    load({"SOGO_D_LOGIN_MFA": False, "SOGO_D_LOGIN_MFA_FORCE": True})


@pytest.mark.parametrize("methods", [["sms"], ["external_otp"], ["totp", "push"]])
def test_unknown_method_refused(methods):
    with pytest.raises(ValidationError):
        load({"SOGO_D_LOGIN_MFA_METHOD": methods})


def test_empty_issuer_refused():
    with pytest.raises(ValidationError):
        load({"SOGO_D_LOGIN_MFA_TOTP_ISSUER": ""})
