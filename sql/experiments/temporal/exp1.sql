
-- Experiment 1: Verify temporal AS OF query correctness.
-- MariaDB version tested: 13.0.2-MariaDB-ubu2604
-- Database: wikipedia_time_machine
-- Test article ID: 999999

USE wikipedia_time_machine;

-- Use UTC for the initial test setup.
SET time_zone = '+00:00';

-- Check that the test article ID is unused before loading.
-- Expected: 0 rows counted.
SELECT COUNT(*) AS existing_test_rows
FROM article
WHERE article_id = 999999;

-- Load seven revisions.
-- Revisions 1003 and 1004 share the same revision_date.
-- Their system-time values differ by one microsecond.

CALL apply_wikipedia_revision(
    999999, 1001, 'Temporal Test', 'Revision 1', 'Tester',
    '2026-10-01 10:00:00.000000',
    '2026-10-01 10:00:00.000000'
);

CALL apply_wikipedia_revision(
    999999, 1002, 'Temporal Test', 'Revision 2', 'Tester',
    '2026-10-01 10:00:10.000000',
    '2026-10-01 10:00:10.000000'
);

CALL apply_wikipedia_revision(
    999999, 1003, 'Temporal Test', 'Revision 3', 'Tester',
    '2026-10-01 10:00:20.000000',
    '2026-10-01 10:00:20.000000'
);

CALL apply_wikipedia_revision(
    999999, 1004, 'Temporal Test', 'Revision 4', 'Tester',
    '2026-10-01 10:00:20.000000',
    '2026-10-01 10:00:20.000001'
);

CALL apply_wikipedia_revision(
    999999, 1005, 'Temporal Test', 'Revision 5', 'Tester',
    '2026-10-01 10:00:30.000000',
    '2026-10-01 10:00:30.000000'
);

CALL apply_wikipedia_revision(
    999999, 1006, 'Temporal Test', 'Revision 6', 'Tester',
    '2026-10-01 10:00:40.000000',
    '2026-10-01 10:00:40.000000'
);

CALL apply_wikipedia_revision(
    999999, 1007, 'Temporal Test', 'Revision 7', 'Tester',
    '2026-10-01 10:00:50.000000',
    '2026-10-01 10:00:50.000000'
);

-- Restore the current session timestamp after loading.
SET @@timestamp = UNIX_TIMESTAMP();

-- Inspect the stored historical versions.
SELECT
    revision_id,
    revision_date,
    row_start,
    row_end,
    content
FROM article FOR SYSTEM_TIME ALL
WHERE article_id = 999999
ORDER BY row_start, revision_id;

-- Test 1: Before the first revision.
-- Expected: no row (NULL).
SELECT
    'before first revision' AS test_case,
    'NULL' AS expected,
    COALESCE(CAST((
        SELECT revision_id
        FROM article FOR SYSTEM_TIME AS OF
            '2026-10-01 09:59:59.999999'
        WHERE article_id = 999999
    ) AS CHAR), 'NULL') AS observed;

-- Test 2: Between revisions 1002 and 1003.
-- Expected: 1002.
SELECT
    'between revisions' AS test_case,
    '1002' AS expected,
    COALESCE(CAST((
        SELECT revision_id
        FROM article FOR SYSTEM_TIME AS OF
            '2026-10-01 10:00:15.000000'
        WHERE article_id = 999999
    ) AS CHAR), 'NULL') AS observed;

-- Test 3: Exactly at revision 1003.
-- Expected: 1003.
SELECT
    'exactly at revision 1003' AS test_case,
    '1003' AS expected,
    COALESCE(CAST((
        SELECT revision_id
        FROM article FOR SYSTEM_TIME AS OF
            '2026-10-01 10:00:20.000000'
        WHERE article_id = 999999
    ) AS CHAR), 'NULL') AS observed;

-- Test 4: One microsecond before revision 1004.
-- Expected: 1003.
SELECT
    'one microsecond before revision 1004' AS test_case,
    '1003' AS expected,
    COALESCE(CAST((
        SELECT revision_id
        FROM article FOR SYSTEM_TIME AS OF
            '2026-10-01 10:00:20.000000'
        WHERE article_id = 999999
    ) AS CHAR), 'NULL') AS observed;

-- Test 5: Exactly at revision 1004.
-- Expected: 1004.
SELECT
    'exactly at revision 1004' AS test_case,
    '1004' AS expected,
    COALESCE(CAST((
        SELECT revision_id
        FROM article FOR SYSTEM_TIME AS OF
            '2026-10-01 10:00:20.000001'
        WHERE article_id = 999999
    ) AS CHAR), 'NULL') AS observed;

-- Test 6: After the last revision.
-- Expected: 1007.
SELECT
    'after last revision' AS test_case,
    '1007' AS expected,
    COALESCE(CAST((
        SELECT revision_id
        FROM article FOR SYSTEM_TIME AS OF
            '2026-10-01 10:00:55.000000'
        WHERE article_id = 999999
    ) AS CHAR), 'NULL') AS observed;

-- Test 7: Equivalent instant under UTC+02:00.
-- 12:00:15 at UTC+02:00 corresponds to 10:00:15 UTC.
-- Expected: 1002.
SET @@timestamp = UNIX_TIMESTAMP();
SET time_zone = '+02:00';

SELECT
    'mid-gap at UTC+02:00' AS test_case,
    '1002' AS expected,
    COALESCE(CAST((
        SELECT revision_id
        FROM article FOR SYSTEM_TIME AS OF
            '2026-10-01 12:00:15.000000'
        WHERE article_id = 999999
    ) AS CHAR), 'NULL') AS observed;

-- Restore normal session settings.
SET @@timestamp = UNIX_TIMESTAMP();
SET time_zone = '+00:00';
