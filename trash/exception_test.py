class A(Exception):
    """
    Nothing in particular
    """

def fail():
    raise ValueError("test")


def exec_fail():
    try:
        fail()
    except ValueError as e:
        raise A() from e

try:
    exec_fail()
except A as e:
    print("catch A")
except ValueError as e:
    print("catch ValueError")
