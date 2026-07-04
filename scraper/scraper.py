# scraper/scraper.py

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
import os

# ============================================================
# CONFIGURATION
# ============================================================
OUTPUT_DIR = "data"
PROBLEMS_DIR = os.path.join(OUTPUT_DIR, "problems")
PROBLEMDATA_DIR = os.path.join(OUTPUT_DIR, "problemdata")
TITLES_FILE = os.path.join(OUTPUT_DIR, "problemtitles.txt")
URLS_FILE = os.path.join(OUTPUT_DIR, "problemurls.txt")
LINKS_FILE = os.path.join(OUTPUT_DIR, "lc_links.txt")

MAX_PROBLEMS = 2500
SCROLL_PAUSE = 1.5

# ============================================================
# SETUP
# ============================================================
os.makedirs(PROBLEMS_DIR, exist_ok=True)
os.makedirs(PROBLEMDATA_DIR, exist_ok=True)
# ============================================================
# PHASE 1 — COLLECT ALL PROBLEM URLs
# ============================================================
def collect_problem_links():
    """
    Scrolls LeetCode's problem list page to collect all problem URLs.
    Why Selenium: The problem list is rendered by React (JavaScript).
    A plain requests call returns an empty shell with no problems in it.
    Selenium drives a real Chrome browser that executes the JavaScript,
    exactly like a human visiting the page.
    """
    print("\n[PHASE 1] Starting link collection...")

    # webdriver_manager automatically downloads the correct
    # ChromeDriver version matching your installed Chrome.
    # Without this, you'd have to manually download ChromeDriver
    # and keep updating it every time Chrome auto-updates.
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))

    driver.get("https://leetcode.com/problemset/all/")

    # Wait for initial page load — the problem cards need
    # JavaScript to render, so we wait until at least one
    # element with role="rowgroup" appears (the problem table)
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.TAG_NAME, "a"))
    )

    problem_links = set()  # set = automatic deduplication
    last_height = driver.execute_script("return document.body.scrollHeight")

    print("Scrolling to load all problems...")

    for attempt in range(150):  # max scroll attempts
        # Scroll to bottom — triggers LeetCode to load more problems
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(SCROLL_PAUSE)  # wait for new content to render

        # Find all anchor tags on the page
        all_links = driver.find_elements(By.TAG_NAME, "a")
        for link in all_links:
            try:
                href = link.get_attribute("href")
                # Filter: only keep actual problem pages
                # Exclude: /discuss/, /solution/, /submissions/ etc.
                if href and "/problems/" in href:
                    slug = href.split("/problems/")[1].split("/")[0]
                    if slug:  # ignore empty slugs
                        clean_url = f"https://leetcode.com/problems/{slug}/"
                        problem_links.add(clean_url)
            except:
                # Stale element — DOM updated while we were reading it
                # This is a common Selenium race condition
                # Solution: just skip it, we'll catch it next scroll
                pass

        print(f"  Scroll {attempt + 1}: {len(problem_links)} problems found")

        if len(problem_links) >= MAX_PROBLEMS:
            print(f"  Reached {MAX_PROBLEMS} problems. Stopping.")
            break

        # Check if we've hit the bottom — no new content loaded
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            print("  No more content to load. Page end reached.")
            break
        last_height = new_height

    driver.quit()

    # Save links to file
    with open(LINKS_FILE, "w", encoding="utf-8") as f:
        for link in sorted(problem_links)[:MAX_PROBLEMS]:
            f.write(link + "\n")

    print(f"\n[PHASE 1 DONE] Saved {min(len(problem_links), MAX_PROBLEMS)} links")
    return sorted(problem_links)[:MAX_PROBLEMS]

# ============================================================
# PHASE 2 — SCRAPE EACH PROBLEM PAGE
# ============================================================
def scrape_problems(links):
    """
    Visits each problem URL and extracts title + description.
    Why we need Selenium here too:
    Problem descriptions are rendered by React on the client side.
    The actual text content only exists in the DOM after JavaScript
    executes — a plain HTTP request gets empty divs.
    """
    print("\n[PHASE 2] Starting problem scraping...")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    wait = WebDriverWait(driver, 15)

    title_fp = open(TITLES_FILE, "w", encoding="utf-8")
    url_fp = open(URLS_FILE, "w", encoding="utf-8")

    count = 1  # successful scrape counter

    for i, url in enumerate(links):
        print(f"\nScraping ({i+1}/{len(links)}): {url}")

        try:
            driver.get(url)
            time.sleep(2)  # let JS render

            # --- Get Title ---
            # LeetCode renders the title inside:
            # <div class="text-title-large"><a>Two Sum</a></div>
            title_element = wait.until(EC.presence_of_element_located((
                By.XPATH, '//div[contains(@class, "text-title-large")]//a'
            )))
            title = title_element.text.strip()

            # --- Get Description ---
            # The problem body is inside a div with class "elfjS"
            # This class name is LeetCode's internal React class —
            # it doesn't change often but when it does, this breaks.
            # That's a known fragility of CSS-class based scraping.
            body_element = wait.until(EC.presence_of_element_located((
                By.CLASS_NAME, "elfjS"
            )))
            body = body_element.text.strip()

            if not title or not body:
                print("  Empty content — skipping")
                continue

            # --- Save raw problem text ---
            with open(
                os.path.join(PROBLEMS_DIR, f"problemtext{count}.txt"),
                "w", encoding="utf-8"
            ) as f:
                f.write(body)

            # --- Clean and save problem data ---
            # Strip everything from "Example" onwards —
            # examples and constraints are noisy for TF-IDF.
            # "Given an array of integers, return indices
            #  of two numbers that add up to target."
            # is more signal-rich than
            # "Example 1: Input: [2,7,11,15] Output: [0,1]"
            cleaned = extract_core_statement(body)
            full_content = f"{title}\n\n{cleaned}"
            with open(
                os.path.join(PROBLEMDATA_DIR, f"problemdata{count}.txt"),
                "w", encoding="utf-8"
            ) as f:
                f.write(full_content)

            # --- Save to index files ---
            title_fp.write(title + "\n")
            url_fp.write(url + "\n")

            print(f"  Saved: {title}")
            count += 1

        except Exception as e:
            # Two main reasons this fails:
            # 1. Premium problem — content locked behind paywall,
            #    the expected elements never appear, WebDriverWait times out
            # 2. LeetCode changed their CSS class names —
            #    happens occasionally, requires scraper update
            print(f"  Skipping ({type(e).__name__}): likely premium or layout changed")
            continue

    title_fp.close()
    url_fp.close()
    driver.quit()

    print(f"\n[PHASE 2 DONE] Successfully scraped {count-1} problems")

# ============================================================
# HELPER — CLEAN PROBLEM TEXT
# ============================================================
def extract_core_statement(text):
    """
    Strips examples, constraints, follow-ups from problem text.
    Keeps only the core problem statement.

    Why: TF-IDF scores words by how uniquely they appear in a document.
    "Example 1 Input Output" appears in EVERY problem — so its IDF
    score would be near zero anyway. But keeping it adds noise to
    the vector and slows computation. Cleaner input = better search.
    """
    lines = text.splitlines()
    core_lines = []
    for line in lines:
        # Stop at examples section
        if line.strip().lower().startswith("example"):
            break
        # Stop at constraints section
        if line.strip().lower().startswith("constraint"):
            break
        core_lines.append(line.strip())
    # Remove empty lines
    return "\n".join(line for line in core_lines if line)


# ============================================================
# MAIN — RUN THE FULL PIPELINE
# ============================================================
if __name__ == "__main__":
    print("=" * 50)
    print("LeetCode Search Engine — Scraper")
    print("=" * 50)

    # Phase 1: Collect all problem URLs
    links = collect_problem_links()

    # Phase 2: Scrape each problem page
    scrape_problems(links)

    print("\n" + "=" * 50)
    print("Scraping complete. Data saved to /data folder.")
    print("=" * 50)