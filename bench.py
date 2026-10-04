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


def load(conn, n):
    """One article, n revisions. Revision i gets fake time START + i*STEP."""
    base = make_text(CONTENT_KB)
    t0 = int(START.timestamp())
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS page")
        cur.execute("""CREATE TABLE page (
            page_id INT PRIMARY KEY,
            title VARCHAR(255),
            content MEDIUMTEXT
        ) WITH SYSTEM VERSIONING""")
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


def main():
    admin = connect()
    with admin.cursor() as cur:
        cur.execute(f"CREATE DATABASE IF NOT EXISTS {DB}")
    admin.close()

    results = []
    for n in SIZES:
        conn = connect(DB)
        load_s = load(conn, n)
        data_mb, idx_mb = table_size_mb(conn)
        print(f"N={n}: load {load_s:.1f}s, data {data_mb:.1f} MB, index {idx_mb:.1f} MB")

        t0 = int(START.timestamp())
        points = {"old": 0, "middle": n // 2, "recent": n - 1}
        for name, i in points.items():
            ts = datetime.fromtimestamp(t0 + i * STEP_SECONDS + 60, timezone.utc)
            sql = (f"SELECT page_id, LEFT(content, 40) FROM page "
                   f"FOR SYSTEM_TIME AS OF TIMESTAMP'{ts:%Y-%m-%d %H:%M:%S}' "
                   f"WHERE page_id = 1")
            ms, rows = time_query(conn, sql)
            ok = rows and rows[0][1] is not None and rows[0][1] != ""
            print(f"  AS OF {name}: {ms:.2f} ms (row found: {bool(ok)})")
            results.append({"n_revisions": n, "variant": "plain", "query": f"as_of_{name}",
                            "median_ms": round(ms, 3), "data_mb": round(data_mb, 2),
                            "index_mb": round(idx_mb, 2), "load_s": round(load_s, 2)})
        conn.close()

    with open("results.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=results[0].keys())
        w.writeheader()
        w.writerows(results)
    print("Wrote results.csv")


if __name__ == "__main__":
    main()
