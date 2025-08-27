import re

import psycopg
from psycopg.sql import SQL, Identifier, Literal, Placeholder, Composed


REX_VALID_NAMES = r"^[A-Za-z_0-9]+$"

# conn_string = "postgresql://sogo:sogo@postgresql:5432/sogo?client_encoding=utf8"

# db_conn = psycopg.connect(conn_string, connect_timeout=5)

table : list[str] = ["my_table", "'; select true; --"]
for table_name in table:
    if not re.match(REX_VALID_NAMES, table_name):
        print("ERROR, invalid table name")
    sql_query = f"SELECT column_name, data_type FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '{table_name}'"
    q = SQL("SELECT column_name, data_type FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = {}").format(Identifier(table_name))
    q2 = SQL("SELECT column_name, data_type FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = {}").format(Literal(table_name))
    print(sql_query)
    print(q.as_string())
    print(q2.as_string())

# q = SQL("WHERE {name} = {value}").format(name=Identifier("my_col"), value = "'; select true; --")

print(q.as_string())
# def test(a, b, c) -> None:
#     print(f"a= {a}, b = {b}, c = {c}")

# test(1, 2 ,3)
# test(a=1, b=2, c=3)
# test(b=2, a=1, c=3)

def select_from_table(table_name: str, column_tuple: tuple[str]) -> list | None:
    if len(column_tuple) == 0:
        column_tuple = ("*",)
    sql_query = SQL("SELECT {columns} FROM {table_name} {conditions}").format(
        columns=SQL(", ").join(map(Identifier, column_tuple)),
        table_name=Identifier(table_name),
        conditions=SQL("WHERE 1 = 1")
    )
    print(sql_query.as_string())
        
select_from_table("my_table", ("col1", "col3"))
