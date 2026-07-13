#!/usr/bin/env python3
"""
Integration-style tests for app/manager/db/ClientMySQL.py

This script exercises:
 - connect()
 - insert_in_table()
 - select_from_table()
 - update_in_table()
 - close()

It creates a temporary table, runs operations and drops the table at the end.

Configure connection using environment variables:
 - MYSQL_USER (default: "root")
 - MYSQL_PWD  (default: "")
 - MYSQL_HOST (default: "127.0.0.1")
 - MYSQL_PORT (default: "3306")
 - MYSQL_SSL  (default: "false")  -- currently unused by the client, kept for parity
 - MYSQL_ENC  (default: "utf8mb4")
"""
from __future__ import annotations

import os
import json
import traceback

from typing import Any, List, Tuple


from app.manager.db.ClientMySQL import ClientMySQL 
from app.utils.db.Condition import EqualCondition, NotEqualCondition, OrCondition

TEST_TABLE = "test_client_mysql"


def get_env() -> Tuple[str, str, str, int, bool, str]:
    user = os.environ.get("MYSQL_USER", "sogo")
    pwd = os.environ.get("MYSQL_PWD", "sogo")
    host = os.environ.get("MYSQL_HOST", "mariadb")
    port = int(os.environ.get("MYSQL_PORT", 3306))
    ssl_flag = os.environ.get("MYSQL_SSL", "false").lower() in ("1", "true", "yes")
    enc = os.environ.get("MYSQL_ENC", "utf8mb4")
    return user, pwd, host, port, ssl_flag, enc


def create_table_raw(conn: Any) -> None:
    """
    Create a simple test table using the active connection.
    Uses a raw cursor because ClientMySQL.create_table() expects a Table object.
    """
    create_sql = f"""
    CREATE TABLE IF NOT EXISTS `{TEST_TABLE}` (
        `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
        `name` VARCHAR(255),
        `data` JSON,
        `age` SMALLINT
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    cur = conn.cursor()
    try:
        cur.execute(create_sql)
        conn.commit()
        print("Created table", TEST_TABLE)
    finally:
        cur.close()


def drop_table_raw(conn: Any) -> None:
    cur = conn.cursor()
    try:
        cur.execute(f"DROP TABLE IF EXISTS `{TEST_TABLE}`")
        conn.commit()
        print("Dropped table", TEST_TABLE)
    finally:
        cur.close()


def run_tests() -> None:
    user, pwd, host, port, ssl_flag, enc = get_env()
    client = ClientMySQL(user, pwd, host, port, ssl_flag, enc)

    try:
        print("Connecting to MySQL...")
        client.connect()
        print("Connected")

        if client.db_conn is None:
            raise RuntimeError("db_conn is not set after connect()")

        create_table_raw(client.db_conn)

        # 1) Test insert_in_table - multiple rows, JSON dict and list values
        rows_to_insert: List[List[Any]] = [
            ["Alice", {"k": "v"}, 30],
            ["Bob", {"x": [1, 2, 3]}, 25],
            ["Charlie", {"active": True}, 28],
        ]
        cols = ("name", "data", "age")
        inserted = client.insert_in_table(TEST_TABLE, cols, rows_to_insert)
        print(f"Inserted rows: {inserted}")

        # 2) Test select_from_table - select rows where name = 'Alice'
        cond = EqualCondition("name", "Alice")
        print("Selecting rows with name='Alice':")
        for rec in client.select_from_table(TEST_TABLE, ("id", "name", "data", "age"), cond):
            print("  ->", rec)

        # 3) Test update_in_table - update Bob's age
        update_cols = ("age",)
        update_values = [26]  # new age for Bob
        cond_bob = EqualCondition("name", "Bob")
        updated = client.update_in_table(TEST_TABLE, update_cols, update_values, cond_bob)
        print(f"Updated rows (Bob): {updated}")

        # Verify update
        print("Selecting rows with name='Bob':")
        for rec in client.select_from_table(TEST_TABLE, ("id", "name", "data", "age"), cond_bob):
            print("  ->", rec)

    except Exception as e:
        print("An exception occurred during tests:")
        traceback.print_exc()
    finally:
        # cleanup: drop table and close connection
        try:
            if client.db_conn is not None:
                drop_table_raw(client.db_conn)
        except Exception:
            print("Failed to drop table (continuing):")
            traceback.print_exc()
        client.close()
        print("Client closed")


if __name__ == "__main__":
    run_tests()
