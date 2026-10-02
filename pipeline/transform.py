import json

input_file = "data/sample/raw_wikipedia_data.json"
output_file = "data/sample/cleaned_revisions.json"

with open(input_file, "r", encoding="utf-8") as file:
    raw_data = json.load(file)

clean_data = []

# NEW: We add an outer loop to go through each article in our new list
for article_data in raw_data:
    pages = article_data["query"]["pages"]
    page_id = list(pages.keys())[0] 
    
    # We add a quick check to make sure the page actually has revisions
    if "revisions" in pages[page_id]:
        revisions = pages[page_id]["revisions"]

        # This is your exact same loop from before
        for rev in revisions:
            article_text = rev["slots"]["main"]["*"]
            
            clean_row = {
                "revision_id": rev["revid"],
                "timestamp": rev["timestamp"],
                "content": article_text
            }
            
            clean_data.append(clean_row)

with open(output_file, "w", encoding="utf-8") as file:
    json.dump(clean_data, file, indent=4)

print(f"Success! Cleaned {len(clean_data)} total revisions and saved to {output_file}")