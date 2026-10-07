import json

input_file = "data/sample/raw_wikipedia_data.json"
output_file = "data/sample/cleaned_revisions.json"

try:
    with open(input_file, "r", encoding="utf-8") as file:
        raw_data = json.load(file)
except FileNotFoundError:
    print(f"Error: Could not find {input_file}. Run download.py first.")
    exit()

clean_data = []

for article_data in raw_data:
    # Error handling: skip if the API returned an empty or malformed query
    if "query" not in article_data or "pages" not in article_data["query"]:
        continue
        
    pages = article_data["query"]["pages"]
    page_id_str = list(pages.keys())[0] 
    
    # Error handling: Wikipedia uses "-1" for missing pages
    if page_id_str == "-1" or "revisions" not in pages[page_id_str]:
        print(f"Skipping missing or empty page ID: {page_id_str}")
        continue
        
    article_id = pages[page_id_str]["pageid"]
    article_title = pages[page_id_str]["title"]
    revisions = pages[page_id_str]["revisions"]

    for rev in revisions:
        # Error handling: safely extract content in case a revision is hidden/deleted
        if "slots" in rev and "main" in rev["slots"] and "*" in rev["slots"]["main"]:
            article_text = rev["slots"]["main"]["*"]
        else:
            article_text = "[CONTENT HIDDEN OR UNAVAILABLE]"
        
        # Matches ER Model exactly: ARTICLE VERSION (article_id, ver_date, content)
        clean_row = {
               "article_id": article_id,
               "title": article_title,
               "revision_id": rev.get("revid", 0),
               "revision_date": rev["timestamp"],
               "content": article_text,
               "author": rev.get("user", "[UNKNOWN]")
        }
        
        clean_data.append(clean_row)

try:
    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(clean_data, file, indent=4)
    print(f"Success! Cleaned {len(clean_data)} total revisions and saved to {output_file}")
except IOError as e:
    print(f"Error saving file: {e}")
