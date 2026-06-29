import re
from datetime import datetime
from enum import IntEnum
from app.utils.logger.logger import logger
from app.utils.exceptions import BugException, AggravatedException
from app.utils import errors as err




class Order(IntEnum):
    """
    Enum to tell how to sort database.
    ASC: ascendant
    DESC: descendant
    """
    ASC = 0
    DESC = 1

def order_str_to_order_enum(order:str)->Order:
    """
    Convert a string that indicates the sorting's order to an Order object

    :param order: _description_
    :type order: str
    :raises BugException: _description_
    :return: _description_
    :rtype: Order
    """
    order_lower = order.lower()
    if order_lower in {"ascendant", "asc", "up"}:
        return Order.ASC
    if order_lower in {"descendant", "desc", "down"}:
        return Order.DESC
    raise BugException(f"Trying to use an order not defined or expected {order}", err.ERROR_BUG_UNKNOWN_ORDER)

class Condition:
    """
    This class helps db manager to form the condition for their query
    """

    def __init__(self) -> None:
        pass

class CompareCondition(Condition):
    """
    This condition is to compare  a parameter to a value
    """

    _op = "??"

    def __init__(self, param_name: str, param_value: str | int | datetime):
        super().__init__()
        self.param_name = param_name
        self.param_value = param_value

    def __repr__(self) -> str:
        value = self.param_value
        if isinstance(self.param_value, str):
            value = f"'{value}'"
        return f"{self.__class__.__name__}({self.param_name} {self._op} {value})"

class LogicCondition(Condition):
    """
    This condition is to put logic between two conditions.
    """

    _op = "??"

    def __init__(self, *conditions: Condition):
        super().__init__()
        if len(conditions) < 2:
            raise ValueError("At least two condition is required for AndCondition.")
        self.conditions = list(conditions)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({f" {self._op} ".join(x.__repr__() for x in self.conditions)})"

class TrueCondition(Condition):
    """
    Condition that is always true (1 == 1).

    Use when selecting all the tables without conditions
    """

class EqualCondition(CompareCondition):
    """
    This condition is to check if a named paramater equal a value
    """

    _op = "=="

class NotEqualCondition(CompareCondition):
    """
    This condition is to check if a named paramater does not equal a value
    """
    _op = "!="

class AndCondition(LogicCondition):
    """
    This condition apply the logical operator "AND" between two conditions
    """
    _op = "AND"

class OrCondition(LogicCondition):
    """
    This condition apply the logical operator "OR" between two conditions
    """
    _op = "OR"

class LessOrEqualCondition(CompareCondition):
    """Check if a named parameter is less than or equal to a value."""
    _op = "<="

class GreaterOrEqualCondition(CompareCondition):
    """Check if a named parameter is greater than or equal to a value."""
    _op = ">="


class IsNullCondition(Condition):
    """Check if a named parameter is NULL."""
    def __init__(self, param_name: str):
        super().__init__()
        self.param_name = param_name

class IsNotNullCondition(Condition):
    """Check if a named parameter is NOT NULL."""
    def __init__(self, param_name: str):
        super().__init__()
        self.param_name = param_name

class LikeCondition(Condition):
    """Case-insensitive substring match on a named parameter.

    The pattern must include wildcard characters explicitly (e.g. '%keyword%').
    PostgreSQL maps this to ILIKE; MySQL LIKE is already case-insensitive with utf8mb4.
    """
    def __init__(self, param_name: str, pattern: str):
        super().__init__()
        self.param_name = param_name
        self.pattern = pattern

class FullTextCondition(Condition):
    """Full-text match on a full-text column, backed by a database full-text index.

    Each word of the query is matched as a prefix (so "joe" matches "joel"), rendered per dialect
    against the same column: MATCH(param_name) AGAINST a boolean-mode prefix query (MariaDB, TEXT
    column), param_name @@ a prefix to_tsquery (PostgreSQL, tsvector column). Word/token based, not
    a literal substring match, and it requires a full-text index (see Index(fulltext=True)).
    """
    def __init__(self, param_name: str, query: str):
        super().__init__()
        self.param_name = param_name
        self.query = query

    def terms(self) -> list[str]:
        """Split the query into individual words, each matched as a prefix by the database."""
        return re.findall(r"\w+", self.query)


class JoinClause:
    """Describes an INNER JOIN between two tables.

    Used with select_from_several_table to build multi-table queries.
    Note : This can be updated later to add left or right join.
    """
    def __init__(self, table: str, left_col: str, right_col: str):
        """
        :param table: The table to join.
        :param left_col: Qualified column on the left side (e.g. "reminders.event_key").
        :param right_col: Qualified column on the right side (e.g. "events.key").
        """
        self.table = table
        self.left_col = left_col
        self.right_col = right_col

def string_filter_to_conditions(filter_str:str) -> Condition:
    """
    In configuration, there are filter parameters that expect a string with basic logic

    This method parse this string to render Condition instance that will then be passed to manager (db, ldap,..)

    Syntax rules, mind the space:
    * (...): parenthesis defined a group, a group can habe subgroup and so on
    * ' AND ': defined the and condition
    * ' OR ': defined the or condition
    * ' == ': equal condition
    * ' != ': not equal condition
    * ' <= ': lesser or equal condition
    * ' >= ': greater or equal condition

    :param filter_str: _description_
    :type filter_str: str
    :return: _description_
    :rtype: Condition
    """
    _AND  = 'AND'
    _OR   = 'OR'
    _EQ   = '=='
    _EQNO = '!='
    _LE   = '<='
    _GE   = '>='

    _s = {_LE, _GE, _EQ, _EQNO} #simple condition (one param, one value)
    _c = {_AND, _OR} #complex condiion (can have one or more conditions)

    def _parse_simple_condition(simple_cond:str) -> Condition:
        """
        Case simple_cond:
        * "param == 'value'"  Equal with a string
        * "param != 'value'"  Not Equal with a string
        * "param == value"    Equal with an int
        * "param != value"    Not Equal with an int
        * "param >= value"    Greater or Equal than an int
        * "param <= value"    Lesser or Equald than an int

        :return: The proper condition instance
        :rtype: Condition
        """
        explosed = simple_cond.split()
        if len(explosed) < 3:
            raise AggravatedException(f"Wrong string given, split should produce at least 3 items, not {len(explosed)} for {simple_cond}")
        param = explosed[0]
        op = explosed[1]
        value = simple_cond[len(param)+1+len(op)+1:]
        true_value: str|int
        if value.startswith(('"', "'")) and value.endswith(('"', "'")):
            #value is a string
            true_value = value[1:-1]
        else:
            try:
                #value is an int
                true_value = int(value)
            except ValueError as e:
                raise AggravatedException(f"Filter is not conformed: value {value} not a string or an int") from e
        cond: Condition
        if op == _EQ:
            cond = EqualCondition(param, true_value)
        elif op == _EQNO:
            cond = NotEqualCondition(param, true_value)
        elif op == _GE:
            if not isinstance(true_value, int):
                raise AggravatedException(f"Filter is not conformed: try to use >= with a string instead of a number for {simple_cond}")
            cond = GreaterOrEqualCondition(param, true_value)
        elif op == _LE:
            if not isinstance(true_value, int):
                raise AggravatedException(f"Filter is not conformed: try to use <= with a string instead of a number at {simple_cond}")
            cond = LessOrEqualCondition(param, true_value)
        else:
            raise AggravatedException(f"Filter is not conformed: unknown operator for {op} in {simple_cond}")
        return cond


    def _parse_group(group_str:str) -> Condition:
        i = 0
        all_conds: list[Condition] = []
        current_word = ""
        n = len(group_str)
        current_op = ""
        previous_cond: list[Condition]|None = None
        previous_is_subgroup = False
        while i < n:
            print(f"i={i}/n={n}")
            print(f"current={current_word}")
            print(f"current_op={current_op}")
            print(f"current char={group_str[i]}")
            print(f"all_cond={all_conds}")
            print(f"previous_cond={previous_cond}")
            if group_str[i] == '(':
                #Find another subgroup
                subgroup = ""
                count_opener = 1
                while i<n-1:
                    i += 1
                    subgroup += group_str[i]
                    #A subgroup can contains another subgroupes, make sure to count the '(' and ')'
                    if group_str[i] == '(':
                        count_opener += 1
                    if group_str[i] == ')':
                        count_opener -= 1
                        if count_opener == 0:
                            break
                if subgroup.endswith(")"):
                    print(f"FIND a subgroup: {subgroup[:-1]}")
                    all_conds.append(_parse_group(subgroup[:-1]))
                    print(f"RESULT a subgroup: {all_conds} and i={i}")
                    print(f"RESULT i={i}/n={n}")
                    print(f"RESULT current={current_word}")
                    print(f"RESULT current_op={current_op}")
                    print(f"RESULT current char={group_str[i]}")
                    print(f"RESULT all_cond={all_conds}")
                    print(f"RESULT previous_cond={previous_cond}")
                    previous_is_subgroup = True
                    i += 1 #add the last ')'
                else:
                    raise AggravatedException(f"Filter is not conformed: an opening ( is not closed in \"{group_str}\"")
            elif group_str[i] == ' ':
                #Expect a operator
                if i+4 > n:
                    raise AggravatedException(f"Filter is not conformed: A space at position {i} does not match a operator")

                #Get operator
                if group_str[i+3] == ' ':
                    # operator is 4 char length
                    op = group_str[i+1:i+3]
                elif group_str[i+4] == ' ':
                    # operator is 5 char length
                    op = group_str[i+1:i+4]
                else:
                    raise AggravatedException(f"Filter is not conformed: A space at position {i} does not match a operator")


                if op in _s:
                    # First part of a simple condition, continue
                    current_word += f" {op} "
                    i += len(op) + 2
                    continue
                elif op in _c:
                    # We already have one or more conditions, fecth the next one
                    if previous_is_subgroup or len(all_conds) == 0:
                        #first time meeting a cond, add it
                        if not previous_is_subgroup:
                            all_conds.append(_parse_simple_condition(current_word))
                        current_op = op
                        previous_is_subgroup = False
                    else:
                        if current_op == op:
                            #Case like 'cond1 AND cond2 AND cond3'
                            #We simply add the new condition
                            all_conds.append(_parse_simple_condition(current_word))
                            current_op = op
                        else:
                            if op == _OR and current_op == _AND:
                                #cond1 AND cond2 AND cond3 OR cond4
                                #AND has precedence over OR
                                current_op = _OR
                                all_conds.append(_parse_simple_condition(current_word))
                                if previous_cond:
                                    all_conds= [*previous_cond, AndCondition(*all_conds)]
                                else:
                                    all_conds = [AndCondition(*all_conds)]
                            elif op == _AND and current_op == _OR:
                                #cond1 OR cond2 OR cond3 AND cond4
                                #AND has precedence over OR
                                current_op = _AND
                                previous_cond = all_conds
                                all_conds = [_parse_simple_condition(current_word)]
                            else:
                                raise AggravatedException(f"Wrong operator combination '{op}' and current '{current_op}'")
                    current_word = ""
                    i += len(op)+2 #len(op) +2 spaces 
                else:
                    raise AggravatedException(f"Unknown operator '{op}'")

            else:
                current_word += group_str[i]
                i += 1
        print(f"last cond = currentword= '{current_word}'")
        cond: Condition
        if previous_is_subgroup and not current_word:
            #The last condition as a subgroup nothing to add
            if current_op == _AND:
                cond = AndCondition(*all_conds)
                if previous_cond:
                    cond = OrCondition(*previous_cond, cond)
                return cond
            elif current_op == _OR:
                cond = OrCondition(*all_conds)
                return cond
            else:
                raise AggravatedException(f"Unknown operator '{op}' for final")
        else:
            last_cond = _parse_simple_condition(current_word)
            if current_op == _AND:
                cond = AndCondition(*all_conds, last_cond)
                if previous_cond:
                    cond = OrCondition(*previous_cond, cond)
                return cond
            elif current_op == _OR:
                cond = OrCondition(*all_conds, last_cond)
                return cond
            else:
                raise AggravatedException(f"Unknown operator '{op}' for final")

    if filter_str.startswith("("):
        if filter_str.endswith(")"):
            #Is a group "(...)"
            return _parse_group(filter_str[1:-1])
        else:
            raise AggravatedException("Missing a ')' at the end")
    else:
        #Is a simple condition like "active == 1"
        return _parse_simple_condition(filter_str)
