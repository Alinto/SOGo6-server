from __future__ import annotations
from typing import Callable, TypeVar, ParamSpec
import re
from socket import timeout as sock_timeout, gaierror, error as sock_error
from datetime import datetime

from sievelib.managesieve import Client, Error as SieveError
from sievelib.factory import FiltersSet

from app.utils.exceptions import RequestException, BugException
from app.utils.logger.logger import logger_sieve
from app.manager.mail.ClientFiltering import ClientFiltering
from app.utils import errors as err
from app.utils import constants as cs
from app.utils.constants import (
    FILTER_SECTION_FILTERS,
    FILTER_SECTION_VACATION,
    FILTER_SECTION_FORWARD,
    FILTER_SECTION_NOTIFICATION,
)

P = ParamSpec("P")
R = TypeVar("R")

# Name of the single active Sieve script that merges all sections (filters, vacation, forward, notification).
SIEVE_MASTER_SCRIPT = "sogo-master"


class ClientSieve(ClientFiltering):
    """
    Sieve (ManageSieve) client implementation for Dovecot using sievelib.
    """

    # Sieve commands that are always available and should not be in require
    BUILTIN_SIEVE_COMMANDS = {"redirect", "copy", "keep", "discard", "stop"}

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
                "Sieve connection/auth error for %s@%s:%d – %s",
                username, self.server, self.port, error_msg,
            )
            if "Connection to server failed" in error_msg or "SSL error" in error_msg:
                raise RequestException(f"Sieve connection failed: {error_msg}", err.ERROR_SIEVE_CONNECTION_FAILED) from e
            raise RequestException(f"Sieve error: {error_msg}", err.ERROR_SIEVE_AUTH_FAILED) from e
        except (gaierror, sock_timeout, TimeoutError, ConnectionRefusedError, sock_error) as e:
            logger_sieve.error("Sieve TCP error connecting to %s:%d – %s", self.server, self.port, e)
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
            conditions = self._build_sieve_conditions(rules)
            filters_set.addfilter(
                name=filter_name,
                conditions=conditions,
                actions=self._build_sieve_actions(actions),
            )
            logger_sieve.debug("Added filter '%s' to FiltersSet", filter_name)
        except Exception as e:
            logger_sieve.error("Error adding filter '%s' to FiltersSet: %s", filter_name, e)
            raise RequestException(
                f"Failed to add filter '{filter_name}': {e}",
                err.ERROR_SIEVE_SCRIPT_INVALID,
            ) from e

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
                if missing_capability == "notify" and section_name == FILTER_SECTION_NOTIFICATION:
                    logger_sieve.warning(
                        "Skipping notification section because 'notify' extension is not supported"
                    )
                    skipped_sections.add(FILTER_SECTION_NOTIFICATION)
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

        The merged script follows this order:
        1. Forward rules (redirect or keep+copy)
        2. Filter rules (custom rules)
        3. Vacation auto-reply

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
            FILTER_SECTION_NOTIFICATION: False,
            FILTER_SECTION_VACATION: False,
            FILTER_SECTION_FORWARD: False,
            FILTER_SECTION_FILTERS: False,
        }

        try:
            # Build the merged script by combining all enabled sections
            merged_script_parts = []
            requires_set = set()

            # 1. Process filters (rules)
            filters_list = filters_config.get(FILTER_SECTION_FILTERS, [])
            if filters_list:
                try:
                    filters_set = FiltersSet("sogo-rules")
                    for filter_item in filters_list:
                        if filter_item.get("enabled", 1):
                            self._add_filter_to_set(filters_set, filter_item)

                    if filters_set.filters:  # Only add if filters exist
                        filters_script = self._render_filters_set(filters_set)
                        merged_script_parts.append((FILTER_SECTION_FILTERS, filters_script))
                        # Don't add "copy" to requires - it's a native Sieve command
                        # Only "mailbox" extension is needed if :create is used
                        activated_sections[FILTER_SECTION_FILTERS] = True
                        logger_sieve.debug("Added filters section to merged script")
                except Exception as e:
                    logger_sieve.error("Error processing filters section: %s", e)
                    raise RequestException(
                        f"Failed to process filters: {e}",
                        err.ERROR_SIEVE_SCRIPT_INVALID,
                    ) from e

            # 2. Process forward settings
            forward_config = filters_config.get(FILTER_SECTION_FORWARD)
            if forward_config and forward_config.get("enabled", 0):
                try:
                    forward_addresses = forward_config.get("forwardAddress", [])
                    if forward_addresses:
                        # Validate all addresses
                        for address in forward_addresses:
                            if not self._validate_email(address):
                                raise RequestException(
                                    f"Invalid email address for forward: {address}",
                                    err.ERROR_SIEVE_SCRIPT_INVALID,
                                )

                        keep_copy = forward_config.get("keepCopy", 0)
                        always_send = forward_config.get("alwaysSend", 0)

                        forward_script = self._build_forward_script(forward_addresses, keep_copy, always_send)
                        merged_script_parts.append((FILTER_SECTION_FORWARD, forward_script))
                        # Don't add "redirect" or "copy" to requires - they are native Sieve commands
                        logger_sieve.debug("Added forward section to merged script")
                        activated_sections[FILTER_SECTION_FORWARD] = True
                except RequestException:
                    raise
                except Exception as e:
                    logger_sieve.error("Error processing forward section: %s", e)
                    raise RequestException(
                        f"Failed to process forward: {e}",
                        err.ERROR_SIEVE_SCRIPT_INVALID,
                    ) from e

            # 3. Process vacation settings
            vacation_config = filters_config.get(FILTER_SECTION_VACATION)
            if vacation_config and vacation_config.get("enabled", 0):
                try:
                    vacation_script = self._build_vacation_script(vacation_config)
                    merged_script_parts.append((FILTER_SECTION_VACATION, vacation_script))
                    requires_set.add("vacation")
                    activated_sections[FILTER_SECTION_VACATION] = True
                    logger_sieve.debug("Added vacation section to merged script")
                except Exception as e:
                    logger_sieve.error("Error processing vacation section: %s", e)
                    raise RequestException(
                        f"Failed to process vacation: {e}",
                        err.ERROR_SIEVE_SCRIPT_INVALID,
                    ) from e

            # 4. Process notification settings (RFC 5435)
            # NOTE: This section is optional and requires Dovecot to support the 'notify' extension.
            # If the server doesn't support it, we store the configuration but don't add it to the script.
            notification_config = filters_config.get(FILTER_SECTION_NOTIFICATION)
            if notification_config and notification_config.get("enabled", 0):
                try:
                    notify_addresses = notification_config.get("notifyAddresses", [])
                    if notify_addresses:
                        # Validate all addresses
                        for address in notify_addresses:
                            if not self._validate_email(address):
                                raise RequestException(
                                    f"Invalid email address for notification: {address}",
                                    err.ERROR_SIEVE_SCRIPT_INVALID,
                                )

                        # Build notification script (will be added to merged script if server supports it)
                        notification_script = self._build_notification_script(notification_config)
                        if notification_script:  # Only add if script is not empty
                            merged_script_parts.append((FILTER_SECTION_NOTIFICATION, notification_script))
                            requires_set.add("enotify")
                            logger_sieve.debug("Added notification section to merged script")
                        activated_sections[FILTER_SECTION_NOTIFICATION] = True
                    else:
                        logger_sieve.debug("Notification has no addresses; marking as activated for database persistence")
                        activated_sections[FILTER_SECTION_NOTIFICATION] = True
                except RequestException:
                    raise
                except Exception as e:
                    logger_sieve.error("Error processing notification section: %s", e)
                    raise RequestException(
                        f"Failed to process notification: {e}",
                        err.ERROR_SIEVE_SCRIPT_INVALID,
                    ) from e

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

            logger_sieve.info("Successfully merged and activated all filter sections")
            logger_sieve.info("Activated sections: %s", activated_sections)

            return activated_sections

        except RequestException:
            raise
        except Exception as e:
            logger_sieve.error("Error in set_merged_filters: %s", e)
            raise RequestException(
                f"Failed to merge filters: {e}",
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

    def _build_sieve_conditions(self, rules: dict) -> list[tuple]:
        """Convert API rule tree into a flat list of sievelib conditions."""
        if not rules:
            return []
        conditions: list = []
        self._flatten_rules(rules, conditions)
        return conditions

    def _flatten_rules(self, rule_node: dict, conditions: list, parent_op: str = "and") -> None:
        """Recursively convert a nested rule tree into sievelib condition tuples.

        Preserves AND/OR logic by using sievelib's allof/anyof constructs.

        :param rule_node: A rule node (leaf or group).
        :type rule_node: dict
        :param conditions: The list to append conditions to (mutated).
        :type conditions: list
        :param parent_op: Parent operator ("and" or "or") for context.
        :type parent_op: str
        """
        if "op" in rule_node:
            # Group node with multiple rules
            op = rule_node.get("op", "and").lower()
            nested_rules = rule_node.get("rules", [])

            if not nested_rules:
                return

            if len(nested_rules) == 1:
                # Single rule in group, just process it
                self._flatten_rules(nested_rules[0], conditions, op)
            else:
                # Multiple rules: use allof/anyof
                nested_conditions: list = []
                for nested_rule in nested_rules:
                    self._flatten_rules(nested_rule, nested_conditions, op)

                if nested_conditions:
                    group_op = "anyof" if op == "or" else "allof"
                    conditions.append((group_op, nested_conditions))
        else:
            # Leaf node: a single condition
            field = rule_node.get("field", "")
            operator = rule_node.get("operator", "")
            value = rule_node.get("value", "")
            custom_header = rule_node.get("custom_header", "")

            mapped_field = self._map_field_name(field, custom_header)
            mapped_operator = self._map_operator_name(operator)

            if mapped_field and mapped_operator:
                conditions.append((mapped_field, mapped_operator, value))

    def _map_field_name(self, field: str, custom_header: str = "") -> str:
        """Map API field names to sievelib field names."""
        if field in ("subject", "from", "to"):
            return field
        if field == "header" and custom_header:
            return custom_header
        if field not in ("subject", "from", "to"):
            logger_sieve.warning("Unknown field name: %s", field)
        return field

    def _map_operator_name(self, operator: str) -> str:
        """Map API operator names to sievelib operator names with ':' prefix."""
        mapping = {
            "contains": ":contains", "is": ":is", "equals": ":is",
            "starts-with": ":startswith", "starts_with": ":startswith", "startswith": ":startswith",
            "ends-with": ":endswith", "ends_with": ":endswith", "endswith": ":endswith",
            "matches": ":matches", "regex": ":regex",
            "not-contains": ":notcontains", "not_contains": ":notcontains", "notcontains": ":notcontains",
            "exists": ":exists", "size": ":size",
        }
        mapped = mapping.get(operator.lower())
        if mapped:
            return mapped
        logger_sieve.warning("Unknown operator name: %s, using as-is", operator)
        return f":{operator.lower()}" if not operator.lower().startswith(":") else operator.lower()

    def _build_sieve_actions(self, actions: list[dict]) -> list:
        """Convert API action definitions into sievelib action definitions.

        :param actions: List of action dicts with keys: method, arguments.
        :type actions: list[dict]
        :return: List of action tuples for sievelib.
        :rtype: list
        :raises RequestException: If an action is invalid.
        """
        sieve_actions = []

        for action in actions:
            method = action.get("method", "").lower()
            arguments = action.get("arguments", {})

            if method in ("discard", "keep", "stop"):
                sieve_actions.append((method,))
                logger_sieve.debug("Added %s action", method)
            
            elif method == "fileinto":
                self._add_fileinto_action(sieve_actions, arguments)
            
            elif method == "redirect":
                self._add_redirect_action(sieve_actions, arguments)
            
            elif method == "copy":
                self._add_copy_action(sieve_actions, arguments)
            
            elif method == "removeheader":
                self._add_removeheader_action(sieve_actions, arguments)
            
            else:
                logger_sieve.warning("Unknown filter action method: %s", method)

        return sieve_actions

    def _add_fileinto_action(self, actions_list: list, arguments: dict) -> None:
        """Helper to add a fileinto action."""
        folder = arguments.get("folder", "")
        if not folder:
            logger_sieve.warning("fileinto action has no folder, skipping")
            return
        create_flag = (":create",) if arguments.get("create_if_no_exist", False) else ()
        actions_list.append(("fileinto", *create_flag, folder))
        logger_sieve.debug("Added fileinto action for folder: %s", folder)

    def _add_redirect_action(self, actions_list: list, arguments: dict) -> None:
        """Helper to add a redirect action."""
        address = arguments.get("address", "")
        if not address:
            logger_sieve.warning("redirect action has no address, skipping")
            return
        if not self._validate_email(address):
            logger_sieve.warning("Invalid email address for redirect: %s", address)
            return
        actions_list.append(("redirect", address))
        logger_sieve.debug("Added redirect action to: %s", address)

    def _add_copy_action(self, actions_list: list, arguments: dict) -> None:
        """Helper to add a copy action."""
        folder = arguments.get("folder", "")
        if not folder:
            logger_sieve.warning("copy action has no folder, skipping")
            return
        create_flag = (":create",) if arguments.get("create_if_no_exist", False) else ()
        actions_list.append(("copy", *create_flag, folder))
        logger_sieve.debug("Added copy action for folder: %s", folder)

    def _add_removeheader_action(self, actions_list: list, arguments: dict) -> None:
        """Helper to add a removeheader action."""
        header_name = arguments.get("header_name", "")
        if not header_name:
            logger_sieve.warning("removeheader action has no header_name, skipping")
            return
        actions_list.append(("removeheader", header_name))
        logger_sieve.debug("Added removeheader action for: %s", header_name)

    def _validate_email(self, email: str) -> bool:
        """Validate email address format.

        :param email: Email address to validate.
        :type email: str
        :return: True if valid, False otherwise.
        :rtype: bool
        """
        # Simple regex for email validation
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

    def _parse_vacation_datetime(self, dt_str: str | None, default_tz: str = "UTC") -> tuple[str | None, str | None, str | None]:
        """Parse a vacation datetime string with optional timezone.
        
        Supports formats:
        - Date only: "2026-06-15" → returns (date, None, default_tz)
        - DateTime: "2026-06-15T14:30:00" → returns (date, time, default_tz)
        - DateTime with +HH:MM: "2026-06-15T14:30:00+0100" → returns (date, time, extracted_tz)
        - DateTime with :Zone: "2026-06-15T14:30:00:Europe/Paris" → returns (date, time, "Europe/Paris")
        - DateTime with Z: "2026-06-15T14:30:00Z" → returns (date, time, "UTC")
        
        :param dt_str: DateTime string to parse
        :param default_tz: Default timezone if none specified in the string
        :return: Tuple of (date_str, time_str, timezone_str) - time_str is None for date-only
        """
        if not dt_str or not isinstance(dt_str, str):
            return None, None, default_tz
        
        dt_str = dt_str.strip()
        if not dt_str:
            return None, None, default_tz
        
        # Check if it's date-only (YYYY-MM-DD)
        if len(dt_str) == 10 and dt_str.count("-") == 2:
            try:
                datetime.strptime(dt_str, "%Y-%m-%d")
                return dt_str, None, default_tz
            except ValueError:
                return None, None, default_tz
        
        # Try to parse datetime with timezone
        if "T" not in dt_str:
            return None, None, default_tz
        
        date_part, time_part = dt_str.split("T", 1)
        
        # Validate date part
        try:
            datetime.strptime(date_part, "%Y-%m-%d")
        except ValueError:
            return None, None, default_tz
        
        extracted_tz = default_tz
        
        # Check for timezone info
        if time_part.endswith("Z"):
            # UTC marker
            time_only = time_part[:-1]
            extracted_tz = "UTC"
        elif "+" in time_part:
            # Format with +HH:MM or +HHMM
            idx = time_part.rfind("+")
            time_only = time_part[:idx]
            tz_offset = time_part[idx:]  # Keep as "+HH:MM" or "+HHMM"
            extracted_tz = tz_offset
        elif time_part.count("-") > 0 and time_part.rfind("-") > 7:
            # Format with -HH:MM (negative UTC offset)
            # Find the last dash; only treat as timezone if it appears after the minimum time length
            idx = time_part.rfind("-")
            if idx > 0:
                time_only = time_part[:idx]
                tz_offset = time_part[idx:]
                extracted_tz = tz_offset
            else:
                time_only = time_part
        elif ":" in time_part and time_part.count(":") > 2:
            # Check for :Zone format (e.g., "14:30:00:Europe/Paris")
            # If more than 2 colons (HH:MM:SS = 2), there might be a timezone
            parts = time_part.rsplit(":", 1)
            time_only = parts[0]
            tz_candidate = parts[1]
            # Validate it looks like a timezone (contains / or other valid indicators)
            if "/" in tz_candidate or tz_candidate.startswith("UTC") or tz_candidate.startswith("GMT"):
                extracted_tz = tz_candidate
            else:
                # Not a timezone, just regular time
                time_only = time_part
        else:
            # No timezone info
            time_only = time_part
        
        # Return parsed components
        if time_only and len(time_only.split(":")) >= 2:
            return date_part, time_only, extracted_tz
        
        return date_part, None, extracted_tz

    def _build_vacation_script(self, vacation_config: dict) -> str:
        """Build a Sieve vacation script with advanced filtering options.

        Supports date/time/weekday filtering with timezone awareness, custom subject, and auto-reply text.
        
        Timezone precedence:
        - If startDate/endDate have explicit timezone (e.g., +0100 or :Europe/Paris), use that
        - Else if 'timezone' field is present in config, use it
        - Else use "UTC" as default

        :param vacation_config: Complete vacation settings dict with all fields.
                              Must include: enabled, customSubject, customSubjectEnabled, autoReplyText,
                              startDate, endDate, timezone, startTime, endTime, weekdaysEnabled, days
        :type vacation_config: dict
        :return: The vacation Sieve script.
        :rtype: str
        :raises RequestException: If configuration is invalid.
        """
        logger_sieve.debug("Building vacation script with config: %s", vacation_config)
        
        # Extract fields
        subject = vacation_config.get("customSubject", "")
        custom_subject_enabled = vacation_config.get("customSubjectEnabled", False)
        message = vacation_config.get("autoReplyText", "")
        start_date_raw = vacation_config.get("startDate")
        end_date_raw = vacation_config.get("endDate")
        default_timezone = vacation_config.get("timezone", "UTC")
        start_time = vacation_config.get("startTime")
        end_time = vacation_config.get("endTime")
        weekdays_enabled = vacation_config.get("weekdaysEnabled", False)
        days = vacation_config.get("days", [])

        # Parse dates with timezone awareness
        start_date_str, _, start_tz = self._parse_vacation_datetime(start_date_raw, default_timezone)
        end_date_str, _, end_tz = self._parse_vacation_datetime(end_date_raw, default_timezone)

        # Fallback to default subject if custom subject is not enabled or empty
        if not custom_subject_enabled or not subject:
            subject = "Auto: Away"

        # Escape subject and message for Sieve (single pass, not repeated)
        subject_escaped = subject.replace('"', '\\"').replace('\\', '\\\\')
        message_escaped = message.replace('"', '\\"').replace('\\', '\\\\').replace('\n', '\\n')

        # Build requires clause
        requires = ['vacation']
        
        # Add extensions needed for advanced filtering
        if (start_date_str or end_date_str or start_time or end_time or 
            (weekdays_enabled and days)):
            requires.extend(['relational', 'date', 'comparator-i;ascii-numeric'])

        # Build script
        script = 'require [' + ', '.join(f'"{req}"' for req in requires) + '];\n\n'

        # Build condition block if any filtering is needed
        conditions = self._build_vacation_conditions(
            start_date_str, end_date_str, start_tz, end_tz, start_time, end_time, weekdays_enabled, days
        )

        # Build vacation parameters
        vacation_params = [':subject', f'"{subject_escaped}"', f'"{message_escaped}"']

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

    def _build_vacation_conditions(self, start_date: str = None, end_date: str = None,
                                   start_tz: str = None, end_tz: str = None,
                                   start_time: str = None, end_time: str = None,
                                   weekdays_enabled: bool = False, days: list = None) -> str:
        """Build the condition block for vacation filtering (dates, times, weekdays).
        
        Each date can have its own timezone, which allows fine-grained control.
        
        :param start_date: Start date in YYYY-MM-DD format (or None)
        :param end_date: End date in YYYY-MM-DD format (or None)
        :param start_tz: Timezone for start_date (e.g., "UTC", "Europe/Paris", "+0100")
        :param end_tz: Timezone for end_date (e.g., "UTC", "Europe/Paris", "+0100")
        :param start_time: Start time in HH:MM format (or None)
        :param end_time: End time in HH:MM format (or None)
        :param weekdays_enabled: Whether weekday filtering is enabled
        :param days: List of weekday numbers (0-6)
        :return: Sieve condition block as string, or empty string if no conditions
        """
        if days is None:
            days = []

        conditions = []
        
        # Date range filtering with timezone awareness
        if start_date:
            try:
                datetime.strptime(start_date, "%Y-%m-%d")
                conditions.append(f'currentdate :value "ge" "date" "{start_date}"')
            except ValueError:
                logger_sieve.warning("Invalid startDate format: %s, skipping", start_date)

        if end_date:
            try:
                datetime.strptime(end_date, "%Y-%m-%d")
                conditions.append(f'currentdate :value "le" "date" "{end_date}"')
            except ValueError:
                logger_sieve.warning("Invalid endDate format: %s, skipping", end_date)

        # Time range filtering
        if start_time and end_time and self._is_valid_time(start_time) and self._is_valid_time(end_time):
            start_time_sieve = f"{start_time}:00"
            end_time_sieve = f"{end_time}:00"
            if start_time < end_time:
                conditions.append(
                    f'allof(currentdate :value "ge" "time" "{start_time_sieve}", '
                    f'currentdate :value "le" "time" "{end_time_sieve}")'
                )
            else:  # Overnight range
                conditions.append(
                    f'anyof(allof(currentdate :value "ge" "time" "{start_time_sieve}", '
                    f'currentdate :value "le" "time" "23:59:59"), '
                    f'allof(currentdate :value "ge" "time" "00:00:00", '
                    f'currentdate :value "le" "time" "{end_time_sieve}"))'
                )

        # Weekday filtering
        if weekdays_enabled and days:
            valid_days = [str(d) for d in days if 0 <= d <= 6]
            if valid_days:
                if len(valid_days) == 1:
                    conditions.append(f'currentdate :is "weekday" "{valid_days[0]}"')
                else:
                    day_conditions = ', '.join([f'currentdate :is "weekday" "{day}"' for day in valid_days])
                    conditions.append(f'anyof({day_conditions})')

        if not conditions:
            return ""

        if len(conditions) == 1:
            return "if " + conditions[0].strip() + " {\n"
        else:
            indented = [f"    {c}" for c in conditions]
            return "if allof(\n" + ",\n".join(indented) + "\n) {\n"

    def _is_valid_time(self, time_str: str) -> bool:
        """Validate time format (HH:MM).

        :param time_str: Time string to validate.
        :type time_str: str
        :return: True if valid, False otherwise.
        :rtype: bool
        """
        try:
            datetime.strptime(time_str, "%H:%M")
            return True
        except ValueError:
            return False

    def _build_forward_script(self, forward_addresses: list[str], keep_copy: int = 0, always_send: int = 0) -> str:
        """Build a Sieve forward script.

        Forwards emails to the specified addresses. If keep_copy is enabled,
        uses 'keep' action to retain a local copy after forwarding.

        :param forward_addresses: List of email addresses to forward to.
        :type forward_addresses: list[str]
        :param keep_copy: Whether to keep a copy (0 or 1).
        :type keep_copy: int
        :param always_send: Whether to forward even if sender is unknown (0 or 1).
        :type always_send: int
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

        logger_sieve.debug("Generated forward script (keepCopy=%d, alwaysSend=%d):\n%s", keep_copy, always_send, script)
        return script

    def _build_notification_script(self, notification_config: dict) -> str:
        """Build a Sieve notification script (RFC 5435 - enotify extension).

        :param notification_config: Notification settings dict with keys:
                                   notifyAddresses (list), notifyMessage (str)
        :type notification_config: dict
        :return: The notification Sieve script with require clause.
        :rtype: str
        :raises RequestException: If email addresses are invalid.
        """
        logger_sieve.debug("Building notification script with config: %s", notification_config)

        notify_addresses = notification_config.get("notifyAddresses", [])
        notify_message = notification_config.get("notifyMessage", "")

        if not notify_addresses:
            logger_sieve.warning("No notification addresses provided")
            return ""

        for address in notify_addresses:
            if not self._validate_email(address):
                raise RequestException(
                    f"Invalid email address for notification: {address}",
                    err.ERROR_SIEVE_SCRIPT_INVALID,
                )

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
