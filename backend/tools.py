import json
import os

INDEX_PATH = os.path.join(os.path.dirname(__file__), "data", "index.json")
DOCS_PATH  = os.path.join(os.path.dirname(__file__), "data", "docs")

def load_index() -> dict:
    with open(INDEX_PATH, "r") as f:
        return json.load(f)

def corpus_search(query: str) -> dict:
    """
    Search CPP university markdown documents by keyword.
    Returns top 3 matching results with content snippets and source URLs.
    """
    try:
        index = load_index()
    except FileNotFoundError:
        return {"results": [], "error": "index.json not found"}

    query_lower = query.lower()
    results = []

    for url, filename in index.items():
        filepath = os.path.join(DOCS_PATH, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        except FileNotFoundError:
            continue

        words = query_lower.split()
        score = sum(1 for word in words if word in content.lower())

        if score > 0:
            results.append({
                "url": url,
                "filename": filename,
                "title": filename.replace(".md", "").replace("-", " ").replace("_", " ").title(),
                "snippet": content[:800],
                "score": score
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    top = results[:3]

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