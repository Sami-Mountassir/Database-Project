"""Benchmark harness v1: system-versioned table growth + AS OF query time.

Setup:   pip install pymysql
Run:     python bench.py
Output:  results.csv (one row per N and query point)
"""
import csv
import random
import statistics
import string
import time
from datetime import datetime, timezone

import pymysql

# --- config (edit these) ---
HOST, PORT, USER, PASSWORD = "127.0.0.1", 3306, "bench", "bench"
DB = "timemachine_bench"
SIZES = [100, 1000, 10000]      # revisions per run
VARIANTS = ["plain", "partitioned"]
CONTENT_KB = 20                 # approx article size per revision
RUNS = 7                        # timed runs per query (first is dropped)
START = datetime(2015, 1, 1, tzinfo=timezone.utc)
STEP_SECONDS = 6 * 3600         # fake time between revisions
# ---------------------------


def connect(db=None):
    conn = pymysql.connect(host=HOST, port=PORT, user=USER, password=PASSWORD,
                           database=db, autocommit=False)
    with conn.cursor() as cur:
        cur.execute("SET time_zone = '+00:00'")
    return conn


def make_text(kb):
    words = ["".join(random.choices(string.ascii_lowercase, k=random.randint(3, 9)))
             for _ in range(500)]
    return " ".join(random.choices(words, k=kb * 1024 // 6))[: kb * 1024]


def load(conn, n, variant):
    """Create one article with n revisions in the requested table variant."""
    base = make_text(CONTENT_KB)
    t0 = int(START.timestamp())
    partition_clause = ""
    if variant == "partitioned":
        partition_clause = """
            PARTITION BY SYSTEM_TIME (
                PARTITION p_history HISTORY,
                PARTITION p_current CURRENT
            )"""

    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS page")
        cur.execute(f"""CREATE TABLE page (
            page_id INT PRIMARY KEY,
            title VARCHAR(255),
            content MEDIUMTEXT
        ) WITH SYSTEM VERSIONING{partition_clause}""")
        start = time.perf_counter()
        cur.execute(f"SET timestamp = {t0}")
        cur.execute("INSERT INTO page VALUES (1, 'Test', %s)", (base + " rev0",))
        for i in range(1, n):
            cur.execute(f"SET timestamp = {t0 + i * STEP_SECONDS}")
            cur.execute("UPDATE page SET content = %s WHERE page_id = 1",
                        (base + f" rev{i}",))
            if i % 200 == 0:
                conn.commit()
        conn.commit()
        cur.execute("SET timestamp = DEFAULT")
        return time.perf_counter() - start


def table_size_mb(conn):
    with conn.cursor() as cur:
        cur.execute("ANALYZE TABLE page")
        cur.fetchall()
        cur.execute("""SELECT DATA_LENGTH, INDEX_LENGTH FROM information_schema.TABLES
                       WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'page'""", (DB,))
        data, idx = cur.fetchone()
    return data / 1e6, idx / 1e6


def time_query(conn, sql):
    times = []
    with conn.cursor() as cur:
        for _ in range(RUNS):
            s = time.perf_counter()
            cur.execute(sql)
            rows = cur.fetchall()
            times.append((time.perf_counter() - s) * 1000)
    return statistics.median(times[1:]), rows


def partition_metadata(conn):
    with conn.cursor() as cur:
        cur.execute("""SELECT PARTITION_NAME
                       FROM information_schema.PARTITIONS
                       WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'page'
                       ORDER BY PARTITION_NAME""", (DB,))
        names = [row[0] for row in cur.fetchall() if row[0] is not None]
    return len(names), ",".join(names)


def main():
    admin = connect()
    with admin.cursor() as cur:
        cur.execute(f"CREATE DATABASE IF NOT EXISTS {DB}")
    admin.close()

    results = []
    for n in SIZES:
        for variant in VARIANTS:
            conn = connect(DB)
            load_s = load(conn, n, variant)
            data_mb, idx_mb = table_size_mb(conn)
            partition_count, partition_names = partition_metadata(conn)
            print(f"N={n} {variant}: load {load_s:.1f}s, data {data_mb:.1f} MB, "
                  f"index {idx_mb:.1f} MB, partitions {partition_count}")

            t0 = int(START.timestamp())
            points = {"old": 0, "middle": n // 2, "recent": n - 1}
            for name, i in points.items():
                ts = datetime.fromtimestamp(t0 + i * STEP_SECONDS + 60, timezone.utc)
                sql = (f"SELECT page_id, content FROM page "
                       f"FOR SYSTEM_TIME AS OF TIMESTAMP'{ts:%Y-%m-%d %H:%M:%S}' "
                       f"WHERE page_id = 1")
                ms, rows = time_query(conn, sql)
                correct_content = bool(rows and rows[0][1] is not None and
                                      rows[0][1].endswith(f" rev{i}"))
                if not correct_content:
                    raise AssertionError(
                        f"{variant} AS OF {name}: expected rev{i}, got {rows[0][1][-30:] if rows else None}"
                    )
                print(f"  AS OF {name}: {ms:.2f} ms, content correct: {correct_content}")
                results.append({"n_revisions": n, "variant": variant,
                                "query": f"as_of_{name}", "median_ms": round(ms, 3),
                                "data_mb": round(data_mb, 2),
                                "index_mb": round(idx_mb, 2), "load_s": round(load_s, 2),
                                "partition_count": partition_count,
                                "partition_names": partition_names,
                                "correct_content": correct_content})
            conn.close()

    with open("results.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=results[0].keys())
        w.writeheader()
        w.writerows(results)
    print("Wrote results.csv")


if __name__ == "__main__":
    main()
