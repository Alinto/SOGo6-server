"""
List of sogo server expetions

SOGo server, being an API, should never raise any exceptions. Instead, it should handles them and
give a proper response to the client's API.
"""


class AggravatedException(Exception):
    """
    Exception serious enough to stop all operations.

    Example: SOGo can't reach its own database, making him useless.
    Meaning: Something is wrong with process_settings or the database itself
    Remediation: An admin should check the error and the conf
    """

class RequestException(Exception):
    """
    Exception during a request, mostly unexpected but SOGo can continue to welcome other requests

    Example: Attempting to import an event wich malformed icalender format
    Meaning: Something was wrong with the file, but sogo is still operationnal
    Remediation: An admin should check the log, the input and may report a bug on github if necessary. 
    """

class BugException(Exception):
    """
    Those exceptions should never happen, but as still here in case of bug

    Example: A function was expected a string and got an integger instead.
    Meaning: SOGo miss some robustness 
    Remediation: An admin should report those on github 
    """
