from yarl import URL

def get_domain_from_mail(string_input: str) -> str|None:
    """
    Get a mail string and return the domain if there is one.
    Domain in mail pov so domain for user@domain
    """
    if not isinstance(string_input, str):
        raise ValueError(f"Method get_domain_from_mail expects a str and got {type(string_input)} instead")
    if '@' in string_input:
        tmp : list[str] = string_input.split('@')
        if len(tmp) == 2:
            return tmp[1]
    return None

def get_imap_config_from_url(imap_str: str) -> dict:
    """
    Get a string of an imapr server url and convert it to a dict
    matching the csogo configuration:
    {
        "server": my.server.com;
        "port": 993,
        "encrytpion": SSL/TLS
    }
    Only put info from the string (if there is no port, the dict won't have the port key)

    :param imap_str: _description_
    :type imap_str: str
    :return: _description_
    :rtype: dict
    """
    ret :dict = {}
    imap_url = URL(imap_str)
    query    = imap_url.query
    tls      = query.get("tls", None)

    # Not supported by the imaplib in python
    # Was a mode to tell to check if the tls certificate is trusted and reject otherwise.
    # tlsVerifyMode = query.get("tlsVerifyMode", None)

    encryption: str|None = None
    default_port = 143

    if (scheme := imap_url.scheme) and scheme.lower() == "imaps":
        # Implicit tls
        encryption = "SSL/TLS"
        default_port = 993
    if tls and tls.lower() == "yes":
        # explicit tls (starttls)
        encryption = "Starttls"
        default_port = 143

    if (host := imap_url.host_subcomponent):
        ret["server"] = host
    ret["port"] = port if (port := imap_url.explicit_port) else default_port
    if encryption:
        ret["encryption"] = encryption

    return ret

def quote(input_str:str) -> str:
    """
    Quote a string with "

    :param input: string to quote
    :type input: str
    :return: the string quoted
    :rtype: str
    """
    # Check if the string is already wrapped in double quotes
    if input_str.startswith('"') and input_str.endswith('"'):
        return input_str
    # Escape backslashes and double quotes
    escaped = input_str.replace('\\', '\\\\').replace('"', '\\"')
    return '"' + escaped + '"'

def imap_join_folders(delimiter: str, first_path: str, second_path: str) -> str:
    if first_path[-1] == '"':
        # first paht like this '"my name"'
        first_path = first_path[1:-1]
    if second_path[0] == '"':
        # second path like this '"my name"'
        second_path = second_path[1:-1]
    return quote(f"{first_path}{delimiter}{second_path}")
     