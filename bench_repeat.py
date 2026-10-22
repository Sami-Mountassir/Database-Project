"""Repeated MariaDB temporal-query benchmark using real Wikipedia revisions.

Run from the repository root:
    python bench_repeat.py --input data/sample/cleaned_revisions.json

The benchmark replaces the ``article`` table in its dedicated benchmark
database. Do not point it at a production database.
"""
import argparse
import csv
import json
import re
import statistics
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from pipeline.load_real import ordered_revisions, parse_timestamp


@dataclass(frozen=True)
class Configuration:
    name: str
    interval_partitioning: bool
    row_period_index: bool


CONFIGURATIONS = (
    Configuration("single_history_default_index", False, False),
    Configuration("single_history_row_period_index", False, True),
    Configuration("interval_default_index", True, False),
    Configuration("interval_row_period_index", True, True),
)
MIN_REPETITIONS = 5


def create_table_sql(configuration, interval, partition_start=None):
    index_clause = (
        ",\n    KEY ix_article_period (article_id, row_start, row_end)"
        if configuration.row_period_index else ""
    )
    if configuration.interval_partitioning and partition_start is None:
        raise ValueError("Time-partitioned tables require a partition start timestamp")
    partition_clause = (
        f"PARTITION BY SYSTEM_TIME INTERVAL {interval} "
        f"STARTS TIMESTAMP '{partition_start}' AUTO "
        "(PARTITION p_history HISTORY, PARTITION p_current CURRENT)"
        if configuration.interval_partitioning
        else "PARTITION BY SYSTEM_TIME "
             "(PARTITION p_history HISTORY, PARTITION p_current CURRENT)"
    )
    return f"""CREATE TABLE article (
    article_id INT NOT NULL,
    revision_id BIGINT NOT NULL,
    title VARCHAR(255) NOT NULL,
    content LONGTEXT,
    author VARCHAR(255),
    revision_date DATETIME(6),
    row_start TIMESTAMP(6) GENERATED ALWAYS AS ROW START,
    row_end TIMESTAMP(6) GENERATED ALWAYS AS ROW END,
    PERIOD FOR SYSTEM_TIME (row_start, row_end),
    PRIMARY KEY (article_id){index_clause}
) WITH SYSTEM VERSIONING
{partition_clause}"""


def revisions_for_input(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("The input JSON must contain a list of cleaned revisions")
    revisions = ordered_revisions(data)
    article_ids = {revision["article_id"] for revision, _ in revisions}
    if len(article_ids) < 2:
        raise ValueError(
            f"Need revisions from several articles; found {len(article_ids)}"
        )
    return revisions


def expected_revision_points(revisions):
    by_article = defaultdict(list)
    for revision, system_time in revisions:
        by_article[revision["article_id"]].append((revision, system_time))

    points = []
    for article_id, article_revisions in sorted(by_article.items()):
        positions = (
            ("first", 0),
            ("middle", len(article_revisions) // 2),
            ("recent", len(article_revisions) - 1),
        )
        for point, position in positions:
            revision, system_time = article_revisions[position]
            points.append({
                "article_id": article_id,
                "query_point": point,
                "system_time": system_time,
                "expected_revision_id": revision["revision_id"],
            })
    return points


def interval_partition_start(revisions, interval):
    earliest = min(system_time for _, system_time in revisions)
    unit = interval.split()[1]
    if unit == "DAY":
        start = earliest.replace(hour=0, minute=0, second=0, microsecond=0)
    elif unit == "WEEK":
        start = (earliest - timedelta(days=earliest.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    elif unit == "MONTH":
        start = earliest.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        start = earliest.replace(
            month=1, day=1, hour=0, minute=0, second=0, microsecond=0
        )
    return start.strftime("%Y-%m-%d %H:%M:%S")


def assert_expected_revision(row, expected_revision_id, context):
    actual_revision_id = row[0] if row is not None else None
    if actual_revision_id != expected_revision_id:
        raise AssertionError(
            f"{context}: expected revision_id {expected_revision_id}, "
            f"got {actual_revision_id}"
        )


def connect(args):
    import pymysql

    connection = pymysql.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.database,
        autocommit=False,
    )
    with connection.cursor() as cursor:
        cursor.execute("SET time_zone = '+00:00'")
    return connection


def ensure_database(args):
    if not re.fullmatch(r"[A-Za-z0-9_]+", args.database):
        raise ValueError("Database name may contain only letters, digits, and underscores")
    import pymysql

    connection = pymysql.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        autocommit=True,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET time_zone = '+00:00'")
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{args.database}`")
    finally:
        connection.close()


def load_revisions(connection, revisions, configuration, interval, partition_start):
    with connection.cursor() as cursor:
        cursor.execute("DROP TABLE IF EXISTS article")
        cursor.execute(create_table_sql(configuration, interval, partition_start))
        started = time.perf_counter()
        inserted_articles = set()
        for revision, system_time in revisions:
            cursor.execute(
                "SET timestamp = UNIX_TIMESTAMP(%s)",
                (system_time.strftime("%Y-%m-%d %H:%M:%S.%f"),),
            )
            values = (
                revision["revision_id"],
                revision["article_title"],
                revision["content"],
                revision.get("author", ""),
                parse_timestamp(revision["timestamp"]).strftime(
                    "%Y-%m-%d %H:%M:%S.%f"
                ),
                revision["article_id"],
            )
            if revision["article_id"] in inserted_articles:
                cursor.execute(
                    """UPDATE article
                       SET revision_id = %s, title = %s, content = %s,
                           author = %s, revision_date = %s
                       WHERE article_id = %s""",
                    values,
                )
            else:
                cursor.execute(
                    """INSERT INTO article
                       (article_id, revision_id, title, content, author, revision_date)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (
                        revision["article_id"],
                        revision["revision_id"],
                        revision["article_title"],
                        revision["content"],
                        revision.get("author", ""),
                        parse_timestamp(revision["timestamp"]).strftime(
                            "%Y-%m-%d %H:%M:%S.%f"
                        ),
                    ),
                )
                inserted_articles.add(revision["article_id"])
        cursor.execute("SET timestamp = DEFAULT")
    connection.commit()
    return (time.perf_counter() - started) * 1000


def query_revision(connection, point):
    as_of = point["system_time"].strftime("%Y-%m-%d %H:%M:%S.%f")
    sql = (
        "SELECT revision_id FROM article "
        f"FOR SYSTEM_TIME AS OF TIMESTAMP '{as_of}' "
        "WHERE article_id = %s"
    )
    with connection.cursor() as cursor:
        started = time.perf_counter()
        cursor.execute(sql, (point["article_id"],))
        row = cursor.fetchone()
        elapsed_ms = (time.perf_counter() - started) * 1000
    context = (
        f"article_id={point['article_id']} "
        f"AS OF {as_of} ({point['query_point']})"
    )
    assert_expected_revision(row, point["expected_revision_id"], context)
    return elapsed_ms


def partition_count(connection, database):
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT COUNT(*)
               FROM information_schema.PARTITIONS
               WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'article'
                 AND PARTITION_NAME IS NOT NULL""",
            (database,),
        )
        return cursor.fetchone()[0]


def summarize(run_rows, load_rows):
    query_groups = defaultdict(list)
    repetition_groups = defaultdict(list)
    for row in run_rows:
        key = (
            row["configuration"],
            row["query_point"],
            row["article_id"],
        )
        query_groups[key].append(row["query_ms"])
        repetition_groups[
            (row["configuration"], row["repetition"])
        ].append(row["query_ms"])
    load_groups = defaultdict(list)
    for row in load_rows:
        load_groups[row["configuration"]].append(row["load_ms"])

    summaries = []
    for (configuration, query_point, article_id), values in sorted(query_groups.items()):
        loads = load_groups[configuration]
        summaries.append({
            "configuration": configuration,
            "query_point": query_point,
            "article_id": article_id,
            "repetitions": len(values),
            "mean_query_ms": round(statistics.mean(values), 4),
            "stddev_query_ms": round(statistics.stdev(values), 4),
            "mean_load_ms": round(statistics.mean(loads), 3),
            "stddev_load_ms": round(statistics.stdev(loads), 3),
            "partition_count": next(
                row["partition_count"] for row in run_rows
                if row["configuration"] == configuration
            ),
        })
    workload_groups = defaultdict(list)
    for (configuration, _), values in repetition_groups.items():
        workload_groups[configuration].append(statistics.mean(values))
    for configuration, values in sorted(workload_groups.items()):
        loads = load_groups[configuration]
        summaries.append({
            "configuration": configuration,
            "query_point": "all",
            "article_id": "all",
            "repetitions": len(values),
            "mean_query_ms": round(statistics.mean(values), 4),
            "stddev_query_ms": round(statistics.stdev(values), 4),
            "mean_load_ms": round(statistics.mean(loads), 3),
            "stddev_load_ms": round(statistics.stdev(loads), 3),
            "partition_count": next(
                row["partition_count"] for row in run_rows
                if row["configuration"] == configuration
            ),
        })
    return summaries


def run_benchmark(args):
    if args.repetitions < MIN_REPETITIONS:
        raise ValueError(f"--repetitions must be at least {MIN_REPETITIONS}")
    if args.interval not in {"1 DAY", "1 WEEK", "1 MONTH", "1 YEAR"}:
        raise ValueError("--interval must be 1 DAY, 1 WEEK, 1 MONTH, or 1 YEAR")

    revisions = revisions_for_input(args.input)
    points = expected_revision_points(revisions)
    partition_start = interval_partition_start(revisions, args.interval)
    run_rows = []
    load_rows = []
    ensure_database(args)
    for repetition in range(1, args.repetitions + 1):
        for configuration in CONFIGURATIONS:
            connection = connect(args)
            try:
                load_ms = load_revisions(
                    connection,
                    revisions,
                    configuration,
                    args.interval,
                    partition_start,
                )
                partitions = partition_count(connection, args.database)
                load_rows.append({
                    "configuration": configuration.name,
                    "repetition": repetition,
                    "load_ms": load_ms,
                })
                for point in points:
                    query_ms = query_revision(connection, point)
                    run_rows.append({
                        "configuration": configuration.name,
                        "repetition": repetition,
                        "query_point": point["query_point"],
                        "article_id": point["article_id"],
                        "expected_revision_id": point["expected_revision_id"],
                        "query_ms": query_ms,
                        "load_ms": load_ms,
                        "partition_count": partitions,
                    })
                print(
                    f"{configuration.name} run {repetition}/{args.repetitions}: "
                    f"{len({r['article_id'] for r, _ in revisions})} articles, "
                    f"{len(revisions)} revisions, load {load_ms:.2f} ms"
                )
            finally:
                connection.close()

    summaries = summarize(run_rows, load_rows)
    with Path(args.output).open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=run_rows[0].keys())
        writer.writeheader()
        writer.writerows(run_rows)
    summary_path = Path(args.summary_output)
    with summary_path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=summaries[0].keys())
        writer.writeheader()
        writer.writerows(summaries)

    print("\nMean and sample standard deviation across repeated runs (milliseconds):")
    for row in summaries:
        if row["query_point"] != "all":
            continue
        print(
            f"{row['configuration']} all article/point queries: "
            f"{row['mean_query_ms']:.4f} "
            f"+/- {row['stddev_query_ms']:.4f}; "
            f"load {row['mean_load_ms']:.3f} +/- {row['stddev_load_ms']:.3f}"
        )
    print("Per-article and per-time-point measurements are included in the summary CSV.")
    print(f"Wrote per-run results to {args.output}")
    print(f"Wrote mean/stddev summary to {summary_path}")


def default_input():
    data_input = Path(__file__).resolve().parent / "data/sample/cleaned_revisions.json"
    if data_input.exists():
        return str(data_input)
    return str(Path(__file__).resolve().parent / "samples/wikipedia_revisions.json")


def main():
    parser = argparse.ArgumentParser(
        description="Compare temporal indexes and partitions over real article revisions"
    )
    parser.add_argument("--input", default=default_input())
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3306)
    parser.add_argument("--user", default="bench")
    parser.add_argument("--password", default="bench")
    parser.add_argument("--database", default="timemachine_bench_repeat")
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--interval", default="1 MONTH")
    parser.add_argument("--output", default="bench_repeat_runs.csv")
    parser.add_argument("--summary-output", default="bench_repeat_summary.csv")
    args = parser.parse_args()
    try:
        run_benchmark(args)
    except Exception as error:
        print(f"Benchmark failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
