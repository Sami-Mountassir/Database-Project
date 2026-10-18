import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


def parse_timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def format_datetime(value):
    return parse_timestamp(value).strftime("%Y-%m-%d %H:%M:%S.%f")


def ordered_revisions(data):
    revisions = sorted(
        (revision for revision in data
         if isinstance(revision.get("content"), str)
         and revision["content"] != "[CONTENT HIDDEN OR UNAVAILABLE]"),
        key=lambda revision: (
            revision["article_id"],
            parse_timestamp(revision["timestamp"]),
            revision["revision_id"],
        ),
    )
    previous_article = None
    previous_timestamp = None
    previous_index = -1
    ordered = []
    for revision in revisions:
        timestamp = parse_timestamp(revision["timestamp"])
        if revision["article_id"] == previous_article and timestamp == previous_timestamp:
            previous_index += 1
            timestamp += timedelta(microseconds=previous_index)
        else:
            previous_timestamp = timestamp
            previous_index = 0
        previous_article = revision["article_id"]
        ordered.append((revision, timestamp))
    return ordered


def load_real_articles(input_file, database, table, host="127.0.0.1", port=3306,
                      user="bench", password="bench"):
    if table != "article":
        raise ValueError("apply_wikipedia_revision only supports the article table")

    import pymysql

    data = json.loads(Path(input_file).read_text(encoding="utf-8"))
    connection = pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        autocommit=False,
    )
    loaded = 0
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET time_zone = '+00:00'")
            for revision, system_time in ordered_revisions(data):
                cursor.execute(
                    "CALL apply_wikipedia_revision("
                    "%s, %s, %s, %s, %s, %s, %s)",
                    (
                        revision["article_id"],
                        revision["revision_id"],
                        revision["article_title"],
                        revision["content"],
                        revision.get("author", ""),
                        format_datetime(revision["timestamp"]),
                        system_time.strftime("%Y-%m-%d %H:%M:%S.%f"),
                    ),
                )
                loaded += 1
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return loaded


def main():
    parser = argparse.ArgumentParser(description="Load cleaned Wikipedia revisions into the temporal table")
    parser.add_argument("--input", default="data/sample/cleaned_revisions.json")
    parser.add_argument("--database", required=True)
    parser.add_argument("--table", default="article")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3306)
    parser.add_argument("--user", default="bench")
    parser.add_argument("--password", default="bench")
    args = parser.parse_args()

    try:
        loaded = load_real_articles(
            args.input,
            args.database,
            args.table,
            host=args.host,
            port=args.port,
            user=args.user,
            password=args.password,
        )
    except Exception as error:
        print(f"Load failed: {error}", file=sys.stderr)
        raise SystemExit(1)
    print(f"Loaded {loaded} revisions into {args.database}.{args.table}")


if __name__ == "__main__":
    main()
