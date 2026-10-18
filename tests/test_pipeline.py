import json
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from io import StringIO
from urllib.parse import parse_qs, urlparse

from pipeline.load_real import ordered_revisions, load_real_articles
from pipeline.download import download_article
from pathlib import Path

from pipeline.transform import clean_revision, transform_revisions


class RealRevisionPipelineTests(unittest.TestCase):
    def test_clean_revision_preserves_real_metadata(self):
        raw_revision = {
            "revid": 42,
            "timestamp": "2024-01-01T10:00:00Z",
            "user": "Example Author",
            "slots": {"main": {"*": "Article content"}},
        }

        cleaned = clean_revision(raw_revision, 123, "Example Article")

        self.assertEqual(cleaned["article_id"], 123)
        self.assertEqual(cleaned["article_title"], "Example Article")
        self.assertEqual(cleaned["revision_id"], 42)
        self.assertEqual(cleaned["timestamp"], "2024-01-01T10:00:00Z")
        self.assertEqual(cleaned["author"], "Example Author")
        self.assertEqual(cleaned["content"], "Article content")

    def test_transform_revisions_handles_multiple_articles(self):
        raw_data = [
            {
                "query": {
                    "pages": {
                        "123": {
                            "pageid": 123,
                            "title": "Example Article",
                            "revisions": [
                                {
                                    "revid": 1,
                                    "timestamp": "2024-01-01T00:00:00Z",
                                    "user": "Author One",
                                    "slots": {"main": {"*": "First version"}},
                                }
                            ],
                        }
                    }
                }
            }
        ]

        cleaned = transform_revisions(raw_data)

        self.assertEqual(len(cleaned), 1)
        self.assertEqual(cleaned[0]["article_id"], 123)
        self.assertEqual(cleaned[0]["revision_id"], 1)


class RevisionOrderingTests(unittest.TestCase):
    def revision(self, rid, timestamp="2024-01-01T00:00:00Z", article=1, content="text"):
        return dict(article_id=article, revision_id=rid, timestamp=timestamp, content=content)

    def test_chronological_order(self):
        rows = [self.revision(3, "2024-01-03T00:00:00Z"),
                self.revision(1), self.revision(2, "2024-01-02T00:00:00Z")]
        self.assertEqual([r["revision_id"] for r, _ in ordered_revisions(rows)], [1, 2, 3])

    def test_ties_are_deterministic(self):
        rows = [self.revision(i) for i in [3, 1, 2]]
        expected = ordered_revisions(rows)
        self.assertEqual(expected, ordered_revisions(list(reversed(rows))))
        self.assertEqual([t.microsecond for _, t in expected], [0, 1, 2])
        self.assertEqual([r["revision_id"] for r, _ in expected], [1, 2, 3])

    def test_offsets_reset_for_article_and_second(self):
        rows = [self.revision(1), self.revision(2),
                self.revision(3, "2024-01-01T00:00:01Z"),
                self.revision(4, "2024-01-01T00:00:01Z", article=2)]
        self.assertEqual([t.microsecond for _, t in ordered_revisions(rows)], [0, 1, 0, 0])

    def test_loader_filters_hidden_content_but_preserves_empty_text(self):
        rows = [self.revision(1, content=None),
                self.revision(2, content="[CONTENT HIDDEN OR UNAVAILABLE]"),
                self.revision(3, content="")]
        self.assertEqual([r["revision_id"] for r, _ in ordered_revisions(rows)], [3])

    def test_transform_skips_hidden_revisions(self):
        for raw in [{}, {"texthidden": "", "slots": {"main": {"*": "text"}}},
                    {"slots": {"main": {"texthidden": "", "*": "text"}}},
                    {"slots": {"main": {"*": "[CONTENT HIDDEN OR UNAVAILABLE]"}}}]:
            with self.subTest(raw=raw):
                self.assertIsNone(clean_revision(raw, 1, "Example"))
                data = [{"query": {"pages": {"1": {"pageid": 1, "revisions": [raw]}}}}]
                self.assertEqual(transform_revisions(data), [])
        self.assertEqual(clean_revision({"slots": {"main": {"*": ""}}}, 1, "A")["content"], "")


class DownloadTests(unittest.TestCase):
    def response(self, ids, continuation=None):
        data = {"query": {"pages": {"1": {"pageid": 1, "title": "A",
                "revisions": [{"revid": i} for i in ids]}}}}
        if continuation:
            data["continue"] = {"rvcontinue": continuation, "continue": "||"}
        return StringIO(json.dumps(data))

    @patch("pipeline.download.time.sleep")
    @patch("pipeline.download.urlopen")
    def test_pagination_and_limit(self, open_url, sleep):
        open_url.side_effect = [self.response(range(50), "next"), self.response(range(50, 60))]
        result = download_article("A", limit=60)
        self.assertEqual(len(result["query"]["pages"]["1"]["revisions"]), 60)
        params = parse_qs(urlparse(open_url.call_args.args[0].full_url).query)
        self.assertEqual(params["rvcontinue"], ["next"])
        self.assertEqual(params["rvlimit"], ["10"])
        self.assertEqual(params["rvstart"], ["2020-01-01T00:00:00Z"])
        self.assertEqual(params["rvend"], ["2025-01-01T00:00:00Z"])

    @patch("pipeline.download.time.sleep")
    @patch("pipeline.download.urlopen")
    def test_repeated_token_fails(self, open_url, sleep):
        open_url.side_effect = [self.response([1], "same"), self.response([2], "same")]
        with self.assertRaisesRegex(ValueError, "repeated"):
            download_article("A")

    @patch("pipeline.download.urlopen")
    def test_api_error_fails(self, open_url):
        open_url.return_value = StringIO(json.dumps({"error": {"code": "badvalue"}}))
        with self.assertRaisesRegex(ValueError, "API error"):
            download_article("A")

    @patch("pipeline.download.urlopen")
    def test_natural_termination(self, open_url):
        open_url.return_value = self.response([1])
        download_article("A")
        self.assertEqual(open_url.call_count, 1)


class LoaderTests(unittest.TestCase):
    def test_rejects_unsupported_table_before_connecting(self):
        with self.assertRaisesRegex(ValueError, "only supports the article table"):
            load_real_articles("unused.json", "test", "other_table")

    def test_utc_and_filtered_procedure_calls(self):
        driver = MagicMock()
        connection = driver.connect.return_value
        cursor = connection.cursor.return_value.__enter__.return_value
        rows = [{"article_id": 1, "article_title": "A", "revision_id": 2,
                 "timestamp": "2024-01-01T00:00:00Z", "content": "real"},
                {"content": "[CONTENT HIDDEN OR UNAVAILABLE]"}]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "revisions.json"
            path.write_text(json.dumps(rows), encoding="utf-8")
            with patch.dict("sys.modules", {"pymysql": driver}):
                self.assertEqual(load_real_articles(path, "test", "article"), 1)
        self.assertEqual(cursor.execute.call_args_list[0].args, ("SET time_zone = '+00:00'",))
        self.assertEqual(cursor.execute.call_count, 2)
        self.assertEqual(cursor.execute.call_args.args[1], (
            1, 2, "A", "real", "", "2024-01-01 00:00:00.000000",
            "2024-01-01 00:00:00.000000"))
        connection.commit.assert_called_once()
        connection.close.assert_called_once()


class SampleTests(unittest.TestCase):
    def test_sample_is_small_and_loadable(self):
        path = Path(__file__).resolve().parents[1] / "samples/wikipedia_revisions.json"
        rows = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(len(rows), 20)
        self.assertEqual(len({r["article_id"] for r in rows}), 3)
        self.assertEqual(len({r["revision_id"] for r in rows}), 20)
        self.assertEqual(len(ordered_revisions(rows)), 20)
        for row in rows:
            self.assertTrue(row["article_title"])
            self.assertTrue(row["content"])
            self.assertIn("author", row)


if __name__ == "__main__":
    unittest.main()
