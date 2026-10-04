# Wikipedia Time Machine — Person 1

## Role

i am responsible for the MariaDB database and temporal-table design.

## Files

- `person1_temporal_schema.sql` — creates the system-versioned `article` table, SYSTEM_TIME partitions, and the revision-loading procedure.
- `README_PERSON1.md` — setup, usage, temporal queries, and design decisions.

## Database table

The main table is `article`.

| Column | Purpose |
|---|---|
| `article_id` | Wikipedia article identifier |
| `revision_id` | Wikipedia revision identifier |
| `title` | Article title |
| `content` | Article content |
| `author` | Revision author |
| `revision_date` | Original Wikipedia revision timestamp |
| `row_start` | MariaDB SYSTEM_TIME start |
| `row_end` | MariaDB SYSTEM_TIME end |

The table uses `WITH SYSTEM VERSIONING` and is partitioned by `SYSTEM_TIME` into `p_history` and `p_current`.

## Important time-model decision

Wikipedia revisions already have historical timestamps. MariaDB SYSTEM_TIME normally records when a database change happens. A normal import would therefore make the temporal timeline describe the import process rather than Wikipedia history.

For this project, revisions are replayed chronologically and the loader sets `@@timestamp` to the Wikipedia revision time.

This gives us:

- `revision_date` = original Wikipedia source time
- `row_start` / `row_end` = MariaDB SYSTEM_TIME used by `FOR SYSTEM_TIME`

### Same-second revisions

Wikipedia can contain multiple revisions with the same timestamp.

The loader should sort revisions by:

1. revision timestamp
2. revision ID

If multiple revisions have exactly the same second, use deterministic microsecond offsets such as:

```text
20:00:00.000000
20:00:00.000001
20:00:00.000002
```

The original Wikipedia timestamp remains unchanged in `revision_date`.

## Person 2: loading revisions

Call:

```sql
CALL apply_wikipedia_revision(
    article_id,
    revision_id,
    title,
    content,
    author,
    revision_date,
    system_time
);
```

For `system_time`, use the Wikipedia revision timestamp, including the microsecond tie-breaker when necessary.

Revisions should be loaded chronologically for each article.

## Historical queries

Show all versions:

```sql
SELECT
    article_id,
    revision_id,
    title,
    revision_date,
    row_start,
    row_end
FROM article
FOR SYSTEM_TIME ALL
ORDER BY article_id, row_start;
```

Show one article at a historical moment:

```sql
SELECT *
FROM article
FOR SYSTEM_TIME AS OF '2026-10-03 10:05:00.000000'
WHERE article_id = 1;
```

The UI can use this query to render the article as it existed at the selected time.

## Check SYSTEM_TIME partitions

```sql
SELECT
    TABLE_NAME,
    PARTITION_NAME,
    PARTITION_METHOD,
    PARTITION_DESCRIPTION,
    TABLE_ROWS
FROM information_schema.PARTITIONS
WHERE TABLE_SCHEMA = 'wikipedia_time_machine'
  AND TABLE_NAME = 'article';
```

Expected partitions:

```text
p_history
p_current
```

## Setup

Create/select the project database:

```sql
CREATE DATABASE IF NOT EXISTS wikipedia_time_machine;
USE wikipedia_time_machine;
```

Then run `person1_temporal_schema.sql`.

The SQL file intentionally does not contain a `USE` statement, so it can be reused for the real database and test databases.

## Docker / MariaDB

Development container:

```text
wikipedia-mariadb
```

Connect with:

```powershell
docker exec -it wikipedia-mariadb mariadb -u root -p
```

Then:

```sql
USE wikipedia_time_machine;
```

## Timestamp note

The loader procedure changes the session timestamp with:

```sql
SET @@timestamp = UNIX_TIMESTAMP(p_system_time);
```

This is intentional for the historical replay strategy.

After manual testing or importing in a session, restore normal timestamp behavior with:

```sql
SET @@timestamp = UNIX_TIMESTAMP();
```

The project assumes a controlled single import session, so concurrent writes are not part of the import workflow.

## Temporal history and DELETE

Normal updates and deletes create temporal history.

For example:

```sql
DELETE FROM article
WHERE article_id = 1;
```

does not immediately remove the historical versions.

To explicitly purge temporal history:

```sql
DELETE HISTORY FROM article;
```

Use this only when historical data is intentionally being removed.

## What MariaDB temporal history replaces

System-versioned history means the project does not need a separate database-side table containing every old version of an article.

However, temporal history does **not** replace Wikipedia's revision metadata. Wikipedia revision data is still needed for:

- revision IDs
- authors
- original revision timestamps
- the actual revision sequence

The temporal table provides the database mechanism for reconstructing previous states.

## Person 1 completion checklist

- [x] MariaDB system-versioned table
- [x] SYSTEM_TIME period
- [x] SYSTEM_TIME history/current partitions
- [x] Revision loading procedure
- [x] Historical `FOR SYSTEM_TIME` queries
- [x] Same-second revision handling documented
- [x] Wikipedia time vs MariaDB system-time decision documented
- [x] Partition inspection query
- [x] Temporal DELETE behavior documented

## Team responsibilities

### Person 1
MariaDB, system-versioned table, temporal queries, partitions, and loading procedure.

### Person 2
Wikipedia extraction/API or dump processing and preparation of revision data.

### Person 3
Experiments, benchmarks, storage growth, and performance measurements.

### Person 4
UI, historical article rendering, diff view, and project documentation.
