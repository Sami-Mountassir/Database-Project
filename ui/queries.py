"""All SQL the interface needs. Pure functions: they take an open pymysql cursor.

Rule: the UI never builds SQL by string-formatting user input; every value goes
through %s parameters. Times are always UTC (the connection sets time_zone).
"""


def set_utc(cursor):
    cursor.execute("SET time_zone = '+00:00'")


def list_articles(cursor):
    """[(article_id, title)] - current title of every article."""
    cursor.execute("SELECT article_id, title FROM article ORDER BY title")
    return list(cursor.fetchall())


def list_revisions(cursor, article_id):
    """[(revision_id, revision_date, row_start, author)] oldest first (= timeline)."""
    cursor.execute(
        "SELECT revision_id, revision_date, row_start, author "
        "FROM article FOR SYSTEM_TIME ALL WHERE article_id = %s ORDER BY row_start",
        (article_id,),
    )
    return list(cursor.fetchall())


def article_as_of(cursor, article_id, moment):
    """Article as it was at `moment` (datetime, UTC) or None if it did not exist yet.

    Returns (revision_id, title, content, author, revision_date).
    """
    cursor.execute(
        "SELECT revision_id, title, content, author, revision_date "
        "FROM article FOR SYSTEM_TIME AS OF TIMESTAMP %s WHERE article_id = %s",
        (moment.strftime("%Y-%m-%d %H:%M:%S.%f"), article_id),
    )
    return cursor.fetchone()