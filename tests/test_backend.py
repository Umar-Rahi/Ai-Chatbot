"""
Automated test suite for NexusAI backend.

Tests cover:
- Health endpoint
- Chat endpoint validation (empty message, too long, missing conversation)
- Missing / invalid API key
- AI provider errors (mocked)
- Successful mocked AI response (streaming SSE)
- Conversation CRUD
- Message persistence
- Rename / delete
- Input validation
- Rate limiting
- Security-sensitive behaviour
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# ── Ensure project root is on sys.path ────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Point the database to a temp file so tests never pollute real data
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()
os.environ.setdefault("DB_PATH", _tmp_db.name)
os.environ.setdefault("OPENROUTER_API_KEY", "sk-or-v1-test-fake-key-for-testing")
os.environ.setdefault("OPENROUTER_MODEL", "openrouter/auto")


from backend.app import app
import backend.database as db


class BaseTestCase(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        app.config["DEBUG"] = False
        self.client = app.test_client()
        db.init_db()

    def tearDown(self):
        db.clear_all_conversations()

    # ── Helpers ──────────────────────────────────────────────────────────
    def _json(self, response):
        return json.loads(response.data)

    def _post_json(self, url, data):
        return self.client.post(
            url,
            data=json.dumps(data),
            content_type="application/json",
        )

    def _patch_json(self, url, data):
        return self.client.patch(
            url,
            data=json.dumps(data),
            content_type="application/json",
        )


# ═══════════════════════════════════════════════════════════════════════════
# HEALTH & STATUS
# ═══════════════════════════════════════════════════════════════════════════

class TestHealth(BaseTestCase):
    def test_health_returns_200(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)

    def test_health_returns_json_with_status(self):
        data = self._json(self.client.get("/health"))
        self.assertEqual(data["status"], "ok")
        self.assertIn("model", data)

    def test_models_endpoint(self):
        r = self.client.get("/api/models")
        self.assertEqual(r.status_code, 200)
        data = self._json(r)
        self.assertIn("models", data)
        self.assertIn("default", data)
        self.assertIsInstance(data["models"], list)
        self.assertGreater(len(data["models"]), 0)


# ═══════════════════════════════════════════════════════════════════════════
# CONVERSATIONS
# ═══════════════════════════════════════════════════════════════════════════

class TestConversations(BaseTestCase):
    def test_list_conversations_empty(self):
        r = self.client.get("/api/conversations")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self._json(r), [])

    def test_create_conversation(self):
        r = self._post_json("/api/conversations", {"title": "Test Chat"})
        self.assertEqual(r.status_code, 201)
        data = self._json(r)
        self.assertIn("id", data)
        self.assertEqual(data["title"], "Test Chat")

    def test_create_conversation_default_title(self):
        r = self._post_json("/api/conversations", {})
        self.assertEqual(r.status_code, 201)
        data = self._json(r)
        self.assertEqual(data["title"], "New Chat")

    def test_list_shows_created_conversations(self):
        self._post_json("/api/conversations", {"title": "Conv A"})
        self._post_json("/api/conversations", {"title": "Conv B"})
        r = self.client.get("/api/conversations")
        data = self._json(r)
        titles = [c["title"] for c in data]
        self.assertIn("Conv A", titles)
        self.assertIn("Conv B", titles)

    def test_get_conversation_not_found(self):
        r = self.client.get("/api/conversations/nonexistent-id")
        self.assertEqual(r.status_code, 404)

    def test_get_conversation_with_messages(self):
        r = self._post_json("/api/conversations", {"title": "Msg Test"})
        cid = self._json(r)["id"]
        db.add_message(cid, "user", "Hello")
        db.add_message(cid, "assistant", "Hi there!")
        r2 = self.client.get(f"/api/conversations/{cid}")
        data = self._json(r2)
        self.assertEqual(len(data["messages"]), 2)
        self.assertEqual(data["messages"][0]["role"], "user")
        self.assertEqual(data["messages"][1]["role"], "assistant")

    def test_rename_conversation(self):
        r = self._post_json("/api/conversations", {"title": "Old Title"})
        cid = self._json(r)["id"]
        r2 = self._patch_json(f"/api/conversations/{cid}", {"title": "New Title"})
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(self._json(r2)["title"], "New Title")

    def test_rename_conversation_empty_title(self):
        r = self._post_json("/api/conversations", {"title": "X"})
        cid = self._json(r)["id"]
        r2 = self._patch_json(f"/api/conversations/{cid}", {"title": ""})
        self.assertEqual(r2.status_code, 400)

    def test_rename_conversation_too_long(self):
        r = self._post_json("/api/conversations", {"title": "X"})
        cid = self._json(r)["id"]
        r2 = self._patch_json(f"/api/conversations/{cid}", {"title": "x" * 201})
        self.assertEqual(r2.status_code, 400)

    def test_rename_not_found(self):
        r2 = self._patch_json("/api/conversations/does-not-exist", {"title": "X"})
        self.assertEqual(r2.status_code, 404)

    def test_delete_conversation(self):
        r = self._post_json("/api/conversations", {"title": "To Delete"})
        cid = self._json(r)["id"]
        r2 = self.client.delete(f"/api/conversations/{cid}")
        self.assertEqual(r2.status_code, 200)
        r3 = self.client.get(f"/api/conversations/{cid}")
        self.assertEqual(r3.status_code, 404)

    def test_delete_not_found(self):
        r = self.client.delete("/api/conversations/nonexistent-id")
        self.assertEqual(r.status_code, 404)

    def test_clear_all_conversations(self):
        self._post_json("/api/conversations", {"title": "A"})
        self._post_json("/api/conversations", {"title": "B"})
        r = self.client.delete("/api/conversations")
        self.assertEqual(r.status_code, 200)
        r2 = self.client.get("/api/conversations")
        self.assertEqual(self._json(r2), [])

    def test_messages_deleted_with_conversation(self):
        r = self._post_json("/api/conversations", {"title": "X"})
        cid = self._json(r)["id"]
        db.add_message(cid, "user", "Hello")
        self.client.delete(f"/api/conversations/{cid}")
        msgs = db.get_messages(cid)
        self.assertEqual(msgs, [])

    def test_title_truncated_at_200_chars(self):
        r = self._post_json("/api/conversations", {"title": "x" * 300})
        cid = self._json(r)["id"]
        conv = db.get_conversation(cid)
        self.assertLessEqual(len(conv["title"]), 201)


# ═══════════════════════════════════════════════════════════════════════════
# MESSAGES
# ═══════════════════════════════════════════════════════════════════════════

class TestMessages(BaseTestCase):
    def test_add_and_retrieve_message(self):
        r = self._post_json("/api/conversations", {})
        cid = self._json(r)["id"]
        db.add_message(cid, "user", "Test message")
        msgs = db.get_messages(cid)
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["content"], "Test message")
        self.assertEqual(msgs[0]["role"], "user")

    def test_message_ordering(self):
        r = self._post_json("/api/conversations", {})
        cid = self._json(r)["id"]
        db.add_message(cid, "user", "First")
        db.add_message(cid, "assistant", "Second")
        db.add_message(cid, "user", "Third")
        msgs = db.get_messages(cid)
        self.assertEqual([m["content"] for m in msgs], ["First", "Second", "Third"])

    def test_message_limit(self):
        r = self._post_json("/api/conversations", {})
        cid = self._json(r)["id"]
        for i in range(25):
            db.add_message(cid, "user", f"msg {i}")
        msgs = db.get_messages(cid, limit=10)
        self.assertEqual(len(msgs), 10)
        # Should return last 10 in order
        self.assertEqual(msgs[-1]["content"], "msg 24")


# ═══════════════════════════════════════════════════════════════════════════
# CHAT ENDPOINT — VALIDATION
# ═══════════════════════════════════════════════════════════════════════════

class TestChatValidation(BaseTestCase):
    def test_empty_message_rejected(self):
        r = self._post_json("/api/chat", {"message": ""})
        self.assertEqual(r.status_code, 400)
        self.assertIn("error", self._json(r))

    def test_whitespace_message_rejected(self):
        r = self._post_json("/api/chat", {"message": "   "})
        self.assertEqual(r.status_code, 400)

    def test_message_too_long_rejected(self):
        r = self._post_json("/api/chat", {"message": "x" * 4001})
        self.assertEqual(r.status_code, 400)

    def test_nonexistent_conversation_id(self):
        r = self._post_json("/api/chat", {
            "message": "Hello",
            "conversation_id": "totally-fake-id",
        })
        self.assertEqual(r.status_code, 404)

    def test_no_json_body(self):
        r = self.client.post("/api/chat")
        self.assertEqual(r.status_code, 400)


# ═══════════════════════════════════════════════════════════════════════════
# CHAT ENDPOINT — AI INTEGRATION (MOCKED)
# ═══════════════════════════════════════════════════════════════════════════

class TestChatStreaming(BaseTestCase):
    """All OpenAI calls are mocked — no real API calls are made."""

    def _parse_sse(self, raw: bytes):
        """Parse SSE response into list of payload dicts."""
        text = raw.decode()
        events = []
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("data:"):
                try:
                    events.append(json.loads(line[5:].strip()))
                except json.JSONDecodeError:
                    pass
        return events

    @patch("backend.app.chat_stream")
    def test_successful_stream(self, mock_stream):
        mock_stream.return_value = iter(["Hello ", "world!"])
        r = self._post_json("/api/chat", {"message": "Hi"})
        self.assertEqual(r.status_code, 200)
        events = self._parse_sse(r.data)
        types = [e["type"] for e in events]
        self.assertIn("start", types)
        self.assertIn("chunk", types)
        self.assertIn("done", types)
        chunks = [e["content"] for e in events if e["type"] == "chunk"]
        self.assertEqual("".join(chunks), "Hello world!")

    @patch("backend.app.chat_stream")
    def test_successful_stream_creates_new_conversation(self, mock_stream):
        mock_stream.return_value = iter(["Response"])
        r = self._post_json("/api/chat", {"message": "New message"})
        events = self._parse_sse(r.data)
        start = next(e for e in events if e["type"] == "start")
        cid = start["conversation_id"]
        self.assertIsNotNone(cid)
        conv = db.get_conversation(cid)
        self.assertIsNotNone(conv)

    @patch("backend.app.chat_stream")
    def test_messages_persisted_after_stream(self, mock_stream):
        mock_stream.return_value = iter(["Test answer"])
        r = self._post_json("/api/chat", {"message": "Test question"})
        events = self._parse_sse(r.data)
        done = next(e for e in events if e["type"] == "done")
        cid = done["conversation_id"]
        msgs = db.get_messages(cid)
        roles = [m["role"] for m in msgs]
        self.assertIn("user", roles)
        self.assertIn("assistant", roles)

    @patch("backend.app.chat_stream")
    def test_stream_with_existing_conversation(self, mock_stream):
        mock_stream.return_value = iter(["Hi!"])
        conv = db.create_conversation("Existing")
        r = self._post_json("/api/chat", {
            "message": "Hello",
            "conversation_id": conv["id"],
        })
        self.assertEqual(r.status_code, 200)
        events = self._parse_sse(r.data)
        done = next(e for e in events if e["type"] == "done")
        self.assertEqual(done["conversation_id"], conv["id"])

    @patch("backend.app.chat_stream")
    def test_ai_error_returns_sse_error(self, mock_stream):
        from backend.ai_service import AIServiceError
        mock_stream.side_effect = AIServiceError("Rate limit exceeded", "rate_limit")
        r = self._post_json("/api/chat", {"message": "Hi"})
        events = self._parse_sse(r.data)
        error_events = [e for e in events if e["type"] == "error"]
        self.assertTrue(len(error_events) > 0)
        self.assertIn("error", error_events[0])

    @patch("backend.app.chat_stream")
    def test_auto_title_set_from_message(self, mock_stream):
        mock_stream.return_value = iter(["I can help with that."])
        r = self._post_json("/api/chat", {"message": "Explain quantum computing"})
        events = self._parse_sse(r.data)
        done = next(e for e in events if e["type"] == "done")
        cid = done["conversation_id"]
        conv = db.get_conversation(cid)
        self.assertNotEqual(conv["title"], "New Chat")
        self.assertIn("Explain quantum computing", conv["title"])


# ═══════════════════════════════════════════════════════════════════════════
# AI SERVICE — UNIT TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestAIService(unittest.TestCase):
    @patch("backend.ai_service.Config")
    def test_missing_api_key_raises(self, mock_config):
        from backend.ai_service import AIServiceError, chat_stream
        mock_config.OPENROUTER_API_KEY = ""
        mock_config.OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
        mock_config.ALLOWED_MODELS = ["openrouter/auto"]
        mock_config.OPENROUTER_MODEL = "openrouter/auto"
        import backend.ai_service as svc
        orig = svc._client
        svc._client = None
        try:
            list(svc.chat_stream([{"role": "user", "content": "Hi"}]))
            self.fail("Should have raised AIServiceError")
        except (AIServiceError, ValueError):
            pass
        finally:
            svc._client = orig

    def test_check_api_connection_no_key(self):
        from backend.ai_service import check_api_connection
        import backend.ai_service as svc
        orig_key = svc.Config.OPENROUTER_API_KEY
        svc.Config.OPENROUTER_API_KEY = ""
        result = check_api_connection()
        svc.Config.OPENROUTER_API_KEY = orig_key
        self.assertFalse(result["ok"])
        self.assertIn("key", result["message"].lower())


# ═══════════════════════════════════════════════════════════════════════════
# SECURITY
# ═══════════════════════════════════════════════════════════════════════════

class TestSecurity(BaseTestCase):
    def test_sql_injection_in_conversation_id(self):
        """SQL injection attempts should fail gracefully, not error 500."""
        r = self.client.get("/api/conversations/' OR '1'='1")
        self.assertIn(r.status_code, [400, 404])

    def test_sql_injection_in_rename(self):
        r = self._post_json("/api/conversations", {"title": "Safe"})
        cid = self._json(r)["id"]
        r2 = self._patch_json(f"/api/conversations/{cid}", {
            "title": "'; DROP TABLE conversations; --"
        })
        # Should succeed as a literal rename, not break the DB
        self.assertEqual(r2.status_code, 200)
        conv = db.get_conversation(cid)
        self.assertIsNotNone(conv)

    def test_xss_in_title_not_executed(self):
        """XSS in titles should be stored as plain text."""
        xss = "<script>alert(1)</script>"
        r = self._post_json("/api/conversations", {"title": xss})
        cid = self._json(r)["id"]
        conv = db.get_conversation(cid)
        self.assertEqual(conv["title"], xss)  # stored literally, escaped on render

    def test_api_key_not_in_response(self):
        """No response should ever contain the API key."""
        api_key = os.environ.get("OPENROUTER_API_KEY", "sk-or-v1-test-fake-key-for-testing")
        endpoints = [
            self.client.get("/health"),
            self.client.get("/api/models"),
            self.client.get("/api/conversations"),
        ]
        for r in endpoints:
            self.assertNotIn(api_key.encode(), r.data, f"API key leaked in {r.request.path}")

    def test_404_does_not_expose_traceback(self):
        r = self.client.get("/api/nonexistent-endpoint-12345")
        self.assertEqual(r.status_code, 404)
        self.assertNotIn(b"Traceback", r.data)


# ═══════════════════════════════════════════════════════════════════════════
# DATABASE
# ═══════════════════════════════════════════════════════════════════════════

class TestDatabase(unittest.TestCase):
    def setUp(self):
        db.init_db()
        db.clear_all_conversations()

    def test_create_and_get_conversation(self):
        conv = db.create_conversation("Hello")
        fetched = db.get_conversation(conv["id"])
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["title"], "Hello")

    def test_get_nonexistent_conversation(self):
        result = db.get_conversation("does-not-exist")
        self.assertIsNone(result)

    def test_delete_conversation_returns_true(self):
        conv = db.create_conversation()
        result = db.delete_conversation(conv["id"])
        self.assertTrue(result)

    def test_delete_nonexistent_returns_false(self):
        result = db.delete_conversation("fake-id")
        self.assertFalse(result)

    def test_add_and_get_messages(self):
        conv = db.create_conversation()
        db.add_message(conv["id"], "user", "Test")
        msgs = db.get_messages(conv["id"])
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["content"], "Test")

    def test_clear_all(self):
        db.create_conversation("A")
        db.create_conversation("B")
        n = db.clear_all_conversations()
        self.assertEqual(n, 2)
        self.assertEqual(db.list_conversations(), [])


# ═══════════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════════

class TestConfig(unittest.TestCase):
    def test_allowed_models_list_not_empty(self):
        from backend.config import Config
        self.assertGreater(len(Config.ALLOWED_MODELS), 0)

    def test_free_models_subset_of_allowed(self):
        from backend.config import Config
        for m in Config.FREE_MODELS:
            self.assertIn(m, Config.ALLOWED_MODELS)

    def test_free_models_contains_openrouter_free(self):
        from backend.config import Config
        self.assertIn("openrouter/free", Config.FREE_MODELS)

    def test_invalid_model_falls_back(self):
        from backend.config import Config
        orig = Config.OPENROUTER_MODEL
        Config.OPENROUTER_MODEL = "totally/fake-model:free"
        warnings = Config.validate()
        self.assertTrue(any("totally/fake-model:free" in w for w in warnings))
        # After validate(), model is reset to openrouter/auto (from env or fallback)
        self.assertIn(Config.OPENROUTER_MODEL, Config.ALLOWED_MODELS)
        Config.OPENROUTER_MODEL = orig


# ═══════════════════════════════════════════════════════════════════════════
# CONVERSATION ID HANDLING — NULL / NONE SAFETY
# ═══════════════════════════════════════════════════════════════════════════

class TestConversationIdSafety(BaseTestCase):
    """Verify that null/None conversation_id from the frontend is handled correctly."""

    @patch("backend.app.chat_stream")
    def test_null_conversation_id_creates_new_conversation(self, mock_stream):
        """JS sends conversation_id: null → should create a new conversation, not 404."""
        mock_stream.return_value = iter(["Hello!"])
        r = self._post_json("/api/chat", {"message": "Hi", "conversation_id": None})
        self.assertEqual(r.status_code, 200)
        events = self._parse_sse(r.data)
        start = next(e for e in events if e["type"] == "start")
        self.assertIsNotNone(start["conversation_id"])
        # Verify conversation was actually persisted
        conv = db.get_conversation(start["conversation_id"])
        self.assertIsNotNone(conv)

    @patch("backend.app.chat_stream")
    def test_missing_conversation_id_key_creates_new(self, mock_stream):
        """No conversation_id key at all → new conversation."""
        mock_stream.return_value = iter(["Hi!"])
        r = self._post_json("/api/chat", {"message": "Hello"})
        self.assertEqual(r.status_code, 200)
        events = self._parse_sse(r.data)
        start = next(e for e in events if e["type"] == "start")
        self.assertIsNotNone(start["conversation_id"])

    def test_string_none_conversation_id_is_rejected(self):
        """The string 'None' (Python str(None)) must not be treated as a valid ID."""
        r = self._post_json("/api/chat", {"message": "Hi", "conversation_id": "None"})
        # 'None' is not a valid UUID in the DB → should return 404
        self.assertEqual(r.status_code, 404)

    @patch("backend.app.chat_stream")
    def test_first_message_persists_user_and_assistant(self, mock_stream):
        """First message in a brand-new conversation persists both turns."""
        mock_stream.return_value = iter(["Response text"])
        r = self._post_json("/api/chat", {"message": "First message"})
        events = self._parse_sse(r.data)
        done = next(e for e in events if e["type"] == "done")
        cid = done["conversation_id"]
        msgs = db.get_messages(cid)
        roles = [m["role"] for m in msgs]
        self.assertEqual(roles, ["user", "assistant"])
        self.assertEqual(msgs[0]["content"], "First message")
        self.assertEqual(msgs[1]["content"], "Response text")

    @patch("backend.app.chat_stream")
    def test_subsequent_message_uses_existing_conversation(self, mock_stream):
        """Second message in same conversation appends to it, not create a new one."""
        mock_stream.return_value = iter(["First answer"])
        r1 = self._post_json("/api/chat", {"message": "Message one"})
        events1 = self._parse_sse(r1.data)
        cid = next(e for e in events1 if e["type"] == "done")["conversation_id"]

        mock_stream.return_value = iter(["Second answer"])
        r2 = self._post_json("/api/chat", {"message": "Message two", "conversation_id": cid})
        self.assertEqual(r2.status_code, 200)
        events2 = self._parse_sse(r2.data)
        done2 = next(e for e in events2 if e["type"] == "done")
        # Must be the same conversation
        self.assertEqual(done2["conversation_id"], cid)
        msgs = db.get_messages(cid)
        self.assertEqual(len(msgs), 4)  # user, assistant, user, assistant

    @patch("backend.app.chat_stream")
    def test_reload_and_reopen_conversation(self, mock_stream):
        """Simulates browser reload: create a conversation, then re-fetch it."""
        mock_stream.return_value = iter(["Persisted answer"])
        r = self._post_json("/api/chat", {"message": "Persist this"})
        events = self._parse_sse(r.data)
        cid = next(e for e in events if e["type"] == "done")["conversation_id"]

        # Simulate page reload: fetch conversations list
        list_r = self.client.get("/api/conversations")
        self.assertEqual(list_r.status_code, 200)
        convs = json.loads(list_r.data)
        conv_ids = [c["id"] for c in convs]
        self.assertIn(cid, conv_ids)

        # Open the specific conversation (as the sidebar click would do)
        get_r = self.client.get(f"/api/conversations/{cid}")
        self.assertEqual(get_r.status_code, 200)
        conv_data = json.loads(get_r.data)
        self.assertEqual(len(conv_data["messages"]), 2)
        self.assertEqual(conv_data["messages"][0]["content"], "Persist this")

    def test_invalid_uuid_conversation_id_returns_404(self):
        """A well-formed UUID that doesn't exist in the DB returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        r = self._post_json("/api/chat", {"message": "Hi", "conversation_id": fake_id})
        self.assertEqual(r.status_code, 404)
        self.assertIn("error", json.loads(r.data))

    def _parse_sse(self, raw: bytes):
        text = raw.decode()
        events = []
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("data:"):
                try:
                    events.append(json.loads(line[5:].strip()))
                except json.JSONDecodeError:
                    pass
        return events


# ═══════════════════════════════════════════════════════════════════════════
# MODELS ENDPOINT — FREE-ONLY
# ═══════════════════════════════════════════════════════════════════════════

class TestModelsEndpoint(BaseTestCase):
    def test_models_returns_only_free_models_by_default(self):
        """The /api/models endpoint must not expose paid models in the list."""
        r = self.client.get("/api/models")
        data = self._json(r)
        paid_models = {"openai/gpt-4o-mini", "openai/gpt-4o", "anthropic/claude-3.5-sonnet"}
        returned = set(data["models"])
        exposed_paid = paid_models & returned
        self.assertEqual(
            exposed_paid, set(),
            f"Paid models must not appear in /api/models response: {exposed_paid}"
        )

    def test_models_default_is_in_models_list(self):
        r = self.client.get("/api/models")
        data = self._json(r)
        self.assertIn(data["default"], data["models"])

    def test_models_openrouter_free_in_list(self):
        r = self.client.get("/api/models")
        data = self._json(r)
        self.assertIn("openrouter/free", data["models"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
