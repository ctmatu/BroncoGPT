setup:
1) `cd backend`
2) `python3 -m venv venv`
3) `source venv/bin/activate`
4) `pip install -r requirements.txt`
5) `cp .env.example .env` <- paste the Gemini API key inside it
6) `uvicorn main:app --reload`

the server runs at `http://localhost:8000`

for the api:
`POST /chat`
```json
// to request
{ "message": "...", "history": [] }

// the response
{ "reply": "...", "sources": [{ "title", "url", "filename" }] }
```
`GET /health` <- will confirm the server is live

for our data dev:
1) Place `index.json` in `backend/data/index.json`
2) Place all markdown files in `backend/data/docs/`
3) `index.json` format: `{ "https://cpp.edu/page": "filename.md" }`
4) If you have a custom search implementation, you can replace `tools.py`

to get your own gemini key:
just ask me for it, or you can make one for free at [aistudio.google.com] / (https://aistudio.google.com)