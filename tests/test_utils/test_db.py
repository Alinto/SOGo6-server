
import pytest
import app.utils.db.Condition as dbc
from app.utils.exceptions import BugException, AggravatedException



def test_string_filter_to_conditions_correct():
    """
    _summary_
    """

    list_correct = [
        "param1 == 'value1'",  #Equal with a string
        "param2 != 'value2'",  #Not Equal with a string
        "param3 == \"value3\"",  #Equal with a string
        "param4 != \"value4\"",  #Not Equal with a string
        "param5 == 1",    #Equal with an int
        "param6 != 2",    #Not Equal with an int
        "param7 >= 3",    #Greater or Equal than an int
        "param8 <= 4",    #Lesser or Equald than an int
        "param9 == 'string with spaces    !'",    #Lesser or Equald than an int
    ]
    list_correct_ack = [
        "EqualCondition(param1 == 'value1')",
        "NotEqualCondition(param2 != 'value2')",
        "EqualCondition(param3 == 'value3')",
        "NotEqualCondition(param4 != 'value4')",
        "EqualCondition(param5 == 1)",
        "NotEqualCondition(param6 != 2)",
        "GreaterOrEqualCondition(param7 >= 3)",
        "LessOrEqualCondition(param8 <= 4)",
        "EqualCondition(param9 == 'string with spaces    !')",
    ]

    for idx, correct in enumerate(list_correct):
        assert f"{dbc.string_filter_to_conditions(correct)}" == list_correct_ack[idx], f"Got \"{dbc.string_filter_to_conditions(correct)}\", expected \"{list_correct_ack[idx]}\""

def test_string_filter_to_conditions_incorrect():
    """
    _summary_
    """

    list_incorrect = [
        "param1=='value1'",  #No space
        "param2== 'value2'",  #No space2
        "param2 =='value2'",  #No space3
        "par am2 == 'value2'",  #wrong space
        "param2 == 'value2' bla",  #wrong format
        "param3 == \"value3",  #wrong format2
        "param4 >> \"value4\"",  #wrong operator
        "param5 == value",    #missing quote for string
    ]

    for incorrect in list_incorrect:
        with pytest.raises(AggravatedException):
            dbc.string_filter_to_conditions(incorrect)

def test_complex_filter_correct():
    """
    _summary_
    """

    list_correct = [
        "(param1 == 'value1' AND param2 == 'value2')",  #AND
        "(param1 == 'value1' OR param2 == 'value2')",  #OR
        "(p1 == 'v1' AND p2 == 'v2' AND p3 == 'v3' AND p4 == 'v4')",  #AND several
        "(p1 == 'v1' OR p2 == 'v2' OR p3 == 'v3' OR p4 == 'v4')",  #OR several
        "(p1 == 'v1' OR p2 == 'v2' AND p3 == 'v3')",  #OR then AND
        "(p1 == 'v1' AND p2 == 'v2' OR p3 == 'v3')",  #AND then OR
        "(p1 == 'v1' AND p2 == 'v2' OR p3 == 'v3' OR p4 == 'v4' AND p5 == 'v5' OR p6 == 'v6' AND p7 == 'v7')",  #AND OR mayhem!!
    ]
    list_correct_ack = [
        "AndCondition(EqualCondition(param1 == 'value1') AND EqualCondition(param2 == 'value2'))",
        "OrCondition(EqualCondition(param1 == 'value1') OR EqualCondition(param2 == 'value2'))",
        "AndCondition(EqualCondition(p1 == 'v1') AND EqualCondition(p2 == 'v2') AND EqualCondition(p3 == 'v3') AND EqualCondition(p4 == 'v4'))",
        "OrCondition(EqualCondition(p1 == 'v1') OR EqualCondition(p2 == 'v2') OR EqualCondition(p3 == 'v3') OR EqualCondition(p4 == 'v4'))",
        "OrCondition(EqualCondition(p1 == 'v1') OR AndCondition(EqualCondition(p2 == 'v2') AND EqualCondition(p3 == 'v3')))",
        "OrCondition(AndCondition(EqualCondition(p1 == 'v1') AND EqualCondition(p2 == 'v2')) OR EqualCondition(p3 == 'v3'))",
        "OrCondition(AndCondition(EqualCondition(p1 == 'v1') AND EqualCondition(p2 == 'v2')) OR EqualCondition(p3 == 'v3') OR AndCondition(EqualCondition(p4 == 'v4') " +\
        "AND EqualCondition(p5 == 'v5')) OR AndCondition(EqualCondition(p6 == 'v6') AND EqualCondition(p7 == 'v7')))",
    ]

    for idx, correct in enumerate(list_correct):
        assert f"{dbc.string_filter_to_conditions(correct)}" == list_correct_ack[idx], f"Got \"{dbc.string_filter_to_conditions(correct)}\", expected \"{list_correct_ack[idx]}\""

def test_subgroup_filter_correct():
    """
    _summary_
    """

    list_correct = [
        "((p1 == 'v1' OR p2 == 'v2') AND p3 == 'v3')", #sub OR first place
        "(p1 == 'v1' AND (p2 == 'v2' OR p3 == 'v3'))",  #sub OR last place
        "((p1 == 'v1' AND p2 == 'v2') OR p3 == 'v3')",  #sub AND first place
        "(p1 == 'v1' OR (p2 == 'v2' AND p3 == 'v3'))",  #sub AND last place
        "(p1 == 'v1' AND (p2 == 'v2' OR p3 == 'v3') AND 'p4 == 'v4')",  #sub in middle
        "(p1 == 'v1' AND (p2 == 'v2' OR p3 == 'v3') AND (p4 == 'v4' OR p5 == 'v5'))",  #two subs in middle
        "(p1 == 'v1' AND (p2 == 'v2' OR p3 == 'v3' AND (p4 == 'v4' OR p5 == 'v5')))",  #sub in sub last
        "(((p1 == 'v1' AND p2 == 'v2') OR p3 == 'v3') AND (p4 == 'v4' OR p5 == 'v5'))",  #sub in sub firdt
    ]
    list_correct_ack = [
        "AndCondition(OrCondition(EqualCondition(p1 == 'v1') OR EqualCondition(p2 == 'v2')) AND EqualCondition(p3 == 'v3'))",
        "AndCondition(EqualCondition(p1 == 'v1') AND OrCondition(EqualCondition(p2 == 'v2') OR EqualCondition(p3 == 'v3')))",
        "OrCondition(AndCondition(EqualCondition(p1 == 'v1') AND EqualCondition(p2 == 'v2')) OR EqualCondition(p3 == 'v3'))",
        "OrCondition(EqualCondition(p1 == 'v1') OR AndCondition(EqualCondition(p2 == 'v2') AND EqualCondition(p3 == 'v3')))",
        "AndCondition(EqualCondition(p1 == 'v1') AND OrCondition(EqualCondition(p2 == 'v2') OR EqualCondition(p3 == 'v3')) AND EqualCondition('p4 == 'v4'))",
        "AndCondition(EqualCondition(p1 == 'v1') AND OrCondition(EqualCondition(p2 == 'v2') OR EqualCondition(p3 == 'v3')) AND OrCondition(EqualCondition(p4 == 'v4') OR EqualCondition(p5 == 'v5')))",
        "AndCondition(EqualCondition(p1 == 'v1') AND OrCondition(EqualCondition(p2 == 'v2') OR AndCondition(EqualCondition(p3 == 'v3') AND OrCondition(EqualCondition(p4 == 'v4') OR EqualCondition(p5 == 'v5')))))",
        "AndCondition(OrCondition(AndCondition(EqualCondition(p1 == 'v1') AND EqualCondition(p2 == 'v2')) OR EqualCondition(p3 == 'v3')) AND OrCondition(EqualCondition(p4 == 'v4') OR EqualCondition(p5 == 'v5')))"
    ]

    for idx, correct in enumerate(list_correct):
        # print(f"{dbc.string_filter_to_conditions(correct)}")
        assert f"{dbc.string_filter_to_conditions(correct)}" == list_correct_ack[idx], f"Got \"{dbc.string_filter_to_conditions(correct)}\", expected \"{list_correct_ack[idx]}\""



if __name__ == "__main__":
    # test_string_filter_to_conditions_correct()
    # test_string_filter_to_conditions_incorrect()
    # test_complex_filter_correct()
    test_subgroup_filter_correct()
