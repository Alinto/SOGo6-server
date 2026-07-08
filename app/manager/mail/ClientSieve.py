from __future__ import annotations
from typing import Callable, TypeVar, ParamSpec
import re
from socket import timeout as sock_timeout, gaierror, error as sock_error
from datetime import datetime
from zoneinfo import ZoneInfo

from sievelib.managesieve import Client, Error as SieveError
from sievelib.factory import FiltersSet

from app.utils.exceptions import RequestException, BugException
from app.utils.logger.logger import logger_sieve
from app.manager.mail.ClientFiltering import ClientFiltering
from app.utils import errors as err
from app.utils import constants as cs
from app.utils.datetime.DateTimeUtils import parse_vacation_datetime


P = ParamSpec("P")
R = TypeVar("R")

# Name of the single active Sieve script that merges all sections (filters, vacation, forward, notification).
SIEVE_MASTER_SCRIPT = "sogo-master"


# ---------------------------------------------------------------------------
# Vacation Condition Data Class
# ---------------------------------------------------------------------------

class VacationConditions:
    """Encapsulates all condition parameters for vacation filtering.
    
    Represents the filtering criteria for determining when a vacation reply should be sent:
    - Fixed date/time ranges (start/end with optional embedded times and timezones)
    - Recurring daily time windows (start_time to end_time, every day)
    - Specific weekdays (0-6, where 0 is Sunday)
    
    All three condition types are ALTERNATIVES (OR logic): vacation activates if ANY is true.
    """

    def __init__(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        start_tz: str | None = None,
        end_tz: str | None = None,
        start_date_time: str | None = None,
        end_date_time: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        weekdays_enabled: bool = False,
        weekday: list | None = None,
    ):
        """Initialize vacation condition parameters.
        
        :param start_date: Start date in YYYY-MM-DD format (or None)
        :param end_date: End date in YYYY-MM-DD format (or None)
        :param start_tz: Timezone for start_date (already in Sieve format)
        :param end_tz: Timezone for end_date (already in Sieve format)
        :param start_date_time: Start time extracted from start_date (HH:MM:SS or None)
        :param end_date_time: End time extracted from end_date (HH:MM:SS or None)
        :param start_time: Recurring start time in HH:MM or HH:MM:SS format (independent, or None)
        :param end_time: Recurring end time in HH:MM or HH:MM:SS format (independent, or None)
        :param weekdays_enabled: Whether weekday filtering is enabled
        :param weekday: List of weekday numbers (0-6)
        """
        self.start_date = start_date
        self.end_date = end_date
        self.start_tz = start_tz
        self.end_tz = end_tz
        self.start_date_time = start_date_time
        self.end_date_time = end_date_time
        self.start_time = start_time
        self.end_time = end_time
        self.weekdays_enabled = weekdays_enabled
        self.weekday = weekday if weekday is not None else []

    @classmethod
    def from_vacation_config(
        cls,
        start_date_raw: str | None,
        end_date_raw: str | None,
        default_timezone: str,
        start_time: str | None,
        end_time: str | None,
        weekdays_enabled: bool,
        weekday: list | None,
        parse_datetime_func: Callable,
    ) -> "VacationConditions":
        """Factory method to create VacationConditions from raw vacation config.
        
        Parses dates with timezone awareness and extracts time components.
        
        :param start_date_raw: Raw start date string (may include time/timezone)
        :param end_date_raw: Raw end date string (may include time/timezone)
        :param default_timezone: Default timezone if not specified in dates
        :param start_time: Independent recurring start time
        :param end_time: Independent recurring end time
        :param weekdays_enabled: Whether weekday filtering is enabled
        :param weekday: List of weekday numbers
        :param parse_datetime_func: Function to parse dates (typically _parse_vacation_datetime)
        :return: Initialized VacationConditions instance
        """
        # Parse dates with timezone awareness
        # Returns (date_str, time_str, tz_normalized)
        start_date_str, start_date_time, start_tz = parse_datetime_func(start_date_raw, default_timezone)
        end_date_str, end_date_time, end_tz = parse_datetime_func(end_date_raw, default_timezone)

        return cls(
            start_date=start_date_str,
            end_date=end_date_str,
            start_tz=start_tz,
            end_tz=end_tz,
            start_date_time=start_date_time,
            end_date_time=end_date_time,
            start_time=start_time,
            end_time=end_time,
            weekdays_enabled=weekdays_enabled,
            weekday=weekday,
        )


class ClientSieve(ClientFiltering):
    """
    Sieve (ManageSieve) client implementation for Dovecot using sievelib.
    """

    # Sieve commands that are always available and should not be in require
    # Note: "copy" is NOT a command, it's a flag on fileinto (:copy) and requires the "copy" extension
    BUILTIN_SIEVE_COMMANDS = {"redirect", "keep", "discard", "stop"}

    def __init__(self, server: str, port: int, encryption: str, auth_mech: str) -> None:
        """
        Initialize the Sieve client.

        :param server: Hostname or IP of the ManageSieve server (SOGO_D_SIEVE_SERVER)
        :type server: str
        :param port: Port of the ManageSieve server (SOGO_D_SIEVE_PORT)
        :type port: int
        :param encryption: Encryption type – one of cs.SOCKET_ENC_* (SOGO_D_SIEVE_ENCRYPTION)
        :type encryption: str
        :param auth_mech: Authentication mechanism (SOGO_D_SIEVE_AUTH_MECH), e.g. "plain", "xoauth2"
        :type auth_mech: str
        """
        super().__init__()
        self.server    = server
        self.port      = port
        self.encryption = encryption
        self.auth_mech  = auth_mech

        self.connection: Client | None = None

    def connect(self) -> None:
        """
        Instantiate the underlying sievelib Client.

        The actual TCP connection (and TLS negotiation) is deferred to :meth:`login`
        because sievelib's ``Client.connect()`` performs both TCP connection and
        authentication in one call.  This step only validates the encryption
        parameter and creates the :class:`~sievelib.managesieve.Client` object.

        :raises BugException: If the encryption parameter is unknown.
        """
        if self.encryption not in cs.SOCK_ENC_LIST:
            raise BugException(
                f"Unknown encryption given: {self.encryption}",
                err.ERROR_CONFIG_ERROR,
            )

        self.connection = Client(self.server, self.port)
        self.connected = True
        logger_sieve.info(
            "Sieve client initialised for %s:%d (encryption=%s)", self.server, self.port, self.encryption
        )

    def login(self, username: str, password: str, authname: str = "") -> None:
        """Connect and authenticate to the ManageSieve server.

        Uses the encryption and auth-mechanism configured at construction time.

        :param username: The username for authentication.
        :type username: str
        :param password: The password / token for authentication.
        :type password: str
        :param authname: Optional authorisation identity (proxy auth). When empty,
                         ``username`` is used.
        :type authname: str
        :raises BugException: If :meth:`connect` was not called first or if the
                              auth mechanism is not supported.
        :raises RequestException: If the TCP connection or authentication fails.
        """
        if self.connection is None:
            raise BugException(
                "login() called before connect()",
                err.ERROR_SIEVE_LOGOUT,
            )

        logger_sieve.info(
            "Logging in to Sieve as %s using auth_mech=%s", username, self.auth_mech
        )

        # Map our internal encryption constants to sievelib parameters.
        use_ssl     = self.encryption == cs.SOCKET_ENC_IMPLICIT_TLS
        use_starttls = self.encryption == cs.SOCKET_ENC_EXPLICIT_TLS

        # Map our auth-mech string to the format expected by sievelib
        # (sievelib expects uppercase, e.g. "PLAIN", "XOAUTH2").
        auth_mech_upper = self.auth_mech.upper() if self.auth_mech.lower() != "none" else None

        try:
            result = self.connection.connect(
                login=username,
                password=password,
                authz_id=authname if authname else "",
                starttls=use_starttls,
                ssl=use_ssl,
                authmech=auth_mech_upper,
            )
        except SieveError as e:
            error_msg = str(e)
            logger_sieve.error(
                "Sieve connection/auth error for %s@%s:%d - %s",
                username, self.server, self.port, error_msg,
            )
            if "Connection to server failed" in error_msg or "SSL error" in error_msg:
                raise RequestException(f"Sieve connection failed: {error_msg}", err.ERROR_SIEVE_CONNECTION_FAILED) from e
            raise RequestException(f"Sieve error: {error_msg}", err.ERROR_SIEVE_AUTH_FAILED) from e
        except (gaierror, sock_timeout, TimeoutError, ConnectionRefusedError, sock_error) as e:
            logger_sieve.error("Sieve TCP error connecting to %s:%d - %s", self.server, self.port, e)
            raise RequestException(f"Sieve connection failed: {e}", err.ERROR_SIEVE_CONNECTION_FAILED) from e

        if not result:
            error_detail = self.connection.errmsg.decode() if isinstance(self.connection.errmsg, bytes) else str(self.connection.errmsg)
            logger_sieve.error(
                "Sieve authentication failed for %s – %s", username, error_detail
            )
            raise RequestException(
                f"Sieve authentication failed: {error_detail}",
                err.ERROR_SIEVE_AUTH_FAILED,
            )

        self.authenticated = True
        logger_sieve.info(
            "Successfully authenticated to Sieve server %s:%d as %s",
            self.server, self.port, username,
        )

    def _exec_sieve_method(self, method: Callable[P, R], *args:P.args, **kwargs: P.kwargs) -> R:
        """Wrapper that converts :class:`~sievelib.managesieve.Error` exceptions
        into :class:`~app.utils.exceptions.RequestException`.

        This mirrors the role of ``_exec_imap4_method`` in :class:`ClientImap`.

        :raises BugException: If called while not connected/authenticated.
        :raises RequestException: If the ManageSieve command fails.
        :return: The return value of *method*.
        """
        if self.connection is None or not self.authenticated:
            raise BugException("Sieve command issued while not connected/authenticated",err.ERROR_SIEVE_LOGOUT)
        try:
            return method(*args, **kwargs)
        except SieveError as e:
            logger_sieve.error("Sieve command failed: %s", e)
            raise RequestException(str(e), err.ERROR_SIEVE_COMMAND_FAILED) from e

    def _get_sieve_error_message(self) -> str:
        """Extract error message from the Sieve server response.

        The sievelib Client stores error messages in the `errmsg` attribute
        which may be bytes or string. This method normalizes it for logging.

        :return: Error message from the server, or a generic message if unavailable.
        :rtype: str
        """
        if self.connection is None:
            return "No connection available"

        # errmsg can be bytes or string depending on the sievelib version
        errmsg = self.connection.errmsg
        if errmsg is None:
            return "Unknown error (no error message from server)"

        if isinstance(errmsg, bytes):
            return errmsg.decode('utf-8', errors='replace')
        else:
            return str(errmsg)


    def _extract_missing_capability(self, error_msg: str) -> str:
        """Extract the name of the missing Sieve capability from an error message.

        :param error_msg: Error message from the server.
        :type error_msg: str
        :return: Name of the missing capability, raise BugException if not found.
        :rtype: str
        """
        # Pattern 1: unknown Sieve capability `xxx'
        match = re.search(r"unknown Sieve capability [`']([^`']+)[`']", error_msg)
        if match:
            return match.group(1)

        # Pattern 2: unknown command 'xxx'
        match = re.search(r"unknown command ['\"]([^'\"]+)['\"]", error_msg)
        if match:
            return match.group(1)

        #return "notify"
        raise BugException("Unknown Sieve capability", err.ERROR_SIEVE_CAPABILITY_NOT_FOUND)

    def put_script(self, name: str, content: str) -> tuple[bool, str | None]:
        """Upload a Sieve script to the server.

        :param name: Name under which to store the script.
        :type name: str
        :param content: The Sieve script source.
        :type content: str
        :return: Tuple of (success: bool, missing_capability: str | None).
                 If success is False and missing_capability is not None, 
                 it indicates an unsupported Sieve extension.
        :rtype: tuple[bool, str | None]
        :raises BugException: If not connected/authenticated.
        :raises RequestException: If the command fails for reasons other than unsupported extensions.
        """
        if self.connection is None or not self.authenticated:
            raise BugException("Sieve command issued while not connected/authenticated",err.ERROR_SIEVE_LOGOUT)
        logger_sieve.debug("Putting Sieve script '%s'", name)
        logger_sieve.debug("Script content:\n%s", content)
        success = self._exec_sieve_method(self.connection.putscript, name, content)

        if not success:
            # Extract error details from the server response
            error_detail = self._get_sieve_error_message()
            logger_sieve.error(
                "Failed to upload Sieve script '%s': %s", name, error_detail
            )

            # Check if the error is due to unsupported Sieve capability
            if "unknown Sieve capability" in error_detail or "unknown command" in error_detail:
                # Extract which capability is missing
                capability = self._extract_missing_capability(error_detail)
                logger_sieve.warning(
                    "Server does not support Sieve extension '%s'. "
                    "Will attempt to compile script without this extension.",
                    capability
                )
                return (False, capability)

            raise RequestException(
                f"Failed to upload Sieve script '{name}': {error_detail}",
                err.ERROR_SIEVE_SCRIPT_INVALID,
            )

        return (True, None)

    def delete_script(self, name: str) -> None:
        """Delete a Sieve script from the server.

        :param name: Name of the script to delete.
        :type name: str
        :raises BugException: If not connected/authenticated.
        :raises RequestException: If the command fails or the script does not exist.
        """
        if self.connection is None or not self.authenticated:
            raise BugException("Sieve command issued while not connected/authenticated",err.ERROR_SIEVE_LOGOUT)

        logger_sieve.debug("Deleting Sieve script '%s'", name)
        success = self._exec_sieve_method(self.connection.deletescript, name)
        if not success:
            raise RequestException(
                f"Failed to delete Sieve script '{name}'",
                err.ERROR_SIEVE_SCRIPT_NOT_FOUND,
            )

    def set_active(self, name: str) -> None:
        """Set a Sieve script as the active (executed) script.

        Pass an empty string to deactivate all scripts.

        :param name: Name of the script to activate.
        :type name: str
        :raises BugException: If not connected/authenticated.
        :raises RequestException: If the command fails.
        """
        if self.connection is None or not self.authenticated:
            raise BugException("Sieve command issued while not connected/authenticated",err.ERROR_SIEVE_LOGOUT)
        logger_sieve.debug("Setting active Sieve script to '%s'", name)
        success = self._exec_sieve_method(self.connection.setactive, name)
        if not success:
            raise RequestException(
                f"Failed to set active Sieve script to '{name}'",
                err.ERROR_SIEVE_COMMAND_FAILED,
            )


    def _add_filter_to_set(self, filters_set: FiltersSet, filter_item: dict) -> None:
        """Convert a single API filter definition and add it to a FiltersSet.

        Special handling: If the filter uses "cc or to" field, creates two separate
        filters (one for CC, one for TO) with the same actions to achieve OR logic.

        :param filters_set: The FiltersSet to add the filter to.
        :type filters_set: FiltersSet
        :param filter_item: Filter definition with keys: name, enabled, actions, rules.
        :type filter_item: dict
        :raises RequestException: If the filter definition is malformed or cannot be compiled.
        """
        filter_name = filter_item.get("name", "unknown")
        actions = filter_item.get("actions", [])
        rules = filter_item.get("rules", {})

        if not actions:
            logger_sieve.debug("Filter '%s' has no actions, skipping", filter_name)
            return

        try:
            # Check if the top-level rule uses "cc or to" field
            if self._rule_uses_cc_or_to(rules):
                # Handle "cc or to" by creating two filters
                self._add_cc_or_to_filter_to_set(filters_set, filter_item)
            else:
                # Normal filter processing
                conditions, matchtype = self._build_sieve_conditions(rules)
                filters_set.addfilter(
                    name=filter_name,
                    conditions=conditions,
                    actions=self._build_sieve_actions(actions),
                    matchtype=matchtype,
                )
                logger_sieve.debug("Added filter '%s' to FiltersSet with matchtype=%s", filter_name, matchtype)
        except Exception as e:
            logger_sieve.error("Error adding filter '%s' to FiltersSet: %s", filter_name, e)
            raise RequestException(
                f"Failed to add filter '{filter_name}': {e}",
                err.ERROR_SIEVE_SCRIPT_INVALID,
            ) from e

    def _rule_uses_cc_or_to(self, rule_node: dict) -> bool:
        """Check if a rule tree uses the 'cc or to' field.
        
        :param rule_node: A rule node (leaf or group).
        :type rule_node: dict
        :return: True if 'cc or to' field is used anywhere in the rule tree.
        :rtype: bool
        """
        if "op" in rule_node:
            # Group node: check nested rules
            nested_rules = rule_node.get("rules", [])
            return any(self._rule_uses_cc_or_to(rule) for rule in nested_rules)
        else:
            # Leaf node: check field
            field = rule_node.get("field", "")
            return field == "cc or to"

    def _add_cc_or_to_filter_to_set(self, filters_set: FiltersSet, filter_item: dict) -> None:
        """Handle 'cc or to' field by creating two separate filters.
        
        Creates two filters with the same actions but different conditions:
        - One for CC field
        - One for TO field
        
        This achieves OR logic at the filter level.
        
        :param filters_set: The FiltersSet to add filters to.
        :type filters_set: FiltersSet
        :param filter_item: Original filter definition with 'cc or to' field.
        :type filter_item: dict
        """
        filter_name = filter_item.get("name", "unknown")
        actions = filter_item.get("actions", [])
        rules = filter_item.get("rules", {})

        # Create two versions of the rules: one with "cc" and one with "to"
        cc_rules = self._replace_field_in_rules(rules, "cc or to", "cc")
        to_rules = self._replace_field_in_rules(rules, "cc or to", "to")

        # Add both filters to the set
        cc_conditions, cc_matchtype = self._build_sieve_conditions(cc_rules)
        to_conditions, to_matchtype = self._build_sieve_conditions(to_rules)
        sieve_actions = self._build_sieve_actions(actions)

        # Create two filters with suffixes to differentiate them
        filters_set.addfilter(
            name=f"{filter_name} (CC)",
            conditions=cc_conditions,
            actions=sieve_actions,
            matchtype=cc_matchtype,
        )
        logger_sieve.debug("Added filter '%s' (CC variant) to FiltersSet", filter_name)

        filters_set.addfilter(
            name=f"{filter_name} (TO)",
            conditions=to_conditions,
            actions=sieve_actions,
            matchtype=to_matchtype,
        )
        logger_sieve.debug("Added filter '%s' (TO variant) to FiltersSet", filter_name)

    def _replace_field_in_rules(self, rule_node: dict, old_field: str, new_field: str) -> dict:
        """Recursively replace field names in a rule tree.
        
        :param rule_node: A rule node (leaf or group).
        :type rule_node: dict
        :param old_field: Field name to replace.
        :type old_field: str
        :param new_field: Replacement field name.
        :type new_field: str
        :return: New rule tree with replaced field names.
        :rtype: dict
        """
        if "op" in rule_node:
            # Group node: recursively replace in nested rules
            nested_rules = [self._replace_field_in_rules(rule, old_field, new_field) 
                          for rule in rule_node.get("rules", [])]
            return {
                "op": rule_node.get("op"),
                "rules": nested_rules
            }
        else:
            # Leaf node: replace field if it matches
            new_rule = dict(rule_node)  # Shallow copy
            if new_rule.get("field") == old_field:
                new_rule["field"] = new_field
            return new_rule

    def _detect_required_extensions_from_rules(self, rule_node: dict) -> set[str]:
        """Recursively detect Sieve extensions required by a rule tree.
        
        Returns a set of extension names needed:
        - "body" for body field searches (RFC 5173)
        
        :param rule_node: A rule node (leaf or group).
        :type rule_node: dict
        :return: Set of extension names required.
        :rtype: set[str]
        """
        required_extensions = set()

        if "op" in rule_node:
            # Group node: recursively check nested rules
            nested_rules = rule_node.get("rules", [])
            for nested_rule in nested_rules:
                required_extensions.update(self._detect_required_extensions_from_rules(nested_rule))
        else:
            # Leaf node: check the field
            field = rule_node.get("field", "")
            if field == "body":
                required_extensions.add("body")

        return required_extensions

    def _detect_required_extensions_from_actions(self, actions: list[dict]) -> set[str]:
        """Recursively detect Sieve extensions required by filter actions.
        
        Returns a set of extension names needed:
        - "fileinto" for fileinto actions
        - "copy" for fileinto with :copy flag (keep_copy=True)
        - "mailbox" for fileinto with :create flag
        - "imap4flags" for imapflags action
        - "enotify" for notify action
        
        :param actions: List of action dicts with keys: method, arguments.
        :type actions: list[dict]
        :return: Set of extension names required.
        :rtype: set[str]
        """
        required_extensions = set()

        for action in actions:
            method = action.get("method", "").lower()
            arguments = action.get("arguments", {})

            if method == cs.FILTER_ACTION_FILEINTO:
                # fileinto is an extension (RFC 5228)
                required_extensions.add("fileinto")

                # Check for :copy flag (requires "copy" extension)
                if arguments.get("keep_copy", False):
                    required_extensions.add("copy")

                # Check for :create flag (requires "mailbox" extension)
                if arguments.get("create_if_no_exist", False):
                    required_extensions.add("mailbox")

            elif method == cs.FILTER_ACTION_FLAG:
                # imapflags action requires imap4flags extension (RFC 5232)
                required_extensions.add("imap4flags")

            elif method == cs.FILTER_ACTION_NOTIFY:
                # notify action requires enotify extension
                required_extensions.add("enotify")

        return required_extensions

    def _check_authenticated(self, method_name: str) -> None:
        """Verify that the client is connected and authenticated.

        :param method_name: Name of the method calling this check (for error messages).
        :type method_name: str
        :raises BugException: If not connected/authenticated.
        """
        if self.connection is None or not self.authenticated:
            raise BugException(
                f"{method_name} called while not connected/authenticated",
                err.ERROR_SIEVE_LOGOUT,
            )

    def _store_and_activate_script(self, script_name: str, script_content: str,
                                   requires_set: set = None, script_parts: list = None) -> set:
        """Upload and activate a Sieve script with automatic fallback for unsupported extensions.

        If an unsupported Sieve extension is detected (e.g., 'notify'), this method
        automatically removes that extension and tries to recompile and upload the script.
        This ensures that as much filtering as possible is saved even if some features
        aren't supported by the server.

        :param script_name: Name to store the script under.
        :type script_name: str
        :param script_content: The Sieve script source.
        :type script_content: str
        :param requires_set: Set of required extensions (used for retry compilation).
        :type requires_set: set
        :param script_parts: List of script parts (used for retry compilation).
        :type script_parts: list
        :return: Set of sections that were skipped due to unsupported extensions (e.g., {'notification'}).
        :rtype: set
        :raises RequestException: If upload fails or if script compilation cannot succeed.
        """
        logger_sieve.debug("Storing and activating Sieve script '%s'", script_name)
        success, missing_capability = self.put_script(script_name, script_content)

        if success:
            self.set_active(script_name)
            logger_sieve.info("Successfully stored and activated Sieve script '%s'", script_name)
            return set()  # No sections were skipped

        skipped_sections = set()

        # If a capability is missing and we have the original parts, try to recompile without it
        if missing_capability and requires_set is not None and script_parts is not None:
            logger_sieve.info(
                "Retrying script compilation without unsupported extension '%s'",
                missing_capability
            )
            # Remove the unsupported extension from the requires set
            requires_set_retry = requires_set - {missing_capability}

            # Remove script parts that depend on this extension
            script_parts_retry = []
            for section_name, section_content in script_parts:
                # Skip notification section if notify extension is unsupported
                if missing_capability == "notify" and section_name == cs.FILTER_SECTION_NOTIFICATION:
                    logger_sieve.warning(
                        "Skipping notification section because 'notify' extension is not supported"
                    )
                    skipped_sections.add(cs.FILTER_SECTION_NOTIFICATION)
                    continue
                script_parts_retry.append((section_name, section_content))

            # If there are still script parts to process, recompile and retry
            if script_parts_retry:
                try:
                    master_script_retry = self._compile_merged_script(requires_set_retry, script_parts_retry)
                    logger_sieve.info("Retrying upload with modified script (without '%s' extension)", missing_capability)
                    success_retry, missing_capability_retry = self.put_script(script_name, master_script_retry)

                    if success_retry:
                        self.set_active(script_name)
                        logger_sieve.info(
                            "Successfully stored and activated Sieve script '%s' (without '%s' extension)",
                            script_name, missing_capability
                        )
                        return skipped_sections
                    elif missing_capability_retry:
                        # Another extension is also unsupported - recursively retry
                        logger_sieve.warning(
                            "Another unsupported extension '%s' found; attempting another retry",
                            missing_capability_retry
                        )
                        additional_skipped = self._store_and_activate_script(script_name, master_script_retry, requires_set_retry, script_parts_retry)
                        return skipped_sections | additional_skipped
                except Exception as e:
                    logger_sieve.error("Error during retry compilation: %s", e)
                    raise RequestException(
                        f"Failed to compile script without '{missing_capability}' extension: {e}",
                        err.ERROR_SIEVE_SCRIPT_INVALID,
                    ) from e

        # If we couldn't retry or there are no more parts, raise an error
        if missing_capability:
            raise RequestException(
                f"Sieve extension '{missing_capability}' is not enabled on the server. "
                f"Contact your mail server administrator.",
                err.ERROR_SIEVE_SCRIPT_INVALID,
            )
        else:
            raise RequestException(
                f"Failed to upload Sieve script '{script_name}'",
                err.ERROR_SIEVE_SCRIPT_INVALID,
            )

    def _cleanup_scripts(self, script_names: list) -> None:
        """Delete a list of Sieve scripts, silently ignoring if they don't exist.

        :param script_names: List of script names to delete.
        :type script_names: list
        """
        for script_name in script_names:
            try:
                self.delete_script(script_name)
            except RequestException as e:
                if e.error == err.ERROR_SIEVE_SCRIPT_NOT_FOUND:
                    logger_sieve.debug("Script '%s' doesn't exist (already deleted)", script_name)
                else:
                    logger_sieve.warning("Could not delete script %s: %s", script_name, e)

    def set_merged_filters(self, filters_config: dict) -> dict[str, bool]:
        """Merge all filter sections into a single Sieve script and activate it.

        This method ensures that filters, vacation, and forward rules all coexist
        and execute together by compiling them into a single master script named
        'sogo-master' which is then activated. Individual scripts are deleted to
        keep the server clean.

        The merged script order depends on forward and vacation priority (controlled by always_send):
        - If forward.always_send=True: Forward first, then (Vacation if always_send), then Filters, then Notification
        - Else if vacation.always_send=True: Vacation first, then Forward, then Filters, then Notification
        - Otherwise: Forward, then Filters, then Vacation, then Notification

        :param filters_config: Complete filters dict with keys: 'filters', 'Vacation',
                              'Forward', 'Notification'.
        :type filters_config: dict
        :return: Dictionary indicating which sections were successfully activated.
                 Keys are 'notification', 'vacation', 'forward', 'filters'.
                 Values are True if activated, False if not supported by server.
        :rtype: dict[str, bool]
        :raises BugException: If not connected/authenticated.
        :raises RequestException: If script compilation or upload fails.
        """
        self._check_authenticated("set_merged_filters()")
        logger_sieve.info("Merging all filter sections into single master script")

        # Track which sections were actually activated on the server
        activated_sections = {
            cs.FILTER_SECTION_NOTIFICATION: False,
            cs.FILTER_SECTION_VACATION: False,
            cs.FILTER_SECTION_FORWARD: False,
            cs.FILTER_SECTION_FILTERS: False,
        }

        # Build the merged script by combining all enabled sections
        merged_script_parts = []
        requires_set = set()

        # Get configurations
        forward_config = filters_config.get(cs.FILTER_SECTION_FORWARD)
        vacation_config = filters_config.get(cs.FILTER_SECTION_VACATION)

        # Determine priority: forward has priority over vacation if both have always_send=True
        forward_has_priority = forward_config and forward_config.get("enabled", False) and forward_config.get("always_send", False)
        vacation_has_priority = vacation_config and vacation_config.get("enabled", False) and vacation_config.get("always_send", False)

        # Process forward and vacation sections with priority handling
        # Forward has priority over vacation if both have always_send=True
        if forward_has_priority:
            priority_insert_pos = self._process_forward_section(forward_config, merged_script_parts, requires_set, activated_sections)
            if vacation_has_priority and vacation_config.get("enabled", False):
                self._process_vacation_section(vacation_config, merged_script_parts, requires_set, activated_sections, insert_pos=priority_insert_pos + 1)
        elif vacation_has_priority:
            self._process_vacation_section(vacation_config, merged_script_parts, requires_set, activated_sections, insert_pos=0)

        # Process non-priority forward (normal order)
        if not forward_has_priority and forward_config and forward_config.get("enabled", False):
            self._process_forward_section(forward_config, merged_script_parts, requires_set, activated_sections)

        # Process filters (rules)
        self._process_filters_section(filters_config.get(cs.FILTER_SECTION_FILTERS, []), merged_script_parts, requires_set, activated_sections)

        # Process non-priority vacation (normal order)
        if not vacation_has_priority and vacation_config and vacation_config.get("enabled", False):
            self._process_vacation_section(vacation_config, merged_script_parts, requires_set, activated_sections)

        # Process notification settings
        self._process_notification_section(filters_config.get(cs.FILTER_SECTION_NOTIFICATION), merged_script_parts, requires_set, activated_sections)

        # If nothing is enabled, deactivate then delete the master script.
        if not merged_script_parts:
            logger_sieve.info("No filter sections are enabled; deactivating and deleting master script")
            try:
                self.set_active("")
                logger_sieve.debug("Deactivated active Sieve script before cleanup")
            except RequestException as e:
                logger_sieve.debug("Could not deactivate Sieve script (may not be active): %s", e)
            self._cleanup_scripts([SIEVE_MASTER_SCRIPT])
            return activated_sections

        # Compile final merged script with all requirements
        master_script = self._compile_merged_script(requires_set, merged_script_parts)
        # Upload and activate the master script with automatic retry for unsupported extensions
        skipped_sections = self._store_and_activate_script(SIEVE_MASTER_SCRIPT, master_script, requires_set, merged_script_parts)

        # Mark sections as activated based on what was included and not skipped
        for section_name, _ in merged_script_parts:
            if section_name not in skipped_sections:
                activated_sections[section_name] = True

        logger_sieve.info("Activated sections: %s", activated_sections)

        return activated_sections

    def _process_forward_section(self, forward_config: dict, merged_script_parts: list, requires_set: set, activated_sections: dict) -> int:
        """Process forward section and add it to merged script parts.
        
        :param forward_config: Forward configuration dict.
        :type forward_config: dict
        :param merged_script_parts: List to append the forward script part to.
        :type merged_script_parts: list
        :param requires_set: Set of required extensions to update.
        :type requires_set: set
        :param activated_sections: Dictionary to update with activation status.
        :type activated_sections: dict
        :return: Index where the script part was inserted.
        :rtype: int
        :raises RequestException: If forward processing fails.
        """
        try:
            forward_addresses = forward_config.get("forward_address", [])
            if forward_addresses:
                keep_copy = forward_config.get("keep_copy", False)
                always_send = forward_config.get("always_send", False)

                forward_script = self._build_forward_script(forward_addresses, keep_copy, always_send)
                merged_script_parts.append((cs.FILTER_SECTION_FORWARD, forward_script))
                # Don't add "redirect" or "copy" to requires - they are native Sieve commands
                logger_sieve.debug("Added forward section to merged script")
                activated_sections[cs.FILTER_SECTION_FORWARD] = True
                return len(merged_script_parts) - 1
        except Exception as e:
            logger_sieve.error("Error processing forward section: %s", e)
            raise RequestException(
                f"Failed to process forward: {e}",
                err.ERROR_SIEVE_SCRIPT_INVALID,
            ) from e
        return -1

    def _process_vacation_section(self, vacation_config: dict, merged_script_parts: list, requires_set: set, 
                                  activated_sections: dict, insert_pos: int = None) -> None:
        """Process vacation section and add it to merged script parts.
        
        :param vacation_config: Vacation configuration dict.
        :type vacation_config: dict
        :param merged_script_parts: List to append the vacation script part to.
        :type merged_script_parts: list
        :param requires_set: Set of required extensions to update.
        :type requires_set: set
        :param activated_sections: Dictionary to update with activation status.
        :type activated_sections: dict
        :param insert_pos: Position to insert the script part (if None, append).
        :type insert_pos: int | None
        :raises RequestException: If vacation processing fails.
        """
        try:
            vacation_script = self._build_vacation_script(vacation_config)
            if insert_pos is not None:
                merged_script_parts.insert(insert_pos, (cs.FILTER_SECTION_VACATION, vacation_script))
            else:
                merged_script_parts.append((cs.FILTER_SECTION_VACATION, vacation_script))
            requires_set.add("vacation")
            activated_sections[cs.FILTER_SECTION_VACATION] = True
            logger_sieve.debug("Added vacation section to merged script")
        except Exception as e:
            logger_sieve.error("Error processing vacation section: %s", e)
            raise RequestException(
                f"Failed to process vacation: {e}",
                err.ERROR_SIEVE_SCRIPT_INVALID,
            ) from e

    def _process_filters_section(self, filters_list: list, merged_script_parts: list, requires_set: set, 
                                activated_sections: dict) -> None:
        """Process filters section and add it to merged script parts.
        
        :param filters_list: List of filter definitions.
        :type filters_list: list
        :param merged_script_parts: List to append the filters script part to.
        :type merged_script_parts: list
        :param requires_set: Set of required extensions to update.
        :type requires_set: set
        :param activated_sections: Dictionary to update with activation status.
        :type activated_sections: dict
        :raises RequestException: If filters processing fails.
        """
        if not filters_list:
            return

        try:
            filters_set = FiltersSet("sogo-rules")
            for filter_item in filters_list:
                if filter_item.get("enabled", True):
                    self._add_filter_to_set(filters_set, filter_item)

                    # Detect required extensions from filter rules
                    rules = filter_item.get("rules", {})
                    if rules:
                        required_exts = self._detect_required_extensions_from_rules(rules)
                        requires_set.update(required_exts)

                    # Detect required extensions from filter actions
                    # This includes "copy" for :copy flag and "mailbox" for :create
                    actions = filter_item.get("actions", [])
                    if actions:
                        action_exts = self._detect_required_extensions_from_actions(actions)
                        requires_set.update(action_exts)

            if filters_set.filters:  # Only add if filters exist
                filters_script = self._render_filters_set(filters_set)
                merged_script_parts.append((cs.FILTER_SECTION_FILTERS, filters_script))
                activated_sections[cs.FILTER_SECTION_FILTERS] = True
                logger_sieve.debug("Added filters section to merged script")
        except Exception as e:
            logger_sieve.error("Error processing filters section: %s", e)
            raise RequestException(
                f"Failed to process filters: {e}",
                err.ERROR_SIEVE_SCRIPT_INVALID,
            ) from e

    def _process_notification_section(self, notification_config: dict, merged_script_parts: list, requires_set: set,
                                     activated_sections: dict) -> None:
        """Process notification section and add it to merged script parts.
        
        NOTE: This section is optional and requires Dovecot to support the 'notify' extension.
        If the server doesn't support it, we store the configuration but don't add it to the script.
        
        :param notification_config: Notification configuration dict (or None).
        :type notification_config: dict
        :param merged_script_parts: List to append the notification script part to.
        :type merged_script_parts: list
        :param requires_set: Set of required extensions to update.
        :type requires_set: set
        :param activated_sections: Dictionary to update with activation status.
        :type activated_sections: dict
        :raises RequestException: If notification processing fails.
        """
        if not notification_config or not notification_config.get("enabled", False):
            return

        try:
            notify_addresses = notification_config.get("notify_addresses", [])
            if notify_addresses:
                # Addresses are already validated by the Marshmallow schema
                # Build notification script (will be added to merged script if server supports it)
                notification_script = self._build_notification_script(notification_config)
                if notification_script:  # Only add if script is not empty
                    merged_script_parts.append((cs.FILTER_SECTION_NOTIFICATION, notification_script))
                    requires_set.add("enotify")
                    logger_sieve.debug("Added notification section to merged script")
                activated_sections[cs.FILTER_SECTION_NOTIFICATION] = True
            else:
                logger_sieve.debug("Notification has no addresses; marking as activated for database persistence")
                activated_sections[cs.FILTER_SECTION_NOTIFICATION] = True
        except Exception as e:
            logger_sieve.error("Error processing notification section: %s", e)
            raise RequestException(
                f"Failed to process notification: {e}",
                err.ERROR_SIEVE_SCRIPT_INVALID,
            ) from e

    def _compile_merged_script(self, requires_set: set, script_parts: list) -> str:
        """Compile multiple script sections into a single merged Sieve script.

        :param requires_set: Set of Sieve extensions required (e.g., 'fileinto', 'vacation').
        :type requires_set: set
        :param script_parts: List of tuples (section_name, script_content) to merge.
        :type script_parts: list
        :return: The complete merged Sieve script.
        :rtype: str
        :raises RequestException: If script compilation fails.
        """
        try:
            if not requires_set:
                requires_set = set()

            # Extract all requires declared by each section (e.g. sievelib adds
            # "mailbox" when fileinto :create is used) before stripping them so
            # nothing is lost in the merged require statement.
            for _section_name, section_content in script_parts:
                for line in section_content.split('\n'):
                    stripped = line.strip()
                    if stripped.startswith('require'):
                        requires_set.update(re.findall(r'"([^"]+)"', stripped))

            # Filter out builtin Sieve commands that should not be in require
            requires_list = sorted(requires_set - self.BUILTIN_SIEVE_COMMANDS)

            # Only add require clause if there are actual extensions needed
            if requires_list:
                merged_script = 'require [' + ', '.join(f'"{req}"' for req in requires_list) + '];\n'
                merged_script += '\n'
            else:
                merged_script = ''

            # Add section header comments and content
            for section_name, section_content in script_parts:
                merged_script += f'# ---- {section_name.upper()} SECTION ----\n'

                # Strip require lines – they are already in the merged header above
                section_lines = section_content.split('\n')
                filtered_lines = [
                    line for line in section_lines
                    if not line.strip().startswith('require')
                ]
                section_content_filtered = '\n'.join(filtered_lines).strip()

                merged_script += section_content_filtered + '\n\n'

            logger_sieve.debug("Compiled merged script:\n%s", merged_script)
            return merged_script

        except Exception as e:
            logger_sieve.error("Error compiling merged script: %s", e)
            raise RequestException(
                f"Failed to compile merged script: {e}",
                err.ERROR_SIEVE_SCRIPT_INVALID,
            ) from e

    def _render_filters_set(self, filters_set: FiltersSet) -> str:
        """Compile a FiltersSet into a Sieve script string."""
        try:
            return str(filters_set)
        except Exception as e:
            logger_sieve.error("Error rendering Sieve script: %s", e)
            raise RequestException(
                f"Failed to render Sieve script: {e}",
                err.ERROR_SIEVE_SCRIPT_INVALID,
            ) from e

    def _build_sieve_conditions(self, rules: dict) -> tuple[list[tuple], str]:
        """Convert API rule tree into a flat list of sievelib conditions and return matchtype.
        
        Returns a tuple of (conditions_list, matchtype) where:
        - conditions_list: flat list of condition tuples for sievelib
        - matchtype: "anyof" or "allof" for the top-level grouping
        
        :param rules: Rule tree from API (leaf or group node)
        :type rules: dict
        :return: Tuple of (conditions list, matchtype string)
        :rtype: tuple[list[tuple], str]
        """
        if not rules:
            return [], "allof"

        conditions: list = []
        matchtype_ref: list = ["allof"]  # Default, will be mutated
        self._flatten_rules(rules, conditions, matchtype_ref)
        return conditions, matchtype_ref[0]

    def _flatten_rules(self, rule_node: dict, conditions: list, matchtype_ref: list = None, parent_op: str = "and") -> None:
        """Recursively convert a nested rule tree into sievelib condition tuples.

        Handles both leaf conditions (single rules) and group nodes (multiple rules with AND/OR).
        For groups with multiple rules, sets the matchtype_ref to reflect the top-level operator.

        :param rule_node: A rule node (leaf or group).
        :type rule_node: dict
        :param conditions: The list to append conditions to (mutated).
        :type conditions: list
        :param matchtype_ref: Single-element list holding the matchtype ("anyof" or "allof"). 
                              Mutated to track top-level operator.
        :type matchtype_ref: list | None
        :param parent_op: Parent operator ("and" or "or") for context.
        :type parent_op: str
        """
        if matchtype_ref is None:
            matchtype_ref = ["allof"]

        if "op" in rule_node:
            # Group node with multiple rules
            op = rule_node.get("op", "and").lower()
            nested_rules = rule_node.get("rules", [])

            if not nested_rules:
                return

            if len(nested_rules) == 1:
                # Single rule in group, just process it recursively
                self._flatten_rules(nested_rules[0], conditions, matchtype_ref, op)
            else:
                # Multiple rules: set matchtype based on operator, then flatten all
                matchtype_ref[0] = "anyof" if op == "or" else "allof"
                for nested_rule in nested_rules:
                    self._flatten_rules(nested_rule, conditions, matchtype_ref, op)
        else:
            # Leaf node: a single condition
            field = rule_node.get("field", "")
            operator = rule_node.get("operator", "")
            value = rule_node.get("value", "")
            custom_header = rule_node.get("custom_header", "")

            # Special handling for "size" field (uses :size operator, not a regular field)
            if field == cs.FILTER_FIELD_SIZE:
                mapped_operator = f":{operator.lower()}"
                conditions.append(("size", mapped_operator, value))
                logger_sieve.debug("Added size condition with operator %s and value %s", operator, value)

            # Special handling for "body" field (RFC 5173 - Body Extension)
            elif field == cs.FILTER_FIELD_BODY:
                mapped_operator = f":{operator.lower()}"
                # For body, sievelib expects: ("body", ":text", ":contains", "value")
                conditions.append(("body", ":text", mapped_operator, value))
                logger_sieve.debug("Added body condition with operator %s and value %s", operator, value)

            else:
                # Standard field handling (including cc, header, etc.)
                mapped_field = self._map_field_name(field, custom_header)
                mapped_operator = f":{operator.lower()}"

                if mapped_field and mapped_operator:
                    # sievelib expects lists for most operators (e.g., subject, from, to, cc)
                    # Convert single string value to list
                    value_for_sieve = [value] if isinstance(value, str) else value
                    conditions.append((mapped_field, mapped_operator, value_for_sieve))
                    logger_sieve.debug("Added condition: field=%s, operator=%s, value=%s", mapped_field, mapped_operator, value_for_sieve)

    def _map_field_name(self, field: str, custom_header: str = "") -> str:
        """Map API field names to Sieve field names for use with sievelib.
        
        Supports the following field types:
        - Standard headers: "subject", "from", "to", "cc"
        - Custom headers: "header" (requires custom_header parameter)
        - Body: "body" (uses Sieve body extension)
        - Size: "size" (special operator, maps to empty string as size uses :size operator on any field)
        
        The field has already been validated by the schema (FilterRuleSchema).
        
        :param field: API field name (pre-validated by schema)
        :type field: str
        :param custom_header: Custom header name (used when field == "header")
        :type custom_header: str
        :return: Sieve field name (or empty string for special cases like "size")
        :rtype: str
        """
        # Standard headers that map directly to Sieve
        if field in {cs.FILTER_FIELD_SUBJECT, cs.FILTER_FIELD_FROM, cs.FILTER_FIELD_TO, cs.FILTER_FIELD_CC}:
            return field

        # Custom header field
        if field == cs.FILTER_FIELD_HEADER:
            if custom_header:
                return custom_header
            logger_sieve.warning("header field used but no custom_header specified")
            return ""

        # Body field (requires body extension in Sieve)
        if field == cs.FILTER_FIELD_BODY:
            return "body"

        # Size field (uses :size operator, returns empty since size works differently)
        # In Sieve, :size is an operator applied to the message, not a header field
        if field == cs.FILTER_FIELD_SIZE:
            return ""

        # Unknown field - should have been caught by schema validation
        raise BugException(f"Unknown field for filter given {field}")

    def _build_sieve_actions(self, actions: list[dict]) -> list:
        """Convert API action definitions into sievelib action definitions.

        :param actions: List of action dicts with keys: method, arguments.
        :type actions: list[dict]
        :return: List of action tuples for sievelib.
        :rtype: list
        :raises RequestException: If an action is invalid.
        """
        sieve_actions: list[tuple] = []

        for action in actions:
            method = action.get("method", "").lower()
            arguments = action.get("arguments", {})

            if method in {cs.FILTER_ACTION_DISCARD, cs.FILTER_ACTION_KEEP, cs.FILTER_ACTION_STOP}:
                sieve_actions.append((method,))
                logger_sieve.debug("Added %s action", method)

            elif method == cs.FILTER_ACTION_FILEINTO:
                self._add_fileinto_action(sieve_actions, arguments)

            elif method == cs.FILTER_ACTION_REDIRECT:
                self._add_redirect_action(sieve_actions, arguments)

            elif method == cs.FILTER_ACTION_REJECT:
                # Reject action can have an optional message
                message = arguments.get("message", "")
                if message:
                    sieve_actions.append(("reject", message))
                    logger_sieve.debug("Added reject action with message")
                else:
                    sieve_actions.append(("reject",))
                    logger_sieve.debug("Added reject action")

            elif method == cs.FILTER_ACTION_FLAG:
                flags = arguments.get("flags", [])
                if flags:
                    for flag in flags:
                        sieve_actions.append(("addflag", flag))
                    logger_sieve.debug("Added addflag action with flags: %s", flags)
                else:
                    logger_sieve.warning("imapflags action has no flags, skipping")

            elif method == cs.FILTER_ACTION_NOTIFY:
                method_val = arguments.get("method", "mailto")
                priority = arguments.get("priority", "normal")
                message_text = arguments.get("message_text", "")
                sieve_actions.append(("notify", method_val, priority, message_text))
                logger_sieve.debug("Added notify action")

            else:
                raise BugException(f"Unknown filter action {method}")

        return sieve_actions

    def _add_fileinto_action(self, actions_list: list, arguments: dict) -> None:
        """Helper to add fileinto action(s).
        
        Supports multiple folders and the :copy flag:
        - Single folder (backward compatible): arguments.get("folder")
        - Multiple folders: arguments.get("folders") list
        - Copy flag: arguments.get("keep_copy") boolean
        
        For each folder, adds a fileinto action to the actions list, optionally with :copy flag.
        
        In Sieve syntax:
        - Without copy: fileinto "Folder";
        - With copy: fileinto :copy "Folder";
        """
        folders = arguments.get("folders", [])

        # Backward compatibility: if no folders list, try single folder
        if not folders:
            folder = arguments.get("folder", "")
            if folder:
                folders = [folder]

        if not folders:
            logger_sieve.warning("fileinto action has no folder(s), skipping")
            return

        create_flag = (":create",) if arguments.get("create_if_no_exist", False) else ()
        copy_flag = (":copy",) if arguments.get("keep_copy", False) else ()

        # Add a fileinto action for each folder
        for folder in folders:
            if not folder or not isinstance(folder, str):
                logger_sieve.warning("Skipping invalid folder: %s", folder)
                continue
            actions_list.append(("fileinto", *copy_flag, *create_flag, folder))
            log_msg = f"Added fileinto action for folder: {folder}"
            if arguments.get("keep_copy", False):
                log_msg += " (with :copy flag)"
            logger_sieve.debug(log_msg)

    def _add_redirect_action(self, actions_list: list, arguments: dict) -> None:
        """Helper to add redirect action(s).
        
        Supports multiple addresses:
        - Single address (backward compatible): arguments.get("address")
        - Multiple addresses: arguments.get("addresses") list
        
        For each address, adds a separate redirect action to the actions list.
        
        In Sieve syntax, each redirect address becomes a separate action:
        - redirect "admin@example.com";
        - redirect "boss@example.com";
        
        :param actions_list: List to append redirect actions to.
        :type actions_list: list
        :param arguments: Action arguments dict containing address(es).
        :type arguments: dict
        """
        addresses = arguments.get("addresses", [])

        # Backward compatibility: if no addresses list, try single address
        if not addresses:
            address = arguments.get("address", "")
            if address:
                addresses = [address]

        if not addresses:
            logger_sieve.warning("redirect action has no address(es), skipping")
            return

        # Add a redirect action for each address
        for address in addresses:
            if not address or not isinstance(address, str):
                logger_sieve.warning("Skipping invalid redirect address: %s", address)
                continue
            # Address is already validated by the Marshmallow schema
            actions_list.append(("redirect", address))
            logger_sieve.debug("Added redirect action to: %s", address)


    def _parse_vacation_datetime(self, dt_str: str | None, default_tz: str = "UTC") -> tuple[str | None, str | None, str | None]:
        """Parse a vacation datetime string with optional timezone.
        
        Wrapper around the utility function from DateTimeUtils for backward compatibility.
        This method delegates to the module-level parse_vacation_datetime function, passing
        the _convert_tz_to_sieve_format method as the timezone converter.
        
        :param dt_str: DateTime string to parse
        :param default_tz: Default timezone if none specified in the string (can be IANA name or offset)
        :return: Tuple of (date_str, time_str, timezone_str_sieve_format) - time_str is None for date-only
        """
        return parse_vacation_datetime(dt_str, default_tz, self._convert_tz_to_sieve_format)

    def _convert_tz_to_sieve_format(self, tz_str: str, date_str: str = None) -> str:
        """Convert a timezone string to Sieve-compatible UTC offset format.
        
        RFC 5260 (Sieve Date extension) :zone parameter accepts only UTC offsets
        in the format "+HHMM" or "-HHMM" (e.g., "+0200", "-0500").
        
        This method:
        - Passes through existing UTC offsets (+HHMM, -HHMM, Z)
        - Converts IANA timezone names (e.g., "Europe/Paris") to their UTC offset AT the specified date
        - Defaults to "+0000" (UTC) if conversion fails
        
        :param tz_str: Timezone string (IANA name or UTC offset)
        :type tz_str: str
        :param date_str: Optional date in YYYY-MM-DD format to get the exact offset on that date
                        (useful for DST transitions). If not provided, uses current date.
        :type date_str: str
        :return: UTC offset in Sieve format (e.g., "+0200")
        :rtype: str
        """
        if not tz_str:
            return "+0000"

        tz_str = tz_str.strip()

        # Already in UTC offset format (+/-HHMM or +/-HH:MM)
        if tz_str[0] in ("+", "-"):
            # Normalize to +HHMM format (remove colon if present)
            return tz_str.replace(":", "")

        # Handle Z (UTC)
        if tz_str.upper() == "Z":
            return "+0000"

        # Handle UTC/GMT special cases
        if tz_str.upper() in ("UTC", "GMT"):
            return "+0000"

        # Try to convert IANA timezone name to UTC offset at the specified date
        try:
            tz_info = ZoneInfo(tz_str)

            # If a date is provided, use it to get the correct offset (accounting for DST)
            if date_str:
                try:
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                    dt_with_tz = dt.replace(tzinfo=tz_info)
                except ValueError:
                    # Invalid date format, fall back to current date
                    dt_with_tz = datetime.now(tz_info)
            else:
                # Use current date/time
                dt_with_tz = datetime.now(tz_info)

            offset = dt_with_tz.utcoffset()
            if offset is None:
                return "+0000"

            # Convert timedelta to +/-HHMM format
            total_seconds = int(offset.total_seconds())
            hours, remainder = divmod(abs(total_seconds), 3600)
            minutes = remainder // 60
            sign = "-" if total_seconds < 0 else "+"
            return f"{sign}{hours:02d}{minutes:02d}"
        except (KeyError, ValueError) as e:
            logger_sieve.warning(
                "Could not convert timezone '%s' to UTC offset: %s. Using UTC (+0000).",
                tz_str, str(e)
            )
            return "+0000"

    def _normalize_time_to_sieve(self, time_str: str) -> str:
        """Normalize a time string to HH:MM:SS format for Sieve.
        
        Accepts:
        - "HH:MM" → "HH:MM:00"
        - "HH:MM:SS" → "HH:MM:SS"
        
        :param time_str: Time string in HH:MM or HH:MM:SS format
        :type time_str: str
        :return: Normalized time in HH:MM:SS format
        :rtype: str
        """
        if not time_str:
            return "00:00:00"

        time_str = time_str.strip()
        parts = time_str.split(":")

        if len(parts) == 2:
            # HH:MM → HH:MM:00
            return f"{parts[0]}:{parts[1]}:00"
        elif len(parts) == 3:
            # Already HH:MM:SS
            return time_str
        else:
            # Invalid format, return default
            logger_sieve.warning("Invalid time format: %s, using 00:00:00", time_str)
            return "00:00:00"

    def _build_vacation_script(self, vacation_config: dict) -> str:
        """Build a Sieve vacation script with advanced filtering options.

        Supports date/time/weekday filtering with timezone awareness, custom subject, and auto-reply text.
        
        Timezone precedence:
        - If start_date/end_date have explicit timezone (e.g., +0100 or :Europe/Paris), use that
        - Else if 'timezone' field is present in config, use it
        - Else use "UTC" as default

        :param vacation_config: Complete vacation settings dict with all fields.
                              Must include: enabled, custom_subject, custom_subject_enabled, auto_reply_text,
                              start_date, end_date, timezone, start_time, end_time, weekdays_enabled, weekday, days
        :type vacation_config: dict
        :return: The vacation Sieve script.
        :rtype: str
        :raises RequestException: If configuration is invalid.
        """
        logger_sieve.debug("Building vacation script with config: %s", vacation_config)

        # Extract fields
        subject = vacation_config.get("custom_subject", "")
        custom_subject_enabled = vacation_config.get("custom_subject_enabled", False)
        message = vacation_config.get("auto_reply_text", "")
        start_date_raw = vacation_config.get("start_date")
        end_date_raw = vacation_config.get("end_date")
        default_timezone = vacation_config.get("timezone", "UTC")
        start_time = vacation_config.get("start_time")
        end_time = vacation_config.get("end_time")
        weekdays_enabled = vacation_config.get("weekdays_enabled", False)
        weekday = vacation_config.get("weekday", [])
        days = vacation_config.get("days")  # RFC 5230 :days parameter (integer or None)

        # Create VacationConditions object from raw config
        vacation_conditions = VacationConditions.from_vacation_config(
            start_date_raw=start_date_raw,
            end_date_raw=end_date_raw,
            default_timezone=default_timezone,
            start_time=start_time,
            end_time=end_time,
            weekdays_enabled=weekdays_enabled,
            weekday=weekday,
            parse_datetime_func=self._parse_vacation_datetime,
        )

        # Escape message for Sieve
        message_escaped = message.replace('"', '\\"').replace('\\', '\\\\').replace('\n', '\\n')

        # Build requires clause
        requires = ['vacation']

        # Add extensions needed for advanced filtering
        if (vacation_conditions.start_date or vacation_conditions.end_date or 
            vacation_conditions.start_time or vacation_conditions.end_time or 
            (vacation_conditions.weekdays_enabled and vacation_conditions.weekday)):
            requires.extend(['relational', 'date', 'comparator-i;ascii-numeric'])

        # Build script
        script = 'require [' + ', '.join(f'"{req}"' for req in requires) + '];\n\n'

        # Build condition block if any filtering is needed
        conditions = self._build_vacation_conditions(vacation_conditions)

        # Build vacation parameters
        # Sieve syntax: vacation [:days N] [:subject "..."] "message";
        vacation_params = []

        # Add RFC 5230 :days parameter first (before :subject)
        if days is not None and days > 0:
            vacation_params.append(':days')
            vacation_params.append(str(days))

        # Add custom subject if enabled
        if custom_subject_enabled and subject:
            subject_escaped = subject.replace('"', '\\"').replace('\\', '\\\\')
            vacation_params.append(':subject')
            vacation_params.append(f'"{subject_escaped}"')

        # Add the message (always the last element)
        vacation_params.append(f'"{message_escaped}"')

        if conditions:
            # Wrap vacation in conditional block
            script += conditions
            script += '    vacation ' + ' '.join(vacation_params) + ';\n'
            script += '}\n'
        else:
            # Generate the vacation directive at the root level
            script += 'vacation ' + ' '.join(vacation_params) + ';\n'

        logger_sieve.debug("Generated vacation script:\n%s", script)
        return script

    def _build_vacation_conditions(self, conditions: VacationConditions) -> str:
        """Build the condition block for vacation filtering (dates, times, weekdays).
        
        The vacation response is active if ANY of the following is true:
        1. Within the fixed date/time range (start_date to end_date, including their embedded times)
        2. Within the recurring daily time window (start_time to end_time, every day)
        3. On any of the specified weekdays (all day)
        
        All three conditions are ALTERNATIVES (OR logic), not requirements.
        
        Handles date ranges with timezone awareness. Each date can have its own timezone.
        
        Special handling for overnight time ranges (e.g., 18:00 to 08:00):
        - Converted to: anyof(time >= 18:00 OR time < 08:00)
        
        :param start_date: Start date in YYYY-MM-DD format (or None)
        :param end_date: End date in YYYY-MM-DD format (or None)
        :param start_tz: Timezone for start (already in Sieve format from _parse_vacation_datetime)
        :param end_tz: Timezone for end (already in Sieve format from _parse_vacation_datetime)
        :param start_date_time: Start time extracted from start_date (or None if date-only)
        :param end_date_time: End time extracted from end_date (or None if date-only)
        :param start_time: Recurring start time in HH:MM or HH:MM:SS format (independent, or None)
        :param end_time: Recurring end time in HH:MM or HH:MM:SS format (independent, or None)
        :type conditions: VacationConditions
        :return: Sieve condition block as string, or empty string if no conditions
        :rtype: str
        """
        # Build individual condition parts that will be combined with OR (anyof)
        condition_parts = []

        # === PART 1: Fixed date/time range condition ===
        # Represents: start_date (with its time if present) to end_date (with its time if present)
        date_range_condition = None
        date_range_parts = []

        if conditions.start_date:
            try:
                datetime.strptime(conditions.start_date, "%Y-%m-%d")
                sieve_tz = conditions.start_tz if conditions.start_tz else "+0000"
                zone_param = f' :zone "{sieve_tz}"'

                if conditions.start_date_time:
                    start_time_sieve = self._normalize_time_to_sieve(conditions.start_date_time)
                    # Condition: date > start_date OR (date == start_date AND time >= start_date_time)
                    date_range_parts.append(
                        f'allof(currentdate{zone_param} :value "eq" "date" "{conditions.start_date}", '
                        f'currentdate{zone_param} :value "ge" "time" "{start_time_sieve}")'
                    )
                else:
                    # Date-only: date >= start_date
                    date_range_parts.append(f'currentdate{zone_param} :value "ge" "date" "{conditions.start_date}"')
            except ValueError:
                logger_sieve.warning("Invalid start_date format: %s, skipping", conditions.start_date)

        if conditions.end_date:
            try:
                datetime.strptime(conditions.end_date, "%Y-%m-%d")
                sieve_tz = conditions.end_tz if conditions.end_tz else "+0000"
                zone_param = f' :zone "{sieve_tz}"'

                if conditions.end_date_time:
                    end_time_sieve = self._normalize_time_to_sieve(conditions.end_date_time)
                    # Condition: date < end_date OR (date == end_date AND time <= end_date_time)
                    date_range_parts.append(
                        f'allof(currentdate{zone_param} :value "eq" "date" "{conditions.end_date}", '
                        f'currentdate{zone_param} :value "le" "time" "{end_time_sieve}")'
                    )
                else:
                    # Date-only: date <= end_date
                    date_range_parts.append(f'currentdate{zone_param} :value "le" "date" "{conditions.end_date}"')
            except ValueError:
                logger_sieve.warning("Invalid end_date format: %s, skipping", conditions.end_date)

        # Combine date range parts with AND (all must be true for date range to match)
        if date_range_parts:
            if len(date_range_parts) == 1:
                date_range_condition = date_range_parts[0]
            else:
                date_range_condition = f'allof(\n        {", ".join(date_range_parts)})'
            condition_parts.append(date_range_condition)

        # === PART 2: Recurring daily time window ===
        # Represents: every day between start_time and end_time (independent of date range)
        if conditions.start_time and conditions.end_time:
            start_time_sieve = self._normalize_time_to_sieve(conditions.start_time)
            end_time_sieve = self._normalize_time_to_sieve(conditions.end_time)
            sieve_tz = conditions.start_tz if conditions.start_tz else "+0000"
            zone_param = f' :zone "{sieve_tz}"'

            if conditions.start_time < conditions.end_time:
                # Normal range (e.g., 09:00 to 17:00): time >= 09:00 AND time <= 17:00
                daily_time_condition = (
                    f'allof(currentdate{zone_param} :value "ge" "time" "{start_time_sieve}", '
                    f'currentdate{zone_param} :value "le" "time" "{end_time_sieve}")'
                )
            else:
                # Overnight range (e.g., 18:00 to 08:00): time >= 18:00 OR time < 08:00
                daily_time_condition = (
                    f'anyof(currentdate{zone_param} :value "ge" "time" "{start_time_sieve}", '
                    f'currentdate{zone_param} :value "lt" "time" "{end_time_sieve}")'
                )
            condition_parts.append(daily_time_condition)

        # === PART 3: Weekday filtering ===
        # Represents: specific weekdays, all day long (independent conditions)
        if conditions.weekdays_enabled and conditions.weekday:
            valid_days = [str(d) for d in conditions.weekday if 0 <= d <= 6]
            if valid_days:
                sieve_tz = conditions.start_tz if conditions.start_tz else "+0000"
                zone_param = f' :zone "{sieve_tz}"'

                if len(valid_days) == 1:
                    weekday_condition = f'currentdate{zone_param} :is "weekday" "{valid_days[0]}"'
                else:
                    day_conditions = ', '.join([f'currentdate{zone_param} :is "weekday" "{day}"' for day in valid_days])
                    weekday_condition = f'anyof({day_conditions})'
                condition_parts.append(weekday_condition)

        if not condition_parts:
            return ""

        # Combine all parts with OR (anyof): activation if ANY condition is true
        if len(condition_parts) == 1:
            return "if " + condition_parts[0].strip() + " {\n"
        else:
            indented = [f"    {part}" for part in condition_parts]
            return "if anyof(\n" + ",\n".join(indented) + "\n) {\n"


    def _build_forward_script(self, forward_addresses: list[str], keep_copy: int = 0, always_send: int = 0) -> str:
        """Build a Sieve forward script.

        Forwards emails to the specified addresses. If keep_copy is enabled,
        uses 'keep' action to retain a local copy after forwarding.

        :param forward_addresses: List of email addresses to forward to.
        :type forward_addresses: list[str]
        :param keep_copy: Whether to keep a copy.
        :type keep_copy: bool
        :param always_send: Whether to forward even if sender is unknown.
        :type always_send: bool
        :return: The forward Sieve script (without require clause).
        :rtype: str
        """
        script = ''

        # Forward to each address using simple redirect
        for address in forward_addresses:
            script += f'redirect "{address}";\n'
            logger_sieve.debug("Added forward to: %s", address)

        # After redirect, specify the final action:
        if keep_copy:
            script += 'keep;\n'
        else:
            script += 'discard;\n'

        logger_sieve.debug("Generated forward script (keep_copy=%s, always_send=%s):\n%s", keep_copy, always_send, script)
        return script

    def _build_notification_script(self, notification_config: dict) -> str:
        """Build a Sieve notification script (RFC 5435 - enotify extension).

        :param notification_config: Notification settings dict with keys:
                                   notify_addresses (list), notify_message (str)
        :type notification_config: dict
        :return: The notification Sieve script with require clause.
        :rtype: str
        :raises RequestException: If email addresses are invalid.
        """
        logger_sieve.debug("Building notification script with config: %s", notification_config)

        notify_addresses = notification_config.get("notify_addresses", [])
        notify_message = notification_config.get("notify_message", "")

        if not notify_addresses:
            logger_sieve.warning("No notification addresses provided")
            return ""

        # Addresses are already validated by the Marshmallow schema

        if not notify_message:
            notify_message = "A mail event has been triggered."

        # Escape message for Sieve
        message_escaped = notify_message.replace('"', '\\"').replace('\\', '\\\\').replace('\n', '\\n')

        script = 'require ["enotify"];\n\n'

        for address in notify_addresses:
            script += f'notify :message "{message_escaped}" "mailto:{address}";\n'
            logger_sieve.debug("Added notification to: %s", address)

        logger_sieve.debug("Generated notification script:\n%s", script)
        return script

    def logout(self) -> None:
        """Disconnect from the ManageSieve server.

        Safe to call even if the connection is already closed.
        """
        logger_sieve.debug("Logging out from Sieve server")
        if self.connection is not None:
            try:
                self.connection.logout()
            except SieveError as e:
                logger_sieve.warning("Error during Sieve logout: %s", e)
            finally:
                self.connection    = None
                self.connected     = False
                self.authenticated = False
