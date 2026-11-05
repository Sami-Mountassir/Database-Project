# Wikipedia Time Machine


# 1. Project Goal

The goal of this project is to investigate how a **temporal database** can be used to build a Wikipedia-like "time machine".

Instead of storing only the current state of an article, the database should preserve its historical versions so that the state of an article can be retrieved at a specific point in time.

The project focuses on using **MariaDB system-versioned tables** to maintain this historical information and evaluating whether this approach is suitable for storing and querying a large collection of article revisions.

The project therefore has two main aspects:

1. **Correctness:** Can we accurately reconstruct an article as it existed at a particular point in time?
2. **Scalability:** How does the database behave as the amount of historical data grows?

---

# 2. Why System-Versioned Tables?

A Wikipedia article can be modified many times during its lifetime.

If we only keep the latest version, historical information is lost:

```text
Version 1
   ↓
UPDATE
   ↓
Version 2
   ↓
UPDATE
   ↓
Version 3

Only Version 3 remains
```

A system-versioned table instead preserves the different states:

```text
Version 1 ────────┐
Version 2 ────────┤
Version 3 ────────┤──→ Temporal history
Version 4 ────────┘
```

This makes it possible to query the database according to a point in time.

For example:

```sql
FOR SYSTEM_TIME AS OF ...
```

can be used to ask which version of an article was present at a particular moment.

---

# 3. Temporal Model

The central entity of the project is an article and its historical revisions.

A revision is associated with:

* an `article_id`
* a revision date
* the article content and relevant metadata

Our proposed identifier for a version is:

```text
(article_id, ver_date)
```

where:

* `article_id` identifies the article.
* `ver_date` identifies the revision in the article's timeline.

Conceptually:

```text
                 ARTICLE
                    │
                    │
              has revisions
                    │
                    ▼
              ARTICLE VERSION
                    │
          ┌─────────┼─────────┐
          │         │         │
     article_id  ver_date  content
```

The exact relational schema will be finalized as the implementation progresses.

---

# 4. Historical Revision Dates

A major issue in this project is the difference between the **historical revision date** and the **time at which the data is imported into MariaDB**.

For example:

```text
Historical data:

Article 42
Revision date: 2019-04-12


Import:

2026
```

If the historical revision is simply inserted into a system-versioned table during the 2026 import, MariaDB's temporal information may naturally correspond to the database operation rather than the historical revision.

That would not represent the historical timeline we are trying to reconstruct.

## Our approach

We therefore investigate how MariaDB allows us to **control the temporal context during the historical-data import**.

The intended process is:

```text
Historical revision date
          │
          ▼
Controlled temporal timestamp
          │
          ▼
MariaDB system-versioned table
          │
          ▼
Historical temporal state
```

The objective is for the temporal history represented by MariaDB to correspond to the historical revision timeline rather than simply reflecting when the dataset was imported.

This mechanism will be validated experimentally before being used in the final implementation.

---

# 5. Architecture

The overall architecture is:

```text
              Wikipedia Revision Data
                       │
                       ▼
                Import Process
                       │
                       │
             Historical dates
                       │
                       ▼
              MariaDB Database
                       │
              ┌────────┴────────┐
              │                 │
              ▼                 ▼
       Current Articles    Temporal History
                                │
                                ▼
                       Temporal Queries
                                │
                                ▼
                    Article at time T
```

The architecture separates the historical data source from the temporal database and allows the database to be evaluated independently through controlled experiments.

---

# 6. MariaDB Version

The project uses:

```text
MariaDB: 13.0.2-MariaDB-ubu2604
```

The exact version is important because temporal-table behaviour and available system-versioning functionality depend on the database version.

The version used for the experiments will therefore be documented explicitly to make the results reproducible.

---

# 7. Experimental Methodology

The project is not only an implementation exercise.

An important part of the work is experimentally determining whether our temporal model behaves as expected.

Each experiment follows a controlled process:

```text
Question
   ↓
Experiment setup
   ↓
Database operation
   ↓
Observe temporal history
   ↓
Compare with expected result
   ↓
Record measurements
   ↓
Conclusion
```

The experiments will be documented together with:

* the hypothesis or question being investigated
* the database state before the experiment
* the SQL operations performed
* the expected result
* the observed result
* measurements
* the conclusion

This allows the results to be reproduced and compared between experiments.

---

# 8. Experiment 1 — Temporal Correctness

## Research Question

> **Does our temporal model actually work?**

The first experiment focuses on validating the fundamental temporal behaviour of the system.

The main chain being tested is:

```text
Revision date
      ↓
System timestamp
      ↓
FOR SYSTEM_TIME AS OF
      ↓
Correct article version?
```

The experiment therefore verifies that a historical revision can be inserted with the intended temporal information and subsequently retrieved correctly using MariaDB's temporal querying functionality.

### Example

Suppose an article has a historical revision:

```text
article_id = 42
revision date = 2020-05-17
```

We want to verify that a temporal query corresponding to that point in time returns the expected version of article `42`.

Conceptually:

```text
Historical revision
        │
        ▼
2020-05-17
        │
        ▼
MariaDB temporal history
        │
        ▼
FOR SYSTEM_TIME AS OF
        │
        ▼
Expected article version
```

### Measurements

Counts from the test database (`docs/experiment1_output.txt`):

| Item | Value |
| ---- | ----- |
| Articles | 2 |
| Revisions loaded | 7 |
| Stored versions (`FOR SYSTEM_TIME ALL`) | 7 |
| Current rows | 2 |

---
## Result

**Goal.** Show that FOR SYSTEM_TIME AS OF returns the revision that was current at any chosen moment.

**Method.** 7 revisions of 2 test articles were loaded through apply_wikipedia_revision, including two revisions in the same second. They were then queried at 16 moments: before, on and between revisions, one microsecond around boundaries, and under a different session time zone.

**Result.** 16 of 16 cases returned the expected revision on MariaDB 13.0.2 (output in docs/experiment1_output.txt). The two revisions in the same second (1003 and 1004) were stored one microsecond apart and both were returned correctly. The current rows end at 2106-02-07 rather than 2038-01-19, because recent MariaDB versions have a larger TIMESTAMP range.

**Conclusion.** The time model is correct to the microsecond when the session time zone is UTC, which every project tool sets.
# 9. Experiment 2 — Real Wikipedia History Import

## Research Question

> **Can we load real, multi-year Wikipedia revision histories so that every revision is stored exactly once, in the right order, with the right content, and can be retrieved at its own moment in time?**

Experiment 1 validated the temporal model on a few hand-made revisions. This experiment checks the same promise on **real data**.

## Setup

```text
Wikipedia API
     │   pipeline/download.py   (all revisions of selected articles, oldest first)
     ▼
raw JSON
     │   pipeline/transform.py  (keep id, title, timestamp, author, content; skip hidden revisions)
     ▼
cleaned JSON
     │   pipeline/load_real.py  (replay revisions in time order through apply_wikipedia_revision)
     ▼
MariaDB system-versioned table `article`
     │   pipeline/verify_load.py (independent check against the JSON)
     ▼
report: "checked N revisions, 0 problem(s)"
```

Two revisions of the same article can share the same second. The loader separates them by one microsecond each, so no revision is lost.

## Method

`verify_load.py` re-reads the cleaned JSON and, for **every** revision, asks the database:

1. `FOR SYSTEM_TIME AS OF <revision time>` must return this revision (same revision id and same content hash).
2. `FOR SYSTEM_TIME AS OF <one microsecond earlier>` must return the previous revision (or nothing for the first one).
3. The number of stored versions of each article must equal the number of loaded revisions.
## Expected result

0 problems: the database holds exactly the revisions of the source file, in the right order.

## Observed result and measurements

All rows use the selected window **2024-01-01T00:00:00Z through
2026-10-22T00:00:00Z**, inclusive UTC. Text MB means decimal UTF-8 content MB,
excluding JSON metadata and database storage overhead.

| Article | Usable revisions | Stored versions, including current* | Text MB |
|---|---:|---:|---:|
| Great Wall of China | 111 | 111 | 6.628311 |
| Photosynthesis | 129 | 129 | 14.518570 |
| Apollo 11 | 227 | 227 | 43.510335 |
| Leonardo da Vinci | 217 | 217 | 30.314905 |
| Coffee | 333 | 333 | 47.618482 |
| **Total** | **1017** | **1017** | **142.590603** |

*Stored counts are inferred from the successful verifier's per-article
`FOR SYSTEM_TIME ALL` count-equality checks, not a separately retained SQL count
listing. These counts include each article's current version.

| Measurement | Result | Repository evidence |
|---|---|---|
| Dataset window, article counts and text sizes | As above | [Person 2 dataset measurements](README_PERSON2.md#real-dataset), cross-checked against the local approved manifest and JSON |
| Cleaned JSON size | 143,662,715 bytes | [Person 2 dataset measurements](README_PERSON2.md#real-dataset) |
| Full verification | `checked 1017 revisions, 0 problem(s)` | [Committed database output](docs/real_data_verification.txt) |
| Stored version counts | Equal to usable counts above | [Verifier count checks](pipeline/verify_load.py) and successful committed output |
| Actual measured load time for this import | **Missing: no timing record tied to this verified import was found** | Verification output contains no duration; benchmark CSV timings concern separate Experiment 3 runs |
| Database storage size for this import | Not recorded in the retained Experiment 2 output | Dataset text/JSON sizes above are not database sizes |
| Timestamp drift | `bad_drift = 0` reported in the earlier handover | [Person 2 handover attribution](README_PERSON2.md#real-database-verification-and-friday-checks); no raw real-data drift-query output is committed |

The local manifest is distributed with the approved dataset; large data files are
excluded from Git. The committed Person 2 README records its measured values and
checksum. Rebuild commands and distribution details are at the top of
[README_PERSON2.md](README_PERSON2.md#rebuild-the-approved-real-dataset).

Request for Ghofrane (prepared, not sent): please provide any existing elapsed-time
record for the verified real-data import, with units, timing boundaries and the
associated command/database/dataset. Please also provide the original drift-query
output if available. No reset or reload is needed to answer this request.

## Conclusion

The committed full-verification result supports that the selected articles have
the expected number of stored versions and that every checked revision is
retrievable at its effective historical timestamp with the expected revision ID
and content hash. Checks immediately before each timestamp also passed. This
validates the imported history against the approved source file under the
verifier's checks; content equality is assessed through hashes. It does not
establish import throughput, query scalability or storage efficiency. Load-time
evidence remains missing, so no performance conclusion is drawn. The verified
database was not reset or reloaded for this documentation review.

---

# 10. Experiment 3 — Growth and Partitioning

One of the required experiments is to investigate how the database behaves as the amount of temporal history grows.

This experiment focuses on **growth and partitioning**.

The motivation is straightforward:

Every historical revision that is preserved contributes additional data to the temporal table.

Therefore, as the number of revisions increases:

```text
More revisions
      ↓
More historical rows
      ↓
Larger database
      ↓
Potentially higher query/storage costs
```

The experiment will investigate this growth and evaluate the effect of partitioning.

## Measurements

For different dataset sizes, we will record:

* Number of articles
* Number of revisions
* Number of generated rows
* Database size
* Import time
* Query performance
* Partition configuration

The results will allow us to compare the behaviour of the system as the temporal history becomes larger.

### Conceptual experiment

```text
Small dataset
      │
      ▼
Measure
      │
      ▼
Medium dataset
      │
      ▼
Measure
      │
      ▼
Large dataset
      │
      ▼
Measure
      │
      ▼
Compare growth
```

Partitioning will then be evaluated as a possible way of managing the resulting temporal data.

---

# 11. Experimental Metrics

The following metrics will be tracked throughout the experiments.

| Metric               | Purpose                              |
| -------------------- | ------------------------------------ |
| Number of articles   | Measures dataset size                |
| Number of revisions  | Measures historical density          |
| Number of rows       | Measures temporal storage growth     |
| Database size        | Measures storage requirements        |
| Import time          | Measures loading performance         |
| Query time           | Measures temporal query performance  |
| Number of partitions | Evaluates partitioning configuration |

The same metrics should be collected consistently across comparable experiments.

---

# 12. Setup
 
All commands are for **Windows PowerShell** and are run from the repository root (the folder that contains `pipeline/` and `README.md`).
 
> **Two kinds of prompt.** `PS C:\...>` is PowerShell: use it for `docker`, `python` and `git`.
> `MariaDB [...]>` is the SQL client: use it only for SQL. Type `exit` to leave the SQL client.
 
## Requirements
 
* Docker Desktop (running)
* Python 3 (the team uses 3.13) and `pip`
* Git
* The Python packages `PyMySQL` and `streamlit`
* MariaDB **13.0.2** (from the Docker image, see below)
## 1. Get the code
 
```powershell
git clone https://github.com/Sami-Mountassir/Database-Project
cd Database-Project
python -m pip install PyMySQL streamlit
```
 
## 2. Start MariaDB
 
Choose your own root password.
 
```powershell
docker run --name wikipedia-mariadb -e MARIADB_ROOT_PASSWORD=choose_a_password -p 3306:3306 -d mariadb:latest --max-allowed-packet=134217728
docker ps
```
 
`docker ps` must show `wikipedia-mariadb` with status `Up`. Wait about 20 seconds on the first start. Later, use `docker stop wikipedia-mariadb` and `docker start wikipedia-mariadb`; do not run the `docker run` line twice.
 
If port 3306 is already used on your machine, use `-p 3307:3306` and add `--port 3307` to every Python command below.
 
## 3. Create the database, the user and the schema
 
```powershell
docker cp person1_temporal_schema.sql wikipedia-mariadb:/tmp/person1_temporal_schema.sql
docker exec -it wikipedia-mariadb mariadb -u root -p
```
 
In the SQL client:
 
```sql
DROP DATABASE IF EXISTS wikipedia_time_machine;
CREATE DATABASE wikipedia_time_machine CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'bench'@'%' IDENTIFIED BY 'bench';
GRANT ALL PRIVILEGES ON wikipedia_time_machine.* TO 'bench'@'%';
GRANT ALL PRIVILEGES ON timemachine_bench_repeat.* TO 'bench'@'%';
GRANT ALL PRIVILEGES ON exp1_temporal.* TO 'bench'@'%';
FLUSH PRIVILEGES;
USE wikipedia_time_machine;
SOURCE /tmp/person1_temporal_schema.sql
SHOW TABLES;
```
 
`SHOW TABLES` must list `article`. Type `exit` to leave the client. (`DROP DATABASE` deletes everything in that database: use it only on a fresh setup.)
 
Check that the `bench` user can set the session clock, which the loader needs:
 
```powershell
docker exec -it wikipedia-mariadb mariadb -u bench -pbench -e "SET timestamp = 1700000000; SELECT @@timestamp;"
```
 
It must print `1700000000.000000`.
 
## 4. Load and verify the sample data
 
```powershell
python pipeline/load_real.py --input samples/wikipedia_revisions.json --database wikipedia_time_machine --user bench --password bench
python pipeline/verify_load.py --input samples/wikipedia_revisions.json --database wikipedia_time_machine
```
 
The second command must end with `checked 20 revisions, 0 problem(s)`. Load into an **empty** database only: loading twice corrupts the timeline. To start over, repeat step 3.
 
## 5. Run the tests
 
```powershell
python -m unittest discover -s tests -v
```
 
The last line must be `OK`.
 
## 6. Run the interface
 
```powershell
python -m streamlit run ui/app.py
```
 
The browser opens at `http://localhost:8501`. The sidebar defaults (host `127.0.0.1`, port `3306`, user `bench`, password `bench`, database `wikipedia_time_machine`) match the setup above.
 
* Choose an article.
* Choose the moment either with the **revision slider** or with **exact date and time** (UTC).
* The page shows the article **as it was** at that moment: title, revision id, author, edit date and the stored text.
* A date before the first stored version shows "did not exist yet".
* The **Changes vs previous version** tab shows a side-by-side comparison with the previous version.
Limits of this version: the content is **wikitext** (raw `[[links]]` and `{{templates}}`), not a rendered web page, and all times are UTC.
 
## 7. Load the full dataset (optional)
 
The downloaded data is large and is not stored in Git (`data/` is ignored). The exact commands, the article list, the time window and the dataset size are in `README_PERSON2.md`. The order is always: download, transform, **reset the database (step 3)**, load, verify.
 
## Troubleshooting
 
| Symptom | Cause and fix |
| ------- | ------------- |
| `docker: error during connect` | Docker Desktop is not running. Start it and wait until it says it is running. |
| `port is already allocated` | Something else uses 3306. Use `-p 3307:3306` and `--port 3307`. |
| `docker cp ... file not found` / `No such file or directory` | You are not in the repository root. Run `dir` and check that `person1_temporal_schema.sql` is listed. |
| `ERROR: Failed to open file '/tmp/person1_temporal_schema.sql'` | The `docker cp` line of step 3 was skipped. Run it, then `SOURCE` again. |
| A `docker` or `python` command typed after `MariaDB [...]>` shows `->` lines | You are inside the SQL client. Type `\c`, then `exit`, then run it in PowerShell. |
| `Can't connect to MySQL server` | The container is still starting (check `docker logs wikipedia-mariadb` for "ready for connections") or the port is wrong. |
| `Access denied for user 'bench'` | The user lines of step 3 did not run. Run them again, then `FLUSH PRIVILEGES;`. |
| `Access denied; you need ... SUPER privilege` | Add `--user root --password <root password>` to the Python command. |
| `versions stored=X, expected=Y` from `verify_load.py` | The database was not empty before loading. Repeat step 3, then load again. |
| `Got a packet bigger than 'max_allowed_packet'` | Start the container with `--max-allowed-packet=134217728` as in step 2. |
| `ModuleNotFoundError: No module named 'pymysql'` or `streamlit` | Install with `python -m pip install PyMySQL streamlit` (use `python -m pip`, not `pip`). |
| `Start directory is not importable: 'tests'` | You are not in the repository root. |
 
---
 
# 13. Repository Structure
 
```text
.
├── README.md                      this file
├── README_PERSON1.md              schema and temporal-model notes
├── README_PERSON2.md              data pipeline and real dataset
├── person1_temporal_schema.sql    schema + apply_wikipedia_revision procedure
├── bench.py, bench_repeat.py      repeated benchmark (Experiment 3)
│
├── pipeline/
│   ├── download.py                download revisions from the Wikipedia API
│   ├── transform.py               clean the raw JSON
│   ├── load_real.py               replay revisions into MariaDB in time order
│   ├── verify_load.py             check the database against the JSON
│   └── make_subset.py             create 25% / 50% datasets for growth runs
│
├── sql/
│   └── experiments/temporal/      Experiment 1 (temporal correctness)
│
├── samples/
│   └── wikipedia_revisions.json   small sample (3 articles, 20 revisions)
│
├── ui/
│   ├── app.py                     Streamlit interface
│   └── queries.py                 all SQL used by the interface
│
├── tests/                         unit tests (python -m unittest discover -s tests)
├── docs/                          experiment outputs and screenshots
└── data/                          downloaded datasets (not in Git)
```
 
Each experiment folder or file contains enough information to reproduce its results.
 
---


# 14. Results

Experimental results will be added as the experiments are completed.

For each experiment, the results should include:

### Setup

What dataset and database configuration were used?

### Procedure

What operations were performed?

### Results

What did MariaDB actually produce?

### Measurements

What were the observed execution times, row counts, database sizes, etc.?

### Conclusion

What does the experiment tell us about the temporal model?

---

# 15. Open Questions

The following questions are currently part of the investigation:

* How should historical revision dates be mapped to MariaDB system timestamps?
  -The stored procedure `apply_wikipedia_revision` sets `@@timestamp` to the revision's own time before each insert or update, so `row_start` is the historical moment (`person1_temporal_schema.sql`; `docs/experiment1_output.txt`, `drift_us` is 0 for every row except 1004, which is 1 on purpose).
* Can historical revisions be imported while preserving their intended temporal order?
  -Yes. The loader sorts each article's revisions chronologically and `verify_load.py` found 0 problems across 1,017 real revisions (`docs/real_data_verification.txt`).
* Does `FOR SYSTEM_TIME AS OF` return the expected article version?
  - Yes, 16 of 16 test cases passed, including boundaries one microsecond apart (`docs/experiment1_output.txt`).
* How many temporal rows are generated as revisions accumulate?
* How does database size grow with the number of revisions?
* How does temporal query performance change as the dataset grows?
* Does partitioning improve the management or performance of the temporal data?
* What partitioning strategy is appropriate for the resulting history?

These questions will be progressively resolved through the experiments and implementation work.

---

# 16. Current Status

### Project setup

* [x] Define project goal
* [x] Identify temporal database approach
* [x] Define initial temporal model
* [x] Identify historical-date challenge
* [x] Finalize schema
* [x] Finalize MariaDB environment

### Temporal experiments

* [ ] Establish baseline MariaDB temporal behaviour
* [ ] Test historical timestamp handling
* [ ] Validate `FOR SYSTEM_TIME AS OF`
* [ ] Record revision/row/storage/import measurements

### Growth and partitioning

* [ ] Define dataset sizes
* [ ] Measure database growth
* [ ] Measure import performance
* [ ] Measure query performance
* [ ] Implement/test partitioning
* [ ] Compare results

### Implementation

* [ ] Complete database implementation
* [x] Implement data import
* [ ] Implement required queries
* [ ] Run final tests

## Real data and interface
 
* [x] Download, transform and load pipeline for real revisions
* [x] Independent verification tool (`verify_load.py`)
* [x] Interface version 0 (article, moment, side-by-side changes)
* [ ] Real multi-year dataset loaded and verified
* [ ] Interface checked on the real dataset

---

# 17. Project Timeline

The project is divided into four main tasks.

```text
Task 1
Temporal experiments
        │
        ▼
Validate temporal model
        │
        ▼
Task 2
Real-data import and interface
        │
        ▼
Task 3
Growth + partitioning experiment
        │
        ▼
Evaluate scalability
        │
        ▼
Task 4
Coding / final implementation
```

The README will be updated throughout the project so that the documented architecture and experimental results remain synchronized with the implementation.

---

# 18. Conclusion

The Wikipedia Time Machine project investigates the use of MariaDB system-versioned tables for preserving and querying the historical evolution of articles.

The project combines database modelling, implementation, and experimental evaluation.

The first experimental stage focuses on validating the core temporal model:

```text
revision date
      ↓
system timestamp
      ↓
FOR SYSTEM_TIME AS OF
      ↓
correct historical article
```

The later growth and partitioning experiment evaluates how the temporal database behaves as the amount of historical data increases.

Together, these experiments allow us to evaluate both the **correctness** and the **scalability** of the proposed temporal architecture.
