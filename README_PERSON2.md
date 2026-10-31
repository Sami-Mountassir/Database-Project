# Person 2: Wikipedia pipeline

Run commands from the repository root (the folder containing `pipeline/`).

```sh
python -m unittest discover -s tests -v
python pipeline/download.py --start 2020-01-01T00:00:00Z --end 2025-01-01T00:00:00Z
python pipeline/transform.py
python -m pip install PyMySQL
python pipeline/load_real.py --database wikipedia_time_machine
```

The downloader follows `rvcontinue` in batches of at most 50 content revisions,
oldest first. The default fetches the entire five-year window for all five default
articles. Use repeated `--article "Title"` options to select articles. An optional
`--limit 100` caps revisions per article and can truncate the requested years;
omit it for the full window. Newly created articles may have a shorter history.
Full content histories can be large. Generated data stays under ignored `data/`.
API/network errors are reported per article, and failed articles are omitted
rather than saved with partial histories. Successful articles are still saved;
check the failure messages and rerun failed titles separately. Repeated continuation
tokens raise an error. There are no automatic retries.

Transformation skips hidden/unavailable content and preserves genuine empty text.
The loader also rejects missing content and the old placeholder, including in older
cleaned datasets. Revisions are sorted chronologically per article, with revision ID
breaking ties and offsets of 0, 1, 2, ... microseconds for identical timestamps.
The database session is set to UTC before calling the existing stored procedure.

## Small sample

`samples/wikipedia_revisions.json` contains exactly 3 articles and 20 cleaned
revisions (7 Great Wall of China, 7 Photosynthesis, 6 Apollo 11). These are unmodified
revision records selected at evenly spaced indices from the existing local
`data/sample/cleaned_revisions.json` Wikipedia download. This small fixture covers
2025-2026, not the multi-year window used for new downloads. No new network download
was needed to create it. It is outside ignored directories and ready to add to Git.

Initialize the existing `person1_temporal_schema.sql` in a fresh database using
Person 1's setup instructions, then load the sample directly (no transform needed):

```sh
python -m pip install PyMySQL
python pipeline/load_real.py --input samples/wikipedia_revisions.json --database wikipedia_time_machine --user bench --password bench
```

Use a fresh database for repeat imports so historical revisions are not replayed
onto an already populated timeline. Connection options also include `--host` and
`--port`. The existing procedure targets `article`; `--table` is retained for CLI
compatibility; values other than `article` are rejected.

Wikipedia text remains subject to Wikipedia's applicable CC BY-SA/GFDL terms.
Each record retains its author and revision ID; the following permanent URLs and
history links provide revision provenance and contributor attribution:

- [Great Wall of China history](https://en.wikipedia.org/w/index.php?title=Great%20Wall%20of%20China&action=history)
  - [1327388334](https://en.wikipedia.org/w/index.php?oldid=1327388334) (2025-12-14T03:26:02Z)
  - [1332568782](https://en.wikipedia.org/w/index.php?oldid=1332568782) (2026-01-12T15:51:47Z)
  - [1348327487](https://en.wikipedia.org/w/index.php?oldid=1348327487) (2026-04-12T01:44:25Z)
  - [1353692202](https://en.wikipedia.org/w/index.php?oldid=1353692202) (2026-05-11T20:07:26Z)
  - [1356002776](https://en.wikipedia.org/w/index.php?oldid=1356002776) (2026-05-25T05:03:46Z)
  - [1357976059](https://en.wikipedia.org/w/index.php?oldid=1357976059) (2026-06-05T20:30:44Z)
  - [1374512030](https://en.wikipedia.org/w/index.php?oldid=1374512030) (2026-09-12T14:41:42Z)
- [Photosynthesis history](https://en.wikipedia.org/w/index.php?title=Photosynthesis&action=history)
  - [1328455398](https://en.wikipedia.org/w/index.php?oldid=1328455398) (2025-12-20T00:03:34Z)
  - [1341738923](https://en.wikipedia.org/w/index.php?oldid=1341738923) (2026-03-04T19:58:58Z)
  - [1348223446](https://en.wikipedia.org/w/index.php?oldid=1348223446) (2026-04-11T12:27:02Z)
  - [1348234734](https://en.wikipedia.org/w/index.php?oldid=1348234734) (2026-04-11T13:52:03Z)
  - [1357968301](https://en.wikipedia.org/w/index.php?oldid=1357968301) (2026-06-05T19:46:25Z)
  - [1369485787](https://en.wikipedia.org/w/index.php?oldid=1369485787) (2026-08-15T07:47:06Z)
  - [1371284103](https://en.wikipedia.org/w/index.php?oldid=1371284103) (2026-08-25T17:04:29Z)
- [Apollo 11 history](https://en.wikipedia.org/w/index.php?title=Apollo%2011&action=history)
  - [1347262407](https://en.wikipedia.org/w/index.php?oldid=1347262407) (2026-04-05T17:50:38Z)
  - [1348104921](https://en.wikipedia.org/w/index.php?oldid=1348104921) (2026-04-10T18:29:32Z)
  - [1349847975](https://en.wikipedia.org/w/index.php?oldid=1349847975) (2026-04-19T04:52:07Z)
  - [1350374639](https://en.wikipedia.org/w/index.php?oldid=1350374639) (2026-04-21T15:38:24Z)
  - [1357060873](https://en.wikipedia.org/w/index.php?oldid=1357060873) (2026-05-31T14:46:30Z)
  - [1371120273](https://en.wikipedia.org/w/index.php?oldid=1371120273) (2026-08-24T18:22:02Z)

## Historical sample validation limits

The following describes the earlier sample review; the real dataset verification below supersedes its pending database status. Unit tests mock network and database access. A live API request was blocked by
local socket permissions during review. No MariaDB client or running Docker daemon
was available, so actual `row_start`/`row_end`, microsecond preservation and AS OF
results still need verification on the team's MariaDB instance. The seven procedure
arguments and six-digit timestamp formatting match `person1_temporal_schema.sql`.
The database/table character set must support the Wikipedia text (prefer utf8mb4),
and server settings must permit the procedure's historical `SET @@timestamp`.
The sample was checked against the existing raw API download: all 20 records match.


## Real dataset

Final approved window: **2024-01-01T00:00:00Z through 2026-10-22T00:00:00Z**, inclusive UTC.
The 2024-2026 dataset was selected from the preserved larger 2023-2026 download,
not independently downloaded. The original download contained 1,504 raw revisions;
transformation retained 1,502. Selection excluded 485 usable revisions before 2024,
leaving **1,017** usable revisions. Two unavailable Apollo 11 revisions
(1354949872 and 1355671368) were excluded by the transformer.

MB below means decimal MB (UTF-8 content bytes / 1,000,000), excluding JSON metadata.

| Article | Revisions | First UTC revision | Last UTC revision | Text MB |
|---|---:|---|---|---:|
| Great Wall of China | 111 | 2024-01-13T02:13:29Z | 2026-09-12T14:41:42Z | 6.628311 |
| Photosynthesis | 129 | 2024-01-03T02:20:32Z | 2026-10-08T19:44:08Z | 14.518570 |
| Apollo 11 | 227 | 2024-01-08T18:40:48Z | 2026-10-21T12:19:47Z | 43.510335 |
| Leonardo da Vinci | 217 | 2024-01-02T02:26:24Z | 2026-09-30T05:14:33Z | 30.314905 |
| Coffee | 333 | 2024-01-04T09:17:29Z | 2026-10-20T04:05:07Z | 47.618482 |
| TOTAL | 1017 | 2024-01-02T02:26:24Z | 2026-10-21T12:19:47Z | 142.590603 |

Total text: **142,590,603 bytes**. Cleaned JSON: **143,662,715 bytes**.
The actual earliest/latest timestamps in the total row differ from the selected window.
Counts, timestamps, content sizes and cleaned SHA-256 were independently checked
against the local approved JSON during this final review on 2026-10-31.

### Provenance and reproducible commands

The preserved `data/real/download.log`, `DAY2_REPORT.md`, candidate manifest and
preparation script document the historical download/transform/preparation stages.
The following download/transform commands reproduce those stages with the current CLI;
exact historical shell invocations were not retained. They were **not rerun** during
this review. Use a separate fresh checkout with no existing data to preserve originals.
Wikipedia can suppress or change availability of old revisions, so a fresh fetch is
not guaranteed to reproduce the approved byte checksum.

```powershell
python pipeline/download.py --start 2023-01-01T00:00:00Z --end 2026-10-22T00:00:00Z --output data/real/raw.json
python pipeline/transform.py --input data/real/raw.json --output data/real/cleaned.json
python pipeline/prepare_2024_candidate.py
```

No `--limit` was used; the defaults select all five articles above. The tracked
`pipeline/prepare_2024_candidate.py` preserves the original ignored preparation
script's logic, with its machine-specific repository path replaced by a path
relative to the script. It re-transforms raw data and checks equality with source
cleaned records, filters the inclusive UTC window, checks IDs/ordering/content,
and writes the candidate JSON, manifest, report, checksums and ZIP. It refuses
an existing `data/real/2024_candidate` directory. It is tied to this historical
1,017-revision / 142,590,603-byte snapshot and intentionally rejects different data.
It was inspected and syntax-checked, not rerun over existing artifacts.

Generated manifests/reports retain their historical candidate and approval-pending
labels. These describe preparation time; the later approval, Drive sharing and
Ghofrane's successful load are confirmed by Moaz's final handover. They are
preserved unchanged so the distributed checksums remain valid.

Loading syntax below is for reproduction on a **separate empty database** prepared
with Person 1's schema. Do not run it on the already verified team database.
The exact connection arguments used by Ghofrane were not retained in the committed
output; these are current CLI examples using its default local bench connection.

```powershell
python -m pip install PyMySQL
python pipeline/load_real.py --input data/real/cleaned.json --database wikipedia_time_machine --table article
python pipeline/verify_load.py --input data/real/cleaned.json --database wikipedia_time_machine --every 1
```

The load is reported as already completed by Ghofrane; no database operation was
executed during this review. Adjust `--host`, `--port`, `--user`, `--password` to the
intended environment without committing credentials. Verification checks version
counts, AS OF revision IDs/content hashes and the microsecond before each revision.

### Distribution and integrity

Use the existing Google Drive folder **Wikipedia Time Machine - Final Dataset
2024-2026**, shared by Moaz. Obtain the existing folder link from the project handover;
a verified direct link is not recorded in this repository. Download these three files:

- `wikipedia_time_machine_2024-2026.zip` (49,376,162 bytes)
- `manifest.json`
- `SHA256SUMS.txt`

Local originals are under ignored `data/real/2024_candidate/`; datasets and archives
are deliberately excluded from Git. The ZIP supplies `data/real/cleaned.json`,
`manifest.json`, `DATASET_REPORT.md`, and `SHA256SUMS.txt` when extracted at the
repository root. Preserve any existing `data/real` files before extraction, or use
a separate checkout. Do not substitute the larger preserved 2023 `cleaned.json`.

```powershell
(Get-FileHash -Algorithm SHA256 .\wikipedia_time_machine_2024-2026.zip).Hash
# After extraction at the repository root:
(Get-FileHash -Algorithm SHA256 data/real/cleaned.json).Hash
Get-Content data/real/SHA256SUMS.txt
(Get-FileHash -Algorithm SHA256 data/real/manifest.json).Hash
(Get-FileHash -Algorithm SHA256 data/real/DATASET_REPORT.md).Hash
```

Expected ZIP SHA-256:
`8105257a5999a14fa874f1b0c6a3db3451134a6ed0107ad1752d1d4cc30998ed`

Expected approved cleaned JSON SHA-256:
`e876db36a7235fd9ae21fb013b505445852ccc5376a5a256ca2011cd684e7c10`

Compare all three member hashes with `SHA256SUMS.txt`; it covers cleaned JSON,
manifest and report. ZIP hash is recorded separately to avoid circular hashing.
Check the manifest window and counts as well. Revision IDs, authors and content
remain intact; Wikipedia attribution/licensing requirements above also apply.

### Real database verification and Friday checks

Ghofrane's shared-main commit `af5b222` adds
[`docs/real_data_verification.txt`](docs/real_data_verification.txt), containing exactly:

```text
checked 1017 revisions, 0 problem(s)
```

Moaz's final handover additionally confirms database `wikipedia_time_machine`,
MariaDB **13.0.2**, 1,017 loaded historical revisions, successful ZIP/checksum receipt,
and **bad_drift = 0**. Those additional details are handover evidence; the committed
file contains only the verification output above. No reset or reload was performed.

Final review on 2026-10-31 after integrating the shared-main evidence:

- Real database loaded and verifier reports zero problems: satisfied by Ghofrane's evidence.
- Task 2.9 dataset window, five counts, sizes, UTC extrema, provenance and commands: documented here.
- Helpers/tests are tracked and already published: `pipeline/verify_load.py`,
  `pipeline/make_subset.py`, `tests/test_verify_load.py`, `tests/test_make_subset.py`.
- Executed `python -m unittest discover -s tests -v`: **45 passed, 0 failures, 0 errors**.
  Unit tests use mocks and do not independently repeat live database verification.

Receipt status: Ghofrane confirmed (final handover). Sami and Ranim remain
**pending**: no explicit acknowledgment found in repository reports or the connected
Gmail project search during this review. A Drive access-request email establishes
the folder name, not receipt by either teammate. Earlier local reports predate the
approved sharing/load and should not be read as current status.

Ready-to-send follow-up (not sent):
> Sami and Ranim: please confirm receipt of the approved 2024-2026 dataset ZIP and
> that your extracted cleaned.json matches SHA-256
> e876db36a7235fd9ae21fb013b505445852ccc5376a5a256ca2011cd684e7c10.
> Ghofrane has already verified all 1,017 database revisions with zero problems;
> the reported drift is zero.
