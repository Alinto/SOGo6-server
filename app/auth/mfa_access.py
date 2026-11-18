"""
Endpoints reachable with an MFA session, per stage.

An MFA session gives access to nothing else: on every other endpoint the request is anonymous.
Keys are Flask endpoints of the basic api ("user#<Blueprint>.v1_<Blueprint>.<Blueprint>.<View>").
"""
from app.utils import constants as cs

MFA_ENDPOINT_VERIFY = "user#Auth.v1_Auth.Auth.ApiAuthUserMfaVerify"
MFA_ENDPOINT_BEGIN = "user#Mfa.v1_Mfa.Mfa.ApiUserMfa"
MFA_ENDPOINT_CONFIRM = "user#Mfa.v1_Mfa.Mfa.ApiUserMfaConfirm"

MFA_STAGE_ENDPOINTS: dict[str, set[tuple[str, str]]] = {
    cs.MFA_STAGE_VERIFY: {
        (MFA_ENDPOINT_VERIFY, "POST"),
    },
    cs.MFA_STAGE_ENROLL: {
        (MFA_ENDPOINT_BEGIN, "POST"),
        (MFA_ENDPOINT_CONFIRM, "POST"),
    },
}


def is_endpoint_allowed_for_mfa_stage(stage: str, endpoint: str | None, method: str) -> bool:
    """
    Tell if an MFA session at this stage can call this endpoint with this HTTP method

    :param stage: stage of the MFA session (cs.MFA_STAGE_VERIFY or cs.MFA_STAGE_ENROLL)
    :type stage: str
    :param endpoint: Flask endpoint of the request
    :type endpoint: str | None
    :param method: HTTP method of the request
    :type method: str
    :return: True if allowed
    :rtype: bool
    """
    if not endpoint:
        return False
    return (endpoint, method.upper()) in MFA_STAGE_ENDPOINTS.get(stage, set())
