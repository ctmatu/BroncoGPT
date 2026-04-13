import json
import os
import math
import re

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

# word variants so "majors" still matches "major" etc
STEM_MAP = {
    "majors": "major", "degrees": "degree", "programs": "program",
    "classes": "class", "courses": "course", "requirements": "requirement",
    "deadlines": "deadline", "applications": "application", "fees": "fee",
    "housing": "hous", "offices": "office", "students": "student",
    "scholarships": "scholarship", "internships": "internship",
    "departments": "department", "professors": "professor",
    "advisors": "advisor", "advisement": "advis", "advising": "advis",
    "transferring": "transfer", "transferred": "transfer", "transfers": "transfer",
    "graduating": "graduat", "graduation": "graduat", "graduate": "graduat",
    "enrolled": "enroll", "enrollment": "enroll", "enrolling": "enroll",
    "applying": "apply", "applied": "appli", "applicants": "applicant",
}

def normalize_words(words: list[str]) -> list[str]:
    # search both the original word and the normalized version
    normalized = []
    for w in words:
        normalized.append(STEM_MAP.get(w, w))
    return list(set(normalized + words))

def load_index() -> dict:
    with open(INDEX_PATH, "r") as f:
        return json.load(f)

def strip_footer(content: str) -> str:
    # cut off the cpp footer boilerplate that shows up on every page
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

def extract_headings(content: str) -> str:
    # pull out the ## headings, matches here are a good signal
    headings = re.findall(r'^#{1,3}\s+(.+)$', content, re.MULTILINE)
    return " ".join(headings).lower()

def best_snippet(content: str, query_words: list[str], length: int = 1200) -> str:
    # slide a window and grab the chunk with the most query hits
    content_lower = content.lower()
    best_pos = 0
    best_hits = 0

    step = 200
    for i in range(0, max(1, len(content) - length), step):
        window = content_lower[i:i + length]
        hits = sum(window.count(w) for w in query_words)
        if hits > best_hits:
            best_hits = hits
            best_pos = i

    return content[best_pos:best_pos + length].strip()

def corpus_search(query: str) -> dict:
    try:
        index = load_index()
    except FileNotFoundError:
        return {"results": [], "error": "index.json not found"}

    raw_words = query.lower().split()
    query_words = normalize_words(raw_words)
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

        # base frequency score, normalized by doc length
        word_count = len(content.split())
        if word_count == 0:
            continue
        raw_score = sum(content_lower.count(word) for word in query_words)
        if raw_score == 0:
            continue
        normalized_score = (raw_score / math.log(word_count + 1)) * 100

        url_bonus = sum(600 for word in raw_words if word in url_lower)

        # bigger boost for longer topic words in the url
        topic_words = [w for w in raw_words if len(w) > 4]
        url_topic_bonus = sum(1000 for word in topic_words if word in url_lower)

        intro = content_lower[:500]
        intro_bonus = sum(50 for word in query_words if word in intro)

        # heading matches are usually really relevant
        headings = extract_headings(content)
        heading_bonus = sum(400 for word in query_words if word in headings)

        phrase_bonus = 0
        for i in range(len(raw_words)):
            for j in range(i + 2, min(i + 4, len(raw_words) + 1)):
                phrase = " ".join(raw_words[i:j])
                if phrase in content_lower:
                    phrase_bonus += 500
                if phrase in intro:
                    phrase_bonus += 300

        total_score = (
            normalized_score + url_bonus + url_topic_bonus +
            intro_bonus + heading_bonus + phrase_bonus
        )

        results.append({
            "url": url,
            "filename": filename,
            "title": filename.replace(".md", "").replace("-", " ").replace("_", " ").title(),
            "snippet": best_snippet(content, query_words),
            "score": round(total_score, 2)
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    top = results[:3]

    for r in top:
        del r["score"]
        del r["filename"]  # llm doesn't need this

    return {"results": top}


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