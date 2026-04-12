# BroncoGPT — AI Campus Knowledge Assistant for Cal Poly Pomona

> An AI-powered conversational assistant that answers student questions about Cal Poly Pomona using grounded, source-attributed responses from the official CPP website corpus.

---

## Demo

> _Add a screenshot or screen recording of the chat interface here_

---

## Features

### Core Requirements
- **Chat Interface** — Clean, conversational web UI for asking natural language questions
- **Corpus Search Tool** — Tool calling integration that searches 7,900+ cleaned CPP web pages
- **Grounded Responses** — Answers are based strictly on the CPP corpus; the agent says so when information is not found
- **Source Attribution** — Every response includes the source URL(s) from the corpus
- **Multi-turn Conversation** — Maintains context across messages so students don't have to repeat themselves

### Bonus Features
- **User Accounts & Chat History** — Students can create accounts and revisit past conversations
- **Email Verification** — Secure account creation with email verification
- **Multilingual Support** — Interface supports multiple languages (responses in English)
- **Starter Questions** — Suggested questions displayed on load to help students get started
- **Semantic Search** — Embedding-based search for better retrieval beyond keyword matching

---

## Architecture

```
Student types question
        ↓
Frontend (HTML/JS) sends message to FastAPI backend
        ↓
agent.py receives message + conversation history
        ↓
LLM (via OpenRouter) decides to call the corpus_search tool
        ↓
tools.py searches 7,900+ cleaned CPP markdown files
        ↓
Top results returned with content snippets + source URLs
        ↓
LLM reads results and writes a grounded, attributed answer
        ↓
Student sees the response with source links
```

### How the Corpus Search Works
The raw CPP website corpus (8,042 scraped pages) was cleaned with a multi-pass pipeline:
1. Stripped universal navbar and header boilerplate present on every page
2. Extracted content starting from the first markdown heading (`#`) on each page
3. Removed footer boilerplate (social links, copyright, etc.)
4. Filtered out redirect pages, oversized non-informational files, and known noisy documents

The result is **7,912 clean markdown files** indexed by their original CPP URL. At query time, the search function scores documents using normalized term frequency, URL relevance bonuses, and exact phrase matching to surface the most relevant pages.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML, CSS, JavaScript |
| Backend | Python, FastAPI, Uvicorn |
| AI Agent | OpenRouter API (auto-selects best available model) |
| Search | Custom keyword search with semantic re-ranking |
| Data | 7,912 cleaned Markdown files + index.json |

---

## Setup & Running Locally

### Prerequisites
- Python 3.9+
- An [OpenRouter](https://openrouter.ai/) API key (free tier available)

### 1. Clone the repository
```bash
git clone https://github.com/ctmatu/BroncoGPT.git
cd BroncoGPT
```

### 2. Add the corpus
Download the cleaned corpus and place the files as follows:
```
backend/
└── data/
    ├── index.json
    └── docs/
        ├── admissions_index.md
        ├── financial-aid_index.md
        └── ... (7,912 .md files)
```
> The corpus is not included in this repository due to its size. Contact the team for access or run the cleaning pipeline yourself (see `explore.py` and the cleaning scripts).

### 3. Install Python dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 4. Set up environment variables
```bash
cp .env.example .env
```
Open `.env` and add your OpenRouter API key:
```
OPENROUTER_API_KEY=your_key_here
```

### 5. Start the backend
```bash
uvicorn main:app --reload
```
The API will be running at `http://localhost:8000`

### 6. Open the frontend
Open `frontend/index.html` in your browser, or serve it with any static file server.

---

## Project Structure

```
BroncoGPT/
├── backend/
│   ├── data/
│   │   ├── index.json          # Maps CPP URLs to markdown filenames
│   │   └── docs/               # 7,912 cleaned CPP web pages
│   ├── agent.py                # LLM agent logic and tool calling loop
│   ├── tools.py                # corpus_search function and tool definition
│   ├── main.py                 # FastAPI server and API routes
│   ├── requirements.txt        # Python dependencies
│   └── .env.example            # Environment variable template
├── frontend/
│   └── index.html              # Chat interface
├── explore.py                  # Corpus exploration and data cleaning scripts
├── search.py                   # Standalone search testing
└── README.md
```

---

## Team

| Name | Role |
|---|---|
| _Yengkai Yang_ | Project Lead |
| _Caden Thomas Matuszewicz_ | LLM & Agent Development |
| _Swathi Kabilan_ | Data Engineering & Search |
| _Katie Yue_ | Frontend & UI/UX |
| _Sophia Raldugina-Zhu_ | Q/A Test / Documentation / Presentation |

---

## License

Built for the MISSA ITC AI Case Competition 2026.





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
