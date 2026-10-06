"""Tests for multi-user access management (admin-granted)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from qm_training.ai.mock import MockAIProvider
from qm_training.ai.service import AIService
from qm_training.bot import SessionStore, Workflow
from qm_training.bot.adapters import MockTelegramAdapter
from qm_training.core.config import Settings
from qm_training.core.users import UserStore
from qm_training.validation.models import ValidationReport

OWNER = "1"


def _workflow(tmp: Path, allowed=("1",), owners=("1",)):
    users = UserStore(tmp / "users.json")
    workflow = Workflow(
        store=SessionStore(tmp / "sessions"),
        ai_service=AIService(MockAIProvider()),
        settings=Settings(ai_provider="mock", allowed_user_ids=allowed, owner_user_ids=owners),
        user_store=users,
        convert_pdf=lambda *a, **k: None,
        validate=lambda d, p=None: ValidationReport(),
    )
    return workflow, users, MockTelegramAdapter(workflow, slow_threshold=5.0)


class TestUserStore(unittest.TestCase):
    def test_add_query_deactivate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = UserStore(Path(tmp) / "users.json")
            store.add("42", role="user")
            self.assertTrue(store.is_active("42"))
            self.assertEqual(store.role_of("42"), "USER")
            store.set_active("42", False)
            self.assertFalse(store.is_active("42"))
            self.assertTrue(store.is_admin("42") is False)

    def test_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "users.json"
            UserStore(path).add("42", role="admin")
            reloaded = UserStore(path)
            self.assertTrue(reloaded.is_active("42"))
            self.assertTrue(reloaded.is_admin("42"))


class TestAuthorization(unittest.TestCase):
    def test_owner_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workflow, _, adapter = _workflow(Path(tmp))
            messages = adapter.receive(OWNER, "/whoami", update_id=1)
            self.assertIn("OWNER", messages[0].text)
            self.assertEqual(workflow._role(OWNER), "OWNER")

    def test_unauthorized_reply_includes_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, _, adapter = _workflow(Path(tmp))
            messages = adapter.receive("777", "/new_training", update_id=1)
            self.assertIn("belum terdaftar", messages[0].text.lower())
            self.assertIn("777", messages[0].text)

    def test_allow_then_user_can_use(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, users, adapter = _workflow(Path(tmp))
            reply = adapter.receive(OWNER, "/allow 42", update_id=1)
            self.assertIn("42", reply[0].text)
            self.assertTrue(users.is_active("42"))
            # the new user can start a session without restarting the bot
            messages = adapter.receive("42", "/new_training", update_id=2)
            self.assertIn("Kirim materi pelatihan", messages[0].text)

    def test_deny_revokes_access(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, users, adapter = _workflow(Path(tmp))
            adapter.receive(OWNER, "/allow 42", update_id=1)
            adapter.receive(OWNER, "/deny 42", update_id=2)
            self.assertFalse(users.is_active("42"))
            messages = adapter.receive("42", "/new_training", update_id=3)
            self.assertIn("belum terdaftar", messages[0].text.lower())

    def test_non_admin_cannot_manage_users(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, _, adapter = _workflow(Path(tmp))
            adapter.receive(OWNER, "/allow 42", update_id=1)  # 42 = normal USER
            messages = adapter.receive("42", "/allow 43", update_id=2)
            self.assertIn("admin", messages[0].text.lower())
            listing = adapter.receive("42", "/users", update_id=3)
            self.assertIn("admin", listing[0].text.lower())

    def test_users_listing_for_admin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, _, adapter = _workflow(Path(tmp))
            adapter.receive(OWNER, "/allow 42 admin", update_id=1)
            messages = adapter.receive(OWNER, "/users", update_id=2)
            text = messages[0].text
            self.assertIn(OWNER, text)
            self.assertIn("42", text)
            self.assertIn("ADMIN", text)

    def test_open_mode_when_no_allowlist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, _, adapter = _workflow(Path(tmp), allowed=(), owners=())
            messages = adapter.receive("999", "/new_training", update_id=1)
            self.assertIn("Kirim materi pelatihan", messages[0].text)


class TestFailClosedGuard(unittest.TestCase):
    def test_refuses_when_no_access_configured(self) -> None:
        from qm_training.app import access_refusal_reason

        with tempfile.TemporaryDirectory() as tmp:
            store = UserStore(Path(tmp) / "users.json")
            settings = Settings(ai_provider="mock", allowed_user_ids=(), owner_user_ids=())
            self.assertIsNotNone(access_refusal_reason(settings, store))

    def test_allows_with_allowed_ids(self) -> None:
        from qm_training.app import access_refusal_reason

        with tempfile.TemporaryDirectory() as tmp:
            store = UserStore(Path(tmp) / "users.json")
            settings = Settings(ai_provider="mock", allowed_user_ids=("1",))
            self.assertIsNone(access_refusal_reason(settings, store))

    def test_allows_with_owner_ids(self) -> None:
        from qm_training.app import access_refusal_reason

        with tempfile.TemporaryDirectory() as tmp:
            store = UserStore(Path(tmp) / "users.json")
            settings = Settings(ai_provider="mock", owner_user_ids=("1",))
            self.assertIsNone(access_refusal_reason(settings, store))

    def test_allows_with_store_user(self) -> None:
        from qm_training.app import access_refusal_reason

        with tempfile.TemporaryDirectory() as tmp:
            store = UserStore(Path(tmp) / "users.json")
            store.add("42")
            settings = Settings(ai_provider="mock", allowed_user_ids=(), owner_user_ids=())
            self.assertIsNone(access_refusal_reason(settings, store))

    def test_allows_when_open_access_explicit(self) -> None:
        from qm_training.app import access_refusal_reason

        with tempfile.TemporaryDirectory() as tmp:
            store = UserStore(Path(tmp) / "users.json")
            settings = Settings(ai_provider="mock", allowed_user_ids=(), owner_user_ids=(), allow_open_access=True)
            self.assertIsNone(access_refusal_reason(settings, store))


if __name__ == "__main__":
    unittest.main()
