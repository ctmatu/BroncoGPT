import os
import json
import random
from typing import Generator
from groq import Groq
from dotenv import load_dotenv
from tools import corpus_search, tokenize

load_dotenv()

client = Groq(api_key=os.environ["GROQ_API_KEY"])

MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """You are BroncoAI, the AI assistant for Cal Poly Pomona (CPP).
Help students find information about CPP. Be friendly, brief, and accurate.
- For greetings or small talk: reply briefly, do not mention CPP topics unless asked.
- For CPP questions: answer using only the search results provided. Do not invent info.
- Keep all responses under 250 words.
- For broad list questions (majors, programs): group by college with 1-2 examples, mention cpp.edu.
- If no search results are useful: say you couldn't find it and suggest cpp.edu or the relevant office.
- Do NOT add citation markers, "(Source: ...)", footnotes, or numbered references in your reply. Sources are shown separately by the UI.
- Reply in the same language the user writes in. Default to English if unsure.
- Never output raw JSON or search result objects. Always summarize in plain language.
"""

GREETINGS = {
    "hi", "hello", "hey", "hiya", "howdy", "sup", "what's up", "whats up",
    "good morning", "good afternoon", "good evening", "hola", "bonjour",
    "yo", "greetings", "hi there", "hello there", "hey there", "how are you",
    "how r u", "how are u",
}

GREETING_REPLIES = [
    "Hey! I'm BroncoAI, your CPP assistant. What can I help you with today?",
    "Hi there! I'm BroncoAI. Got a question about Cal Poly Pomona? Ask away!",
    "Hello! Happy to help with anything CPP-related. What's on your mind?",
]


def is_greeting(message: str) -> bool:
    cleaned = message.lower().strip().rstrip("!.,?")
    if cleaned in GREETINGS:
        return True
    words = cleaned.split()
    return len(words) <= 3 and words[0] in GREETINGS


def clean_history(history: list) -> list:
    cleaned = [
        {"role": t["role"], "content": t["content"]}
        for t in history
        if t.get("role") in ("user", "assistant") and isinstance(t.get("content"), str)
    ]
    return cleaned[-6:]


# ── Retrieval query builder ───────────────────────────────────────────────────

def _extract_topic(prior_history: list, min_tokens: int = 2) -> str:
    """
    Walk backwards through all prior USER messages and return the tokens from
    the first one that has enough substantive content (>= min_tokens meaningful
    words after stop-word removal).

    Handles multi-hop follow-up chains correctly:
      Turn 1 user: "where is the financial aid office"  -> topic: "financial aid"
      Turn 2 user: "how can I contact them?"            -> short -> looks back -> "financial aid"
      Turn 3 user: "can you find their phone number?"   -> short -> looks back -> "financial aid"

    Scanning ALL prior user turns (not just the immediately preceding one)
    means we always recover the original substantive topic, no matter how deep
    the follow-up chain goes.
    """
    for msg in reversed(prior_history):
        if msg.get("role") != "user":
            continue
        tokens = tokenize(msg["content"])
        if len(tokens) >= min_tokens:
            return " ".join(tokens[:6])  # cap at 6 tokens to stay focused
    return ""


def build_retrieval_query(user_message: str, history: list) -> str:
    tokens = tokenize(user_message)

    if len(tokens) <= 4:
        prior_history = history[:-1]
        topic = _extract_topic(prior_history)
        combined = f"{topic} {user_message}".strip() if topic else user_message
        return combined

    return user_message


def format_results(results: list) -> str:
    if not results:
        return ""
    parts = []
    for i, r in enumerate(results, 1):
        parts.append(f"[{i}] {r['title']}\nURL: {r['url']}\n{r['snippet']}")
    return "\n\n".join(parts)


def _build_messages(user_message: str, history: list) -> tuple[list, list]:
    print(f"[DEBUG] history length: {len(history)}")
    print(f"[DEBUG] retrieval query: {build_retrieval_query(user_message, history)}")
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += clean_history(history[:-1])

    retrieval_query = build_retrieval_query(user_message, history)
    tool_result = corpus_search(retrieval_query)
    sources = tool_result.get("results", [])

    user_turn = user_message
    if sources:
        user_turn = f"Search results:\n{format_results(sources)}\n\nUser question: {user_message}"

    messages.append({"role": "user", "content": user_turn})
    return messages, sources


def run_agent(user_message: str, history: list) -> dict:
    if is_greeting(user_message):
        return {"reply": random.choice(GREETING_REPLIES), "sources": []}

    messages, sources = _build_messages(user_message, history)
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_tokens=350,
    )
    return {"reply": response.choices[0].message.content, "sources": sources}


def run_agent_stream(user_message: str, history: list) -> Generator[str, None, None]:
    if is_greeting(user_message):
        reply = random.choice(GREETING_REPLIES)
        yield f"data: {json.dumps({'type': 'sources', 'sources': []})}\n\n"
        yield f"data: {json.dumps({'type': 'token', 'text': reply})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return

    try:
        messages, sources = _build_messages(user_message, history)
        yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"

        stream = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            max_tokens=350,
            stream=True,
        )

        for chunk in stream:
            text = chunk.choices[0].delta.content
            if text:
                yield f"data: {json.dumps({'type': 'token', 'text': text})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except Exception as e:
        print(f"[STREAM ERROR] {type(e).__name__}: {e}")
        yield f"data: {json.dumps({'type': 'error', 'text': str(e)})}\n\n"