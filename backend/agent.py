import os
from openai import OpenAI
from dotenv import load_dotenv
from tools import corpus_search, CORPUS_SEARCH_TOOL
import json

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
- Base your answers on the search results. Do not make up information.
- If the corpus returns no results, say you couldn't find that info and suggest the student contact the relevant CPP office.
- Be friendly, concise, and helpful.
- When citing information, mention the source page so students can verify.
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

def run_agent(user_message: str, history: list) -> dict:
    """
    Run one turn of the agent.
    Returns { reply: str, sources: list }
    """

    # Build messages array
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for turn in history[:-1]:
        messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": user_message})

    sources = []

    # First call — LLM decides whether to use a tool
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=TOOLS,
        tool_choice="auto"
    )

    msg = response.choices[0].message

    # Check if model wants to call a tool
    if msg.tool_calls:
        tool_call = msg.tool_calls[0]
        args = json.loads(tool_call.function.arguments)
        query = args.get("query", user_message)

        # Execute the tool
        tool_result = corpus_search(query)
        sources = tool_result.get("results", [])

        # Add assistant message + tool result to history
        messages.append(msg)
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": json.dumps(tool_result)
        })

        # Second call — generate final grounded answer
        final_response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
        )
        reply = final_response.choices[0].message.content

    else:
        reply = msg.content

    return {"reply": reply, "sources": sources}