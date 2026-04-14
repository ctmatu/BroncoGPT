from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
from collections import defaultdict
from supabase import create_client, Client
import time
import os
from dotenv import load_dotenv
from agent import run_agent, run_agent_stream

load_dotenv()

app = FastAPI(title="BroncoGPT – CPP Student Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Supabase client ───────────────────────────────────────────────────────────
supabase: Client = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SERVICE_KEY"],
)

# ── Rate limiter: 20 requests per IP per hour ─────────────────────────────────
_request_counts: dict[str, list] = defaultdict(list)

def check_rate_limit(ip: str):
    now = time.time()
    hour_ago = now - 3600
    _request_counts[ip] = [t for t in _request_counts[ip] if t > hour_ago]
    if len(_request_counts[ip]) >= 20:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again later.")
    _request_counts[ip].append(now)


# ── Auth helper ───────────────────────────────────────────────────────────────
def get_current_user(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ")[1]
    try:
        return supabase.auth.get_user(token).user
    except Exception:
        return None


# ── Static / frontend ─────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def root():
    return FileResponse("static/index.html")

@app.get("/health")
def health():
    return {"status": "ok", "model": "openrouter/auto"}


# ── Shared request/response models ───────────────────────────────────────────

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Message]] = []
    conversation_id: Optional[str] = None

class ChatResponse(BaseModel):
    reply: str
    sources: list
    conversation_id: Optional[str] = None


# ── Helper: persist a completed exchange to Supabase ─────────────────────────

def _save_to_db(user, req: ChatRequest, reply: str, sources: list) -> Optional[str]:
    """Saves user + assistant messages. Returns the conversation_id."""
    conversation_id = req.conversation_id

    if not conversation_id:
        title = req.message[:60] + ("..." if len(req.message) > 60 else "")
        conv = supabase.table("conversations").insert({
            "user_id": str(user.id),
            "title": title,
        }).execute()
        conversation_id = conv.data[0]["id"]

    supabase.table("messages").insert({
        "conversation_id": conversation_id,
        "role": "user",
        "content": req.message,
        "sources": [],
    }).execute()

    supabase.table("messages").insert({
        "conversation_id": conversation_id,
        "role": "assistant",
        "content": reply,
        "sources": sources,
    }).execute()

    return conversation_id


# ── POST /chat — original non-streaming endpoint (kept for compatibility) ─────

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, request: Request):
    check_rate_limit(request.client.host)
    user = get_current_user(request)

    try:
        history = [{"role": m.role, "content": m.content} for m in req.history]
        history.append({"role": "user", "content": req.message})

        result = run_agent(req.message, history)
        reply   = result["reply"]
        sources = result["sources"]

        conversation_id = req.conversation_id
        if user:
            conversation_id = _save_to_db(user, req, reply, sources)

        return ChatResponse(reply=reply, sources=sources, conversation_id=conversation_id)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── POST /chat/stream — streaming SSE endpoint ────────────────────────────────
#
# The frontend connects here. Events arrive as SSE:
#   data: {"type": "sources", "sources": [...]}
#   data: {"type": "token",   "text": "..."}
#   data: {"type": "done"}
#
# After "done", the frontend POSTs to /chat/save to persist the exchange.

@app.post("/chat/stream")
def chat_stream(req: ChatRequest, request: Request):
    check_rate_limit(request.client.host)

    history = [{"role": m.role, "content": m.content} for m in req.history]
    history.append({"role": "user", "content": req.message})

    return StreamingResponse(
        run_agent_stream(req.message, history),
        media_type="text/event-stream",
        headers={
            # Prevent proxies / nginx from buffering the stream
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
        },
    )


# ── POST /chat/save — called by frontend after stream completes ───────────────
#
# Receives the fully assembled reply + sources so we can persist to Supabase.

class SaveRequest(BaseModel):
    message: str
    reply: str
    sources: list
    conversation_id: Optional[str] = None

class SaveResponse(BaseModel):
    conversation_id: Optional[str] = None

@app.post("/chat/save", response_model=SaveResponse)
def chat_save(req: SaveRequest, request: Request):
    user = get_current_user(request)
    if not user:
        return SaveResponse(conversation_id=req.conversation_id)

    try:
        # Reuse the save helper — wrap into ChatRequest-compatible shape
        class _Req:
            message = req.message
            conversation_id = req.conversation_id

        conversation_id = _save_to_db(user, _Req(), req.reply, req.sources)
        return SaveResponse(conversation_id=conversation_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Conversation history ──────────────────────────────────────────────────────

@app.get("/conversations")
def get_conversations(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    convs = supabase.table("conversations")\
        .select("*")\
        .eq("user_id", str(user.id))\
        .order("created_at", desc=True)\
        .execute()
    return convs.data


@app.get("/conversations/{conversation_id}/messages")
def get_messages(conversation_id: str, request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    msgs = supabase.table("messages")\
        .select("*")\
        .eq("conversation_id", conversation_id)\
        .order("created_at")\
        .execute()
    return msgs.data