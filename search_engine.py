# search_engine.py

import os
import json
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# ============================================================
# CONFIGURATION
# ============================================================
DATA_DIR    = "data"
PROBLEMS_DIR = os.path.join(DATA_DIR, "problems")
TITLES_FILE = os.path.join(DATA_DIR, "problemtitles.txt")
URLS_FILE   = os.path.join(DATA_DIR, "problemurls.txt")
TOP_K       = 10

# ============================================================
# QUERY EXPANSION DICTIONARY
# ============================================================
# Why query expansion?
# TF-IDF is exact string matching only.
# "BFS" and "Breadth-First Search" are completely different
# tokens — zero overlap. A user typing "BFS" gets zero
# matches against tags saying "Breadth-First Search".
# Query expansion bridges this gap by appending known
# synonyms and full forms before vectorization.
#
# Why append and not replace?
# Replacing "BFS" with "breadth first search" loses the
# original token. Appending keeps both — matches documents
# containing either form.
#
# Why manual dictionary and not a thesaurus API?
# Our domain is CS/algorithms — highly specific.
# General thesauruses don't know "BFS" means
# "Breadth-First Search" or "DP" means
# "Dynamic Programming". Manual domain-specific
# expansion is more accurate than general NLP tools.

QUERY_EXPANSIONS = {
    # Abbreviations → full forms matching our tags
    "bfs dfs"         : "graph breadth-first search depth-first search",
    "graph bfs"       : "graph breadth-first search",
    "graph dfs"       : "graph depth-first search",
    "graph traversal" : "graph breadth-first search depth-first search",
    "bfs"                    : "breadth first search breadth-first search graph",
    "dfs"                    : "depth first search depth-first search graph",
    "dp"                     : "dynamic programming",
    "bst"                    : "binary search tree",
    "lcs"                    : "longest common subsequence dynamic programming",
    "lis "                    : "longest increasing subsequence dynamic programming",
    "mst"                    : "minimum spanning tree graph",

    # Concept descriptions → technique keywords
    "shortest path"          : "shortest path breadth-first search graph",
    "minimum cost"           : "minimum cost dynamic programming",
    "find path"              : "graph breadth-first search depth-first search",
    "all paths"              : "graph depth-first search backtracking",
    "connected components"   : "graph union find depth-first search",
    "detect cycle"           : "graph depth-first search union find",
    "level order"            : "breadth-first search tree",
    "optimal substructure"   : "dynamic programming memoization",
    "overlapping subproblems": "dynamic programming memoization",
    "sliding window"         : "sliding window array",
    "two pointers"           : "two pointers array",
    "divide and conquer"     : "divide conquer recursion",
    "topological"            : "topological sort graph directed",
    "memoization"            : "dynamic programming memoization",
    "tabulation"             : "dynamic programming",
    "backtrack"              : "backtracking recursion",
    "trie"                   : "trie prefix tree string",
    "heap"                   : "heap priority queue",
    "monotonic stack"        : "stack monotonic array",
    "deque"                  : "deque sliding window monotonic",
    "graph traversal"        : "graph breadth-first search depth-first search",
    "tree traversal"         : "tree depth-first search binary tree",
    "hash map"               : "hash table array",
    "hash table"             : "hash table array",
    "two sum"                : "array hash table two sum",
    "linked list"            : "linked list",
    "merge sort"             : "divide conquer sorting merge sort",
    "quick sort"             : "sorting divide conquer",
    "binary search"          : "binary search array sorted",
    "recursion"              : "recursion depth-first search backtracking",
    "greedy"                 : "greedy algorithm",
    "bit manipulation"       : "bit manipulation bitwise",
    "matrix"                 : "matrix array depth-first search",
    "interval"               : "intervals sorting greedy",
    "palindrome"             : "string dynamic programming palindrome",
    "anagram"                : "string hash table sorting",
    "substring"              : "string sliding window hash table",
}


def expand_query(query):
    """
    Expands user query with domain-specific synonyms
    and full forms before passing to TF-IDF vectorizer.

    Example:
    Input:  "graph traversal BFS DFS"
    Output: "graph traversal bfs dfs
             breadth first search breadth-first search graph
             depth first search depth-first search graph
             graph breadth-first search depth-first search"

    This ensures that even if a user types abbreviations
    or concept descriptions, the expanded query matches
    the full-form tag text in our enriched corpus.
    """
    expanded = query.lower()
    additions = []

    for term, expansion in QUERY_EXPANSIONS.items():
        if term in expanded:
            additions.append(expansion)

    if additions:
        expanded = expanded + " " + " ".join(additions)
        print(f"[SearchEngine] Query expanded: '{expanded[:80]}...'")

    return expanded


# ============================================================
# STEP 1 — LOAD ALL DATA
# ============================================================
def load_data():
    print("[SearchEngine] Loading data...")

    titles = []
    urls   = []
    corpus = []

    # Read titles
    with open(TITLES_FILE, "r", encoding="utf-8") as f:
        titles = [line.strip() for line in f if line.strip()]

    # Read URLs
    with open(URLS_FILE, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip()]

    # Load tags if available
    tags_file = os.path.join(DATA_DIR, "tags.json")
    if os.path.exists(tags_file):
        with open(tags_file, "r") as f:
            all_tags = json.load(f)
        print(f"[SearchEngine] Tags loaded for {len(all_tags)} problems")
    else:
        all_tags = {}
        print("[SearchEngine] No tags file — using text only")

    # Read problem files sorted numerically
    # Critical: must sort numerically not alphabetically.
    # Alphabetical: 1, 10, 100, 1000, 2 (WRONG)
    # Numerical:    1, 2, 3, 4, 5      (CORRECT)
    # Wrong sort = titles[0] doesn't match corpus[0]
    # = search returns wrong titles for problems
    files = sorted(
        os.listdir(PROBLEMS_DIR),
        key=lambda x: int(''.join(filter(str.isdigit, x)) or 0)
    )

    for i, filename in enumerate(files):
        filepath = os.path.join(PROBLEMS_DIR, filename)

        # Read with UTF-8, fallback to latin-1
        # Some problems have non-UTF-8 math symbols
        # e.g. ≤ × → which latin-1 handles safely
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                text = f.read().strip()
        except UnicodeDecodeError:
            with open(filepath, "r", encoding="latin-1") as f:
                text = f.read().strip()

        # Enrich document with topic tags
        # Why? Problem statements never say "use dynamic programming"
        # They say "find minimum cost" — the technique is in the tags.
        # Appending tags means TF-IDF can match technique queries.
        # This solves the "vocabulary mismatch problem" —
        # query vocabulary and document vocabulary not overlapping
        # even though the meaning matches.
        if i < len(urls):
            slug = urls[i].rstrip("/").split("/problems/")[-1].split("/")[0]
            tags = all_tags.get(slug, [])
            if tags:
                # Repeat tags 3x — field boosting.
                # Tags are 1-3 words in a 200-word document.
                # Raw TF ≈ 0.005 — too weak to influence scores.
                # Repeating 3x raises TF to 0.015 — meaningful signal.
                # Same technique Elasticsearch uses internally
                # via its "boost" parameter on fields.
                tag_text = " ".join(tags * 3)
                text = text + "\n" + tag_text

        corpus.append(text)

    # Align all three lists — they must be same length.
    # If scraper crashed mid-run, counts could mismatch.
    # Truncating to minimum ensures parallel alignment:
    # titles[i], urls[i], corpus[i] always same problem.
    min_len = min(len(titles), len(urls), len(corpus))
    titles  = titles[:min_len]
    urls    = urls[:min_len]
    corpus  = corpus[:min_len]

    print(f"[SearchEngine] Loaded {min_len} problems")
    return titles, urls, corpus


# ============================================================
# STEP 2 — BUILD TF-IDF MATRIX
# ============================================================
def build_tfidf_engine(corpus):
    """
    Converts all problem texts into a TF-IDF matrix.

    TF-IDF intuition:
    TF (Term Frequency) — how often a word appears in THIS
    document divided by total words in that document.
    e.g. "graph" appears 5 times in 100-word problem → TF = 0.05

    IDF (Inverse Document Frequency):
    log(total_docs / docs_containing_word)
    "graph" in 200 of 2000 problems → IDF = log(10) ≈ 2.3
    "the" in all 2000 problems      → IDF = log(1)  = 0

    TF-IDF = TF × IDF
    Common words (the, is, a) → IDF ≈ 0 → TF-IDF ≈ 0
    Rare specific words (dijkstra, trie) → high TF-IDF

    Why scikit-learn over manual implementation:
    Sparse matrix storage — 2000 × 88000 = 176M cells.
    Most are zero. scikit-learn stores only non-zero values
    — ~100x less memory than a dense matrix.
    Also handles unicode, empty docs, edge cases
    that a manual implementation would need separately.
    """
    print("[SearchEngine] Building TF-IDF matrix...")

    vectorizer = TfidfVectorizer(
        stop_words="english",
        # Removes: the, is, a, an, of, for, etc.
        # These appear in every problem — IDF ≈ 0 anyway.
        # Removing early reduces vocabulary size ~20%.

        ngram_range=(1, 2),
        # Captures single words AND two-word phrases.
        # "dynamic programming" as one unit scores higher
        # than "dynamic" and "programming" separately.
        # Dramatically improves multi-word concept search.
        # Why not trigrams (1,3)?
        # Triples vocabulary size → 3x memory, 3x slower.
        # Most meaningful CS concepts are 1-2 words.

        max_df=0.95,
        # Ignore words in >95% of documents.
        # True noise words — appear in almost everything.
        # Raised from 0.85 — was removing domain words
        # like "array", "return" that still carry signal
        # when combined with rare words in bigrams.

        min_df=1,
        # Keep all words appearing in at least 1 document.
        # Lowered from 2 — "dijkstra", "memoization",
        # "bellman" appear in very few problems but are
        # exactly the high-value search terms users type.
        # min_df=2 was silently removing them.

        sublinear_tf=True
        # Applies log(1 + tf) instead of raw tf.
        # "graph" mentioned 10 times vs 1 time doesn't
        # mean 10x more relevant — relationship is
        # logarithmic. Prevents long problems dominating
        # just because they repeat words more.
    )

    tfidf_matrix = vectorizer.fit_transform(corpus)
    # fit    — learns vocabulary + IDF from corpus
    # transform — converts each doc to TF-IDF vector
    # Result shape: (num_problems, vocabulary_size)

    print(f"[SearchEngine] Matrix shape: {tfidf_matrix.shape}")
    print(f"[SearchEngine] Vocabulary size: {len(vectorizer.vocabulary_)}")

    return vectorizer, tfidf_matrix


# ============================================================
# STEP 3 — SEARCH
# ============================================================
def search(query, titles, urls, vectorizer, tfidf_matrix, top_k=TOP_K):
    """
    Takes a natural language query, expands it, vectorizes it,
    computes cosine similarity against all 2000+ problems,
    returns top_k results ranked by relevance score.

    Cosine similarity — why angle not distance?
    Each document = vector in high-dimensional space.
    Euclidean distance is biased by vector magnitude —
    longer documents have larger magnitude even if same topic.
    Cosine similarity measures ANGLE only — direction not length.
    Short and long documents about same topic score equally.

    Score = 1.0 → identical direction (perfect match)
    Score = 0.0 → perpendicular (no common relevant words)
    Score < 0   → impossible with TF-IDF (all values positive)
    """
    if not query.strip():
        return []

    # Expand query with synonyms and full forms
    # BEFORE vectorizing — so expanded terms are
    # looked up in the fitted vocabulary
    expanded = expand_query(query)

    # Transform using SAME vectorizer fit on corpus.
    # Must use transform() NOT fit_transform() here.
    # fit_transform() learns NEW vocabulary from query —
    # "graph" would get different index than in matrix.
    # Comparison would be meaningless — classic bug.
    query_vector = vectorizer.transform([expanded])

    # Cosine similarity: query vs every document
    # Result shape: (1, num_problems)
    scores = cosine_similarity(query_vector, tfidf_matrix).flatten()

    # argsort → ascending indices → reverse → descending
    # [:top_k] → take only top K
    top_indices = np.argsort(scores)[::-1][:top_k]

    results = []
    for idx in top_indices:
        if scores[idx] == 0:
            # Zero score = no common relevant terms
            # Not a meaningful result — skip it
            continue
        results.append({
            "id"   : int(idx + 1),
            "title": titles[idx],
            "url"  : urls[idx],
            "score": round(float(scores[idx]) * 100, 2),
        })

    return results


# ============================================================
# STEP 4 — INITIALIZE (called once at Flask startup)
# ============================================================
def initialize():
    """
    Loads all data and builds TF-IDF matrix.
    Called ONCE when server starts — not per request.

    Why once at startup?
    Building TF-IDF on 2000+ docs takes 1-3 seconds.
    Per-request rebuild = every search takes 3 seconds setup
    then milliseconds to actually search. Unacceptable.
    Load once → keep in memory → every search < 0.5 seconds.
    Standard pattern for ML models in production:
    load once, serve many. Same as TensorFlow Serving,
    FastAPI with loaded models, recommendation engines.
    """
    titles, urls, corpus = load_data()
    vectorizer, tfidf_matrix = build_tfidf_engine(corpus)
    return titles, urls, vectorizer, tfidf_matrix


# ============================================================
# TEST — run directly to verify results
# ============================================================
if __name__ == "__main__":
    titles, urls, vectorizer, tfidf_matrix = initialize()

    test_queries = [
        "dynamic programming",
        "minimum cost dynamic programming",
        "binary search tree",
        "graph traversal BFS DFS",
        "two sum array hash map",
        "sliding window maximum",
        "detect cycle linked list",
        "shortest path graph",
    ]

    for query in test_queries:
        print(f"\nQuery: '{query}'")
        print("-" * 40)
        results = search(query, titles, urls, vectorizer, tfidf_matrix)
        for r in results:
            print(f"  [{r['score']}%] {r['title']} — {r['url']}")