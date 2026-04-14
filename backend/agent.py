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
- If the user is just greeting you or making small talk, respond naturally and briefly. Do NOT search for anything.
- For questions about CPP, base your answers only on the search results provided in the context.
- Do not make up information. If search results have nothing useful, say so and suggest cpp.edu or the relevant office.
- Be friendly and concise. Keep responses under 120 words.
- For broad questions (like "what majors are offered?"), summarize by college/department with 1-2 examples each, then link to cpp.edu for the full list. Do not enumerate every single major.
- Mention the source page when citing specific information.
- Always respond in the same language the user is writing in. Default to English if uncertain.
- If you cannot confidently respond in the user's language, use English instead.
"""

# greetings that should skip corpus search entirely
GREETINGS = {
    "hi", "hello", "hey", "hiya", "howdy", "sup", "what's up", "whats up",
    "good morning", "good afternoon", "good evening", "hola", "bonjour",
    "yo", "greetings", "hi there", "hello there", "hey there"
}

def is_greeting(message: str) -> bool:
    # check if the message is just a greeting with no real question
    cleaned = message.lower().strip().rstrip("!.,?")
    return cleaned in GREETINGS or len(cleaned.split()) <= 2 and any(g in cleaned for g in GREETINGS)

# anchor queries for common questions
ANCHOR_QUERIES = {
    "application deadline": "admissions application deadline dates",
    "when to apply": "admissions application deadline dates",
    "how to apply": "admissions application deadline dates",
    "what majors": "cpp majors programs degrees colleges",
    "majors offered": "cpp majors programs degrees colleges",
    "what degrees": "cpp majors programs degrees colleges",
    "financial aid": "financial aid scholarships grants office",
    "scholarship": "financial aid scholarships grants office",
    "dining": "on campus dining food restaurants meal plan",
    "dining options": "on campus dining food restaurants meal plan",
    "campus food": "on campus dining food restaurants meal plan",
    "student housing": "student housing residence halls on campus living",
    "residence hall": "student housing residence halls on campus living",
    "dorm": "student housing residence halls on campus living",
    "transfer": "transfer admissions requirements credits",
    "tuition": "tuition fees cost of attendance",
    "parking": "parking permits campus transportation",
    "library": "robert e kennedy library hours resources",
    "gym": "recreation center fitness campus",
    "student health": "student health services campus wellness",
    "financial aid office": "financial aid office location contact",
    "where is the": "campus offices locations contact information",
}

def get_anchor_query(user_message: str) -> str | None:
    # match on phrases first (more specific), then fall back to single keywords
    msg_lower = user_message.lower()
    for phrase, anchor in ANCHOR_QUERIES.items():
        if phrase in msg_lower:
            return anchor
    return None

def clean_history(history: list) -> list:
    # only keep plain user/assistant turns, strip tool internals
    cleaned = []
    for turn in history:
        if turn.get("role") in ("user", "assistant") and isinstance(turn.get("content"), str):
            cleaned.append({"role": turn["role"], "content": turn["content"]})
    return cleaned

def run_agent(user_message: str, history: list) -> dict:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += clean_history(history[:-1])
    messages.append({"role": "user", "content": user_message})

    sources = []

    # skip search entirely for greetings/small talk
    if not is_greeting(user_message):
        anchor = get_anchor_query(user_message)
        query = anchor if anchor else user_message
        tool_result = corpus_search(query)
        sources = tool_result.get("results", [])

        # retry with raw message if anchor gave nothing
        if not sources and anchor:
            tool_result = corpus_search(user_message)
            sources = tool_result.get("results", [])

        # only inject search results if we actually found something
        if sources:
            messages.append({
                "role": "system",
                "content": f"Relevant search results:\n{json.dumps(tool_result)}"
            })

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_tokens=350,
    )

    reply = response.choices[0].message.content
    return {"reply": reply, "sources": sources}