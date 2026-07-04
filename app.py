# app.py

from flask import Flask, request, jsonify, render_template
import search_engine
import os

# ============================================================
# INITIALIZE FLASK
# ============================================================

app = Flask(__name__)

# Why __name__?
# Flask uses this to know where to look for templates/ and static/
# folders. __name__ gives Flask the current module's name,
# which tells it the root directory of the project.
# If you hardcoded a string like Flask("app"), it would work
# in most cases but break when the module is imported elsewhere.

# ============================================================
# LOAD SEARCH ENGINE AT STARTUP — NOT PER REQUEST
# ============================================================

print("\n" + "="*50)
print("Starting LeetCode Search Engine...")
print("="*50)

titles, urls, vectorizer, tfidf_matrix = search_engine.initialize()

print("="*50)
print(f"Engine ready. {len(titles)} problems loaded.")
print("="*50 + "\n")

# Why load here at module level and not inside a route?
# If we loaded inside the /search route, every single search
# request would rebuild the entire TF-IDF matrix — 2-3 seconds
# per search. Loading at module level means Flask builds it
# once when the server starts, then every search is instant.
# This is called "eager loading" vs "lazy loading".
# For a search engine, eager loading is correct because
# we know we'll need the matrix for every request.

# ============================================================
# ROUTE 1 — HOME PAGE
# ============================================================

@app.route("/")
def home():
    """
    Serves the main search page.
    render_template looks for index.html inside /templates folder.
    Flask knows to look there because of how we initialized
    the app with __name__.
    """
    return render_template("index.html")

# ============================================================
# ROUTE 2 — SEARCH API
# ============================================================

@app.route("/search")
def search():
    """
    Takes a query parameter from the URL and returns
    top 10 matching problems as JSON.

    Example request:
    GET /search?q=dynamic+programming

    Example response:
    [
        {
            "id": 322,
            "title": "Coin Change",
            "url": "https://leetcode.com/problems/coin-change/",
            "score": 42.3,
            "snippet": "You are given an integer array coins..."
        },
        ...
    ]

    Why GET and not POST?
    Search is a READ operation — it doesn't modify any data.
    HTTP convention: GET for reads, POST for writes.
    GET also allows the query to be bookmarked and shared
    via URL — e.g. /search?q=binary+search is shareable.
    POST requests cannot be bookmarked.

    Why return JSON and not HTML?
    Separating the API from the UI is called a
    "decoupled architecture". The frontend fetches JSON
    and renders it with JavaScript. This means:
    1. The same API could serve a mobile app, CLI tool,
       or browser extension without changing backend code.
    2. The page doesn't reload on each search — 
       faster, smoother user experience.
    3. Easier to test — you can hit /search?q=test
       directly in the browser or with curl.
    """

    # Get query from URL parameter
    # request.args is a dict of all URL query parameters
    # .get("q", "") returns empty string if "q" not present
    # — prevents KeyError crash on missing parameter
    query = request.args.get("q", "").strip()

    # Guard against empty queries
    if not query:
        return jsonify({
            "error": "Please enter a search query",
            "results": []
        }), 400

    # Why 400 and not 200?
    # HTTP status codes communicate intent.
    # 400 = Bad Request — the client sent an invalid request.
    # Returning 200 with an error message is a common mistake
    # that makes error handling on the frontend ambiguous —
    # the frontend can't tell success from failure by status code.
    # 400 lets the frontend handle errors cleanly with one check.

    # Guard against suspiciously long queries
    # Prevents abuse — someone sending a 10,000 word query
    # to try to slow down the server
    if len(query) > 200:
        return jsonify({
            "error": "Query too long. Please keep it under 200 characters.",
            "results": []
        }), 400

    # Run search
    results = search_engine.search(
        query,
        titles,
        urls,
        vectorizer,
        tfidf_matrix
    )

    # Enrich results with problem snippets
    # A snippet is the first 200 characters of the problem text
    # shown in search results so the user can preview before clicking
    enriched = []
    for r in results:
        problem_id = r["id"]
        snippet = get_snippet(problem_id)
        enriched.append({
            **r,           # spread all existing fields (id, title, url, score)
            "snippet": snippet
        })

    return jsonify(enriched)

    # Why jsonify and not json.dumps?
    # jsonify is Flask's wrapper around json.dumps that:
    # 1. Sets the correct Content-Type header (application/json)
    #    so browsers and clients know what they're receiving
    # 2. Handles Python-specific types like numpy floats
    #    that json.dumps would crash on
    # 3. Respects Flask's debug mode for pretty printing

# ============================================================
# ROUTE 3 — INDIVIDUAL PROBLEM PAGE
# ============================================================

@app.route("/problem/<int:problem_id>")
def problem(problem_id):
    """
    Serves a full problem page for a given problem ID.

    Why <int:problem_id> and not <problem_id>?
    Flask's URL converter <int:...> automatically:
    1. Validates that the value is an integer
       — /problem/abc returns 404 automatically
    2. Converts it from string to Python int
       — no need for int() conversion in the function
    This is called a URL converter — it's cleaner and
    safer than manually parsing and validating.

    Why a separate page for each problem?
    Two reasons:
    1. UX — users can bookmark and share individual problems
    2. The search results only show a snippet (200 chars).
       The full problem text can be 2000+ characters.
       Loading all full texts in search results would make
       the JSON response massive and slow.
    """

    # Validate problem_id range
    if problem_id < 1 or problem_id > len(titles):
        return render_template(
            "problem.html",
            title="Problem Not Found",
            url="#",
            full_text="This problem does not exist.",
            problem_id=problem_id
        ), 404

    # Arrays are 0-indexed but our IDs are 1-indexed
    title = titles[problem_id - 1]
    url = urls[problem_id - 1]

    # Load full problem text
    problem_file = os.path.join(
        "data", "problems",
        f"problemtext{problem_id}.txt"
    )

    try:
        with open(problem_file, "r", encoding="utf-8") as f:
            full_text = f.read()
    except FileNotFoundError:
        full_text = "Full problem text not available."
    except UnicodeDecodeError:
        with open(problem_file, "r", encoding="latin-1") as f:
            full_text = f.read()

    return render_template(
        "problem.html",
        title=title,
        url=url,
        full_text=full_text,
        problem_id=problem_id
    )

# ============================================================
# HELPER — GET SNIPPET
# ============================================================

def get_snippet(problem_id):
    """
    Returns first 200 characters of a problem's core statement.
    Used in search results as a preview.

    Why 200 characters?
    Long enough to give context, short enough to keep the
    JSON response small. At 10 results × 200 chars = 2000 chars
    of snippet data per search — negligible payload size.
    If we returned full texts, 10 results × 2000 chars average
    = 20,000 chars per search response — 10x larger for no UX gain
    since the user won't read the full text in search results anyway.
    """
    snippet_file = os.path.join(
        "data", "problemdata",
        f"problemdata{problem_id}.txt"
    )
    try:
        with open(snippet_file, "r", encoding="utf-8") as f:
            text = f.read().strip()
            # Skip the title line (first line) for the snippet
            # because the title is already shown separately
            lines = text.split("\n")
            body = " ".join(lines[2:])  # skip title + blank line
            return body[:200] + "..." if len(body) > 200 else body
    except:
        return ""

# ============================================================
# LAUNCH
# ============================================================

if __name__ == "__main__":
    app.run(debug=True, port=5000)

# Why debug=True only in __main__?
# debug=True enables:
# 1. Auto-reload when you change code (no manual restart)
# 2. Detailed error pages in browser showing exact line and traceback
# 3. Interactive debugger in browser
# BUT debug=True in production is a critical security vulnerability —
# the interactive debugger allows arbitrary Python code execution.
# When Railway runs the app via Procfile (gunicorn), it never
# hits __main__ so debug mode never activates in production.
# This is the correct pattern — debug locally, safe in production.