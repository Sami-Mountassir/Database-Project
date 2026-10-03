import json
import time
from urllib.parse import urlencode
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

articles = ["Great Wall of China", "Photosynthesis", "Apollo 11", "Leonardo da Vinci", "Coffee"]
url = "https://en.wikipedia.org/w/api.php"
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
    
    try:
        # Added a 10-second timeout to prevent infinite hanging
        with urlopen(f"{url}?{urlencode(params)}", timeout=10) as response:
            data = json.load(response)
            all_raw_data.append(data)
            
    except HTTPError as e:
        print(f"Server Error for {title}: {e.code}")
    except URLError as e:
        print(f"Network Error for {title}: Check your connection. ({e.reason})")
    except json.JSONDecodeError:
        print(f"Data Error for {title}: Received invalid JSON.")
    except Exception as e:
        print(f"Unexpected Error for {title}: {e}")
        
    time.sleep(1)

output_file = "data/sample/raw_wikipedia_data.json"

try:
    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(all_raw_data, file, indent=4)
    print(f"Success! Downloaded {len(all_raw_data)} articles and saved to {output_file}")
except IOError as e:
    print(f"File Save Error: Could not write to {output_file}. {e}")