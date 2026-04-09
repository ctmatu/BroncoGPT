import os
from google import genai
from google.genai import types
from dotenv import load_dotenv
from tools import corpus_search, CORPUS_SEARCH_TOOL

load_dotenv()

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
MODEL = "gemini-2.0-flash"

SYSTEM_PROMPT = """You are BroncoGPT, the official AI assistant for Cal Poly Pomona (CPP).
Your job is to help students find accurate, helpful information about the university.

Rules:
- ALWAYS call corpus_search before answering any question about CPP.
- Base your answers on the search results. Do not make up information.
- If the corpus returns no results, say you couldn't find that info and suggest the student contact the relevant CPP office.
- Be friendly, concise, and helpful.
- When citing information, mention the source page so students can verify.
"""

def run_agent(user_message: str, history: list) -> dict:
    """
    Run one turn of the agent.
    Returns { reply: str, sources: list }
    """

    messages = []
    for turn in history[:-1]:
        messages.append({
            "role": turn["role"],
            "parts": [{"text": turn["content"]}]
        })
    messages.append({
        "role": "user",
        "parts": [{"text": user_message}]
    })

    tools = types.Tool(function_declarations=[CORPUS_SEARCH_TOOL])
    sources = []

    # --- First call: LLM decides whether to use a tool ---
    response = client.models.generate_content(
        model=MODEL,
        contents=messages,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=[tools],
        )
    )

    candidate = response.candidates[0].content

    # --- Check if model wants to call a tool ---
    tool_call = None
    for part in candidate.parts:
        if hasattr(part, "function_call") and part.function_call:
            tool_call = part.function_call
            break

    if tool_call and tool_call.name == "corpus_search":
        query = tool_call.args.get("query", user_message)

        tool_result = corpus_search(query)
        sources = tool_result.get("results", [])

        messages.append({"role": "model", "parts": candidate.parts})
        messages.append({
            "role": "user",
            "parts": [types.Part(
                function_response=types.FunctionResponse(
                    name="corpus_search",
                    response=tool_result
                )
            )]
        })

        final_response = client.models.generate_content(
            model=MODEL,
            contents=messages,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
            )
        )
        reply = final_response.text

    else:
        reply = response.text

    return {"reply": reply, "sources": sources}