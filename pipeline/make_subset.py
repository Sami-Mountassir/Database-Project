"""Keep only the OLDEST fraction of each article's revisions (for growth benchmarks).

    python pipeline/make_subset.py --input data/real/cleaned.json --fraction 0.25 --output data/real/cleaned_25.json

Each article keeps its first ceil(fraction * count) revisions (by timestamp, then
revision id), so a 25% file is literally the first quarter of the 100% history.
At least 1 revision per article is always kept.
"""
import argparse
import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path

try:
    from .load_real import ordered_revisions
except ImportError:  # direct script execution
    from load_real import ordered_revisions


def subset(data, fraction):
    if isinstance(fraction, bool) or not isinstance(fraction, (int, float)) or not 0 < fraction <= 1:
        raise ValueError("fraction must be a finite number > 0 and <= 1")
    if not isinstance(data, list):
        raise ValueError("input must be a JSON array of revision records")
    by_article = defaultdict(list)
    for index, revision in enumerate(data):
        if not isinstance(revision, dict):
            raise ValueError(f"record {index}: expected an object")
        for field in ("article_id", "revision_id"):
            if type(revision.get(field)) is not int:
                raise ValueError(f"record {index}: {field} must be an integer")
        try:
            timestamp = datetime.fromisoformat(revision["timestamp"].replace("Z", "+00:00"))
            if timestamp.utcoffset() is None:
                raise ValueError("timestamp must include a timezone")
        except (KeyError, TypeError, AttributeError, ValueError) as error:
            raise ValueError(f"record {index}: invalid timezone-aware timestamp") from error
    for revision, _ in ordered_revisions(data):
        by_article[revision["article_id"]].append(revision)
    kept = []
    for revisions in by_article.values():
        kept.extend(revisions[:max(1, math.ceil(len(revisions) * fraction))])
    return kept


def main():
    parser = argparse.ArgumentParser(description="Create an oldest-first subset of cleaned revisions")
    parser.add_argument("--input", required=True)
    parser.add_argument("--fraction", type=float, required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if not 0 < args.fraction <= 1:
        parser.error("--fraction must be > 0 and <= 1")
    source = Path(args.input)
    out = Path(args.output)
    if source.resolve() == out.resolve() or (out.exists() and source.exists() and source.samefile(out)):
        parser.error("--output must differ from --input; source data must be preserved")
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
        kept = subset(data, args.fraction)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(kept, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"kept {len(kept)} of {len(data)} revisions "
          f"({len({r['article_id'] for r in kept})} articles) -> {out}")


if __name__ == "__main__":
    main()
