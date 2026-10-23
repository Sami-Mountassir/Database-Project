import sys
import unittest
import copy
import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
import make_subset  # noqa: E402


class SubsetTests(unittest.TestCase):
    def data(self):
        return [{"article_id": a, "revision_id": r, "timestamp": f"2020-01-{r:02d}T00:00:00Z"}
                for a, n in ((1, 10), (2, 3)) for r in range(1, n + 1)]

    def test_keeps_oldest_fraction_per_article(self):
        kept = make_subset.subset(self.data(), 0.25)
        self.assertEqual(sorted(r["revision_id"] for r in kept if r["article_id"] == 1), [1, 2, 3])
        self.assertEqual(sorted(r["revision_id"] for r in kept if r["article_id"] == 2), [1])

    def test_full_fraction_keeps_everything(self):
        self.assertEqual(len(make_subset.subset(self.data(), 1.0)), 13)

    def test_half_keeps_oldest_per_article(self):
        kept = make_subset.subset(list(reversed(self.data())), 0.5)
        self.assertEqual([r["revision_id"] for r in kept if r["article_id"] == 1], [1, 2, 3, 4, 5])
        self.assertEqual([r["revision_id"] for r in kept if r["article_id"] == 2], [1, 2])

    def test_empty_input(self):
        self.assertEqual(make_subset.subset([], 0.25), [])

    def test_invalid_fractions(self):
        for fraction in (0, -1, 1.1, float("nan"), float("inf"), True, "0.25", None):
            with self.subTest(fraction=fraction), self.assertRaises(ValueError):
                make_subset.subset([], fraction)

    def test_malformed_records(self):
        for data in ({}, [None], [{}], [{"article_id": [], "revision_id": 1}],
                     [{"article_id": 1, "revision_id": 1, "timestamp": "bad"}],
                     [{"article_id": 1, "revision_id": 1, "timestamp": "2020-01-01"}]):
            with self.subTest(data=data), self.assertRaises(ValueError):
                make_subset.subset(data, 0.5)

    def test_does_not_mutate_records_or_order(self):
        data = list(reversed(self.data()))
        before = copy.deepcopy(data)
        make_subset.subset(data, 0.5)
        self.assertEqual(data, before)

    def test_timestamp_ties_use_revision_id(self):
        data = self.data()[:2]
        data[1]["timestamp"] = data[0]["timestamp"]
        self.assertEqual(make_subset.subset(list(reversed(data)), 0.5), [data[0]])

    def test_timezone_offsets_sort_by_instant(self):
        data = self.data()[:2]
        data[0]["timestamp"] = "2020-01-01T01:00:00+02:00"
        data[1]["timestamp"] = "2020-01-01T00:00:00Z"
        self.assertEqual(make_subset.subset(list(reversed(data)), 0.5), [data[0]])

    def test_cli_preserves_source_and_writes_deterministic_json(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.json"
            output = Path(directory) / "output.json"
            source.write_text(json.dumps(self.data()), encoding="utf-8")
            original = source.read_bytes()
            command = [sys.executable, str(Path(make_subset.__file__)), "--input", str(source),
                       "--fraction", "0.25", "--output", str(output)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("kept 4 of 13 revisions (2 articles)", result.stdout)
            self.assertEqual(len(json.loads(output.read_text(encoding="utf-8"))), 4)
            first_output = output.read_bytes()
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(output.read_bytes(), first_output)
            command[-1] = str(source)
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(source.read_bytes(), original)

    def test_article_order_matches_loader(self):
        data = list(reversed(self.data()))
        kept = make_subset.subset(data, 1)
        self.assertEqual([r['article_id'] for r in kept], [1] * 10 + [2] * 3)


if __name__ == "__main__":
    unittest.main()
