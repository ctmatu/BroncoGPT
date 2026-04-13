import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from tools import corpus_search

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"]
)

MODEL = "openrouter/auto"

SYSTEM_PROMPT = """You are BroncoAI, the official AI assistant for Cal Poly Pomona (CPP).
Your job is to help students find accurate, helpful information about the university.

Rules:
- Base your answers on the search results provided. Do not make up information.
- If the search results have no useful info, say you couldn't find it and suggest the student contact the relevant CPP office or visit cpp.edu.
- Be friendly, concise, and helpful. Keep responses under 150 words.
- Never list every item from a long list — instead summarize by category or department and link to the full list.
  Example: for "what majors are offered?" name the colleges (Engineering, Business, Arts, etc.) with 1-2 example majors each, then say "see cpp.edu/academic-programs for the full list."
- When citing information, mention the source page so students can verify.
- Always respond in the same language the user is writing in. If the user writes in Spanish, respond in Spanish. If they write in Chinese, respond in Chinese. Default to English if uncertain.
- If you cannot confidently respond in the user's language, respond in English rather than producing broken or inaccurate text.
"""

# anchor queries for common questions — maps likely phrasings to better search terms
ANCHOR_QUERIES = {
    "deadline": "admissions application deadline dates",
    "apply": "admissions application deadline dates",
    "major": "cpp majors programs degrees colleges",
    "majors": "cpp majors programs degrees colleges",
    "degree": "cpp majors programs degrees colleges",
    "financial aid": "financial aid scholarships grants office",
    "financial": "financial aid scholarships grants office",
    "aid": "financial aid scholarships grants office",
    "scholarship": "financial aid scholarships grants office",
    "dining": "on campus dining food restaurants meal plan",
    "food": "on campus dining food restaurants meal plan",
    "eat": "on campus dining food restaurants meal plan",
    "housing": "student housing residence halls on campus living",
    "dorm": "student housing residence halls on campus living",
    "transfer": "transfer admissions requirements credits",
    "tuition": "tuition fees cost of attendance",
    "cost": "tuition fees cost of attendance",
    "engineering": "college of engineering majors programs cpp",
    "parking": "parking permits campus transportation",
    "library": "robert e kennedy library hours resources",
    "gym": "recreation center fitness campus",
    "health": "student health services campus wellness",
    "address": "campus offices locations contact information",
    "location": "campus offices locations contact information",
    "where is": "campus offices locations contact information",
    "office hours": "campus offices locations contact information",
    "contact": "campus offices locations contact information",
}

def get_anchor_query(user_message: str) -> str | None:
    # check if the message matches a known common question
    msg_lower = user_message.lower()
    for keyword, anchor in ANCHOR_QUERIES.items():
        if keyword in msg_lower:
            return anchor
    return None

def clean_history(history: list) -> list:
    # strip out tool call stuff from old turns, just keep the actual messages
    cleaned = []
    for turn in history:
        if turn.get("role") in ("user", "assistant") and isinstance(turn.get("content"), str):
            cleaned.append({"role": turn["role"], "content": turn["content"]})
    return cleaned

def run_agent(user_message: str, history: list) -> dict:
    # run corpus search directly in python — skip the first LLM call entirely
    anchor = get_anchor_query(user_message)
    query = anchor if anchor else user_message
    tool_result = corpus_search(query)
    sources = tool_result.get("results", [])

    # if nothing came back, retry with the raw message
    if not sources and anchor:
        tool_result = corpus_search(user_message)
        sources = tool_result.get("results", [])

    # build messages with search results already baked in
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += clean_history(history[:-1])
    messages.append({"role": "user", "content": user_message})
    messages.append({
        "role": "system",
        "content": f"Search results for this question:\n{json.dumps(tool_result)}"
    })

    # single LLM call to generate the answer
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_tokens=400,
    )

    reply = response.choices[0].message.content
    return {"reply": reply, "sources": sources}