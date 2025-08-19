from app.utils.logger.logger import logger

class Condition:
    """
    This class helps db manager to form the condition for their query
    """

    def __init__(self) -> None:
        pass

class EqualCondition(Condition):
    """
    This condition is to check if a named paramater equal a value
    """
    def __init__(self, param_name: str, param_value: str | int):
        super().__init__()
        self.param_name = param_name
        self.param_value = param_value

class NotEqualCondition(Condition):
    """
    This condition is to check if a named paramater does not equal a value
    """
    def __init__(self, param_name: str, param_value: str | int):
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
