class FullTextValue:
    """Marks a text value destined for a full-text column.

    On PostgreSQL the column is a tsvector, so the database manager wraps the bound text in
    to_tsvector(...) at write time; on MariaDB the column is plain TEXT and the text is written
    as-is. Repositories wrap their search aggregation in this marker so the write path stays
    database-agnostic, the same way a dict is wrapped for JSON columns.
    """

    def __init__(self, text: str) -> None:
        self.text = text
