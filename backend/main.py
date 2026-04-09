from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from agent import run_agent

app = FastAPI(title="BroncoAI  CPP Student Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class Message(BaseModel):
    role: str      
    content: str

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Message]] = []

class ChatResponse(BaseModel):
    reply: str
    sources: list

@app.get("/health")
def health():
    return {"status": "ok", "model": "gemini-2.0-flash"}

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    try:
        history = [{"role": m.role, "content": m.content} for m in req.history]
        history.append({"role": "user", "content": req.message})
        result = run_agent(req.message, history)
        return ChatResponse(reply=result["reply"], sources=result["sources"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))