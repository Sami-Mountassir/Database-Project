import argparse
import json
from pathlib import Path


def clean_revision(revision, article_id, article_title):
    slots = revision.get("slots", {})
    main_slot = slots.get("main", {})
    content = main_slot.get("*")
    if ("texthidden" in revision or "suppressed" in revision
            or "texthidden" in main_slot or "contenthidden" in main_slot
            or not isinstance(content, str)
            or content == "[CONTENT HIDDEN OR UNAVAILABLE]"):
        return None
    return {
        "article_id": article_id,
        # Keep origin/main's field names and the aliases used by load_real.py.
        "title": article_title,
        "article_title": article_title,
        "revision_id": revision.get("revid", 0),
        "revision_date": revision.get("timestamp", ""),
        "timestamp": revision.get("timestamp", ""),
        "author": revision.get("user", "[UNKNOWN]"),
        "content": content,
    }


def transform_revisions(raw_data):
    clean_data = []
    for article_data in raw_data:
        if "query" not in article_data or "pages" not in article_data["query"]:
            continue

        for page in article_data["query"]["pages"].values():
            page_id = page.get("pageid")
            if page_id is None or page_id == -1:
                continue
            article_title = page.get("title", "")
            for revision in page.get("revisions", []):
                cleaned = clean_revision(revision, page_id, article_title)
                if cleaned is not None:
                    clean_data.append(cleaned)
    return clean_data


def main():
    parser = argparse.ArgumentParser(description="Clean Wikipedia revision data")
    parser.add_argument("--input", default="data/sample/raw_wikipedia_data.json")
    parser.add_argument("--output", default="data/sample/cleaned_revisions.json")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Could not find {input_path}. Run download.py first.")

    raw_data = json.loads(input_path.read_text(encoding="utf-8"))
    clean_data = transform_revisions(raw_data)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(clean_data, indent=4), encoding="utf-8")
    print(f"Cleaned {len(clean_data)} revisions and saved to {output_path}")


if __name__ == "__main__":
    main()
