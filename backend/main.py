from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from collections import defaultdict
import time
from agent import run_agent

app = FastAPI(title="BroncoGPT – CPP Student Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
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

class ChatResponse(BaseModel):
    reply: str
    sources: list

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, request: Request):
    check_rate_limit(request.client.host)
    try:
        history = [{"role": m.role, "content": m.content} for m in req.history]
        history.append({"role": "user", "content": req.message})
        result = run_agent(req.message, history)
        return ChatResponse(reply=result["reply"], sources=result["sources"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))