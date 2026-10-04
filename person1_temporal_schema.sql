-- Wikipedia Time Machine
-- Person 1: MariaDB / Temporal Database Setup
--
-- IMPORTANT:
-- Select the target database before running this file.
-- Example:
--   USE wikipedia_time_machine;
--
-- This file intentionally does NOT contain a USE statement.
-- This makes it reusable for the real database and test databases.

DROP PROCEDURE IF EXISTS apply_wikipedia_revision;

CREATE TABLE IF NOT EXISTS article (
    article_id INT NOT NULL,
    revision_id BIGINT NOT NULL,
    title VARCHAR(255) NOT NULL,
    content LONGTEXT,
    author VARCHAR(255),
    revision_date DATETIME(6),

    row_start TIMESTAMP(6) GENERATED ALWAYS AS ROW START,
    row_end   TIMESTAMP(6) GENERATED ALWAYS AS ROW END,

    PERIOD FOR SYSTEM_TIME (row_start, row_end),

    PRIMARY KEY (article_id)
)
WITH SYSTEM VERSIONING
PARTITION BY SYSTEM_TIME (
    PARTITION p_history HISTORY,
    PARTITION p_current CURRENT
);

DELIMITER //

CREATE PROCEDURE apply_wikipedia_revision(
    IN p_article_id INT,
    IN p_revision_id BIGINT,
    IN p_title VARCHAR(255),
    IN p_content LONGTEXT,
    IN p_author VARCHAR(255),
    IN p_revision_date DATETIME(6),
    IN p_system_time DATETIME(6)
)
MODIFIES SQL DATA
BEGIN
    IF EXISTS (
        SELECT 1
        FROM article
        WHERE article_id = p_article_id
    ) THEN
        SET @@timestamp = UNIX_TIMESTAMP(p_system_time);

        UPDATE article
        SET
            revision_id = p_revision_id,
            title = p_title,
            content = p_content,
            author = p_author,
            revision_date = p_revision_date
        WHERE article_id = p_article_id;
    ELSE
        SET @@timestamp = UNIX_TIMESTAMP(p_system_time);

        INSERT INTO article
        (
            article_id,
            revision_id,
            title,
            content,
            author,
            revision_date
        )
        VALUES
        (
            p_article_id,
            p_revision_id,
            p_title,
            p_content,
            p_author,
            p_revision_date
        );
    END IF;
END //

DELIMITER ;
