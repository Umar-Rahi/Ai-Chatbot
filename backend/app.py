"""
Flask application — main entry point.

Endpoints:
  GET  /               → serve index.html
  GET  /health         → health check
  GET  /api/status     → API connection status
  GET  /api/models     → list allowed models
  GET  /api/conversations          → list conversations
  POST /api/conversations          → create conversation
  GET  /api/conversations/<id>     → get conversation with messages
  PATCH /api/conversations/<id>    → rename
  DELETE /api/conversations/<id>   → delete
  DELETE /api/conversations        → clear all
  POST /api/chat                   → chat (streaming SSE)
"""

import json
import logging
import sys
import time
from collections import defaultdict
from functools import wraps

from flask import Flask, Response, jsonify, request, stream_with_context
from flask_cors import CORS

from backend.config import Config
from backend.database import (
    add_message,
    clear_all_conversations,
    create_conversation,
    delete_conversation,
    get_conversation,
    get_messages,
    init_db,
    list_conversations,
    rename_conversation,
)
from backend.ai_service import AIServiceError, chat_stream

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.DEBUG if Config.DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# ── App ───────────────────────────────────────────────────────────────────────

app = Flask(
    __name__,
    template_folder="../templates",
    static_folder="../static",
)
app.config["SECRET_KEY"] = Config.SECRET_KEY
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Print config warnings on startup
for warning in Config.validate():
    logger.warning(warning)

# Initialise database
init_db()

# ── Rate limiter (simple in-memory per-IP) ────────────────────────────────────

_rate_store: dict[str, list[float]] = defaultdict(list)
WINDOW = 60  # seconds


def rate_limited(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        ip = request.remote_addr or "unknown"
        now = time.time()
        timestamps = _rate_store[ip]
        # Drop timestamps outside the window
        _rate_store[ip] = [t for t in timestamps if now - t < WINDOW]
        if len(_rate_store[ip]) >= Config.RATE_LIMIT:
            return jsonify({"error": "Rate limit exceeded. Please slow down."}), 429
        _rate_store[ip].append(now)
        return fn(*args, **kwargs)
    return wrapper


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def _error(message: str, code: int = 400) -> tuple:
    return jsonify({"error": message}), code


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    from flask import render_template
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({"status": "ok", "model": Config.OPENROUTER_MODEL})


@app.route("/api/status")
def api_status():
    from backend.ai_service import check_api_connection
    result = check_api_connection()
    return jsonify(result), 200 if result["ok"] else 503


@app.route("/api/models")
def get_models():
    # Expose only free-tier models in the UI selector.
    # The active model (from env) is included even if it's not in FREE_MODELS,
    # so it always appears as a valid selection.
    ui_models = list(Config.FREE_MODELS)
    if Config.OPENROUTER_MODEL not in ui_models:
        ui_models.insert(0, Config.OPENROUTER_MODEL)
    return jsonify({"models": ui_models, "default": Config.OPENROUTER_MODEL})


# ── Conversations ─────────────────────────────────────────────────────────────

@app.route("/api/conversations", methods=["GET"])
def list_convs():
    return jsonify(list_conversations())


@app.route("/api/conversations", methods=["POST"])
def create_conv():
    data = request.get_json(silent=True) or {}
    title = str(data.get("title", "New Chat"))[:200]
    conv = create_conversation(title)
    return jsonify(conv), 201


@app.route("/api/conversations", methods=["DELETE"])
def clear_convs():
    n = clear_all_conversations()
    return jsonify({"deleted": n})


@app.route("/api/conversations/<cid>", methods=["GET"])
def get_conv(cid: str):
    conv = get_conversation(cid)
    if not conv:
        return _error("Conversation not found.", 404)
    msgs = get_messages(cid)
    return jsonify({**conv, "messages": msgs})


@app.route("/api/conversations/<cid>", methods=["PATCH"])
def rename_conv(cid: str):
    data = request.get_json(silent=True) or {}
    title = str(data.get("title", "")).strip()
    if not title:
        return _error("Title cannot be empty.")
    if len(title) > 200:
        return _error("Title too long.")
    if not rename_conversation(cid, title):
        return _error("Conversation not found.", 404)
    return jsonify({"ok": True, "title": title})


@app.route("/api/conversations/<cid>", methods=["DELETE"])
def delete_conv(cid: str):
    if not delete_conversation(cid):
        return _error("Conversation not found.", 404)
    return jsonify({"ok": True})


# ── Chat (streaming SSE) ──────────────────────────────────────────────────────

@app.route("/api/chat", methods=["POST"])
@rate_limited
def chat():
    data = request.get_json(silent=True) or {}

    # ── Validate input ────────────────────────────────────────────────────────
    message: str = str(data.get("message", "")).strip()
    if not message:
        return _error("Message cannot be empty.")
    if len(message) > Config.MAX_MESSAGE_LENGTH:
        return _error(f"Message exceeds {Config.MAX_MESSAGE_LENGTH} character limit.")

    raw_cid = data.get("conversation_id")
    conversation_id: str = str(raw_cid).strip() if raw_cid and raw_cid != "null" else ""
    model: str | None = data.get("model")

    # ── Conversation resolution ───────────────────────────────────────────────
    if conversation_id:
        conv = get_conversation(conversation_id)
        if not conv:
            return _error("Conversation not found.", 404)
    else:
        conv = create_conversation("New Chat")
        conversation_id = conv["id"]

    # ── Persist user message ──────────────────────────────────────────────────
    add_message(conversation_id, "user", message)

    # ── Build context window ──────────────────────────────────────────────────
    history = get_messages(conversation_id, limit=Config.MAX_CONTEXT_MESSAGES)
    openai_messages = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in history
        if msg["role"] in ("user", "assistant")
    ]

    # ── Stream response ───────────────────────────────────────────────────────
    def generate():
        full_response = []
        try:
            # Send conversation_id so the client knows which conv this belongs to
            yield _sse({"type": "start", "conversation_id": conversation_id})

            for chunk in chat_stream(openai_messages, model=model):
                full_response.append(chunk)
                yield _sse({"type": "chunk", "content": chunk})

            assistant_reply = "".join(full_response)
            add_message(conversation_id, "assistant", assistant_reply)

            # Auto-title: use first ~60 chars of first user message
            if conv["title"] == "New Chat":
                short = message[:60].strip()
                if len(message) > 60:
                    short += "…"
                rename_conversation(conversation_id, short)

            yield _sse({"type": "done", "conversation_id": conversation_id})

        except AIServiceError as exc:
            yield _sse({"type": "error", "error": exc.user_message, "code": exc.code})
        except Exception as exc:
            logger.exception("Unexpected error during streaming")
            yield _sse({"type": "error", "error": "An unexpected error occurred.", "code": "server_error"})

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── Error handlers ────────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(_):
    return _error("Not found.", 404)


@app.errorhandler(405)
def method_not_allowed(_):
    return _error("Method not allowed.", 405)


@app.errorhandler(500)
def internal_error(_):
    logger.exception("Internal server error")
    return _error("Internal server error.", 500)


# ── Dev runner ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=Config.DEBUG, port=5000, threaded=True)
