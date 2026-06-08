from datetime import datetime
from enum import IntEnum
from app.utils.logger.logger import logger
from app.utils.exceptions import BugException
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

class TrueCondition(Condition):
    """
    Condition that is always true (1 == 1).

    Use when selecting all the tables without conditions
    """

class EqualCondition(Condition):
    """
    This condition is to check if a named paramater equal a value
    """
    def __init__(self, param_name: str, param_value: str | int | datetime):
        super().__init__()
        self.param_name = param_name
        self.param_value = param_value

class NotEqualCondition(Condition):
    """
    This condition is to check if a named paramater does not equal a value
    """
    def __init__(self, param_name: str, param_value: str | int | datetime):
        super().__init__()
        self.param_name = param_name
        self.param_value = param_value

class AndCondition(Condition):
    """
    This condition apply the logical operator "AND" between two conditions
    """
    def __init__(self, condition1: Condition, condition2: Condition):
        super().__init__()
        self.condition1 = condition1
        self.condition2 = condition2

class OrCondition(Condition):
    """
    This condition apply the logical operator "OR" between two conditions
    """
    def __init__(self, condition1: Condition, condition2: Condition):
        super().__init__()
        self.condition1 = condition1
        self.condition2 = condition2

class LessOrEqualCondition(Condition):
    """Check if a named parameter is less than or equal to a value."""
    def __init__(self, param_name: str, param_value: str | int | datetime):
        super().__init__()
        self.param_name = param_name
        self.param_value = param_value

class GreaterOrEqualCondition(Condition):
    """Check if a named parameter is greater than or equal to a value."""
    def __init__(self, param_name: str, param_value: str | int | datetime):
        super().__init__()
        self.param_name = param_name
        self.param_value = param_value

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
