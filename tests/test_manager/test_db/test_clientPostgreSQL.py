from app.manager.db.ClientPostgreSQL import condition_to_query
from app.utils.db.Condition import Condition, EqualCondition, NotEqualCondition, AndCondition, OrCondition


def test_condition_to_query():
    a = EqualCondition("test", 1)
    b = condition_to_query(a, add_where=True)
    assert b.as_string() == "WHERE \"test\" = 1"

    a = EqualCondition("test", "test")
    b = condition_to_query(a, add_where=True)
    assert b.as_string() == "WHERE \"test\" = 'test'"



if __name__ == "__main__":
    test_condition_to_query() 