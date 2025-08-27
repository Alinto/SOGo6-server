from app.manager.db.ClientPostgreSQL import condition_to_query
from app.utils.db.Condition import EqualCondition, NotEqualCondition, AndCondition, OrCondition


def test_condition_to_query():
    """
    Test the convertion between Condition object and condition query
    """
    a1 = EqualCondition("test", 1)
    b1 = condition_to_query(a1, add_where=True)
    assert b1.as_string() == "WHERE \"test\" = 1"

    a2 = EqualCondition("test2", "test2")
    b2 = condition_to_query(a2, add_where=True)
    assert b2.as_string() == "WHERE \"test2\" = 'test2'"

    a3 = NotEqualCondition("test3", 3)
    b3 = condition_to_query(a3, add_where=True)
    assert b3.as_string() == "WHERE \"test3\" != 3"

    a4 = NotEqualCondition("test4", "test4")
    b4 = condition_to_query(a4, add_where=True)
    assert b4.as_string() == "WHERE \"test4\" != 'test4'"

    a5 = AndCondition(a1, a2)
    b5 = condition_to_query(a5, add_where=True)
    assert b5.as_string() == "WHERE (\"test\" = 1 AND \"test2\" = 'test2')"

    a6 = OrCondition(a3, a4)
    b6 = condition_to_query(a6, add_where=True)
    assert b6.as_string() == "WHERE (\"test3\" != 3 OR \"test4\" != 'test4')"

    a7 = AndCondition(a5, a6)
    b7 = condition_to_query(a7, add_where=True)
    assert b7.as_string() == "WHERE ((\"test\" = 1 AND \"test2\" = 'test2') AND (\"test3\" != 3 OR \"test4\" != 'test4'))"





if __name__ == "__main__":
    test_condition_to_query()
