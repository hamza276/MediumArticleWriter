import os
import uuid
import asyncio
import tempfile
import shutil
import unittest
import importlib
import atexit
from pathlib import Path

# ---------------------------------------------------------------------------
# Baseline environment configuration (ensures settings can load)
# ---------------------------------------------------------------------------
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("SECRET_KEY", "test-secret")

from app.config import settings

# Use an isolated workspace so tests never touch the developer's data.
TEST_ROOT = Path(tempfile.mkdtemp(prefix="article_writer_tests_"))
settings.DATABASE_PATH = str(TEST_ROOT / "medium_articles_test.db")
settings.LOG_FILE = str(TEST_ROOT / "article_generation_test.log")
settings.STATIC_DIR = TEST_ROOT / "static"
settings.TEMPLATES_DIR = TEST_ROOT / "templates"
settings.IMAGES_DIR = settings.STATIC_DIR / "images"
for folder in (settings.STATIC_DIR, settings.TEMPLATES_DIR, settings.IMAGES_DIR):
    Path(folder).mkdir(parents=True, exist_ok=True)

# Import logger and database modules AFTER settings overrides so they use test paths.
import app.utils.logger as logger_module  # pylint: disable=wrong-import-position
import app.database.operations as operations_module  # pylint: disable=wrong-import-position
from app.database.models import Base, ArticleQueue  # pylint: disable=wrong-import-position
from app.utils.latex_handler import latex_handler  # pylint: disable=wrong-import-position
from app.api.websocket import ConnectionManager  # pylint: disable=wrong-import-position

db_ops = operations_module.db_ops


def _cleanup() -> None:
    """Remove the temporary workspace (called on interpreter exit)."""
    try:
        db_ops.engine.dispose()
    except Exception:  # pragma: no cover - best effort cleanup
        pass
    shutil.rmtree(TEST_ROOT, ignore_errors=True)


atexit.register(_cleanup)


def reset_database() -> None:
    """Recreate every table so each test starts with a blank DB."""
    Base.metadata.drop_all(db_ops.engine)
    Base.metadata.create_all(db_ops.engine)


# ---------------------------------------------------------------------------
# Stub implementations for async dependencies (OpenAI + LangGraph).
# ---------------------------------------------------------------------------
class StubGenerator:
    """Simplified generator that returns deterministic content."""

    def __init__(self) -> None:
        self.chat_messages = []
        self.validation_calls = []

    def reset(self) -> None:
        self.chat_messages.clear()
        self.validation_calls.clear()

    async def chat_with_user(self, messages):
        self.chat_messages.append(messages)
        for token in ["Hello", " ", "writer!"]:
            await asyncio.sleep(0)
            yield token

    async def generate_article(self, requirements):
        del requirements
        for chunk in ["# Demo Article\n", "Content body"]:
            await asyncio.sleep(0)
            yield chunk

    async def regenerate_content(self, node_name, feedback, current_content):
        del node_name, feedback, current_content
        for chunk in ["Regenerated content"]:
            await asyncio.sleep(0)
            yield chunk

    async def validate_content(self, validator_type, content, metadata):
        self.validation_calls.append((validator_type, content, metadata))
        await asyncio.sleep(0)
        return {
            "score": 9.2,
            "feedback": f"{validator_type} looks good",
            "flesch_reading_ease": 72,
            "gunning_fog_index": 8.1,
        }


class StubWorkflowManager:
    """Tracks invocations to ensure routes call into the workflow."""

    def __init__(self) -> None:
        self.run_inputs = []
        self.saved_states = {}

    def reset(self) -> None:
        self.run_inputs.clear()
        self.saved_states.clear()

    async def run(self, state):
        new_state = dict(state)
        new_state.setdefault("content", "# Stub\nContent")
        new_state["status"] = "completed"
        new_state["overall_score"] = new_state.get("overall_score", 9.4)
        self.run_inputs.append(new_state)
        self.saved_states[new_state["session_id"]] = new_state
        await asyncio.sleep(0)
        return new_state

    async def get_state(self, session_id):
        await asyncio.sleep(0)
        return self.saved_states.get(session_id, {"session_id": session_id, "status": "unknown"})


class StubConnectionManager:
    """Captures outbound websocket events."""

    def __init__(self) -> None:
        self.events = []

    def reset(self) -> None:
        self.events.clear()

    async def send_token(self, session_id, token, message_type="content"):
        self.events.append(("token", session_id, token, message_type))

    async def send_status(self, session_id, status, data=None):
        self.events.append(("status", session_id, status, data or {}))

    async def send_node_update(self, session_id, node_name, status, score=None):
        self.events.append(("node", session_id, node_name, status, score))

    async def send_error(self, session_id, error):
        self.events.append(("error", session_id, error))

    async def send_completion(self, session_id, article_id, overall_score):
        self.events.append(("completion", session_id, article_id, overall_score))


STUB_GENERATOR = StubGenerator()
STUB_WORKFLOW = StubWorkflowManager()
STUB_MANAGER = StubConnectionManager()


import app.agents.generator as generator_module  # pylint: disable=wrong-import-position
import app.agents.graph as graph_module  # pylint: disable=wrong-import-position
import app.api.websocket as websocket_module  # pylint: disable=wrong-import-position
import app.api.routes as routes_module  # pylint: disable=wrong-import-position


generator_module.generator = STUB_GENERATOR
graph_module.workflow_manager = STUB_WORKFLOW
websocket_module.manager = STUB_MANAGER
routes_module.generator = STUB_GENERATOR
routes_module.workflow_manager = STUB_WORKFLOW
routes_module.manager = STUB_MANAGER


def run_async(coro):
    """Helper to execute async callables inside synchronous tests."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------
class DatabaseOperationsTestCase(unittest.TestCase):
    """Covers CRUD helpers inside app.database.operations."""

    def setUp(self):
        reset_database()

    def _base_article(self):
        article_id = f"article_{uuid.uuid4().hex[:8]}"
        session_id = f"session_{uuid.uuid4().hex[:8]}"
        db_ops.create_article(
            article_id=article_id,
            session_id=session_id,
            title="Sample",
            author="Tester",
            metadata={"topic": "AI"},
        )
        return article_id, session_id

    def test_article_and_version_flow(self):
        article_id, _ = self._base_article()
        db_ops.update_article(article_id, content="Updated", status="completed", score=9.1)

        stored = db_ops.get_article(article_id)
        self.assertIsNotNone(stored)
        self.assertEqual(stored.status, "completed")
        self.assertAlmostEqual(stored.overall_score, 9.1)

        db_ops.create_version(article_id, "v1 content", {"structure": 9.0}, "generate")
        versions = db_ops.get_versions(article_id)
        self.assertEqual(len(versions), 1)
        self.assertEqual(versions[0].version_number, 1)

    def test_queue_checkpoint_chat_validation_and_analytics(self):
        article_id, session_id = self._base_article()

        # Queue operations
        position = db_ops.add_to_queue(session_id)
        self.assertEqual(position, 1)
        db_ops.update_queue_status(session_id, "processing")
        self.assertEqual(db_ops.get_processing_count(), 1)
        self.assertEqual(db_ops.get_queue_position(session_id), 1)

        # Chat + validation logs
        db_ops.add_chat_message(session_id, user_message="Hello world")
        db_ops.add_chat_message(session_id, bot_response="Hi there")
        history = db_ops.get_chat_history(session_id)
        self.assertEqual(len(history), 2)

        db_ops.add_validation_log(
            article_id=article_id,
            node_name="structure",
            score=8.5,
            feedback={"summary": "ok"},
            retry_count=0,
            status="passed",
        )
        logs = db_ops.get_validation_logs(article_id)
        self.assertEqual(len(logs), 1)

        # Checkpoints + analytics
        checkpoint_id = f"chk_{uuid.uuid4().hex[:6]}"
        db_ops.save_checkpoint(checkpoint_id, article_id, "generate", {"content": "draft"})
        checkpoint = db_ops.get_checkpoint(checkpoint_id)
        self.assertEqual(checkpoint.node_name, "generate")

        db_ops.add_analytics(article_id, "token_usage", 123.0, {"model": "stub"})
        analytics = db_ops.get_analytics(article_id)
        self.assertEqual(len(analytics), 1)

        # Next in queue should be None because everyone is processing/completed
        next_session = db_ops.get_next_in_queue()
        self.assertIsNone(next_session)


class LatexHandlerTestCase(unittest.TestCase):
    """Ensures LaTeX extraction and image conversion behave as expected."""

    def setUp(self):
        reset_database()
        shutil.rmtree(settings.IMAGES_DIR, ignore_errors=True)
        Path(settings.IMAGES_DIR).mkdir(parents=True, exist_ok=True)

    def test_extract_and_process_equations(self):
        content = "Einstein wrote $E=mc^2$ while Pythagoras showed $$a^2+b^2=c^2$$."
        equations = latex_handler.extract_equations(content)
        self.assertEqual(len(equations), 2)

        processed, count = latex_handler.process_article_equations(content, "article123")
        self.assertEqual(count, 2)
        self.assertIn("![Equation 1]", processed)
        self.assertTrue(list(Path(settings.IMAGES_DIR).glob("eq_article123_*.png")))


class ConnectionManagerTestCase(unittest.TestCase):
    """Covers websocket connection lifecycle helpers."""

    def setUp(self):
        reset_database()

    def test_connection_manager_tracks_clients(self):
        manager = ConnectionManager()

        class DummyWebSocket:
            def __init__(self):
                self.accepted = False
                self.messages = []

            async def accept(self):
                self.accepted = True

            async def send_json(self, data):
                self.messages.append(data)

        async def scenario():
            socket = DummyWebSocket()
            await manager.connect(socket, "session-x")
            await manager.send_token("session-x", "hi")
            await manager.send_status("session-x", "processing", {"step": 1})
            await manager.send_completion("session-x", "article-test", 9.5)
            manager.disconnect("session-x")
            return socket.messages

        messages = run_async(scenario())
        self.assertEqual(len(messages), 3)  # token + status + completion
        self.assertEqual(messages[0]["type"], "token")


class APIRoutesTestCase(unittest.TestCase):
    """Hits the FastAPI route functions directly with stubbed dependencies."""

    def setUp(self):
        reset_database()
        STUB_MANAGER.reset()
        STUB_WORKFLOW.reset()
        STUB_GENERATOR.reset()

    def _create_article_for_reports(self):
        article_id = "article_report"
        session_id = "session_report"
        db_ops.create_article(
            article_id=article_id,
            session_id=session_id,
            title="Report",
            author="Analyst",
            metadata={"topic": "Testing"},
        )
        db_ops.create_version(article_id, "Version content", {"structure": 8.0}, "generate")
        db_ops.add_validation_log(
            article_id=article_id,
            node_name="structure",
            score=8.0,
            feedback={"details": "ok"},
            retry_count=0,
            status="passed",
        )
        return article_id, session_id

    def test_chat_endpoint_streams_and_persists_history(self):
        chat_msg = routes_module.ChatMessage(session_id="chat123", message="Need an outline")
        response = run_async(routes_module.chat_endpoint(chat_msg))
        self.assertTrue(response["success"])
        history = db_ops.get_chat_history("chat123")
        self.assertEqual(len(history), 2)  # user + assistant
        self.assertTrue(any(event[0] == "token" for event in STUB_MANAGER.events))

    def test_generate_article_endpoint_creates_records(self):
        req = routes_module.ArticleRequest(
            session_id="session_gen",
            requirements={
                "topic": "AI safety",
                "author": "Researcher",
                "target_audience": "engineers",
                "article_type": "tutorial",
                "tone": "pragmatic",
            },
        )
        response = run_async(routes_module.generate_article_endpoint(req))
        self.assertTrue(response["success"])
        article = db_ops.get_article(response["article_id"])
        self.assertIsNotNone(article)
        self.assertEqual(article.title, "AI safety")

    def test_run_workflow_updates_queue_and_emits_completion(self):
        session_id = "session_flow"
        article_id = "article_flow"
        db_ops.create_article(article_id, session_id, "Flow", "Tester", {"topic": "Flow"})
        db_ops.add_to_queue(session_id)

        state = {
            "session_id": session_id,
            "article_id": article_id,
            "content": "# Flow\nContent",
            "scores": {},
            "feedback": {},
            "retry_counts": {},
            "failed_nodes": [],
        }
        final_state = run_async(routes_module.run_workflow(state))
        self.assertEqual(final_state["status"], "completed")
        self.assertTrue(any(event[0] == "completion" for event in STUB_MANAGER.events))

        with db_ops.get_session() as session:
            queue = session.query(ArticleQueue).filter_by(session_id=session_id).first()
            self.assertEqual(queue.status, "completed")

    def test_article_queries_and_reports(self):
        article_id, session_id = self._create_article_for_reports()
        db_ops.add_to_queue(session_id)

        article_response = run_async(routes_module.get_article(article_id))
        self.assertTrue(article_response["success"])

        report = run_async(routes_module.get_validation_report(article_id))
        self.assertTrue(report["success"])
        self.assertTrue(report["report"]["validations"])

        articles = run_async(routes_module.get_all_articles())
        self.assertTrue(articles["success"])
        self.assertGreaterEqual(len(articles["articles"]), 1)

        status = run_async(routes_module.get_article_status(session_id))
        self.assertTrue(status["success"])
        self.assertEqual(status["queue_position"], 1)

    def test_time_travel_creates_new_article_from_checkpoint(self):
        article_id = "article_original"
        session_id = "session_original"
        db_ops.create_article(article_id, session_id, "Original", "Author", {"topic": "History"})
        checkpoint_id = "checkpoint123"
        db_ops.save_checkpoint(
            checkpoint_id,
            article_id,
            "generate",
            {
                "session_id": session_id,
                "article_id": article_id,
                "content": "# Original\nContent",
                "scores": {},
                "feedback": {},
                "retry_counts": {},
                "failed_nodes": [],
            },
        )

        req = routes_module.TimeTravel(
            article_id=article_id,
            checkpoint_id=checkpoint_id,
            modifications={"topic": "Updated Topic"},
        )
        response = run_async(routes_module.time_travel(req))
        self.assertTrue(response["success"])
        self.assertIn("new_article_id", response)


if __name__ == "__main__":
    unittest.main(verbosity=2)

