import json
import os
import re
from rank_bm25 import BM25Okapi

INDEX_PATH = os.path.join(os.path.dirname(__file__), "data", "index.json")
DOCS_PATH  = os.path.join(os.path.dirname(__file__), "data", "docs")

BLOCKLIST = {
    "kellogg-gallery__exhibitions__2024-inkandclay46.md",
    "kellogg-gallery__exhibitions__2021-ink-clay-45.md",
    "kellogg-gallery__exhibitions__2021-ink-clay-45-ve__index1.shtml.md",
    "kellogg-gallery__exhibitions__2019-ink-clay-44.md",
    "kellogg-gallery__exhibitions__2017-ink-clay-43.md",
    "sci__sees__biomedical.shtml.md",
    "library__about__news-events__golden-leaves__archived-past-exhibits.shtml.md",
    "cba__technology-and-operations-management__current-students__jobs-internships.shtml.md",
    "ceis__about__cctc-mild-moderat-support-needs.shtml.md",
    "ceis__about__cctc-extensive-support-needs-education-specialist.shtml.md",
    "ceis__about__cctc-multiple-subject.shtml.md",
    "ceis__about__cctc__multiple-subjects-credential-program.shtml.md",
    "conceptests__question-library__mat215.shtml.md",
    "conceptests__question-library__mat214.shtml.md",
    "kellogg-gallery__exhibitions__past_exhibitions.shtml.md",
    "our-cpp__students__stars__projects.shtml.md",
    "class__music__current-students__studio-proficiency-levels.shtml.md",
    "student-affairs__updcommittee.shtml.md",
    "studentsuccess__oss__i-am-first__profiles.shtml.md",
}

STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "this", "that", "these",
    "those", "it", "its", "about", "what", "how", "when", "where", "which",
    "who", "i", "my", "me", "we", "our", "you", "your", "whats", "their",
    "also", "just", "tell",
    # FIX 3: generic institutional nouns that hurt precision
    "office", "department", "center", "services", "service",
}


# ── Query cleaning ────────────────────────────────────────────────────────────

FILLER_PHRASES = re.compile(
    r"^(can you tell me|tell me|what can you tell me about|"
    r"what is|what are|how do i|where is|where are|"
    r"i want to know about|do you know|give me info on|"
    r"give me information about|more about|i need info on)\s+",
    re.IGNORECASE
)

def clean_query(text: str) -> str:
    """Strip conversational filler so BM25 sees only the meaningful terms."""
    text = text.strip()
    text = FILLER_PHRASES.sub("", text)
    return text.strip()


# ── Text helpers ──────────────────────────────────────────────────────────────

def strip_footer(content: str) -> str:
    footer_markers = [
        "Copyright ©",
        "A campus of\n[The California State University]",
        "[![Cal Poly Pomona logo",
        "[Apply](https://www.cpp.edu/apply/)\n[Maps]",
    ]
    for marker in footer_markers:
        idx = content.find(marker)
        if idx != -1:
            return content[:idx].strip()
    return content


def tokenize(text: str) -> list[str]:
    """Lowercase, remove punctuation, remove stop words."""
    words = re.findall(r'\b[a-z]{2,}\b', text.lower())
    return [w for w in words if w not in STOP_WORDS]


def best_snippet(content: str, query_words: list[str], length: int = 500) -> str:
    """Find the passage in content with the highest density of query words."""
    content_lower = content.lower()
    best_pos = 0
    best_hits = 0
    step = 150
    for i in range(0, max(1, len(content) - length), step):
        window = content_lower[i:i + length]
        hits = sum(window.count(w) for w in query_words)
        if hits > best_hits:
            best_hits = hits
            best_pos = i
    snippet = content[best_pos:best_pos + length].strip()
    lines = snippet.split('\n')
    if len(lines) > 2:
        snippet = '\n'.join(lines[1:-1]) if best_pos > 0 else '\n'.join(lines[:-1])
    return snippet.strip()


def _make_title(filename: str, url: str) -> str:
    """Generate a clean, human-readable title from the URL or filename."""
    try:
        parts = [p for p in url.rstrip("/").split("/") if p and "cpp.edu" not in p]
        if parts:
            last = parts[-1]
            last = re.sub(r'\.(shtml|html|php|aspx?)$', '', last)
            last = last.replace("-", " ").replace("_", " ")
            if len(parts) >= 2:
                parent = parts[-2].replace("-", " ").replace("_", " ")
                if parent.lower() not in {"index", "current-students", "about", "www", "static"}:
                    label = f"{parent.title()} – {last.title()}"
                    return label
            return last.title()
    except Exception:
        pass

    name = filename.replace(".md", "").replace(".shtml", "")
    name = name.replace("__", " – ").replace("_", " ").replace("-", " ")
    return name.title()


# ── FIX 5: Majors/programs intent detection ───────────────────────────────────

MAJORS_INTENT_RE = re.compile(
    r'\b(majors?|programs?|degrees?|colleges?|bachelor|undergrad(uate)?|graduate)\b',
    re.IGNORECASE,
)

# If any of these appear alongside a majors-intent word the query is specific,
# not a broad "what does CPP offer?" question — skip the canned response.
SUBJECT_WORDS = {
    "computer", "science", "engineering", "business", "nursing", "biology",
    "chemistry", "psychology", "history", "math", "mathematics", "english",
    "art", "music", "architecture", "accounting", "finance", "marketing",
    "management", "economics", "political", "sociology", "physics",
    "electrical", "mechanical", "civil", "aerospace", "environmental",
    "hospitality", "agriculture", "kinesiology", "communications",
    "graphic", "animation", "philosophy", "anthropology", "geography",
    "information", "technology", "cybersecurity", "data", "statistics",
    "pre", "med", "law", "education", "liberal", "interdisciplinary",
    "requirements", "courses", "curriculum", "classes", "units", "credits",
    "admission", "transfer", "gpa", "prerequisite",
}

MAJORS_CANNED = {
    "title": "Cal Poly Pomona – Academic Programs",
    "url":   "https://www.cpp.edu/academics/index.shtml",
    "snippet": (
        "CPP offers undergraduate and graduate programs across 9 colleges: "
        "Agriculture, Business Administration, Education & Integrative Studies, "
        "Engineering, Environmental Design, Letters Arts & Social Sciences, "
        "Science, Extended University, and the Collins College of Hospitality Management. "
        "Browse the full list at cpp.edu/academics."
    ),
}

def _is_majors_query(query: str) -> bool:
    """
    Return True only for truly generic 'what majors does CPP offer?' questions.
    Returns False as soon as a specific subject, field, or action word appears.
    """
    if not MAJORS_INTENT_RE.search(query):
        return False

    tokens = set(tokenize(query))

    # Any recognised subject word → specific question, not a broad listing
    if tokens & SUBJECT_WORDS:
        return False

    # 5+ unique meaningful tokens → specific question
    if len(tokens) >= 5:
        return False

    return True


# ── Corpus loading ────────────────────────────────────────────────────────────

_DOCS: list[dict] = []
_BM25: BM25Okapi | None = None


def _build_index():
    global _DOCS, _BM25

    try:
        with open(INDEX_PATH, "r") as f:
            index: dict[str, str] = json.load(f)
    except FileNotFoundError:
        print("[tools] WARNING: index.json not found — corpus search disabled")
        return

    tokenized_corpus = []

    for url, filename in index.items():
        if filename in BLOCKLIST:
            continue
        filepath = os.path.join(DOCS_PATH, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                raw = f.read()
        except FileNotFoundError:
            continue

        if len(raw) < 300 or len(raw) > 80_000:
            continue

        content = strip_footer(raw)
        tokens  = tokenize(content)
        if not tokens:
            continue

        _DOCS.append({
            "url":      url,
            "filename": filename,
            "title":    _make_title(filename, url),
            "content":  content,
        })
        tokenized_corpus.append(tokens)

    _BM25 = BM25Okapi(tokenized_corpus)
    print(f"[tools] BM25 index built: {len(_DOCS)} documents")


def _get_index():
    if _BM25 is None:
        _build_index()
    return _DOCS, _BM25


# ── Main search function ──────────────────────────────────────────────────────

def corpus_search(query: str, top_k: int = 5) -> dict:
    docs, bm25 = _get_index()
    if not docs or bm25 is None:
        return {"results": [], "error": "Corpus not available"}

    query = clean_query(query)

    # FIX 5: intercept broad majors/programs queries before BM25
    if _is_majors_query(query):
        return {"results": [MAJORS_CANNED]}

    query_tokens = tokenize(query)
    if not query_tokens:
        return {"results": []}

    scores = bm25.get_scores(query_tokens)

    # Only apply prefix boost if the top result is confident
    raw_ranked = sorted(zip(scores, docs), key=lambda x: x[0], reverse=True)
    top_prefix = None
    if raw_ranked and raw_ranked[0][0] >= 8.0:
        top_filename = raw_ranked[0][1]["filename"]
        parts = top_filename.split("__")
        if len(parts) >= 2:
            top_prefix = "__".join(parts[:2])

    # Re-rank with prefix boost
    def boosted_score(score, doc):
        if top_prefix and doc["filename"].startswith(top_prefix):
            return score * 1.5
        return score

    ranked = sorted(
        [(boosted_score(s, d), d) for s, d in zip(scores, docs)],
        key=lambda x: x[0],
        reverse=True,
    )

    MIN_SCORE = 1.0
    results = []
    seen = set()

    for score, doc in ranked:
        if len(results) >= top_k:
            break
        if score < MIN_SCORE or doc["filename"] in seen:
            continue
        seen.add(doc["filename"])
        results.append({
            "url":     doc["url"],
            "title":   doc["title"],
            "snippet": best_snippet(doc["content"], query_tokens),
        })

    return {"results": results[:top_k]}


# ── Tool schema ───────────────────────────────────────────────────────────────

CORPUS_SEARCH_TOOL = {
    "name": "corpus_search",
    "description": (
        "Search the official Cal Poly Pomona (CPP) university knowledge base to find "
        "accurate information about programs, admissions, financial aid, campus resources, "
        "policies, deadlines, and anything else students ask about. "
        "Always use this tool before answering so your response is grounded in real CPP data. "
        "If the first search returns weak results, call it again with a rephrased query."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "A concise, keyword-focused search query based on what the student is asking. "
                    "Use specific academic terms — e.g. 'computer science major requirements' "
                    "rather than 'what classes do I need for CS'."
                )
            }
        },
        "required": ["query"]
    }
}