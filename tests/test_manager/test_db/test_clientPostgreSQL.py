from unittest import mock

import pytest
from pytest_mock.plugin import MockerFixture

from psycopg.errors import Error, OperationalError, DuplicateTable

from app.manager.db.ClientPostgreSQL import ClientPostgreSQL, str_to_varchar, list_to_array, table_to_query, condition_to_query
from app.utils.exceptions import RequestException, BugException
from app.utils.db.Condition import EqualCondition, NotEqualCondition, AndCondition, OrCondition
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

    def __init__(self, data):
        self.data = data

    def fetchone(self):
        return self.data
    
    def fetchall(self):
        return self.data

class FakePostgresqlConn:
    """
    Fake psyocgpg connection object
    """

    def __init__(self):
        self.closed = False
    
    def execute(self, sql_query):
        match sql_query.as_string():
            case "SELECT column_name, data_type FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'test'":
                return FakePostgresqlCursor([('col_name1', 'jsonb'),
                                             ('col_name2', 'integer'),
                                             ('col_name3', 'character varying'),
                                             ('col_name4', 'ARRAY'),
                                             ('col_name5', 'smallint')])
            case "SELECT column_name, data_type FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'test2'":
                raise OperationalError()
            case "CREATE TABLE \"test\" (\"test\" varchar NOT NULL)":
                return None
            case "CREATE TABLE \"duplicate\" (\"test\" varchar NOT NULL)":
                raise DuplicateTable()
            case "CREATE TABLE \"error\" (\"test\" varchar NOT NULL)":
                raise Error()
            case _:
                raise Exception(f"FakePostgresqlConn: unexpected execute query: {sql_query.as_string()}")
    
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





if __name__ == "__main__":
    test_condition_to_query()
