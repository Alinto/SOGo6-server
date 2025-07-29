from sqlalchemy import create_engine


class CLientSQL:
    """
    Class to connect, read and write into a sql database
    """

    def __init__(self, db_user: str, db_pwd: str, db_host: str, db_port: int,  db_ssl: bool, db_enc: str):
        """
        Connect to the client...
        """

    def read_from_table(self, table: tuple[str], fields: tuple[str], conditions: tuple[str]):
        """
        SELECT fields FROM tables WHERE conditions
        """
