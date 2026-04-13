import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from tools import corpus_search, CORPUS_SEARCH_TOOL

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"]
)

MODEL = "openrouter/auto"

SYSTEM_PROMPT = """You are BroncoAI, the official AI assistant for Cal Poly Pomona (CPP).
Your job is to help students find accurate, helpful information about the university.

Rules:
- ALWAYS call corpus_search before answering any question about CPP.
- When forming your search query, use specific academic keywords — not the student's raw message.
  Example: if they ask "how do I get financial help?", search "financial aid scholarships CPP".
- If the first search returns no useful results, call corpus_search again with a rephrased query before giving up.
- Base your answers on the search results. Do not make up information.
- If after two searches the corpus returns no results, say you couldn't find that info and suggest the student contact the relevant CPP office or visit cpp.edu.
- Be friendly, concise, and helpful.
- When citing information, mention the source page so students can verify.
- Always respond in the same language the user is writing in. If the user writes in Spanish, respond in Spanish. If they write in Chinese, respond in Chinese. Default to English if uncertain.
- If you cannot confidently respond in the user's language, respond in English rather than producing broken or inaccurate text.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": CORPUS_SEARCH_TOOL["name"],
            "description": CORPUS_SEARCH_TOOL["description"],
            "parameters": CORPUS_SEARCH_TOOL["parameters"]
        }
    }
]

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
    # build messages, skip the last item in history since we add the user message fresh
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += clean_history(history[:-1])
    messages.append({"role": "user", "content": user_message})

    sources = []
    search_attempts = 0
    max_searches = 2

    while search_attempts < max_searches:
        # force a search on the first try, let it decide on retry
        tool_choice = "required" if search_attempts == 0 else "auto"

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice=tool_choice
        )

        msg = response.choices[0].message

        if not msg.tool_calls:
            # only hits here on retry if model decides it doesn't need to search
            reply = msg.content
            return {"reply": reply, "sources": sources}

        tool_call = msg.tool_calls[0]
        args = json.loads(tool_call.function.arguments)
        query = args.get("query", user_message)

        # on the first search, override with anchor query if we have one
        if search_attempts == 0:
            anchor = get_anchor_query(user_message)
            if anchor:
                query = anchor

        tool_result = corpus_search(query)
        new_sources = tool_result.get("results", [])
        search_attempts += 1

        # merge sources, skip dupes
        seen_urls = {s["url"] for s in sources}
        for s in new_sources:
            if s["url"] not in seen_urls:
                sources.append(s)
                seen_urls.add(s["url"])

        messages.append(msg)
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": json.dumps(tool_result)
        })

        if new_sources:
            break

        # no results, nudge it to try again with a different query
        if search_attempts < max_searches:
            messages.append({
                "role": "user",
                "content": (
                    "The search returned no results. "
                    "Please try corpus_search again with a different, more specific query."
                )
            })

    # generate the final answer
    final_response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
    )

    reply = final_response.choices[0].message.content
    return {"reply": reply, "sources": sources}