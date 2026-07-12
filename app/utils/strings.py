import re
import unicodedata

from yarl import URL

# Unicode names of atomic latin letters carry their ASCII base: "LATIN SMALL LETTER O WITH
# STROKE" -> "o", "LATIN SMALL LIGATURE OE" -> "oe". Bases longer than 2 letters (THORN, ETH)
# have no ASCII equivalent and are kept as-is.
_REX_LATIN_BASE = re.compile(r"^LATIN (?:SMALL|CAPITAL) (?:LETTER|LIGATURE) ([A-Z]{1,2})(?: WITH [A-Z ]+)?$")


def _fold_latin_letter(char: str) -> str:
    """Reduce an atomic latin letter to its ASCII base; other characters are returned unchanged."""
    matched = _REX_LATIN_BASE.match(unicodedata.name(char, ""))
    if not matched:
        return char
    base: str = matched.group(1)
    return base if " CAPITAL " in unicodedata.name(char) else base.lower()


def strip_accents(text: str) -> str:
    """Lowercase and remove accents so two spellings of the same word compare equal.

    Strips combining diacritics (NFKD), casefolds (also turns eszett into "ss"), then folds the
    remaining atomic latin letters (o-stroke, l-stroke, ae/oe ligatures...) to their ASCII base
    through their Unicode name. Non-latin scripts (cyrillic, greek, CJK...) are left untouched.
    """
    decomposed: str = unicodedata.normalize("NFKD", text)
    no_accents: str = "".join(c for c in decomposed if not unicodedata.combining(c))
    folded: str = no_accents.casefold()
    return "".join(_fold_latin_letter(c) if ord(c) > 127 else c for c in folded)

class SecretString(str):
    """
    A class that override the __repr__ to censor secrets/passwords
    """

    def set_censored(self, censored_value:str="SecretString('***')") -> None:
        """
        :param censored_value: Value to show in the log instead of the true value
        :type censored_value: str
        """
        self._censored = censored_value # pylint: disable=attribute-defined-outside-init

    def __repr__(self) -> str:
        if hasattr(self, "_censored"):
            return self._censored
        return "SecretString('***')"

def get_domain_from_mail(string_input: str) -> str|None:
    """
    Get a mail string and return the domain if there is one.
    Domain in mail pov so domain for user@domain
    """
    if '@' in string_input:
        tmp : list[str] = string_input.split('@')
        if len(tmp) == 2:
            return tmp[1]
    return None

def get_domain_from_contact(string_input: str) -> str|None:
    """
    A contact is either directly a mail "foo@bar.nu" or a full name
    "Foo Bar <foo@bar.nu>"
    """
    mail = string_input.strip()
    if "<" in mail:
        try:
            idx = mail.index("<")
            mail = mail[idx+1:-1]  # extracting mail between < and >
            if '<' in mail or '>' in mail:
                raise ValueError(f"Contact is not conformed to 'CN <mail>': '{string_input}'")
        except (ValueError, IndexError) as e:
            raise ValueError(f"Contact is not conformed to 'CN <mail>': '{string_input}'") from e
    return get_domain_from_mail(mail)

def parse_url_str(url_str:str) -> dict:
    """
    Return a dict form an url string

    {
        'protocol': str, http, https, mysql...
        'hostname': str, hostname or ip
        'port': int, port
        'username': str|None, username of None value
        'password': str|None, password of None value
        'params': dict[str, str|list[str]], key = value
    }

    :param url_str: string of the url
    :type url_str: str
    :return: response dict
    :rtype: dict
    """
    parsed = URL(url_str)

    # Preserve all query values as lists
    params: dict = {}
    for k, v in parsed.query.items():
        if k in params:
            if isinstance(params[k], list):
                params[k].append(v)
            else:
                params[k] = [params[k], v]
        else:
            params[k] = v

    return {
        'protocol': parsed.scheme,
        'hostname': parsed.host if parsed.host else "", # pylint: disable=[using-constant-test]
        'port': parsed.port if parsed.port else 80, # pylint: disable=[using-constant-test]
        'username': parsed.user if parsed.user else "", # pylint: disable=[using-constant-test]
        'password': parsed.password if parsed.password else "", # pylint: disable=[using-constant-test]
        'params': params
    }


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
    """
    Join two imap folder_path together accordinf to the delimiter
    """
    if first_path[-1] == '"':
        # first paht like this '"my name"'
        first_path = first_path[1:-1]
    if second_path[0] == '"':
        # second path like this '"my name"'
        second_path = second_path[1:-1]
    return quote(f"{first_path}{delimiter}{second_path}")

def string_to_sort_score(s: str) -> int:
    """Convert a string to an integer score for sorting purposes."""
    score = 0
    for char in s:
        score = (score << 8) | ord(char)  # Décalage de 8 bits pour chaque caractère
    return score
