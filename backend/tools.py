import json
import os
import math

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

def load_index() -> dict:
    with open(INDEX_PATH, "r") as f:
        return json.load(f)

def strip_footer(content: str) -> str:
    """Remove common CPP page footer boilerplate."""
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

def corpus_search(query: str) -> dict:
    """
    Search CPP university markdown documents by keyword.
    Returns top 3 matching results with content snippets and source URLs.
    """
    try:
        index = load_index()
    except FileNotFoundError:
        return {"results": [], "error": "index.json not found"}

    query_words = query.lower().split()
    results = []

    for url, filename in index.items():
        if filename in BLOCKLIST:
            continue

        filepath = os.path.join(DOCS_PATH, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                raw_content = f.read()
        except FileNotFoundError:
            continue

        if len(raw_content) < 300 or len(raw_content) > 80000:
            continue

        content = strip_footer(raw_content)
        content_lower = content.lower()
        url_lower = url.lower()

        # Normalized frequency score
        word_count = len(content.split())
        if word_count == 0:
            continue
        raw_score = sum(content_lower.count(word) for word in query_words)
        if raw_score == 0:
            continue
        normalized_score = (raw_score / math.log(word_count + 1)) * 100

        # URL match bonus
        url_bonus = sum(600 for word in query_words if word in url_lower)

        # Topic word URL bonus - ignore short filler words
        topic_words = [w for w in query_words if len(w) > 4]
        url_topic_bonus = sum(1000 for word in topic_words if word in url_lower)

        # Intro bonus
        intro = content_lower[:500]
        intro_bonus = sum(50 for word in query_words if word in intro)

        # Exact phrase bonus
        phrase_bonus = 0
        for i in range(len(query_words)):
            for j in range(i+2, min(i+4, len(query_words)+1)):
                phrase = " ".join(query_words[i:j])
                if phrase in content_lower:
                    phrase_bonus += 500
                if phrase in intro:
                    phrase_bonus += 300

        total_score = normalized_score + url_bonus + url_topic_bonus + intro_bonus + phrase_bonus

        results.append({
            "url": url,
            "filename": filename,
            "title": filename.replace(".md", "").replace("-", " ").replace("_", " ").title(),
            "snippet": content[:800],
            "score": round(total_score, 2)
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    top = results[:5]

    for r in top:
        del r["score"]

    return {"results": top}


CORPUS_SEARCH_TOOL = {
    "name": "corpus_search",
    "description": (
        "Search the official Cal Poly Pomona (CPP) university knowledge base to find "
        "accurate information about programs, admissions, financial aid, campus resources, "
        "policies, deadlines, and anything else students ask about. "
        "Always use this tool before answering so your response is grounded in real CPP data."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "A concise search query based on what the student is asking about."
            }
        },
        "required": ["query"]
    }
}