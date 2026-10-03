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
MariaDB: [VERSION]
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

The experiment will also record basic characteristics of the imported dataset, including:

* Number of articles
* Number of revisions
* Number of generated temporal rows
* Database size
* Import time

These measurements provide a baseline for the later scalability experiments.

---

# 9. Experiment 2 — [Title]

This section will document the second project experiment once its exact objective and implementation are finalized.

The README will record:

* Research question
* Experimental setup
* Method
* Expected result
* Observed result
* Measurements
* Conclusion

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

## Requirements

The project requires:

* MariaDB
* SQL client / command-line client
* Git
* The project dataset

The exact MariaDB version will be specified once the experimental environment is finalized.

## Database Setup

The database setup instructions will be added here once the schema has been finalized.

Example:

```bash
git clone <repository>
cd <repository>
```

The SQL initialization scripts can then be executed against the MariaDB instance.

---

# 13. Running the Experiments

The experiments will be organized separately from the production database schema.

A possible repository structure is:

```text
.
├── README.md
│
├── sql/
│   ├── schema/
│   │   └── ...
│   │
│   ├── experiments/
│   │   ├── temporal/
│   │   └── growth/
│   │
│   └── queries/
│
├── data/
│   └── ...
│
└── docs/
    ├── architecture/
    └── experiments/
```

Each experiment should contain enough information to reproduce its results.

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
* Can historical revisions be imported while preserving their intended temporal order?
* Does `FOR SYSTEM_TIME AS OF` return the expected article version?
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
* [ ] Finalize schema
* [ ] Finalize MariaDB environment

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
* [ ] Implement data import
* [ ] Implement required queries
* [ ] Run final tests

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
[Project-specific task]
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
