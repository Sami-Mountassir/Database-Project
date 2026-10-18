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

## Validation limits

Unit tests mock network and database access. A live API request was blocked by
local socket permissions during review. No MariaDB client or running Docker daemon
was available, so actual `row_start`/`row_end`, microsecond preservation and AS OF
results still need verification on the team's MariaDB instance. The seven procedure
arguments and six-digit timestamp formatting match `person1_temporal_schema.sql`.
The database/table character set must support the Wikipedia text (prefer utf8mb4),
and server settings must permit the procedure's historical `SET @@timestamp`.
The sample was checked against the existing raw API download: all 20 records match.
