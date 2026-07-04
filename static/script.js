// static/script.js

// ============================================================
// WHY VANILLA JAVASCRIPT AND NOT REACT/VUE?
// ============================================================
// React would add 130KB+ of library code for a page that has
// exactly ONE dynamic component — the results list.
// Vanilla JS handles this in ~150 lines with zero dependencies,
// zero build step, zero npm install, and loads instantly.
// The rule: use a framework when the complexity of managing
// state manually exceeds the cost of the framework.
// Here, our state is literally one variable — the results array.
// That doesn't justify React.
// Interviewers appreciate this reasoning — it shows you choose
// tools deliberately, not because they're trendy.

// ============================================================
// DOM ELEMENT REFERENCES
// ============================================================
// Cache DOM references at the top — not inside functions.
// Why? document.getElementById() traverses the entire DOM
// tree every time it's called. Calling it once and storing
// the reference means subsequent access is instant memory
// lookup instead of DOM traversal.
// On 60fps animations this matters enormously.
// For a search page it's minor — but the pattern is correct.

const searchInput  = document.getElementById("searchInput");
const searchBtn    = document.getElementById("searchBtn");
const statusMsg    = document.getElementById("statusMessage");
const resultsInfo  = document.getElementById("resultsInfo");
const resultsCount = document.getElementById("resultsCount");
const resultsQuery = document.getElementById("resultsQuery");
const responseTime = document.getElementById("responseTime");
const resultsList  = document.getElementById("resultsList");

// ============================================================
// STATE
// ============================================================
// Single variable tracking whether a search is in progress.
// Prevents duplicate requests if user clicks Search rapidly.
// This is called a "loading lock" or "request guard".

let isSearching = false;

// ============================================================
// EVENT LISTENERS — SET UP ON PAGE LOAD
// ============================================================

// Enter key triggers search
// Why listen on keydown and not keyup?
// keydown fires when key is pressed (feels instant).
// keyup fires when key is released (slight delay).
// For search, instant response on keydown feels snappier.
searchInput.addEventListener("keydown", function(event) {
    if (event.key === "Enter") {
        handleSearch();
    }
});

// Focus search input immediately on page load
// Why? This is a search engine — the user's intent
// is to type immediately. Making them click the input
// first is friction. Auto-focusing removes that step.
// Gmail, Google, GitHub search all do this.
window.addEventListener("load", function() {
    searchInput.focus();
});

// ============================================================
// MAIN SEARCH HANDLER
// ============================================================

async function handleSearch() {
    // Why async/await over .then().catch()?
    // Both are valid Promise patterns.
    // async/await reads like synchronous code — easier
    // to follow the logic flow and handle errors with
    // try/catch which developers already know.
    // .then().catch() chains become hard to read with
    // multiple sequential async operations (callback hell
    // in a nicer suit). async/await is the modern standard.

    const query = searchInput.value.trim();

    // Guard 1 — Empty query
    if (!query) {
        showStatus("Please enter a search query.");
        searchInput.focus();
        return;
    }

    // Guard 2 — Query too short
    if (query.length < 2) {
        showStatus("Query too short. Try something more specific.");
        return;
    }

    // Guard 3 — Already searching (prevents duplicate requests)
    if (isSearching) return;

    // Lock search and show loading state
    isSearching = true;
    setLoadingState(true);
    showStatus("🔍 Searching...");
    clearResults();

    // Record start time for response time measurement
    // Why measure response time?
    // Your CV says "delivering results within 0.5 sec".
    // Showing the actual response time proves it.
    // Also useful debugging info — if search is slow,
    // user can see it and report it.
    const startTime = performance.now();
    // Why performance.now() over Date.now()?
    // Date.now() returns milliseconds since Unix epoch —
    // an integer. performance.now() returns microsecond-
    // precision float from page load. For measuring
    // short durations (sub-second), performance.now()
    // is significantly more accurate.

    try {
        // ---- FETCH API CALL ----
        // Why fetch() over XMLHttpRequest (XHR)?
        // XHR is the old way — callback-based, verbose,
        // hard to read. fetch() is Promise-based, works
        // with async/await, much cleaner syntax.
        // Every modern browser supports fetch().
        // XHR is only needed for IE11 support (2026 — irrelevant).

        // Why encodeURIComponent(query)?
        // URL query strings can't contain spaces or special
        // characters. "dynamic programming" → "dynamic%20programming"
        // Without encoding, spaces break the URL and the
        // server receives a malformed query.
        // encodeURIComponent handles: spaces, &, =, +, #, etc.

        const response = await fetch(
            `/search?q=${encodeURIComponent(query)}`
        );

        // Check HTTP status BEFORE parsing JSON
        // Why? If Flask returns a 400 or 500 error,
        // response.json() might still work but the data
        // will be an error object not results.
        // Checking response.ok (true for 200-299) first
        // lets us handle errors cleanly.
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || "Search failed");
        }

        const results = await response.json();

        // Calculate how long the search took
        const elapsed = ((performance.now() - startTime) / 1000).toFixed(3);

        // Render results
        renderResults(results, query, elapsed);

    } catch (error) {
        // Two types of errors land here:
        // 1. Network error — fetch() itself fails
        //    (server down, no internet, CORS issue)
        // 2. HTTP error — we threw manually above
        //    (400 bad request, 500 server error)
        // We handle both the same way — show error message.

        showStatus(`❌ Error: ${error.message}. Please try again.`);
        console.error("Search error:", error);
        // console.error goes to browser DevTools console —
        // useful for debugging without showing technical
        // details to the user.
    } finally {
        // finally block ALWAYS runs — success or error.
        // Why put cleanup here?
        // If we put it in try{}, errors skip it.
        // If we put it in catch{}, success skips it.
        // finally guarantees cleanup no matter what happened.
        // This ensures the button is never permanently stuck
        // in loading state even if something unexpected happens.
        isSearching = false;
        setLoadingState(false);
    }
}

// ============================================================
// QUICK SEARCH — called by chip buttons
// ============================================================

function quickSearch(query) {
    // Fill input with chip text then search
    // Why fill the input too?
    // User can see what was searched and modify it.
    // If chips just silently searched, the input would
    // show empty while results appeared — confusing UX.
    searchInput.value = query;
    handleSearch();
}

// ============================================================
// RENDER RESULTS
// ============================================================

function renderResults(results, query, elapsed) {
    clearResults();

    // No results case
    if (!results || results.length === 0) {
        showStatus(
            `No results found for "${query}". ` +
            `Try different keywords or broader terms.`
        );
        return;
    }

    // Show results metadata bar
    hideStatus();
    resultsInfo.style.display = "flex";
    resultsCount.textContent = `${results.length} results`;
    resultsQuery.textContent = `for "${query}"`;
    responseTime.textContent = `· ${elapsed}s`;
    // Showing actual response time is a UX and credibility
    // choice — your CV claims <0.5s, showing the real time
    // proves it. If it's consistently 0.08s, that's impressive.

    // Render each result card
    results.forEach((problem, index) => {
        const card = createResultCard(problem, index);
        resultsList.appendChild(card);
    });
}

// ============================================================
// CREATE A SINGLE RESULT CARD
// ============================================================

function createResultCard(problem, index) {
    // Why createElement instead of innerHTML string?
    // Two reasons:
    // 1. Security — innerHTML with user data creates XSS risk.
    //    If a problem title contained <script>alert(1)</script>,
    //    innerHTML would execute it. createElement builds DOM
    //    nodes directly — no HTML parsing, no script execution.
    // 2. Performance — innerHTML triggers a full reparse of
    //    the HTML string. createElement operations are direct
    //    DOM manipulations — faster for many elements.

    const card = document.createElement("div");
    card.className = "result-card";

    // Clicking anywhere on card goes to problem page
    // Why the whole card and not just the title link?
    // Larger click target = better UX, especially on mobile.
    // This is Fitts's Law — the time to click a target
    // depends on its size and distance. Bigger = faster.
    card.addEventListener("click", function(e) {
        // Don't double-navigate if user clicked a link inside
        if (e.target.tagName === "A") return;
        window.location.href = `/problem/${problem.id}`;
    });

    // Sanitize text before inserting into DOM
    // textContent is safe — it never parses HTML.
    // If title = "<b>Two Sum</b>", textContent shows
    // the literal string, innerHTML would render bold text
    // and could execute scripts.

    // Card header — title + score badge
    const header = document.createElement("div");
    header.className = "card-header";

    const title = document.createElement("a");
    title.className = "card-title";
    title.href = `/problem/${problem.id}`;
    title.textContent = problem.title;
    // Stop card click handler from also firing
    title.addEventListener("click", e => e.stopPropagation());

    const badge = document.createElement("span");
    badge.className = "score-badge";
    badge.textContent = `${problem.score}% match`;

    header.appendChild(title);
    header.appendChild(badge);

    // Snippet
    const snippet = document.createElement("p");
    snippet.className = "card-snippet";
    snippet.textContent = problem.snippet || "No preview available.";

    // Card footer — links and ID
    const footer = document.createElement("div");
    footer.className = "card-footer";

    const viewLink = document.createElement("a");
    viewLink.className = "card-link";
    viewLink.href = `/problem/${problem.id}`;
    viewLink.textContent = "View Problem";
    viewLink.addEventListener("click", e => e.stopPropagation());

    const lcLink = document.createElement("a");
    lcLink.className = "card-link";
    lcLink.href = problem.url;
    lcLink.target = "_blank";
    lcLink.rel = "noopener noreferrer";
    lcLink.textContent = "LeetCode →";
    lcLink.addEventListener("click", e => e.stopPropagation());

    const idSpan = document.createElement("span");
    idSpan.className = "card-id";
    idSpan.textContent = `#${problem.id}`;

    footer.appendChild(viewLink);
    footer.appendChild(lcLink);
    footer.appendChild(idSpan);

    // Assemble card
    card.appendChild(header);
    card.appendChild(snippet);
    card.appendChild(footer);

    // Staggered animation — each card fades in slightly
    // after the previous one. Creates a smooth reveal effect.
    // Why setTimeout and not CSS animation-delay?
    // CSS animation-delay requires knowing the delay at
    // render time — we'd need to inject inline styles.
    // setTimeout lets us add the animation class after
    // a JS-controlled delay — cleaner separation of concerns.
    setTimeout(() => {
        card.style.opacity = "1";
        card.style.transform = "translateY(0)";
    }, index * 60);
    // 60ms between each card — subtle enough to not feel slow,
    // noticeable enough to feel polished.

    // Start invisible for animation
    card.style.opacity = "0";
    card.style.transform = "translateY(10px)";
    card.style.transition = "opacity 0.3s ease, transform 0.3s ease";

    return card;
}

// ============================================================
// UI STATE HELPERS
// ============================================================

function showStatus(message) {
    statusMsg.textContent = message;
    statusMsg.style.display = "block";
    resultsInfo.style.display = "none";
}

function hideStatus() {
    statusMsg.style.display = "none";
}

function clearResults() {
    resultsList.innerHTML = "";
    // innerHTML = "" is the fastest way to clear all children.
    // Alternative: while(el.firstChild) el.removeChild(el.firstChild)
    // That's more thorough for removing event listeners but
    // since our cards have no persistent listeners that cause
    // memory leaks, innerHTML="" is fine and faster.
}

function setLoadingState(loading) {
    // Disable button and change text during search
    // Why disable the button?
    // Prevents double-submit — user clicking Search rapidly
    // would fire multiple fetch requests simultaneously,
    // causing race conditions where an older slower response
    // overwrites a newer faster one.
    searchBtn.disabled = loading;
    searchBtn.textContent = loading ? "Searching..." : "Search";
    searchInput.disabled = loading;
    // Also disable input — prevents query changing mid-request
    // which would make the results confusing.
}