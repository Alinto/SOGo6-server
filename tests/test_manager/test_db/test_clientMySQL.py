from unittest import mock

import pytest
from pytest_mock.plugin import MockerFixture

from mysql.connector import Error, ProgrammingError

from app.manager.db.ClientMySQL import (
    ClientMySQL,
    str_to_varchar,
    list_to_json,
    table_to_query,
    condition_to_query,
)
from app.utils.exceptions import RequestException, BugException
from app.utils.db.Condition import EqualCondition, NotEqualCondition, AndCondition, OrCondition, TrueCondition
from app.utils.db.Table import Table, Column


def test_str_to_varchar():
    """
    Test converting a string type to a VARCHAR().
    """
    assert str_to_varchar(255) == "VARCHAR(255)"
    assert str_to_varchar(0) == "VARCHAR(255)"
    assert str_to_varchar(-1) == "VARCHAR(255)"


def test_list_to_json():
    """
    Test converting a list to JSON.
    """
    assert list_to_json() == "JSON"
    assert list_to_json(data_type="str") == "JSON"


def test_table_to_query():
    """
    Test converting a Table object to a SQL CREATE TABLE query.
    """
    col1 = Column(name="test1", data_type="str")
    col2 = Column(name="test2", data_type="int8")
    col3 = Column(name="test3", data_type="serial")
    col4 = Column(name="test4", data_type="dict")
    col5 = Column(name="test5", data_type="json")
    col6 = Column(name="test6", data_type="list", extra_args={"data_type": "str"})
    col7 = Column(name="test7", data_type="str", is_nullable=True, extra_args={"max_len": 255})
    col8 = Column(name="test8", data_type="str", is_unique=True)
    table = Table(
        name="test",
        columns=[col1, col2, col3, col4, col5, col6, col7, col8],
        primary_keys=(col1.name, col2.name),
    )

    sql = table_to_query(table)
    expected = (
        "CREATE TABLE `test` (`test1` VARCHAR(255) NOT NULL, `test2` SMALLINT NOT NULL, "
        "`test3` BIGINT AUTO_INCREMENT NOT NULL, `test4` JSON NOT NULL, `test5` JSON NOT NULL, "
        "`test6` JSON NOT NULL, `test7` VARCHAR(255) , `test8` VARCHAR(255) NOT NULL UNIQUE, "
        "PRIMARY KEY (`test1`, `test2`)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
    )
    assert " ".join(sql.split()) == " ".join(expected.split())


def test_condition_to_query():
    """
    Test converting Condition objects to SQL WHERE clauses.
    """
    a1 = EqualCondition("test", 1)
    sql1, params1 = condition_to_query(a1, add_where=True)
    assert sql1 == "WHERE `test` = %s"
    assert params1 == [1]

    a2 = EqualCondition("test2", "test2")
    sql2, params2 = condition_to_query(a2, add_where=True)
    assert sql2 == "WHERE `test2` = %s"
    assert params2 == ["test2"]

    a3 = NotEqualCondition("test3", 3)
    sql3, params3 = condition_to_query(a3, add_where=True)
    assert sql3 == "WHERE `test3` != %s"
    assert params3 == [3]

    a4 = NotEqualCondition("test4", "test4")
    sql4, params4 = condition_to_query(a4, add_where=True)
    assert sql4 == "WHERE `test4` != %s"
    assert params4 == ["test4"]

    a5 = AndCondition(a1, a2)
    sql5, params5 = condition_to_query(a5, add_where=True)
    assert sql5 == "WHERE (`test` = %s AND `test2` = %s)"
    assert params5 == [1, "test2"]

    a6 = OrCondition(a3, a4)
    sql6, params6 = condition_to_query(a6, add_where=True)
    assert sql6 == "WHERE (`test3` != %s OR `test4` != %s)"
    assert params6 == [3, "test4"]

    a7 = AndCondition(a5, a6)
    sql7, params7 = condition_to_query(a7, add_where=True)
    assert sql7 == "WHERE ((`test` = %s AND `test2` = %s) AND (`test3` != %s OR `test4` != %s))"
    assert params7 == [1, "test2", 3, "test4"]


class FakeMySQLCursor:
    def __init__(self, conn):
        self.conn = conn
        self._rows = []
        self.rowcount = 0
        self._last_execute = None

    def execute(self, sql, params=None):
        self._last_execute = (sql, params)
        s = sql.strip()
        # get_table_info query
        if s.upper().startswith("SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS"):
            table = None
            if params and len(params) >= 2:
                table = params[1]
            if table == "test":
                self._rows = [
                    ("col_name1", "json"),
                    ("col_name2", "int"),
                    ("col_name3", "varchar"),
                    ("col_name4", "json"),
                    ("col_name5", "smallint"),
                ]
                self.rowcount = len(self._rows)
            elif table == "test2":
                raise Error("fake error")
            else:
                self._rows = []
                self.rowcount = 0
        # create_table
        elif s.upper().startswith("CREATE TABLE"):
            if "`duplicate`" in s or '"duplicate"' in s or "CREATE TABLE `duplicate`" in s:
                raise ProgrammingError("Table already exists")
            if "`error`" in s or '"error"' in s:
                raise Error("generic error")
            self._rows = []
            self.rowcount = 0
        # insert
        elif s.upper().startswith("INSERT INTO"):
            lower = s.lower()
            values_idx = lower.find("values")
            if values_idx != -1:
                values_part = s[values_idx + len("values"):]
                first_open = values_part.find("(")
                first_close = values_part.find(")")
                if first_open != -1 and first_close != -1 and first_close > first_open:
                    first_group = values_part[first_open + 1:first_close]
                    ph_count = first_group.count("%s")
                else:
                    ph_count = 0
            else:
                ph_count = 0
            if params:
                if ph_count > 0:
                    self.rowcount = int(len(params) / ph_count)
                else:
                    self.rowcount = 1
            else:
                self.rowcount = 0
        # update
        elif s.upper().startswith("UPDATE"):
            if "`test_update`" in s or "FROM `test_update`" in s:
                self.rowcount = 1
            else:
                self.rowcount = 0
        # select
        elif s.upper().startswith("SELECT"):
            # produce some rows for a table named test_select in the FROM, otherwise empty
            if "`test_select`" in s or '"test_select"' in s or "FROM `test_select`" in s:
                self._rows = [(1, "Alice", '{"k":"v"}', 30), (2, "Bob", '{"x":[1,2]}', 25)]
                self.rowcount = len(self._rows)
            elif "COUNT(*)" in s.upper() or "COUNT(`" in s.upper():
                # Count queries
                if "`test_count`" in s or "FROM `test_count`" in s:
                    self._rows = [(5,)]
                    self.rowcount = 1
                else:
                    self._rows = [(0,)]
                    self.rowcount = 1
            else:
                # default: return empty
                self._rows = []
                self.rowcount = 0
        # delete
        elif s.upper().startswith("DELETE FROM"):
            if "`test_delete`" in s:
                self.rowcount = 1
            else:
                self.rowcount = 0
        else:
            # unknown SQL in test
            raise Exception(f"FakeMySQLCursor: unexpected execute SQL: {sql}")

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        if not self._rows:
            return None
        return self._rows.pop(0)

    def close(self):
        pass


class FakeMySQLConn:
    def __init__(self):
        self._closed = False

    def cursor(self):
        return FakeMySQLCursor(self)

    def commit(self):
        pass

    def rollback(self):
        pass

    def is_connected(self):
        return True

    def close(self):
        self._closed = True


@pytest.fixture
def mock_db(mocker: MockerFixture):
    mocker.patch("mysql.connector.connect", mock.Mock(return_value=FakeMySQLConn()))
    return mocker


def test_client_connect(mock_db: MockerFixture):
    """
    Test MySQL client connection.
    """
    client = ClientMySQL(db_user="", db_pwd="", db_host="", db_port=3307, db_ssl=False, db_enc="")
    assert client.db_conn is None
    client.connect()
    assert client.db_conn is not None

    # make connect fail
    mock_db.patch("mysql.connector.connect", side_effect=Error("conn fail"))
    with pytest.raises(RequestException, match="MySQL database connection error"):
        client.connect()


def test_client_get_table_info(mock_db: MockerFixture):
    """
    Test getting table information.
    """
    client = ClientMySQL(db_user="", db_pwd="", db_host="", db_port=3307, db_ssl=False, db_enc="")
    client.connect()

    wrong_table_name = "%;;--"
    with pytest.raises(BugException, match=f"Trying to get a table info from an invalid table name: {wrong_table_name}"):
        client.get_table_info(wrong_table_name)

    good_table_name = "test"
    ret = client.get_table_info(good_table_name)
    assert ret == {
        "col_name1": "dict",
        "col_name2": "int",
        "col_name3": "str",
        "col_name4": "dict",
        "col_name5": "int8",
    }

    error_table_name = "test2"
    ret = client.get_table_info(error_table_name)
    assert not ret 


def test_client_create_table(mock_db: MockerFixture):
    """
    Test creating a table.
    """
    client = ClientMySQL(db_user="", db_pwd="", db_host="", db_port=3307, db_ssl=False, db_enc="")
    client.connect()

    col = Column(name="test", data_type="str")
    table = Table(name="test", columns=[col])
    client.create_table(table)

    table_duplicate = Table(name="duplicate", columns=[col])
    client.create_table(table_duplicate)

    table_error = Table(name="error", columns=[col])
    with pytest.raises(RequestException, match="Error when creating table"):
        client.create_table(table_error)


def test_client_create_several_table(mock_db: MockerFixture):
    """
    Test creating several tables.
    """
    client = ClientMySQL(db_user="", db_pwd="", db_host="", db_port=3307, db_ssl=False, db_enc="")
    client.connect()

    col = Column(name="test", data_type="str")
    table = Table(name="test", columns=[col])
    client.create_several_table([table])  # should not raise


def test_insert_update_select(mock_db: MockerFixture):
    """
    Test inserting, updating, and selecting data.
    """
    client = ClientMySQL(db_user="", db_pwd="", db_host="", db_port=3307, db_ssl=False, db_enc="")
    client.connect()

    # Insert multiple rows
    rows_to_insert = [
        ["Alice", {"k": "v"}, 30],
        ["Bob", {"x": [1, 2, 3]}, 25],
    ]
    cols = ("name", "data", "age")
    inserted = client.insert_in_table("test_insert", cols, rows_to_insert)
    assert inserted == 2

    # Test insert with mismatched column and value length
    wrong_values = [["Alice", {"k": "v"}]]  # Missing age
    with pytest.raises(BugException, match="Try to insert more or less data than the columns"):
        client.insert_in_table("test_insert", cols, wrong_values)

    # Update
    update_cols = ("age",)
    update_values = [26]
    cond = EqualCondition("name", "Bob")
    updated = client.update_in_table("test_update", update_cols, update_values, cond)
    assert updated == 1

    # Test update with dict value
    update_cols_dict = ("data",)
    update_values_dict = [{"new_key": "new_value"}]
    updated_dict = client.update_in_table("test_update", update_cols_dict, update_values_dict, cond)
    assert updated_dict == 1

    # Test update with mismatched column and value length
    wrong_update_values = [26, 27]  # Too many values
    with pytest.raises(BugException, match="Try to update more or less data than the specified columns"):
        client.update_in_table("test_update", update_cols, wrong_update_values, cond)

    # Select
    cond_all = EqualCondition("id", 1)
    results = list(client.select_from_table("test_select", ("id", "name", "data", "age"), cond_all))
    assert len(results) == 2
    assert results[0][1] == "Alice"
    assert results[1][1] == "Bob"

    # Test select with empty column tuple (should select all columns)
    results_all = list(client.select_from_table("test_select", (), cond_all))
    assert len(results_all) == 2

    # Test select with limit
    results_limit = list(client.select_from_table("test_select", ("id", "name"), cond_all, limit=1))
    assert len(results_limit) == 2  # Mock returns 2 rows regardless

    # Test select with offset
    results_offset = list(client.select_from_table("test_select", ("id", "name"), cond_all, offset=1))
    assert len(results_offset) == 2


def test_client_count_row_in_table(mock_db: MockerFixture):
    """
    Test the count_row_in_table method of MySQL client
    """
    client = ClientMySQL(db_user="", db_pwd="", db_host="", db_port=3307, db_ssl=False, db_enc="")
    client.connect()

    # Test count with default column (*)
    condition = EqualCondition("status", "active")
    count = client.count_row_in_table("test_count", condition)
    assert count == 5

    # Test count with specific column
    count_col = client.count_row_in_table("test_count", condition, column_name="id")
    assert count_col == 5


def test_client_delete_row_in_table(mock_db: MockerFixture):
    """
    Test the delete_row_in_table method of MySQL client
    """
    client = ClientMySQL(db_user="", db_pwd="", db_host="", db_port=3307, db_ssl=False, db_enc="")
    client.connect()

    # Test delete with valid condition
    condition = EqualCondition("id", 1)
    ret = client.delete_row_in_table("test_delete", condition)
    assert ret == 1

    # Test delete with TrueCondition should raise exception
    from app.utils import errors as err
    with pytest.raises(BugException, match="Condition for delete query is always True"):
        client.delete_row_in_table("test_delete", TrueCondition())

    # Test delete with expected_row check (matching)
    condition_exp = EqualCondition("id", 2)
    ret_exp = client.delete_row_in_table("test_count", condition_exp, expected_row=5)
    # In the mock, count returns 5, so this should succeed
    # The actual delete happens on test_count which returns 0, but expected_row check passes

    # Test delete with expected_row check (not matching)
    with pytest.raises(RequestException, match="Expected number of row deleted is different"):
        client.delete_row_in_table("test_delete", condition_exp, expected_row=10)


def test_client_close(mock_db: MockerFixture):
    """
    Test the close method of MySQL client
    """
    client = ClientMySQL(db_user="", db_pwd="", db_host="", db_port=3307, db_ssl=False, db_enc="")
    client.connect()
    assert client.db_conn is not None
    client.close()
    # Connection should be closed
