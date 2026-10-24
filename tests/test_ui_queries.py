import sys
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ui"))
import queries  # noqa: E402


class RecordingCursor:
    def __init__(self, rows=None):
        self.calls, self.rows = [], rows or []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None


class QueryTests(unittest.TestCase):
    def test_as_of_uses_parameters_and_microsecond_format(self):
        cursor = RecordingCursor()
        self.assertIsNone(queries.article_as_of(cursor, 7, datetime(2020, 1, 3, 10, 0, 0, 1)))
        sql, params = cursor.calls[0]
        self.assertIn("FOR SYSTEM_TIME AS OF TIMESTAMP %s", sql)
        self.assertEqual(params, ("2020-01-03 10:00:00.000001", 7))

    def test_timeline_is_oldest_first_and_parameterised(self):
        cursor = RecordingCursor([(1, None, None, "a")])
        queries.list_revisions(cursor, 3)
        sql, params = cursor.calls[0]
        self.assertIn("ORDER BY row_start", sql)
        self.assertEqual(params, (3,))


if __name__ == "__main__":
    unittest.main()