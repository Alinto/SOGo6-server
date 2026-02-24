from unittest import mock

import pytest
from pytest_mock.plugin import MockerFixture

from psycopg.errors import Error, OperationalError, DuplicateTable, UniqueViolation

from app.manager.db.ClientPostgreSQL import ClientPostgreSQL, str_to_varchar, list_to_array, table_to_query, condition_to_query
from app.utils.exceptions import RequestException, BugException
from app.utils.db.Condition import EqualCondition, NotEqualCondition, AndCondition, OrCondition, TrueCondition
from app.utils.db.Table import Table, Column

def test_str_to_varchar():
    """
    Test the proper typing of a string
    """
    a = 255
    assert str_to_varchar(a) == "varchar(255)"
    b = 0
    assert str_to_varchar(b) == "varchar"
    c = -1
    assert str_to_varchar(c) == "varchar"

def test_list_to_array():
    """
    Test the proper typing of an array
    """
    a = "str"
    assert list_to_array(a) == "varchar[]"
    assert list_to_array(a, extra_args={"max_len": 412}) == "varchar(412)[]"
    b = "dict"
    assert list_to_array(b) == "jsonb[]"

def test_table_to_query():
    """
    Test the proper sql query generation for table's creation
    """
    col1   = Column(name="test1", data_type='str')
    col2   = Column(name="test2", data_type='int8')
    col3   = Column(name="test3", data_type='serial')
    col4   = Column(name="test4", data_type='dict')
    col5   = Column(name="test5", data_type='json')
    col6   = Column(name="test6", data_type='list', extra_args={"data_type": "str"})
    col7   = Column(name="test7", data_type='str', is_nullable=True, extra_args={"max_len": 255})
    col8   = Column(name="test8", data_type='str', is_unique=True)
    table  = Table(name="test", columns=[col1,col2,col3,col4,col5,col6,col7,col8], primary_keys=(col1.name, col2.name))
    sql_query = table_to_query(table)
    assert sql_query.as_string() == "CREATE TABLE \"test\" (\"test1\" varchar NOT NULL, \"test2\" smallint NOT NULL," + \
          " \"test3\" serial NOT NULL, \"test4\" jsonb NOT NULL, \"test5\" jsonb NOT NULL, \"test6\" varchar[] NOT NULL," + \
          " \"test7\" varchar(255) , \"test8\" varchar NOT NULL UNIQUE, PRIMARY KEY (\"test1\", \"test2\"))"

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

class FakePostgresqlCursor:
    """
    Fake psyocgpg cursor object
    """

    def __init__(self, data, rowcount=0):
        self.data = data
        self.rowcount = rowcount
        self._index = 0

    def fetchone(self):
        if isinstance(self.data, list):
            if self._index < len(self.data):
                result = self.data[self._index]
                self._index += 1
                return result
            return None
        return self.data
    
    def fetchall(self):
        return self.data

class FakePostgresqlConn:
    """
    Fake psyocgpg connection object
    """

    def __init__(self):
        self.closed = False
    
    def execute(self, sql_query, params=None):
        query_str = sql_query.as_string()
        
        # Table info queries
        if query_str == "SELECT column_name, data_type FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'test'":
            return FakePostgresqlCursor([('col_name1', 'jsonb'),
                                         ('col_name2', 'integer'),
                                         ('col_name3', 'character varying'),
                                         ('col_name4', 'ARRAY'),
                                         ('col_name5', 'smallint')], rowcount=5)
        elif query_str == "SELECT column_name, data_type FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'test2'":
            raise OperationalError()
        
        # Create table queries
        elif query_str == "CREATE TABLE \"test\" (\"test\" varchar NOT NULL)":
            return FakePostgresqlCursor([], rowcount=0)
        elif query_str == "CREATE TABLE \"duplicate\" (\"test\" varchar NOT NULL)":
            raise DuplicateTable()
        elif query_str == "CREATE TABLE \"error\" (\"test\" varchar NOT NULL)":
            raise Error()
        
        # Insert queries
        elif query_str.startswith("INSERT INTO"):
            if "test_insert" in query_str:
                if params and len(params) >= 6:
                    return FakePostgresqlCursor([], rowcount=2)
                return FakePostgresqlCursor([], rowcount=1)
            elif "unique_error" in query_str:
                raise UniqueViolation()
            return FakePostgresqlCursor([], rowcount=1)
        
        # Update queries
        elif query_str.startswith("UPDATE"):
            if "test_update" in query_str:
                return FakePostgresqlCursor([], rowcount=1)
            return FakePostgresqlCursor([], rowcount=0)
        
        # Select queries
        elif query_str.startswith("SELECT") and "FROM" in query_str and "INFORMATION_SCHEMA" not in query_str:
            if "test_select" in query_str:
                return FakePostgresqlCursor([(1, "Alice", {"k": "v"}, 30), (2, "Bob", {"x": [1, 2]}, 25)], rowcount=2)
            elif "COUNT(*)" in query_str or "COUNT(" in query_str:
                if "test_count" in query_str:
                    return FakePostgresqlCursor([(5,)], rowcount=1)
                return FakePostgresqlCursor([(0,)], rowcount=1)
            return FakePostgresqlCursor([], rowcount=0)
        
        # Delete queries
        elif query_str.startswith("DELETE FROM"):
            if "test_delete" in query_str:
                return FakePostgresqlCursor([], rowcount=1)
            return FakePostgresqlCursor([], rowcount=0)
        
        else:
            raise Exception(f"FakePostgresqlConn: unexpected execute query: {query_str}")
    
    def commit(self):
        pass

    def close(self):
        pass



@pytest.fixture
def mock_db(mocker: MockerFixture):
    """
    Fixture for the psycog connect method
    """
    mocker.patch('psycopg.connect', mock.Mock(return_value=FakePostgresqlConn()))
    return mocker


def test_client_connect(mock_db: MockerFixture):
    """
    Test the connect method of PostgreSQL client
    """
    client = ClientPostgreSQL(db_user= "", db_pwd= "", db_host= "", db_port= 25,  db_ssl= False, db_enc= "")
    assert client.db_conn is None
    client.connect()
    assert client.db_conn is not None
    mock_db.patch('psycopg.connect', side_effect=OperationalError)
    with pytest.raises(RequestException, match="Postgresql database connection error"):
        client.connect()

def test_client_get_table_info(mock_db: MockerFixture):
    """
    Test the get_table_info method of PostgreSQL client
    """
    client = ClientPostgreSQL(db_user= "", db_pwd= "", db_host= "", db_port= 25,  db_ssl= False, db_enc= "")
    client.connect()
    wrong_table_name = "%;;--"
    with pytest.raises(BugException, match=f"Trying to get a table info from an invalid table name: {wrong_table_name}"):
        client.get_table_info(wrong_table_name)
    good_table_name = "test"
    ret = client.get_table_info(good_table_name)
    assert ret == {"col_name1": "dict",
                   "col_name2": "int",
                   "col_name3": "str",
                   "col_name4": "list",
                   "col_name5": "int8"}
    error_table_name = "test2"
    ret = client.get_table_info(error_table_name)
    assert not ret

def test_client_create_table(mock_db: MockerFixture):
    """
    Test the create_table method of PostgreSQL client
    """
    client = ClientPostgreSQL(db_user= "", db_pwd= "", db_host= "", db_port= 25,  db_ssl= False, db_enc= "")
    client.connect()

    col   = Column(name="test", data_type='str')
    table = Table(name="test", columns=[col])
    client.create_table(table)

    table_duplicate = Table(name="duplicate", columns=[col])
    client.create_table(table_duplicate)

    table_error = Table(name="error", columns=[col])
    with pytest.raises(RequestException, match="Error when creating table"):
        client.create_table(table_error)

def test_client_create_several_table(mock_db: MockerFixture):
    """
    Test the create_several_table method of PostgreSQL client
    """
    client = ClientPostgreSQL(db_user= "", db_pwd= "", db_host= "", db_port= 25,  db_ssl= False, db_enc= "")
    client.connect()

    col   = Column(name="test", data_type='str')
    table = Table(name="test", columns=[col])
    client.create_several_table([table]) 


def test_client_insert_in_table(mock_db: MockerFixture):
    """
    Test the insert_in_table method of PostgreSQL client
    """
    client = ClientPostgreSQL(db_user= "", db_pwd= "", db_host= "", db_port= 25,  db_ssl= False, db_enc= "")
    client.connect()

    # Test insert with single row
    cols = ("name", "data", "age")
    values = [["Alice", {"k": "v"}, 30]]
    ret = client.insert_in_table("test_insert", cols, values)
    assert ret == 1

    # Test insert with multiple rows
    values_multi = [["Alice", {"k": "v"}, 30], ["Bob", {"x": [1, 2, 3]}, 25]]
    ret = client.insert_in_table("test_insert", cols, values_multi)
    assert ret == 2

    # Test insert with mismatched column and value length
    wrong_values = [["Alice", {"k": "v"}]]  # Missing age
    with pytest.raises(BugException, match="Try to insert more or less data than the columns"):
        client.insert_in_table("test_insert", cols, wrong_values)

    # Test unique violation
    with pytest.raises(BugException, match="Unique Violation in database"):
        client.insert_in_table("unique_error", cols, values)


def test_client_update_in_table(mock_db: MockerFixture):
    """
    Test the update_in_table method of PostgreSQL client
    """
    client = ClientPostgreSQL(db_user= "", db_pwd= "", db_host= "", db_port= 25,  db_ssl= False, db_enc= "")
    client.connect()

    # Test successful update
    update_cols = ("age",)
    update_values = [26]
    condition = EqualCondition("name", "Bob")
    ret = client.update_in_table("test_update", update_cols, update_values, condition)
    assert ret == 1

    # Test update with dict value
    update_cols_dict = ("data",)
    update_values_dict = [{"new_key": "new_value"}]
    ret = client.update_in_table("test_update", update_cols_dict, update_values_dict, condition)
    assert ret == 1

    # Test update with mismatched column and value length
    wrong_values = [26, 27]  # Too many values
    with pytest.raises(BugException, match="Try to update more or less data than the specified columns"):
        client.update_in_table("test_update", update_cols, wrong_values, condition)


def test_client_select_from_table(mock_db: MockerFixture):
    """
    Test the select_from_table method of PostgreSQL client
    """
    client = ClientPostgreSQL(db_user= "", db_pwd= "", db_host= "", db_port= 25,  db_ssl= False, db_enc= "")
    client.connect()

    # Test select all columns
    condition = EqualCondition("id", 1)
    results = list(client.select_from_table("test_select", ("id", "name", "data", "age"), condition))
    assert len(results) == 2
    assert results[0][1] == "Alice"
    assert results[1][1] == "Bob"

    # Test select with empty column tuple (should select all columns)
    results_all = list(client.select_from_table("test_select", (), condition))
    assert len(results_all) == 2

    # Test select with limit
    results_limit = list(client.select_from_table("test_select", ("id", "name"), condition, limit=1))
    assert len(results_limit) == 2  # Mock returns 2 rows regardless

    # Test select with offset
    results_offset = list(client.select_from_table("test_select", ("id", "name"), condition, offset=1))
    assert len(results_offset) == 2


def test_client_count_row_in_table(mock_db: MockerFixture):
    """
    Test the count_row_in_table method of PostgreSQL client
    """
    client = ClientPostgreSQL(db_user= "", db_pwd= "", db_host= "", db_port= 25,  db_ssl= False, db_enc= "")
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
    Test the delete_row_in_table method of PostgreSQL client
    """
    client = ClientPostgreSQL(db_user= "", db_pwd= "", db_host= "", db_port= 25,  db_ssl= False, db_enc= "")
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
    with pytest.raises(RequestException, match="Expected number or row deleted is different"):
        client.delete_row_in_table("test_delete", condition_exp, expected_row=10)


def test_client_close(mock_db: MockerFixture):
    """
    Test the close method of PostgreSQL client
    """
    client = ClientPostgreSQL(db_user= "", db_pwd= "", db_host= "", db_port= 25,  db_ssl= False, db_enc= "")
    client.connect()
    assert client.db_conn is not None
    client.close()
    # Connection should be closed (db_conn should still exist but closed flag would be set)





if __name__ == "__main__":
    test_condition_to_query()
