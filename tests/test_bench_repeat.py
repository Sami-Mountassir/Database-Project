import unittest
from datetime import datetime

from bench_repeat import (
    CONFIGURATIONS,
    assert_expected_revision,
    create_table_sql,
    interval_partition_start,
    summarize,
)


class BenchmarkTests(unittest.TestCase):
    def test_schema_uses_article_system_time_columns_and_optional_index(self):
        default = create_table_sql(CONFIGURATIONS[0], "1 MONTH")
        indexed = create_table_sql(CONFIGURATIONS[1], "1 MONTH")
        interval = create_table_sql(
            CONFIGURATIONS[2], "1 MONTH", "2025-12-01 00:00:00"
        )

        self.assertIn("PERIOD FOR SYSTEM_TIME (row_start, row_end)", default)
        self.assertNotIn("ix_article_period", default)
        self.assertIn(
            "KEY ix_article_period (article_id, row_start, row_end)", indexed
        )
        self.assertIn("PARTITION p_history HISTORY", default)
        self.assertIn(
            "PARTITION BY SYSTEM_TIME INTERVAL 1 MONTH "
            "STARTS TIMESTAMP '2025-12-01 00:00:00'",
            interval,
        )
        self.assertIn(
            "AUTO (PARTITION p_history HISTORY, PARTITION p_current CURRENT)",
            interval,
        )

    def test_interval_partition_start_is_aligned_to_real_revision_dates(self):
        revisions = [
            ({"article_id": 1, "revision_id": 3}, datetime(2026, 2, 15, 12, 30)),
            ({"article_id": 1, "revision_id": 2}, datetime(2026, 2, 2, 8, 0)),
        ]

        self.assertEqual(
            interval_partition_start(revisions, "1 MONTH"),
            "2026-02-01 00:00:00",
        )

    def test_real_article_check_compares_revision_id_to_expected_value(self):
        assert_expected_revision((12345,), 12345, "article 1")
        with self.assertRaisesRegex(AssertionError, "expected revision_id 12345"):
            assert_expected_revision((99999,), 12345, "article 1")

    def test_summary_reports_mean_and_sample_standard_deviation(self):
        run_rows = [
            {
                "configuration": "baseline",
                "repetition": repetition,
                "query_point": "middle",
                "article_id": article_id,
                "query_ms": value,
                "partition_count": 2,
            }
            for article_id, values in ((1, [1.0, 2.0, 3.0, 4.0, 5.0]),)
            for repetition, value in enumerate(values, start=1)
        ]
        load_rows = [
            {"configuration": "baseline", "load_ms": value}
            for value in [10.0, 20.0, 30.0, 40.0, 50.0]
        ]

        summary = next(
            row for row in summarize(run_rows, load_rows)
            if row["query_point"] == "all"
        )

        self.assertEqual(summary["repetitions"], 5)
        self.assertEqual(summary["mean_query_ms"], 3.0)
        self.assertEqual(summary["stddev_query_ms"], 1.5811)
        self.assertEqual(summary["mean_load_ms"], 30.0)


if __name__ == "__main__":
    unittest.main()
