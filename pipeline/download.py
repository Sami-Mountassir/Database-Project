import json
import time
from urllib.parse import urlencode
from urllib.request import urlopen

# 1. Define an array of articles to download
articles = ["Great Wall of China", "Photosynthesis", "Apollo 11", "Leonardo da Vinci", "Coffee"]
url = "https://en.wikipedia.org/w/api.php"

# Create an empty list to hold the data for all articles
all_raw_data = []

for title in articles:
    print(f"Downloading history for: {title}...")
    
    params = {
        "action": "query",
        "format": "json",
        "prop": "revisions",
        "titles": title,
        "rvprop": "ids|timestamp|content",
        "rvslots": "main",
        "rvlimit": 5  
    }
    
    # 2. Fetch data for the current article in the loop
    with urlopen(f"{url}?{urlencode(params)}") as response:
        data = json.load(response)
        all_raw_data.append(data)
        
    time.sleep(1)

# 3. Save all the combined data into your sample folder
output_file = "data/sample/raw_wikipedia_data.json"

with open(output_file, "w", encoding="utf-8") as file:
    json.dump(all_raw_data, file, indent=4)

print(f"Success! Downloaded {len(articles)} articles and saved to {output_file}")