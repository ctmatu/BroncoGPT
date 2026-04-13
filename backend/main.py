from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from collections import defaultdict
from supabase import create_client, Client
import time
import os
from dotenv import load_dotenv
from agent import run_agent

load_dotenv()

app = FastAPI(title="BroncoGPT – CPP Student Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Supabase client (service role for backend operations) ──
supabase: Client = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SERVICE_KEY"]
)

# ── Rate limiter: 20 requests per IP per hour ──
request_counts = defaultdict(list)

def check_rate_limit(ip: str):
    now = time.time()
    hour_ago = now - 3600
    request_counts[ip] = [t for t in request_counts[ip] if t > hour_ago]
    if len(request_counts[ip]) >= 20:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again later.")
    request_counts[ip].append(now)

# ── Verify Supabase JWT and return user ──
def get_current_user(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ")[1]
    try:
        user = supabase.auth.get_user(token)
        return user.user
    except Exception:
        return None

# ── Serve frontend ──
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def root():
    return FileResponse("static/index.html")

@app.get("/health")
def health():
    return {"status": "ok", "model": "openrouter/auto"}

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

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, request: Request):
    check_rate_limit(request.client.host)
    user = get_current_user(request)

    try:
        history = [{"role": m.role, "content": m.content} for m in req.history]
        history.append({"role": "user", "content": req.message})
        result = run_agent(req.message, history)
        reply = result["reply"]
        sources = result["sources"]

        # ── Save to Supabase if user is logged in ──
        conversation_id = req.conversation_id
        if user:
            # Create new conversation if none exists
            if not conversation_id:
                title = req.message[:60] + ("..." if len(req.message) > 60 else "")
                conv = supabase.table("conversations").insert({
                    "user_id": str(user.id),
                    "title": title
                }).execute()
                conversation_id = conv.data[0]["id"]

            # Save user message
            supabase.table("messages").insert({
                "conversation_id": conversation_id,
                "role": "user",
                "content": req.message,
                "sources": []
            }).execute()

            # Save assistant message
            supabase.table("messages").insert({
                "conversation_id": conversation_id,
                "role": "assistant",
                "content": reply,
                "sources": sources
            }).execute()

        return ChatResponse(reply=reply, sources=sources, conversation_id=conversation_id)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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