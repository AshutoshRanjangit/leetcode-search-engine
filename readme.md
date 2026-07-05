# 🔍 DSA Search Engine

A lightweight search engine that finds relevant Data Structure and Algorithm problems using natural language queries — powered by TF-IDF vectorization and cosine similarity.

🌐 **Live Demo:** [leetcodesearchengine.up.railway.app](https://leetcodesearchengine.up.railway.app)

👤 **Author:** [AshutoshRanjangit](https://github.com/AshutoshRanjangit)

---

## 💡 What problem does this solve?

LeetCode has 2500+ problems. Finding problems by concept is hard — the platform only supports title search and tag filtering. This engine lets you search by idea:

- `"find path between nodes"` → graph problems
- `"minimum cost overlapping subproblems"` → DP problems
- `"sliding window maximum subarray"` → sliding window problems
- `"detect cycle in linked list"` → linked list problems

**The key difference from LeetCode's built-in search:**

| Feature | LeetCode Search | DSA Search Engine |
|---------|----------------|-------------------|
| Searches titles only | ✅ | ❌ |
| Searches full problem descriptions | ❌ | ✅ |
| Searches by topic tags | ❌ | ✅ |
| Ranks results by relevance | ❌ | ✅ |
| Natural language queries | ❌ | ✅ |
| Understands abbreviations (BFS, DFS, DP) | ❌ | ✅ |

LeetCode's search is a **filter**. This is a **search engine** — fundamentally different.

---

## ⚙️ How it works

```
User types natural language query
            ↓
Query Expansion (BFS → Breadth-First Search, DP → Dynamic Programming)
            ↓
TF-IDF Vectorizer converts query to weighted term vector
            ↓
Cosine Similarity measures angle between query vector
and each of 2000+ document vectors
            ↓
Top 10 results ranked by relevance score
returned in < 0.5 seconds
```

### Why TF-IDF?

**TF (Term Frequency)** — how often a word appears in one specific problem divided by total words in that document.

**IDF (Inverse Document Frequency)** — penalizes words that appear across all problems like "return", "given", "array" since they carry no search signal. Rare, specific words like "dijkstra", "memoization", "trie" get high IDF scores.

**TF × IDF** — high score only for words frequent in one document but rare across all documents. Exactly the signal needed for search relevance.

### Why Cosine Similarity?

Measures the **angle** between two vectors — not the distance. This means a short problem and a long problem about the same topic score equally. Length doesn't bias results, only topical direction does.

A score of 1.0 means identical direction (perfect match). A score of 0.0 means no common relevant words.

### Why Query Expansion?

TF-IDF is exact string matching only. "BFS" and "Breadth-First Search" are completely different tokens — zero overlap. A user typing "BFS" would get zero matches against tags saying "Breadth-First Search".

Query expansion bridges this gap by appending known synonyms and full forms before vectorization:

```
Input:  "graph traversal BFS DFS"
Output: "graph traversal bfs dfs breadth first search
         breadth-first search graph depth first search
         depth-first search graph..."
```

### Why Tag Enrichment?

LeetCode problem statements never say "use dynamic programming." They say "find the minimum number of coins." The technique is in the official topic tags.

By appending tags to each problem's text before TF-IDF, the word "Dynamic Programming" now exists in every DP problem's document — solving the vocabulary mismatch problem.

Tags are repeated 3× (field boosting) to give them enough weight against the longer problem description text. This is the same technique Elasticsearch uses via its boost parameter.

---

## 🏗️ Architecture

```
leetcode-search-engine/
│
├── data/
│   ├── problems/              ← raw scraped problem text (2014 files)
│   ├── problemdata/           ← cleaned problem statements
│   ├── problemtitles.txt      ← all problem titles (one per line)
│   ├── problemurls.txt        ← all problem URLs (one per line)
│   └── tags.json              ← topic tags from LeetCode GraphQL API
│
├── scraper/
│   └── scraper.py             ← full scraping pipeline (3 phases)
│
├── search_engine.py           ← TF-IDF core + query expansion
├── app.py                     ← Flask API (3 routes)
│
├── templates/
│   ├── index.html             ← search page
│   └── problem.html           ← individual problem page
│
├── static/
│   ├── style.css              ← dark theme UI
│   └── script.js              ← async search, DOM rendering
│
├── requirements.txt
└── Procfile                   ← Railway deployment config
```

---

## 🛠️ Tech Stack

| Layer | Technology | Why chosen over alternatives |
|-------|-----------|------------------------------|
| **Scraping** | Python + Selenium | LeetCode is JS-rendered — plain `requests` or BeautifulSoup returns empty HTML. Selenium drives a real Chrome browser that executes JavaScript |
| **Tag fetching** | LeetCode GraphQL API | Tags are structured data — API returns clean JSON in 0.3s vs 3s per page with Selenium |
| **Search core** | scikit-learn TF-IDF | Sparse matrix storage, battle-tested, handles edge cases. 50x faster than manual implementation |
| **Similarity** | Cosine similarity | Length-invariant — short and long problems score fairly. Euclidean distance biases toward longer documents |
| **Query expansion** | Manual domain dictionary | CS-specific abbreviations (BFS, DFS, DP) not handled by general NLP thesauruses |
| **Backend** | Flask + Gunicorn | Lightweight, no ORM needed — search engine is stateless read-only |
| **Frontend** | Vanilla JavaScript | No framework overhead — one dynamic component doesn't justify React's 130KB+ bundle |
| **Deployment** | Railway | Auto-deploys from GitHub, zero config, free tier |

---

## 🔬 Scraper — How data was collected

The scraper runs in 3 phases inside `scraper/scraper.py`:

### Phase 1 — Link Collection (Selenium)

Scrolls LeetCode's infinite-scroll problem list page, collecting all problem URLs. Selenium is needed because the problem list is rendered by React — a plain HTTP request returns an empty HTML shell with no problems in it.

The scraper detects scroll bottom by comparing `document.body.scrollHeight` before and after each scroll. If height doesn't change, all content is loaded.

**Why scroll instead of paginate?** LeetCode's problem list uses infinite scroll — there are no page 1, 2, 3 URLs to iterate. Scrolling is the only way to trigger new content to load.

### Phase 2 — Content Scraping (Selenium)

Visits each problem URL, waits for JavaScript to render the page, then extracts:
- Title from `div.text-title-large > a`
- Description body from `div.elfjS`

Skips premium problems — their content div never renders without a paid subscription. WebDriverWait times out after 15 seconds and the problem is skipped cleanly.

### Phase 3 — Tag Fetching (GraphQL API)

Fetches official topic tags for each problem via LeetCode's internal GraphQL endpoint. Tags are public — no authentication required.

```python
query = """
query($titleSlug: String!) {
    question(titleSlug: $titleSlug) {
        topicTags { name }
    }
}
"""
```

**Why GraphQL instead of Selenium for tags?** Tags are not JS-gated — they're available via API as clean structured JSON. Selenium would require 2-3 seconds per problem (full browser load). The API takes 0.3 seconds. For 2000+ problems that's the difference between 1.5 hours and 10 minutes.

A Selenium fallback is also implemented in `scraper.py` in case the API endpoint changes — switching is one line.

```bash
# Run full scraper (takes ~5 hours for 2500 problems)
python scraper/scraper.py
```

---

## 🚀 Run Locally

```bash
# Clone repo
git clone https://github.com/AshutoshRanjangit/leetcode-search-engine.git
cd leetcode-search-engine

# Install dependencies
pip install -r requirements.txt

# Run app
python app.py

# Open browser
# http://localhost:5000
```

---

## 📊 Search Quality

| Query | Top Result | Score |
|-------|-----------|-------|
| `binary search tree` | Unique Binary Search Trees | 39% |
| `minimum cost dynamic programming` | Minimum Cost to Merge Stones | 22% |
| `sliding window maximum` | Sliding Window Maximum | 32% |
| `detect cycle linked list` | Linked List Cycle | 25% |
| `shortest path graph` | Minimum Obstacle Removal to Reach Corner | 27% |
| `graph traversal BFS DFS` | All Paths From Source to Target | 29% |

> Scores are cosine similarity as percentage. In a diverse 2000+ document corpus, 20%+ indicates strong relevance. Scores are relative rankings — what matters is the order, not the absolute value.

---

## 🐛 Bugs Encountered & Fixed

### Bug 1 — Wrong file sort order (misaligned titles and content)

**Problem:** Search results showed correct scores but wrong titles — "Two Sum" appeared as "Valid Parentheses." The parallel lists (titles, URLs, corpus) were misaligned.

**Root cause:** Files were sorted alphabetically by default: `problemtext1`, `problemtext10`, `problemtext100`, `problemtext2`. Problem 10's content was loading as problem 2's.

**Fix:** Sorted numerically by extracting the integer from the filename:
```python
files = sorted(
    os.listdir(PROBLEMS_DIR),
    key=lambda x: int(''.join(filter(str.isdigit, x)) or 0)
)
```

### Bug 2 — StaleElementReferenceException in Selenium

**Problem:** Selenium crashed mid-scrape with `StaleElementReferenceException` while iterating over anchor tags.

**Root cause:** LeetCode's React frontend re-rendered the DOM while Selenium was reading elements. The element reference became invalid mid-loop — a classic Selenium race condition.

**Fix:** Wrapped element access in try/except and skipped stale elements — they'd be caught in the next scroll iteration anyway.

### Bug 3 — "lis" expanding inside "linked list"

**Problem:** Searching "detect cycle linked list" returned Longest Increasing Subsequence problems. The word "l-i-s" inside "linked list" was triggering the LIS query expansion.

**Fix:** Changed the expansion key from `"lis"` to `"lis "` (with trailing space) so it only matches "lis" as a standalone word.

### Bug 4 — TF-IDF vocabulary too small (min_df=2 removing important terms)

**Problem:** Searching "dijkstra" or "memoization" returned zero results. Vocabulary was only 11,264 terms — far too small for 2000+ technical documents.

**Root cause:** `min_df=2` was removing words appearing in fewer than 2 documents. Technical terms like "dijkstra", "bellman", "memoization" appear in only 3-5 problems but are exactly the high-value search terms users type.

**Fix:** Changed `min_df=1` to keep all terms, and `max_df=0.95` (from 0.85) to avoid over-aggressively removing domain words. Vocabulary grew to 88,216 terms.

### Bug 5 — Graph queries returning tree problems

**Problem:** "graph traversal BFS DFS" returned binary tree traversal problems because "traversal" appears in 20+ tree problem titles.

**Root cause:** TF-IDF matched "traversal" in tree titles. BFS/DFS abbreviations didn't match "Breadth-First Search" tags — different strings.

**Fix:** Added query expansion dictionary mapping abbreviations to full forms and combined terms to stronger graph-specific signals.

---

## 🔮 Planned Enhancements

### Short term
- **Difficulty badges** — show Easy/Medium/Hard colored tags on each result card
- **Difficulty filter** — filter results by difficulty after searching
- **Mark as Solved** — track which problems you've solved locally using localStorage
- **Solved filter** — filter results to show only unsolved problems

### Medium term
- **User authentication** — JWT-based login so solved status syncs across devices
- **Search history** — save past queries per user, show recent searches
- **Saved problems** — bookmark problems to a personal list with PostgreSQL
- **Problem notes** — add personal notes to any problem

### Long term (scaling)
- **Redis caching** — share TF-IDF matrix across Gunicorn workers instead of each worker loading its own copy (saves ~200MB RAM with 4 workers)
- **Semantic search** — BERT embeddings for meaning-based matching. "find shortest route" would match graph problems even without exact keyword overlap
- **BM25 ranking** — upgrade from TF-IDF to BM25 (used by Elasticsearch) for better handling of varying document lengths
- **AtCoder + Codeforces** — extend scraper to other competitive programming platforms

---

## 📐 System Design — How to scale to 100 concurrent users

Current architecture handles single-user traffic well. For 100 concurrent users:

```
100 Users
    ↓
Nginx (reverse proxy + rate limiting)
    ↓
Gunicorn (4 worker processes)
    ↓          ↓          ↓          ↓
 Worker1    Worker2    Worker3    Worker4
 [Flask]    [Flask]    [Flask]    [Flask]
    ↓                              ↓
       Shared Redis Cache      PostgreSQL
       (TF-IDF matrix)        (users, saved,
                               history)
```

**Why Gunicorn workers?** Flask's dev server is single-threaded — one request at a time. Gunicorn spawns multiple worker processes. With 4 workers on a 2-core server, 4 requests are handled simultaneously.

**Why Redis for the matrix?** Each Gunicorn worker currently loads its own TF-IDF matrix (~50MB). With 4 workers that's 200MB just for matrices. Redis stores one copy shared across all workers.

**Why PostgreSQL for user data?** User accounts, saved problems, and search history are relational data with foreign key relationships. PostgreSQL handles concurrent writes with proper locking — SQLite allows only one write at a time.

---

Made with ❤️ by [Ashutosh](https://github.com/AshutoshRanjangit)