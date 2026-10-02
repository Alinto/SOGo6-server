import app.utils.errors as err


def tets_errors():
    """
    Just a test to trigger the import and see if two errors has the same number
    """
    e = err.E("-1","test_error")
    assert e.c == "-1"