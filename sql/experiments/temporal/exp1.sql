-- Experiment 1: temporal correctness of FOR SYSTEM_TIME AS OF
--
-- Runs in its own throwaway database (exp1_temporal), so it can be re-run at
-- any time and never touches wikipedia_time_machine.
-- Needs /tmp/person1_temporal_schema.sql inside the container.
--
--   docker exec -it wikipedia-mariadb mariadb -u root -p --table
--   tee /tmp/exp1_output.txt
--   SOURCE /tmp/exp1.sql
--   notee

SET time_zone = '+00:00';

DROP DATABASE IF EXISTS exp1_temporal;
CREATE DATABASE exp1_temporal CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE exp1_temporal;

SOURCE /tmp/person1_temporal_schema.sql

-- ---------------------------------------------------------------------------
-- Test history (all times UTC)
--   Article 1: 1001  2024-01-01 10:00:00
--              1002  2024-01-02 12:00:00
--              1003  2024-01-03 09:30:15.000000   same second as 1004
--              1004  2024-01-03 09:30:15.000001   (loader separates by 1 us)
--              1005  2024-02-01 08:00:00
--   Article 2: 2001  2024-01-02 12:00:00
--              2002  2024-01-15 18:00:00
-- Last argument of the procedure = system time given to MariaDB.
-- ---------------------------------------------------------------------------

CALL apply_wikipedia_revision(1, 1001, 'Test A', 'a v1', 'u1', '2024-01-01 10:00:00.000000', '2024-01-01 10:00:00.000000');
CALL apply_wikipedia_revision(1, 1002, 'Test A', 'a v2', 'u1', '2024-01-02 12:00:00.000000', '2024-01-02 12:00:00.000000');
CALL apply_wikipedia_revision(2, 2001, 'Test B', 'b v1', 'u2', '2024-01-02 12:00:00.000000', '2024-01-02 12:00:00.000000');
CALL apply_wikipedia_revision(1, 1003, 'Test A', 'a v3', 'u1', '2024-01-03 09:30:15.000000', '2024-01-03 09:30:15.000000');
CALL apply_wikipedia_revision(1, 1004, 'Test A', 'a v4', 'u1', '2024-01-03 09:30:15.000000', '2024-01-03 09:30:15.000001');
CALL apply_wikipedia_revision(2, 2002, 'Test B', 'b v2', 'u2', '2024-01-15 18:00:00.000000', '2024-01-15 18:00:00.000000');
CALL apply_wikipedia_revision(1, 1005, 'Test A', 'a v5', 'u1', '2024-02-01 08:00:00.000000', '2024-02-01 08:00:00.000000');

SET @@timestamp = DEFAULT;

-- ---------------------------------------------------------------------------
-- Test harness
-- ---------------------------------------------------------------------------

CREATE TABLE verdict (
  case_no     INT PRIMARY KEY,
  description VARCHAR(70),
  asked_text  VARCHAR(30),
  session_tz  VARCHAR(10),
  expected    BIGINT NULL,
  got         BIGINT NULL,
  result      VARCHAR(4)
);

DELIMITER //
CREATE PROCEDURE check_case(
  IN p_no INT, IN p_desc VARCHAR(70), IN p_article INT,
  IN p_ts VARCHAR(30), IN p_expected BIGINT)
BEGIN
  SET @got = NULL;
  SET @q = CONCAT(
    'SELECT revision_id INTO @got FROM article FOR SYSTEM_TIME AS OF TIMESTAMP ''',
    p_ts, ''' WHERE article_id = ', p_article);
  PREPARE s FROM @q;
  EXECUTE s;
  DEALLOCATE PREPARE s;
  INSERT INTO verdict VALUES
    (p_no, p_desc, p_ts, @@session.time_zone, p_expected, @got,
     IF(p_expected <=> @got, 'PASS', 'FAIL'));
END //
DELIMITER ;

SET time_zone = '+00:00';

-- Article 1: before, on, between and around revisions
CALL check_case( 1, 'A1 just before the first revision',        1, '2024-01-01 09:59:59.999999', NULL);
CALL check_case( 2, 'A1 exactly on revision 1001',              1, '2024-01-01 10:00:00.000000', 1001);
CALL check_case( 3, 'A1 between 1001 and 1002',                 1, '2024-01-01 15:00:00.000000', 1001);
CALL check_case( 4, 'A1 one microsecond before 1002',           1, '2024-01-02 11:59:59.999999', 1001);
CALL check_case( 5, 'A1 exactly on revision 1002',              1, '2024-01-02 12:00:00.000000', 1002);
CALL check_case( 6, 'A1 one microsecond before 1003',           1, '2024-01-03 09:30:14.999999', 1002);
CALL check_case( 7, 'A1 exactly on 1003 (same second as 1004)', 1, '2024-01-03 09:30:15.000000', 1003);
CALL check_case( 8, 'A1 one microsecond later: 1004',           1, '2024-01-03 09:30:15.000001', 1004);
CALL check_case( 9, 'A1 between 1004 and 1005',                 1, '2024-01-20 00:00:00.000000', 1004);
CALL check_case(10, 'A1 exactly on revision 1005',              1, '2024-02-01 08:00:00.000000', 1005);
CALL check_case(11, 'A1 long after the last revision',          1, '2025-01-01 00:00:00.000000', 1005);

-- Article 2: independent timeline (article 1 also changed at 2024-01-02 12:00)
CALL check_case(12, 'A2 exactly on revision 2001',              2, '2024-01-02 12:00:00.000000', 2001);
CALL check_case(13, 'A2 between 2001 and 2002',                 2, '2024-01-10 00:00:00.000000', 2001);
CALL check_case(14, 'A2 exactly on revision 2002',              2, '2024-01-15 18:00:00.000000', 2002);

-- Same date text, other session time zone
SET time_zone = '+02:00';
CALL check_case(15, 'A1 text 12:00 read as UTC+2 = 10:00 UTC',  1, '2024-01-02 12:00:00.000000', 1001);
SET time_zone = '-05:00';
CALL check_case(16, 'A1 text 07:00 read as UTC-5 = 12:00 UTC',  1, '2024-01-02 07:00:00.000000', 1002);

SET time_zone = '+00:00';

-- ---------------------------------------------------------------------------
-- Results
-- ---------------------------------------------------------------------------

SELECT * FROM verdict ORDER BY case_no;

SELECT COUNT(*) AS cases,
       SUM(result = 'PASS') AS passed,
       SUM(result = 'FAIL') AS failed,
       IF(COUNT(*) = 16 AND SUM(result = 'FAIL') = 0, 'ALL PASS', 'SOME FAIL') AS summary
FROM verdict;

SELECT article_id, revision_id, row_start, row_end,
       TIMESTAMPDIFF(MICROSECOND, revision_date, row_start) AS drift_us
FROM article FOR SYSTEM_TIME ALL
ORDER BY article_id, row_start;

SELECT COUNT(*) AS all_versions FROM article FOR SYSTEM_TIME ALL;
SELECT COUNT(*) AS current_rows FROM article;
