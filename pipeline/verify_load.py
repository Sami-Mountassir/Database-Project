"""Verify that the database matches the cleaned JSON, revision by revision.

For every revision (same ordering and microsecond tie-breaks as load_real.py):
  1. AS OF its system time        -> must return THIS revision (id + content hash)
  2. AS OF one microsecond before -> must return the PREVIOUS revision
                                     (or nothing for an article's first revision)
And per article: total number of stored versions == number of loaded revisions.

Run from the repository root, AFTER load_real.py, against the same database:
    python pipeline/verify_load.py --input samples/wikipedia_revisions.json --database wikipedia_time_machine
Exit code 0 = everything matches, 1 = at least one mismatch (details printed).
"""
import argparse
import hashlib
import json
import sys
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

try:
    from .load_real import ordered_revisions
except ImportError:  # direct script execution
    from load_real import ordered_revisions

FMT = "%Y-%m-%d %H:%M:%S.%f"


def as_of(cursor, article_id, moment):
    cursor.execute(
        "SELECT revision_id, MD5(content) FROM article "
        f"FOR SYSTEM_TIME AS OF TIMESTAMP '{moment.strftime(FMT)}' "
        "WHERE article_id = %s",
        (article_id,),
    )
    return cursor.fetchone()


def count_versions(cursor, article_id):
    cursor.execute(
        "SELECT COUNT(*) FROM article FOR SYSTEM_TIME ALL WHERE article_id = %s",
        (article_id,),
    )
    return cursor.fetchone()[0]


def verify(cursor, data, every=1):
    """Return (checked, failures). `failures` is a list of readable strings."""
    if type(every) is not int or every < 1:
        raise ValueError("every must be an integer >= 1")
    if not isinstance(data, list) or not data:
        raise ValueError("input must be a non-empty JSON array of revisions")
    ordered = ordered_revisions(data)
    if not ordered:
        raise ValueError("input contains no loadable revisions")
    cursor.execute("SET time_zone = '+00:00'")
    per_article = defaultdict(list)
    for revision, system_time in ordered:
        per_article[revision["article_id"]].append((revision, system_time))

    failures, checked = [], 0
    for article_id, items in per_article.items():
        title = items[0][0]["article_title"]
        stored = count_versions(cursor, article_id)
        if stored != len(items):
            failures.append(f"[{title}] versions stored={stored}, expected={len(items)}")
        for index, (revision, system_time) in enumerate(items):
            if index % every and index != len(items) - 1:
                continue
            checked += 1
            row = as_of(cursor, article_id, system_time)
            expected_hash = hashlib.md5(revision["content"].encode("utf-8")).hexdigest()
            if row is None or row[0] != revision["revision_id"]:
                failures.append(f"[{title}] AS OF {system_time:{FMT}}: got "
                                f"{None if row is None else row[0]}, expected {revision['revision_id']}")
            elif row[1] != expected_hash:
                failures.append(f"[{title}] revision {revision['revision_id']}: content differs "
                                "(check utf8mb4 / max_allowed_packet)")
            before = as_of(cursor, article_id, system_time - timedelta(microseconds=1))
            expected_before = items[index - 1][0]["revision_id"] if index else None
            got_before = None if before is None else before[0]
            if got_before != expected_before:
                failures.append(f"[{title}] 1 microsecond before {system_time:{FMT}}: got "
                                f"{got_before}, expected {expected_before}")
    return checked, failures


def main():
    parser = argparse.ArgumentParser(description="Verify loaded revisions against the JSON")
    parser.add_argument("--input", default="data/sample/cleaned_revisions.json")
    parser.add_argument("--database", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3306)
    parser.add_argument("--user", default="bench")
    parser.add_argument("--password", default="bench")
    parser.add_argument("--every", type=int, default=1,
                        help="check every Nth revision per article (first/last always checked)")
    args = parser.parse_args()
    if args.every < 1:
        parser.error("--every must be >= 1")

    import pymysql

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    connection = pymysql.connect(host=args.host, port=args.port, user=args.user,
                                 password=args.password, database=args.database,
                                 charset="utf8mb4", connect_timeout=10)
    try:
        with connection.cursor() as cursor:
            checked, failures = verify(cursor, data, args.every)
    finally:
        connection.close()

    print(f"checked {checked} revisions, {len(failures)} problem(s)")
    for line in failures[:50]:
        print("  FAIL", line)
    if len(failures) > 50:
        print(f"  ... and {len(failures) - 50} more")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
