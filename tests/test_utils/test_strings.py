import pytest

from app.utils.strings import get_domain_from_mail

def test_get_domain_from_mail():
    with pytest.raises(ValueError):
        get_domain_from_mail(1)
    assert get_domain_from_mail("aa") is None
    assert get_domain_from_mail("aa@bb.com") == "bb.com"
    assert get_domain_from_mail("aa@bb@cc") is None
