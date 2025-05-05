# -*- coding: utf-8 -*-


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
