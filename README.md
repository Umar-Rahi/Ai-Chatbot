# NexusAI

A responsive AI chatbot built with **Flask, vanilla JavaScript, SQLite, and OpenRouter**. NexusAI supports streamed AI responses, multi-turn conversations, conversation history, Markdown rendering, and a model selector.

<p align="center">
  <a href="https://nexusai-ufkn.onrender.com"><strong>🚀 Try the live demo</strong></a>
  &nbsp;·&nbsp;
  <a href="https://github.com/Umar-Rahi/Ai-Chatbot">GitHub repository</a>
</p>

> **Live app:** https://nexusai-ufkn.onrender.com  
> The hosted version uses an OpenRouter API key configured on the server. You do not need to enter an API key in the browser.

---

## Features

- **OpenRouter integration** using the OpenAI-compatible Python SDK.
- **Streaming responses** delivered to the browser with Server-Sent Events (SSE).
- **Multi-turn chat** with conversation context.
- **Conversation history** stored in SQLite, with create, open, rename, delete, and search UI.
- **Markdown responses** with code formatting and syntax highlighting.
- **Stop and regenerate** response controls.
- **Responsive interface** with a collapsible conversation sidebar and mobile layout.
- **Server-side secrets**: the OpenRouter API key stays in backend environment variables.
- **Request rate limiting** on the chat endpoint.

## Live Demo

**[Open NexusAI](https://nexusai-ufkn.onrender.com)**

The app is hosted on Render. On the free instance, the first request after a period of inactivity may take longer while the service wakes up.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML, CSS, vanilla JavaScript |
| Backend | Python, Flask |
| AI provider | OpenRouter |
| SDK | OpenAI Python SDK (OpenRouter-compatible endpoint) |
| Streaming | Server-Sent Events (SSE) |
| Database | SQLite |
| Production server | Gunicorn |
| Hosting | Render |

## Run Locally

### Prerequisites

- Python 3.11 or newer
- Git
- An [OpenRouter API key](https://openrouter.ai/keys)

### 1. Clone the repository

```bash
git clone https://github.com/Umar-Rahi/Ai-Chatbot.git
cd Ai-Chatbot
```

### 2. Create and activate a virtual environment

**Windows PowerShell:**

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**macOS / Linux:**

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a file named `.env` in the project root and add:

```dotenv
OPENROUTER_API_KEY=your_openrouter_api_key
OPENROUTER_MODEL=openrouter/free
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

SECRET_KEY=replace_with_a_long_random_secret
FLASK_DEBUG=false
DB_PATH=chatbot.db
MAX_CONTEXT_MESSAGES=20
MAX_MESSAGE_LENGTH=4000
RATE_LIMIT=30
```

Get your key from [OpenRouter API Keys](https://openrouter.ai/keys). Never commit `.env` or share your key publicly.

The application code currently falls back to `openrouter/auto` if no model is configured. Set `OPENROUTER_MODEL=openrouter/free` explicitly when you want to use the free-model router.

### 5. Start the app

```bash
python run.py
```

Open **http://localhost:5000**.

## Configuration

| Variable | Purpose |
|---|---|
| `OPENROUTER_API_KEY` | OpenRouter API key (required for AI responses) |
| `OPENROUTER_MODEL` | Model/router ID; set to `openrouter/free` for the free router |
| `OPENROUTER_BASE_URL` | OpenRouter endpoint; defaults to `https://openrouter.ai/api/v1` |
| `SECRET_KEY` | Flask secret key; set a strong, private value in production |
| `FLASK_DEBUG` | Enables Flask debug mode when set to `true` |
| `DB_PATH` | SQLite database file path |
| `MAX_CONTEXT_MESSAGES` | Maximum previous messages included as chat context |
| `MAX_MESSAGE_LENGTH` | Maximum allowed user message length |
| `RATE_LIMIT` | Maximum chat requests per minute per client IP |

Free-model availability, rate limits, and provider routing are controlled by OpenRouter and can change. A free model is not guaranteed to be available at every moment.

## Deploy on Render

This repository is deployed at **https://nexusai-ufkn.onrender.com**.

To create your own deployment:

1. Fork this repository or connect it to your Render account.
2. In Render, create a **Web Service** from the GitHub repository.
3. Use these settings:

   | Setting | Value |
   |---|---|
   | Runtime | Python |
   | Build command | `pip install -r requirements.txt` |
   | Start command | `gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120 run:app` |

4. Add these environment variables in the Render service settings:

   | Key | Value |
   |---|---|
   | `OPENROUTER_API_KEY` | Your OpenRouter API key |
   | `OPENROUTER_MODEL` | `openrouter/free` |
   | `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` |
   | `SECRET_KEY` | A long random secret |
   | `FLASK_DEBUG` | `false` |
   | `DB_PATH` | `/tmp/chatbot.db` |

5. Deploy the service and open the `.onrender.com` URL assigned by Render.

### Important: database persistence

The default SQLite database is stored on the service filesystem. On Render's free service, local filesystem changes are ephemeral and may be lost when the instance restarts or is redeployed. For durable conversation history, configure persistent storage supported by your hosting plan or migrate the app to PostgreSQL.

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Basic health check |
| `GET` | `/api/status` | Check OpenRouter connectivity |
| `GET` | `/api/models` | Get models exposed by the app |
| `GET` | `/api/conversations` | List conversations |
| `POST` | `/api/conversations` | Create a conversation |
| `GET` | `/api/conversations/<id>` | Get a conversation and its messages |
| `PATCH` | `/api/conversations/<id>` | Rename a conversation |
| `DELETE` | `/api/conversations/<id>` | Delete a conversation |
| `DELETE` | `/api/conversations` | Clear all conversations |
| `POST` | `/api/chat` | Send a message and receive an SSE stream |

## Run Tests

```bash
python -m pytest tests/ -v
```

AI provider calls should be mocked in automated tests; a successful test run does not replace testing a real OpenRouter key and model in your own environment.

## Security & Usage Notes

- Keep `OPENROUTER_API_KEY` on the server. Never place it in frontend JavaScript, HTML, or a public repository.
- Use a strong `SECRET_KEY` in production.
- The current app does not implement user accounts or per-user conversation isolation. Treat a public deployment as a shared demo, and add authentication and stronger abuse controls before using it for private conversations or opening it to unrestricted public traffic.
- Rate limiting is currently in-memory and per process; it is not a substitute for production-grade, distributed abuse protection.
- OpenRouter free models have provider-specific availability and rate limits. Review the [OpenRouter model catalogue](https://openrouter.ai/models?max_price=0) for current free options.

## Project Structure

```text
Ai-Chatbot/
├── backend/
│   ├── app.py
│   ├── ai_service.py
│   ├── config.py
│   └── database.py
├── static/
│   ├── css/style.css
│   └── js/app.js
├── templates/
│   └── index.html
├── tests/
│   └── test_backend.py
├── run.py
├── requirements.txt
├── Procfile
└── README.md
```

## Author

**Umar Rahi**

- GitHub: [@Umar-Rahi](https://github.com/Umar-Rahi)
- Project: [Ai-Chatbot](https://github.com/Umar-Rahi/Ai-Chatbot)
- Live demo: [NexusAI](https://nexusai-ufkn.onrender.com)
