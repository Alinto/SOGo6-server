from __future__ import annotations
from typing import TYPE_CHECKING, Any

from app.config.db import tables as tbl
from app.utils import errors as err
from app.utils.constants import (
    FILTER_SIEVE_SECTIONS,
)
from app.utils.db.Condition import EqualCondition
from app.utils.exceptions import RequestException, BugException
from app.utils.module.importManager import import_and_instantiate_manager
from app.utils.logger.logger import logger_sieve

if TYPE_CHECKING:
    from app.auth.User import User
    from app.config.settings.DomainSettings import MailSettingsObj
    from app.config.settings.ProcessSetting import ProcessSetting
    from app.manager.mail.ClientFiltering import ClientFiltering
    from app.manager.db.ClientSQL import ClientSQL


REGISTRY_FILTERING_MANAGER: dict[str, str] = {
    "sieve": "ClientSieve",
}


class ModuleFilter:
    """
    Module to handle mail filter operations.

    Communicates with:
    - ClientFiltering (currently ClientSieve) to push filters to the mail server.
    - ClientSQL (currently ClientPostgreSQL) to persist filters in the user profile.
    """

    def __init__(self, user: User, mail_settings: MailSettingsObj, process_settings: ProcessSetting) -> None:
        self.user = user
        self.mail_settings = mail_settings
        self.process_settings = process_settings

        sogo_db_type = f"Client{process_settings.SOGO_P_DB_TYPE}"
        self.sogo_db_manager: ClientSQL = import_and_instantiate_manager(
            module_path="app.manager.db",
            module_and_class_name=sogo_db_type,
            module_args=process_settings.get_db_settings()
        )

    # ------------------------------------------------------------------ #
    # Filtering client                                                         #
    # ------------------------------------------------------------------ #

    def _get_filtering_conf(self) -> dict:
        """Build the filtering client configuration dict from the current mail settings.

        :raises BugException: If ``SOGO_D_MAIL_FILTERING_TYPE`` is not in the registry.
        :return: Filtering client configuration dict.
        :rtype: dict
        """
        filtering_type = self.mail_settings.SOGO_D_MAIL_FILTERING_TYPE

        if filtering_type not in REGISTRY_FILTERING_MANAGER:
            raise BugException(
                f"Filtering type '{filtering_type}' is not supported. "
                f"Supported types: {list(REGISTRY_FILTERING_MANAGER.keys())}"
            )

        args = self.mail_settings.get_mail_filtering_settings_for_type(filtering_type)

        return {"type": filtering_type, "args": args}

    def _open_filtering_client(self) -> ClientFiltering:
        """Instantiate, connect and authenticate a filtering client for the current user.

        The concrete client class is determined by ``SOGO_D_MAIL_FILTERING_TYPE`` via
        :data:`REGISTRY_FILTERING_MANAGER`, so no protocol-specific name appears here.

        :raises BugException: If the configured filtering type is not registered.
        :raises RequestException: If connection or authentication fails.
        :return: An authenticated :class:`~app.manager.mail.ClientFiltering.ClientFiltering` instance.
        :rtype: ClientFiltering
        """
        conf = self._get_filtering_conf()

        client: ClientFiltering = import_and_instantiate_manager(
            module_path="app.manager.mail",
            module_and_class_name=REGISTRY_FILTERING_MANAGER[conf["type"]],
            module_args=conf["args"],
        )
        client.connect()
        client.login(self.user.login_mail_filtering or self.user.uid, self.user.password)
        return client

    # ------------------------------------------------------------------ #
    # DB helpers                                                           #
    # ------------------------------------------------------------------ #

    def _read_current_filters(self) -> dict[str, Any]:
        """Read the current content of the ``filters`` column for this user.

        :raises RequestException: If the user profile row is not found.
        :return: Current filters dict (may be empty if the column was NULL).
        :rtype: dict[str, Any]
        """
        condition = EqualCondition(tbl.COL_USER_UID.name, self.user.uid)
        rows = list(self.sogo_db_manager.select_from_table(
            table_name=tbl.TABLE_USER.name,
            column_tuple=(tbl.COL_USER_FILTERS.name,),
            condition=condition,
        ))
        if not rows:
            raise RequestException(err.ERROR_USER_PROFILE_NOT_FOUND.m, err.ERROR_USER_PROFILE_NOT_FOUND)
        return rows[0][0] or {}

    def _write_filters(self, new_content: dict[str, Any]) -> None:
        """Persist *new_content* to the ``filters`` column for this user.

        :raises RequestException: If the update affects no row.
        :param new_content: Full filters column content to persist.
        :type new_content: dict[str, Any]
        """
        condition = EqualCondition(tbl.COL_USER_UID.name, self.user.uid)
        updated = self.sogo_db_manager.update_in_table(
            table_name=tbl.TABLE_USER.name,
            column_tuple=(tbl.COL_USER_FILTERS.name,),
            values_list=[new_content],
            condition=condition,
        )
        if not updated:
            raise RequestException(err.ERROR_USER_PROFILE_UPDATE_FAILED.m, err.ERROR_USER_PROFILE_UPDATE_FAILED)

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def get_section(self, section_key: str) -> Any:
        """Read one section from the stored filters column.

        :param section_key: Top-level key to read (``"filters"``, ``"Vacation"``,
                            ``"Forward"`` or ``"Notification"``).
        :type section_key: str
        :raises RequestException: If the user profile row is not found.
        :return: The current value for the section, or ``None`` if not set yet.
        :rtype: Any
        """
        self.sogo_db_manager.connect()
        current = self._read_current_filters()
        return current.get(section_key)

    @staticmethod
    def _is_section_enabled(value: Any) -> bool:
        """Return whether a section is intended to be active by the user.

        Branches on the type of *value*:
        - ``list`` (filters): active when at least one item has ``enabled`` truthy.
        - ``dict`` (Vacation / Forward / Notification): active when ``enabled`` is truthy.

        :param value: The section value as supplied by the caller.
        :type value: Any
        :return: ``True`` if the user wants the section active.
        :rtype: bool
        """
        if isinstance(value, list):
            return any(bool(f.get("enabled", True)) for f in value if isinstance(f, dict))
        return isinstance(value, dict) and bool(value.get("enabled", False))

    def set_section(self, section_key: str, value: Any) -> dict[str, Any]:
        """Replace one section of the stored filters column and push to Sieve.

        Reads the current column content, updates the *section_key* entry with
        *value*, persists the result, then notifies the Sieve client.

        All filter-related sections (filters, Vacation, Forward, Notification) are merged into
        a single Sieve script to ensure they coexist and all execute together.

        When a section is disabled by the user (``enabled=0`` / all filters ``enabled=0``),
        Sieve is still called to rebuild the merged script (so the disabled section is
        removed from the live script), but the section **is always persisted** to the
        database so that the stored configuration is not lost.

        If a section is not supported by the Sieve server **and** the user intended it to
        be active (e.g. 'Notification' when the server lacks the ``enotify`` extension),
        the configuration update is NOT persisted to the database to avoid silent failures.

        :param section_key: Top-level key to update (``"filters"``, ``"Vacation"``,
                            ``"Forward"`` or ``"Notification"``).
        :type section_key: str
        :param value: New value for the section.
        :type value: Any
        :raises RequestException: If the user profile is not found, the update
                                  fails, or a Sieve error occurs.
        :return: The full updated filters column content (after persisting to DB).
        :rtype: dict[str, Any]
        """
        # Read current state from DB first
        self.sogo_db_manager.connect()
        current = self._read_current_filters()
        current[section_key] = value

        # Push merged script to Sieve if this is a filter-related section
        client = None
        activated_sections: dict = {}
        try:
            if section_key in FILTER_SIEVE_SECTIONS:
                # These sections are merged and pushed to Sieve as a single script
                client = self._open_filtering_client()

                # Pass the complete, updated filters dict so the client can
                # merge all sections into a single Sieve script.
                # This returns a dict indicating which sections were actually activated.
                activated_sections = client.set_merged_filters(current)

                section_intended_active = self._is_section_enabled(value)
                if section_intended_active and not activated_sections.get(section_key, False):
                    logger_sieve.warning(
                        "Section '%s' was not activated on the Sieve server (likely due to unsupported extension). "
                        "Not persisting to database.",
                        section_key
                    )
                    # Don't persist this section to the database
                    current.pop(section_key, None)

        except (RequestException, BugException) as ex:
            logger_sieve.error("Error communicating with Sieve for section '%s': %s", section_key, str(ex))
            raise
        finally:
            # Always close the client if we opened one
            if client is not None:
                client.logout()

        # Persist the updated column to the database.
        # Reaches here whether the section was active (pushed to Sieve) or disabled
        # (enabled=0 — not pushed to Sieve but still stored so it can be retrieved later).
        self._write_filters(current)

        logger_sieve.info(
            "Section '%s' persisted to DB for user '%s'", section_key, self.user.uid
        )

        return current
