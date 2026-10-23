import hashlib
import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
import verify_load  # noqa: E402
from load_real import ordered_revisions  # noqa: E402


def revision(rid, ts, content, article_id=1):
    return {"article_id": article_id, "article_title": f"A{article_id}", "revision_id": rid,
            "timestamp": ts, "content": content, "author": "x"}


class FakeCursor:
    """Emulates the database: versions with [start, end) validity, AS OF lookups."""
    def __init__(self, data, corrupt=None):
        self.versions = {}
        for rev, start in ordered_revisions(data):
            self.versions.setdefault(rev["article_id"], []).append([start, rev])
        for versions in self.versions.values():
            for i, v in enumerate(versions):
                v.append(versions[i + 1][0] if i + 1 < len(versions) else datetime.max)
        self.corrupt = corrupt or {}
        self.result = None

    def execute(self, sql, params=None):
        if sql.startswith("SET"):
            return
        article_id = params[0]
        versions = self.versions.get(article_id, [])
        if "FOR SYSTEM_TIME ALL" in sql:
            self.result = (len(versions),)
            return
        moment = datetime.strptime(sql.split("TIMESTAMP '")[1].split("'")[0], verify_load.FMT)
        self.result = None
        for start, rev, end in versions:
            if start.replace(tzinfo=None) <= moment < end.replace(tzinfo=None) if end != datetime.max else start.replace(tzinfo=None) <= moment:
                content = self.corrupt.get(rev["revision_id"], rev["content"])
                self.result = (rev["revision_id"], hashlib.md5(content.encode()).hexdigest())

    def fetchone(self):
        return self.result


DATA = [
    revision(11, "2020-01-01T10:00:00Z", "v1"),
    revision(12, "2020-01-02T10:00:00Z", "v2"),
    revision(13, "2020-01-02T10:00:00Z", "v3"),   # same second as 12 -> +1 microsecond
    revision(21, "2020-01-03T10:00:00Z", "w1", article_id=2),
]


class VerifyLoadTests(unittest.TestCase):
    def test_clean_database_has_no_failures(self):
        checked, failures = verify_load.verify(FakeCursor(DATA), DATA)
        self.assertEqual(failures, [])
        self.assertEqual(checked, 4)

    def test_wrong_content_is_reported(self):
        _, failures = verify_load.verify(FakeCursor(DATA, corrupt={12: "tampered"}), DATA)
        self.assertTrue(any("content differs" in f for f in failures))

    def test_missing_version_is_reported(self):
        cursor = FakeCursor(DATA)
        del cursor.versions[1][1]
        _, failures = verify_load.verify(cursor, DATA)
        self.assertTrue(any("versions stored" in f for f in failures))

    def test_sampling_always_checks_first_and_last(self):
        checked, failures = verify_load.verify(FakeCursor(DATA), DATA, every=100)
        self.assertEqual(checked, 3)
        self.assertEqual(failures, [])

    def test_invalid_sampling_is_rejected(self):
        for every in (0, -1, True, 1.5):
            with self.subTest(every=every), self.assertRaises(ValueError):
                verify_load.verify(FakeCursor(DATA), DATA, every=every)

    def test_empty_input_cannot_claim_success(self):
        with self.assertRaises(ValueError):
            verify_load.verify(FakeCursor([]), [])

    def test_loader_order_and_microsecond_ties(self):
        ordered = ordered_revisions(list(reversed(DATA)))
        self.assertEqual([r['revision_id'] for r, _ in ordered], [11, 12, 13, 21])
        self.assertEqual((ordered[2][1] - ordered[1][1]).total_seconds(), 0.000001)

    def test_wrong_revision_id_is_reported(self):
        cursor = FakeCursor(DATA)
        cursor.versions[1][0][1] = dict(DATA[0], revision_id=999)
        _, failures = verify_load.verify(cursor, DATA)
        self.assertTrue(any('expected 11' in f for f in failures))

    def test_unicode_content_hash(self):
        data = [revision(1, '2020-01-01T00:00:00Z', '\u00e9\U0001f680')]
        self.assertEqual(verify_load.verify(FakeCursor(data), data), (1, []))

    def test_queries_use_actual_schema_and_utc(self):
        from unittest.mock import Mock
        cursor = Mock()
        cursor.fetchone.return_value = (1,)
        verify_load.count_versions(cursor, 42)
        self.assertEqual(cursor.execute.call_args.args,
                         ('SELECT COUNT(*) FROM article FOR SYSTEM_TIME ALL WHERE article_id = %s', (42,)))
        verify_load.as_of(cursor, 42, ordered_revisions(DATA)[0][1])
        sql, params = cursor.execute.call_args.args
        self.assertIn('SELECT revision_id, MD5(content) FROM article', sql)
        self.assertIn('FOR SYSTEM_TIME AS OF TIMESTAMP', sql)
        self.assertEqual(params, (42,))


if __name__ == "__main__":
    unittest.main()
