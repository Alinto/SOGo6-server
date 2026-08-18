from __future__ import annotations
from typing import TYPE_CHECKING

from flask import g, request
from flask.views import MethodView
from flask.typing import ResponseReturnValue
from flask_smorest import Blueprint

from app.config.settings.DomainSettings import MailSettings
from app.interface.mail.InterfaceApiMailFilter import InterfaceApiMailFilter
from app.utils.api.ApiBaseResponse import create_api_base_response
from app.utils.errors import ERROR_MAIL_FILTERING_DISABLED, ERROR_MAIL_FILTER_FEATURE_DISABLED
from app.utils.logger.logger import logger_api
from .schemas.filter import (
    FiltersPayloadSchema,
    VacationPayloadSchema,
    ForwardPayloadSchema,
    NotificationPayloadSchema,
    FiltersSetResponseSchema,
    FiltersGetResponseSchema,
    VacationGetResponseSchema,
    ForwardGetResponseSchema,
    NotificationGetResponseSchema,
)

if TYPE_CHECKING:
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.auth.User import User

blp = Blueprint("Mail Filters", __name__, url_prefix="/mailboxes/<string:account_id>")


@blp.before_request
def init_filter_config() -> ResponseReturnValue | None:
    """Initialize the filter interface for the request."""
    logger_api.debug("Calling before_request for ApiMailFilter")
    process: ProcessSetting = g.process_settings
    user_domain_settings: dict = g.user_domain_settings
    user: User = g.user

    mail_settings: dict = user_domain_settings.get(MailSettings.subparent, {})


    if not mail_settings.get("SOGO_D_MAIL_FILTERING_ENABLED", True):
        return create_api_base_response(None, ERROR_MAIL_FILTERING_DISABLED)

    _ROUTE_SETTING_MAP = {
        "/vacation": "SOGO_D_VACATION_ENABLED",
        "/forward":  "SOGO_D_FORWARD_ENABLED",
        "/notify":   "SOGO_D_NOTIFY_ENABLED",
    }

    for suffix, setting_key in _ROUTE_SETTING_MAP.items():
        if request.path.endswith(suffix):
            if not mail_settings.get(setting_key, False):
                logger_api.debug(
                    "Access denied for %s: %s is False", request.path, setting_key
                )
                return create_api_base_response(None, ERROR_MAIL_FILTER_FEATURE_DISABLED)
            break

    g.inter = InterfaceApiMailFilter(
        process_setting=process,
        user_domain_settings=user_domain_settings,
        user=user,
    )


@blp.route("/filters")
class ApiMailFilterResource(MethodView):
    """API resource for mail filter rules."""

    @blp.response(200, FiltersGetResponseSchema, example=FiltersGetResponseSchema.example())
    def get(self, account_id: str) -> ResponseReturnValue:
        """Return the ``filters`` list for a given account.

        :param account_id: Account identifier.
        :type account_id: str
        :return: ApiBaseResponse with the current filters list.
        :rtype: ResponseReturnValue
        """
        logger_api.debug("ApiMailFilterResource.get for account_id: %s", account_id)
        interface: InterfaceApiMailFilter = g.inter
        return interface.get_filters()

    @blp.arguments(FiltersPayloadSchema, example=FiltersPayloadSchema.example(), error_status_code=400)
    @blp.response(200, FiltersSetResponseSchema, example=FiltersSetResponseSchema.example())
    def post(self, payload: dict, account_id: str) -> ResponseReturnValue:
        """Replace the ``filters`` list for a given account.

        :param payload: Validated body — must contain a ``filters`` key.
        :type payload: dict
        :param account_id: Account identifier.
        :type account_id: str
        :return: ApiBaseResponse with the full updated stored content.
        :rtype: ResponseReturnValue
        """
        logger_api.debug("ApiMailFilterResource.post for account_id: %s", account_id)
        interface: InterfaceApiMailFilter = g.inter
        return interface.set_filters(payload["filters"])


@blp.route("/vacation")
class ApiMailVacationResource(MethodView):
    """API resource for vacation / auto-reply settings."""


    @blp.response(200, VacationGetResponseSchema, example=VacationGetResponseSchema.example())
    def get(self, account_id: str) -> ResponseReturnValue:
        """Return the ``Vacation`` section for a given account.

        :param account_id: Account identifier.
        :type account_id: str
        :return: ApiBaseResponse with the current vacation settings.
        :rtype: ResponseReturnValue
        """
        logger_api.debug("ApiMailVacationResource.get for account_id: %s", account_id)
        interface: InterfaceApiMailFilter = g.inter
        return interface.get_vacation()

    @blp.arguments(VacationPayloadSchema, example=VacationPayloadSchema.example(), error_status_code=400)
    @blp.response(200, FiltersSetResponseSchema, example=FiltersSetResponseSchema.example())
    def post(self, payload: dict, account_id: str) -> ResponseReturnValue:
        """Replace the ``Vacation`` section for a given account.

        :param payload: Validated body — must contain a ``Vacation`` key.
        :type payload: dict
        :param account_id: Account identifier.
        :type account_id: str
        :return: ApiBaseResponse with the full updated stored content.
        :rtype: ResponseReturnValue
        """
        logger_api.debug("ApiMailVacationResource.post for account_id: %s", account_id)
        interface: InterfaceApiMailFilter = g.inter
        return interface.set_vacation(payload["Vacation"])


@blp.route("/forward")
class ApiMailForwardResource(MethodView):
    """API resource for mail forwarding settings."""

    @blp.response(200, ForwardGetResponseSchema, example=ForwardGetResponseSchema.example())
    def get(self, account_id: str) -> ResponseReturnValue:
        """Return the ``Forward`` section for a given account.

        :param account_id: Account identifier.
        :type account_id: str
        :return: ApiBaseResponse with the current forward settings.
        :rtype: ResponseReturnValue
        """
        logger_api.debug("ApiMailForwardResource.get for account_id: %s", account_id)
        interface: InterfaceApiMailFilter = g.inter
        return interface.get_forward()

    @blp.arguments(ForwardPayloadSchema, example=ForwardPayloadSchema.example(), error_status_code=400)
    @blp.response(200, FiltersSetResponseSchema, example=FiltersSetResponseSchema.example())
    def post(self, payload: dict, account_id: str) -> ResponseReturnValue:
        """Replace the ``Forward`` section for a given account.

        :param payload: Validated body — must contain a ``Forward`` key.
        :type payload: dict
        :param account_id: Account identifier.
        :type account_id: str
        :return: ApiBaseResponse with the full updated stored content.
        :rtype: ResponseReturnValue
        """
        logger_api.debug("ApiMailForwardResource.post for account_id: %s", account_id)
        interface: InterfaceApiMailFilter = g.inter
        return interface.set_forward(payload["Forward"])


@blp.route("/notify")
class ApiMailNotifyResource(MethodView):
    """API resource for mail notification settings."""

    @blp.response(200, NotificationGetResponseSchema, example=NotificationGetResponseSchema.example())
    def get(self, account_id: str) -> ResponseReturnValue:
        """Return the ``Notification`` section for a given account.

        :param account_id: Account identifier.
        :type account_id: str
        :return: ApiBaseResponse with the current notification settings.
        :rtype: ResponseReturnValue
        """
        logger_api.debug("ApiMailNotifyResource.get for account_id: %s", account_id)
        interface: InterfaceApiMailFilter = g.inter
        return interface.get_notification()

    @blp.arguments(NotificationPayloadSchema, example=NotificationPayloadSchema.example(), error_status_code=400)
    @blp.response(200, FiltersSetResponseSchema, example=FiltersSetResponseSchema.example())
    def post(self, payload: dict, account_id: str) -> ResponseReturnValue:
        """Replace the ``Notification`` section for a given account.

        :param payload: Validated body — must contain a ``Notification`` key.
        :type payload: dict
        :param account_id: Account identifier.
        :type account_id: str
        :return: ApiBaseResponse with the full updated stored content.
        :rtype: ResponseReturnValue
        """
        logger_api.debug("ApiMailNotifyResource.post for account_id: %s", account_id)
        interface: InterfaceApiMailFilter = g.inter
        return interface.set_notification(payload["Notification"])
