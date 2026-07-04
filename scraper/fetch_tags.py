# scraper/fetch_tags.py
# Fetches topic tags for all problems using LeetCode's
# public GraphQL API and saves to data/tags.json

import requests
import json
import time
import os

DATA_DIR = "data"
URLS_FILE = os.path.join(DATA_DIR, "problemurls.txt")
TAGS_FILE = os.path.join(DATA_DIR, "tags.json")

def get_slug(url):
    """
    Extracts problem slug from URL.
    "https://leetcode.com/problems/two-sum/" → "two-sum"
    """
    return url.rstrip("/").split("/problems/")[1].split("/")[0]

def fetch_tags(slug):
    """
    Hits LeetCode's GraphQL API for one problem's tags.
    No authentication needed — topic tags are public.
    """
    url = "https://leetcode.com/graphql"
    query = """
    query($titleSlug: String!) {
        question(titleSlug: $titleSlug) {
            topicTags { name }
        }
    }
    """
    try:
        r = requests.post(
            url,
            json={"query": query, "variables": {"titleSlug": slug}},
            headers={
                "Content-Type": "application/json",
                "Referer": "https://leetcode.com"
            },
            timeout=10
        )
        data = r.json()
        tags = data["data"]["question"]["topicTags"]
        return [t["name"] for t in tags]
    except Exception as e:
        print(f"  Failed for {slug}: {e}")
        return []

def main():
    # Load existing tags if script was interrupted
    # So we don't re-fetch from the beginning every time
    if os.path.exists(TAGS_FILE):
        with open(TAGS_FILE, "r") as f:
            tags_data = json.load(f)
        print(f"Resuming — {len(tags_data)} already fetched")
    else:
        tags_data = {}

    # Read all problem URLs
    with open(URLS_FILE, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip()]

    print(f"Total problems: {len(urls)}")

    for i, url in enumerate(urls):
        slug = get_slug(url)

        # Skip already fetched
        if slug in tags_data:
            continue

        tags = fetch_tags(slug)
        tags_data[slug] = tags
        print(f"[{i+1}/{len(urls)}] {slug}: {tags}")

        # Save every 50 problems in case of interruption
        if (i + 1) % 50 == 0:
            with open(TAGS_FILE, "w") as f:
                json.dump(tags_data, f, indent=2)
            print(f"  Progress saved — {len(tags_data)} problems done")

        # Polite delay — don't hammer LeetCode's servers
        # 0.3 seconds × 2000 problems = 10 minutes total
        # Without delay: likely get rate-limited or IP blocked
        time.sleep(0.3)

    # Final save
    with open(TAGS_FILE, "w") as f:
        json.dump(tags_data, f, indent=2)

    print(f"\nDone. Tags saved for {len(tags_data)} problems → {TAGS_FILE}")

if __name__ == "__main__":
    main()