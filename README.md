# NexusAI — Professional AI Chatbot

A production-quality AI assistant built with **Flask + OpenRouter**, featuring a ChatGPT-inspired interface with streaming responses, persistent conversation history, markdown rendering, and a premium dark-mode UI.

> **Original project:** A basic keyword-matching college chatbot with ~60 lines of code.
> **After upgrade:** A fully functional AI assistant with real LLM integration via OpenRouter, SSE streaming, SQLite persistence, 47 automated tests, and a polished responsive UI.

---

## Features

| Category | Features |
|---|---|
| **AI** | Real OpenRouter API, streaming SSE, multi-turn context, configurable model |
| **UI/UX** | Premium dark/light theme, ChatGPT-inspired layout, smooth animations |
| **Chat** | Markdown rendering, syntax highlighting, code copy, typing indicator, stop generation, regenerate response |
| **History** | Persistent SQLite storage, conversation list, rename, delete, search, auto-title |
| **Sidebar** | Collapsible desktop sidebar, mobile slide-in drawer |
| **Settings** | Theme toggle, model selector, API status, keyboard shortcuts |
| **Security** | API key never exposed to browser, parameterised SQL, HTML sanitisation (DOMPurify), rate limiting |
| **Responsive** | Works on 1920px down to 360px — mobile, tablet, desktop |
| **Testing** | 47 automated backend tests covering all endpoints, mocked AI calls |

---

## Technology Stack

| Layer | Technology |
|---|---|
| **Frontend** | HTML5, CSS3 (custom design tokens), Vanilla JavaScript (ES2022) |
| **Backend** | Python 3.11+, Flask 3.x |
| **AI** | OpenAI Python SDK → OpenRouter (Llama, Mistral, Gemma, DeepSeek, GPT-4o, Claude…) |
| **Streaming** | Server-Sent Events (SSE) |
| **Database** | SQLite (via Python stdlib `sqlite3`) |
| **Markdown** | marked.js + DOMPurify + highlight.js (all CDN) |
| **Production** | Gunicorn |

---

## Architecture

```
NexusAI/
├── backend/
│   ├── __init__.py
│   ├── app.py          ← Flask routes, SSE streaming, rate limiting
│   ├── ai_service.py   ← OpenAI SDK wrapper, error handling
│   ├── config.py       ← Environment-based configuration
│   └── database.py     ← SQLite persistence (conversations + messages)
│
├── static/
│   ├── css/
│   │   └── style.css   ← Design system, dark/light themes, responsive layout
│   └── js/
│       └── app.js      ← Chat UI, SSE client, markdown, history management
│
├── templates/
│   └── index.html      ← App shell (served by Flask)
│
├── tests/
│   └── test_backend.py ← 47 automated tests (all AI calls mocked)
│
├── run.py              ← Development / production entry point
├── requirements.txt
├── .env.example        ← Configuration template (no secrets)
└── README.md
```

---

## Installation

### Prerequisites

- Python 3.11 or higher
- A free [OpenRouter API key](https://openrouter.ai/keys)
- Git

### 1. Clone the repository

```bash
git clone https://github.com/Umar-Rahi/Ai-Chatbot.git
cd Ai-Chatbot
```

### 2. Create a Python virtual environment

```bash
# macOS / Linux
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure your API key

```bash
# Copy the example config file
cp .env.example .env   # macOS / Linux
copy .env.example .env  # Windows
```

Open `.env` in a text editor and set your OpenRouter key:

```dotenv
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxx
OPENROUTER_MODEL=openrouter/auto
```

> **Important:** Never commit `.env` to version control. It is already listed in `.gitignore`.

### 5. Run the application

```bash
python run.py
```

Open your browser at **http://localhost:5000**

---

## Configuration Reference

All settings are read from environment variables (or `.env`):

| Variable | Default | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | *(required)* | Your OpenRouter API key |
| `OPENROUTER_MODEL` | `openrouter/auto` | Model to use (see allowed list in `config.py`) |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | Override for custom endpoints |
| `SECRET_KEY` | *(random)* | Flask session secret — set a fixed value in production |
| `FLASK_DEBUG` | `false` | Enable debug mode |
| `DB_PATH` | `chatbot.db` | SQLite database file path |
| `MAX_CONTEXT_MESSAGES` | `20` | Max conversation messages sent to AI per request |
| `MAX_MESSAGE_LENGTH` | `4000` | Max characters per user message |
| `RATE_LIMIT` | `30` | Max AI requests per minute per IP |

---

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Enter` | Send message |
| `Shift + Enter` | New line in message |
| `Ctrl + K` | Start new chat |
| `Ctrl + /` | Open settings |
| `Esc` | Close any modal |

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/api/status` | OpenRouter connection status |
| `GET` | `/api/models` | List available models |
| `GET` | `/api/conversations` | List all conversations |
| `POST` | `/api/conversations` | Create conversation |
| `DELETE` | `/api/conversations` | Clear all conversations |
| `GET` | `/api/conversations/<id>` | Get conversation + messages |
| `PATCH` | `/api/conversations/<id>` | Rename conversation |
| `DELETE` | `/api/conversations/<id>` | Delete conversation |
| `POST` | `/api/chat` | Send message (SSE streaming) |

---

## Testing

```bash
# Activate venv first, then:
python -m pytest tests/ -v
```

**47 tests — 0 failures.** Tests cover:

- Health and model endpoints
- Conversation CRUD (create, list, get, rename, delete, clear all)
- Message persistence and ordering
- Chat endpoint validation (empty, too long, bad conversation ID)
- Successful streaming with mocked AI response
- AI error handling (rate limit, auth error) via SSE error events
- Auto-titling of conversations
- SQL injection resistance
- API key leak prevention
- 404 does not expose tracebacks
- Config validation and model fallback

All AI API calls are mocked — **no real OpenRouter calls are made during tests**.

---

## Deployment on Render

### 1. Push to GitHub

```bash
git add .
git commit -m "NexusAI: complete upgrade"
git push origin main
```

### 2. Create a new Web Service on Render

1. Go to [render.com](https://render.com) and create a new **Web Service**
2. Connect your GitHub repository
3. Configure the service:

| Setting | Value |
|---|---|
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn --bind 0.0.0.0:$PORT run:app` |

4. Set environment variables in the Render dashboard:

```
OPENROUTER_API_KEY  = sk-or-v1-your-real-key
OPENROUTER_MODEL    = openrouter/auto
SECRET_KEY          = (generate a long random string)
DB_PATH             = /tmp/chatbot.db
```

> **SQLite note:** Render's free tier does not provide persistent disk storage. Using `/tmp/chatbot.db` means conversation history is lost on each redeploy or restart. For persistent history on Render, upgrade to a paid plan with a persistent disk, or migrate to PostgreSQL.

### 3. Deploy

Click **Deploy** — Render will install requirements and start Gunicorn.

---

## Security Notes

- **API key:** Never stored in source code or exposed to the browser. Loaded from environment only.
- **SQL injection:** All database queries use parameterised statements.
- **XSS:** All markdown is sanitised with DOMPurify before rendering.
- **Rate limiting:** 30 requests per minute per IP (configurable) on the `/api/chat` endpoint.
- **Error messages:** Server tracebacks are never returned to the browser.
- **Public deployment:** This project has no user authentication. Before exposing it publicly, add:
  - HTTP Basic Auth or token authentication
  - OpenAI spending limits on your API dashboard
  - Stricter rate limiting
  - HTTPS (Render provides this automatically)

---

## API Costs

This application uses the OpenAI API, which is a **paid service**.

| Model | Approximate cost |
|---|---|
| `gpt-4o-mini` | ~$0.15 / 1M input tokens — very affordable |
| `gpt-4o` | ~$2.50 / 1M input tokens |
| `gpt-3.5-turbo` | ~$0.50 / 1M input tokens |

**Recommendation:** Use `gpt-4o-mini` for development and testing. It provides excellent quality at very low cost.

Set a **spending limit** on your [OpenAI dashboard](https://platform.openai.com/account/limits) to avoid unexpected charges.

---

## Known Limitations

- SQLite is not suitable for concurrent users at scale — migrate to PostgreSQL for production multi-user deployments.
- No user authentication — all conversations are shared if deployed publicly.
- Render free tier does not persist SQLite data between deploys.
- No image/file upload support.
- No voice input.
- Conversation history is cleared on "Clear all" — there is no archive.

---

## Original Project vs Upgrade

| | Before | After |
|---|---|---|
| Lines of code | ~170 (HTML+CSS+JS) | ~1,500+ across all files |
| AI responses | Keyword dictionary (fake) | Real OpenAI API, streaming |
| Conversation history | None | SQLite, persistent, searchable |
| UI | Basic form, yellow chatlog | Premium dark/light theme |
| Streaming | None | Server-Sent Events |
| Markdown | None | marked.js + DOMPurify + highlight.js |
| Tests | None | 47 automated tests |
| Security | API key in browser code | Server-side only, never exposed |
| Responsive | No | Desktop to 360px |
| Models | N/A | GPT-4o, GPT-4o-mini, GPT-4 Turbo, GPT-3.5 |

---

## License

MIT — feel free to use, modify, and distribute.
