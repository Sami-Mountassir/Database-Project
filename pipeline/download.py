import argparse
import json
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

USER_AGENT = "Wikipedia-Time-Machine/1.0 (project-development)"

DEFAULT_ARTICLES = [
    "Great Wall of China",
    "Photosynthesis",
    "Apollo 11",
    "Leonardo da Vinci",
    "Coffee",
]
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"


def download_article(title, limit=None, timeout=30,
                     start="2020-01-01T00:00:00Z", end="2025-01-01T00:00:00Z"):
    """Fetch a complete historical window; limit optionally caps revisions per article."""
    if limit is not None and limit <= 0:
        raise ValueError("limit must be positive")
    if start >= end:
        raise ValueError("start must precede end (use UTC ISO timestamps)")
    params = {
        "action": "query",
        "format": "json",
        "prop": "revisions",
        "titles": title,
        "rvprop": "ids|timestamp|content|user",
        "rvslots": "main",
        "rvdir": "newer",
        "rvstart": start,
        "rvend": end,
    }
    result = {"query": {"pages": {}}}
    count = 0
    seen_tokens = set()
    while True:
        params["rvlimit"] = min(50, limit - count) if limit is not None else 50
        request = Request(f"{WIKIPEDIA_API}?{urlencode(params)}",
                          headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=timeout) as response:
            batch = json.load(response)
        if "error" in batch:
            raise ValueError(f"Wikipedia API error: {batch['error']}")
        pages = batch.get("query", {}).get("pages")
        if not isinstance(pages, dict):
            raise ValueError("Wikipedia API response is missing pages")
        for page_id, page in pages.items():
            if "missing" in page or "invalid" in page:
                raise ValueError(f"Wikipedia article unavailable: {title}")
            target = result["query"]["pages"].setdefault(
                page_id, {**page, "revisions": []})
            revisions = page.get("revisions", [])
            target["revisions"].extend(revisions)
            count += len(revisions)
        continuation = batch.get("continue", {})
        token = continuation.get("rvcontinue")
        if not token or (limit is not None and count >= limit):
            break
        if token in seen_tokens:
            raise ValueError("Wikipedia API repeated a continuation token")
        seen_tokens.add(token)
        params.update(continuation)
        time.sleep(1)
    return result


def download_articles(articles=DEFAULT_ARTICLES, limit=None, timeout=30,
                      start="2020-01-01T00:00:00Z", end="2025-01-01T00:00:00Z"):
    results = []
    for title in articles:
        print(f"Downloading history for: {title}...")
        try:
            results.append(download_article(title, limit, timeout, start, end))
        except (HTTPError, URLError, ValueError, TimeoutError) as error:
            print(f"Failed to download {title}: {error}")
        time.sleep(1)
    return results


def main():
    parser = argparse.ArgumentParser(description="Download Wikipedia revision histories")
    parser.add_argument("--limit", type=int, help="Optional revision cap per article; may truncate the historical window")
    parser.add_argument("--output", default="data/sample/raw_wikipedia_data.json")
    parser.add_argument("--article", action="append", dest="articles")
    parser.add_argument("--start", default="2020-01-01T00:00:00Z")
    parser.add_argument("--end", default="2025-01-01T00:00:00Z")
    args = parser.parse_args()
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be positive")
    if args.start >= args.end:
        parser.error("--start must precede --end; use UTC ISO timestamps")

    articles = args.articles or DEFAULT_ARTICLES
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = download_articles(articles, args.limit, start=args.start, end=args.end)
    output_path.write_text(json.dumps(data, indent=4), encoding="utf-8")
    print(f"Saved {len(data)} article responses to {output_path}")


if __name__ == "__main__":
    main()
