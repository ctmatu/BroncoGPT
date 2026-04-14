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
    "who", "i", "my", "me", "we", "our", "you", "your",
}

ANCHOR_QUERIES = {
    "application deadline": "admissions application deadline dates",
    "when to apply": "admissions application deadline dates",
    "how to apply": "admissions application process",
    "what majors": "undergraduate programs majors degrees",
    "majors offered": "undergraduate programs majors degrees",
    "list of majors": "undergraduate programs majors degrees",
    "what degrees": "undergraduate programs majors degrees",
    "what can i study": "undergraduate programs majors degrees",
    "financial aid": "financial aid scholarships grants",
    "scholarship": "financial aid scholarships",
    "dining": "dining food meal campus",
    "dining options": "dining food meal campus",
    "on campus dining": "dining food meal campus",
    "campus dining": "dining food meal campus",
    "meal plan": "dining meal plan food",
    "food on campus": "dining food meal campus",
    "where to eat": "dining food meal campus",
    "student housing": "student housing residence halls",
    "residence hall": "student housing residence halls",
    "dorm": "student housing residence halls",
    "transfer": "transfer admissions requirements",
    "tuition": "tuition fees cost attendance",
    "parking": "parking permits campus",
    "library": "kennedy library hours",
    "gym": "recreation center fitness",
    "student health": "student health services",
    "financial aid office": "financial aid contact location",
    "where is the": "campus offices locations contact",
}

def get_anchor_query(user_message: str) -> str | None:
    msg_lower = user_message.lower()
    for phrase, anchor in ANCHOR_QUERIES.items():
        if phrase in msg_lower:
            return anchor
    return None


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
    words = re.findall(r'\b[a-z]{2,}\b', text.lower())
    return [w for w in words if w not in STOP_WORDS]


def best_snippet(content: str, query_words: list[str], length: int = 600) -> str:
    """Find the passage with highest query word density."""
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
    # If no hits found, just return the top of the doc
    if best_hits == 0:
        return content[:length].strip()
    snippet = content[best_pos:best_pos + length].strip()
    lines = snippet.split('\n')
    if len(lines) > 2:
        snippet = '\n'.join(lines[1:-1]) if best_pos > 0 else '\n'.join(lines[:-1])
    return snippet.strip()


def _make_title(filename: str, url: str) -> str:
    try:
        parts = [p for p in url.rstrip("/").split("/") if p and "cpp.edu" not in p]
        if parts:
            last = parts[-1]
            last = re.sub(r'\.(shtml|html|php|aspx?)$', '', last)
            last = last.replace("-", " ").replace("_", " ")
            if len(parts) >= 2:
                parent = parts[-2].replace("-", " ").replace("_", " ")
                if parent.lower() not in {"index", "current-students", "about", "www", "static"}:
                    return f"{parent.title()} – {last.title()}"
            return last.title()
    except Exception:
        pass
    name = filename.replace(".md", "").replace(".shtml", "")
    name = name.replace("__", " – ").replace("_", " ").replace("-", " ")
    return name.title()


# ── Module-level singletons ───────────────────────────────────────────────────

_DOCS: list[dict] = []
_BM25 = None


def _build_index():
    global _DOCS, _BM25
    from rank_bm25 import BM25Okapi

    try:
        with open(INDEX_PATH, "r") as f:
            index: dict[str, str] = json.load(f)
    except FileNotFoundError:
        print("[tools] WARNING: index.json not found")
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
        tokens = tokenize(content)
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


# ── Search ────────────────────────────────────────────────────────────────────

def corpus_search(query: str, top_k: int = 5) -> dict:
    docs, bm25 = _get_index()

    if not docs or bm25 is None:
        return {"results": [], "error": "Corpus not available"}

    query_tokens = tokenize(query)
    if not query_tokens:
        return {"results": []}

    bm25_scores = bm25.get_scores(query_tokens)

    # Normalize BM25 scores to 0-1 range
    max_bm25 = max(bm25_scores) if max(bm25_scores) > 0 else 1
    
    scored = []
    for i, (score, doc) in enumerate(zip(bm25_scores, docs)):
        normalized_bm25 = score / max_bm25

        # URL bonus — replicate what made the old system good
        url_lower = doc["url"].lower()
        filename_lower = doc["filename"].lower()
        topic_words = [w for w in query_tokens if len(w) > 3]
        url_bonus = sum(0.4 for w in topic_words if w in url_lower or w in filename_lower)

        # Intro bonus — words in first 500 chars of content
        intro = doc["content"][:500].lower()
        intro_bonus = sum(0.05 for w in query_tokens if w in intro)

        # Exact phrase bonus
        phrase_bonus = 0.3 if " ".join(query_tokens[:3]) in doc["content"].lower() else 0

        total = normalized_bm25 + url_bonus + intro_bonus + phrase_bonus
        scored.append((total, doc))

    scored.sort(key=lambda x: x[0], reverse=True)

    results = []
    for total_score, doc in scored[:top_k]:
        if total_score <= 0:
            break
        results.append({
            "url":     doc["url"],
            "title":   doc["title"],
            "snippet": best_snippet(doc["content"], query_tokens),
        })

    return {"results": results}


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
                    "A concise, keyword-focused search query. "
                    "Use specific terms e.g. 'dining options campus food' rather than 'where can I eat'."
                )
            }
        },
        "required": ["query"]
    }
}