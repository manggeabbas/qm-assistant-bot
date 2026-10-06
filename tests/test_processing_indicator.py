"""Tests for the animated sticker (.tgs) processing indicator."""

from __future__ import annotations

import gzip
import os
import time
import unittest
from unittest import mock

from qm_training.bot.adapters.base import IncomingMessage, OutgoingMessage
from qm_training.bot.adapters.mock import MockTelegramAdapter
from qm_training.bot.adapters.telegram import TelegramBotAdapter
from qm_training.bot.processing import run_with_sticker_indicator
from qm_training.core.config import Settings
from qm_training.paths import PROJECT_ROOT


class _FastWorkflow:
    def handle(self, incoming):
        return [OutgoingMessage("cepat")]


class _SlowWorkflow:
    def __init__(self, delay=0.3):
        self.delay = delay

    def handle(self, incoming):
        time.sleep(self.delay)
        return [OutgoingMessage("selesai")]


class _SlowFailWorkflow:
    def handle(self, incoming):
        time.sleep(0.3)
        raise RuntimeError("boom")


class _FastFailWorkflow:
    def handle(self, incoming):
        raise RuntimeError("boom-fast")


class _DedupSlowWorkflow:
    def __init__(self, delay=0.3):
        self.delay = delay
        self.seen: set[int | None] = set()

    def handle(self, incoming):
        if incoming.update_id in self.seen:
            return []
        self.seen.add(incoming.update_id)
        time.sleep(self.delay)
        return [OutgoingMessage("ok")]


class TestStickerHelper(unittest.TestCase):
    def _run(self, func, threshold, send_fails=False):
        sent, deleted = [], []

        def send():
            if send_fails:
                raise RuntimeError("sticker failed")
            message_id = 555
            sent.append(message_id)
            return message_id

        run_with_sticker_indicator(func, send, lambda mid: deleted.append(mid), threshold=threshold)
        return sent, deleted

    def test_1_fast_operation_no_sticker(self) -> None:
        sent, deleted = self._run(lambda: "ok", threshold=0.2)
        self.assertEqual(sent, [])
        self.assertEqual(deleted, [])

    def test_2_slow_operation_sends_one_sticker(self) -> None:
        sent, deleted = self._run(lambda: (time.sleep(0.4), "ok")[1], threshold=0.1)
        self.assertEqual(sent, [555])
        self.assertEqual(deleted, [555])

    def test_3_sticker_deleted_after_completion(self) -> None:
        sent, deleted = self._run(lambda: (time.sleep(0.3), "ok")[1], threshold=0.05)
        self.assertEqual(len(sent), 1)
        self.assertEqual(deleted, sent)

    def test_4_error_after_sticker_deletes_then_raises(self) -> None:
        def boom():
            time.sleep(0.3)
            raise ValueError("boom")

        sent, deleted = [], []

        def send():
            sent.append(1)
            return 1

        with self.assertRaises(ValueError):
            run_with_sticker_indicator(boom, send, lambda mid: deleted.append(mid), threshold=0.05)
        self.assertEqual(sent, [1])
        self.assertEqual(deleted, [1])

    def test_5_error_before_threshold_no_sticker(self) -> None:
        def boom():
            raise ValueError("boom")

        sent = []
        with self.assertRaises(ValueError):
            run_with_sticker_indicator(boom, lambda: sent.append(1), lambda mid: None, threshold=0.2)
        self.assertEqual(sent, [])

    def test_7_sticker_failure_does_not_fail_operation(self) -> None:
        result = None
        try:
            result = run_with_sticker_indicator(
                lambda: (time.sleep(0.3), "ok")[1],
                lambda: (_ for _ in ()).throw(RuntimeError("sticker failed")),
                lambda mid: None,
                threshold=0.05,
            )
        except Exception as exc:  # noqa: BLE001
            self.fail(f"operation must not fail when the sticker fails: {exc}")
        self.assertEqual(result, "ok")

    def test_8_timer_after_completion_sends_nothing(self) -> None:
        sent, _ = self._run(lambda: "fast", threshold=0.15)
        self.assertEqual(sent, [])


class TestMockAdapterSticker(unittest.TestCase):
    def test_1_fast_no_sticker(self) -> None:
        adapter = MockTelegramAdapter(_FastWorkflow(), slow_threshold=0.5)
        adapter.receive("1", "halo")
        self.assertEqual(adapter.stickers_sent, [])

    def test_2_slow_one_sticker(self) -> None:
        adapter = MockTelegramAdapter(_SlowWorkflow(), slow_threshold=0.1)
        messages = adapter.receive("1", "halo")
        self.assertEqual(len(adapter.stickers_sent), 1)
        self.assertEqual(messages[0].text, "selesai")

    def test_3_sticker_deleted(self) -> None:
        adapter = MockTelegramAdapter(_SlowWorkflow(), slow_threshold=0.05)
        adapter.receive("1", "halo")
        self.assertEqual(len(adapter.stickers_deleted), 1)
        self.assertEqual(adapter.stickers_sent[0][1], adapter.stickers_deleted[0][1])

    def test_4_error_after_sticker_deleted(self) -> None:
        adapter = MockTelegramAdapter(_SlowFailWorkflow(), slow_threshold=0.05)
        with self.assertRaises(RuntimeError):
            adapter.receive("1", "halo")
        self.assertEqual(len(adapter.stickers_sent), 1)
        self.assertEqual(len(adapter.stickers_deleted), 1)

    def test_5_error_before_threshold_no_sticker(self) -> None:
        adapter = MockTelegramAdapter(_FastFailWorkflow(), slow_threshold=0.5)
        with self.assertRaises(RuntimeError):
            adapter.receive("1", "halo")
        self.assertEqual(adapter.stickers_sent, [])

    def test_6_duplicate_update_max_one_sticker(self) -> None:
        adapter = MockTelegramAdapter(_DedupSlowWorkflow(), slow_threshold=0.05)
        adapter.receive("1", "halo", update_id=1)
        adapter.receive("1", "halo", update_id=1)  # duplicate -> no new work
        self.assertEqual(len(adapter.stickers_sent), 1)

    def test_7_sticker_failure_operation_continues(self) -> None:
        adapter = MockTelegramAdapter(_SlowWorkflow(), slow_threshold=0.05, sticker_fails=True)
        messages = adapter.receive("1", "halo")
        self.assertEqual(messages[0].text, "selesai")
        self.assertEqual(adapter.stickers_sent, [])

    def test_fallback_typing_when_sticker_unavailable(self) -> None:
        adapter = MockTelegramAdapter(_SlowWorkflow(), slow_threshold=0.05, sticker_returns_none=True)
        adapter.receive("1", "halo")
        self.assertEqual(adapter.stickers_sent, [])
        self.assertIn(("1", "typing"), adapter.chat_actions)

    def test_production_default_no_sticker_uses_typing(self) -> None:
        # Mirrors production default (sticker upload disabled): no file, typing only.
        adapter = MockTelegramAdapter(_SlowWorkflow(), slow_threshold=0.05, sticker_available=False)
        adapter.receive("1", "halo")
        self.assertEqual(adapter.stickers_sent, [])
        self.assertIn(("1", "typing"), adapter.chat_actions)


class TestTelegramAdapterSticker(unittest.TestCase):
    def _adapter(self, workflow, threshold=0.05):
        adapter = TelegramBotAdapter(
            "dummy-token",
            workflow,
            slow_threshold=threshold,
            sticker_path="assets/hourglass.tgs",
            allow_sticker_upload=True,
        )
        adapter.session = mock.Mock()

        def fake_post(url, **kwargs):
            response = mock.Mock()
            response.json.return_value = {"ok": True, "result": {"message_id": 42, "sticker": {"file_id": "FID"}}}
            return response

        adapter.session.post.side_effect = fake_post
        return adapter

    def test_slow_sends_and_deletes_sticker(self) -> None:
        adapter = self._adapter(_SlowWorkflow())
        adapter._handle_incoming(IncomingMessage(user_id="1", text="halo"))
        urls = [c.args[0] for c in adapter.session.post.call_args_list]
        self.assertTrue(any("sendSticker" in u for u in urls))
        self.assertTrue(any("deleteMessage" in u for u in urls))
        self.assertTrue(any("sendMessage" in u for u in urls))
        self.assertEqual(adapter._sticker_file_id, "FID")

    def test_file_id_reused_after_first_send(self) -> None:
        adapter = self._adapter(_SlowWorkflow())
        adapter._handle_incoming(IncomingMessage(user_id="1", text="halo"))  # 1st: upload .tgs
        adapter._handle_incoming(IncomingMessage(user_id="1", text="halo"))  # 2nd: reuse file_id
        sticker_calls = [c for c in adapter.session.post.call_args_list if "sendSticker" in c.args[0]]
        self.assertGreaterEqual(len(sticker_calls), 2)
        self.assertIn("files", sticker_calls[0].kwargs)  # first send uploads the .tgs
        self.assertIn("json", sticker_calls[-1].kwargs)  # later sends reuse file_id
        self.assertEqual(sticker_calls[-1].kwargs["json"]["sticker"], "FID")

    def test_fast_no_sticker(self) -> None:
        adapter = self._adapter(_FastWorkflow(), threshold=0.5)
        adapter._handle_incoming(IncomingMessage(user_id="1", text="halo"))
        urls = [c.args[0] for c in adapter.session.post.call_args_list]
        self.assertFalse(any("sendSticker" in u for u in urls))

    def test_default_no_upload_no_stray_file(self) -> None:
        # Default config: no file_id and upload disabled -> native typing action,
        # and no file is ever uploaded to the chat.
        adapter = TelegramBotAdapter("dummy-token", _SlowWorkflow(), slow_threshold=0.05)
        adapter.session = mock.Mock()
        adapter.session.post.side_effect = lambda url, **kw: mock.Mock(json=lambda: {})
        adapter._handle_incoming(IncomingMessage(user_id="1", text="halo"))
        calls = adapter.session.post.call_args_list
        urls = [c.args[0] for c in calls]
        self.assertFalse(any("sendSticker" in u for u in urls))
        self.assertFalse(any("sendDocument" in u for u in urls))
        self.assertTrue(any("sendChatAction" in u for u in urls))


class TestConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        settings = Settings(ai_provider="mock")
        self.assertEqual(settings.processing_delay_seconds, 0.5)
        self.assertEqual(settings.hourglass_sticker_path, "assets/hourglass.tgs")
        self.assertIsNone(settings.hourglass_sticker_file_id)
        self.assertFalse(settings.hourglass_sticker_upload)

    def test_env_override(self) -> None:
        env = {
            "HOURGLASS_STICKER_FILE_ID": "CAAC-dummy",
            "HOURGLASS_STICKER_PATH": "assets/hourglass.tgs",
            "PROCESSING_DELAY_SECONDS": "0.3",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            settings = Settings.from_env(load_env=False)
        self.assertEqual(settings.hourglass_sticker_file_id, "CAAC-dummy")
        self.assertAlmostEqual(settings.processing_delay_seconds, 0.3)


class TestStickerAsset(unittest.TestCase):
    def test_tgs_asset_present_and_valid_gzip(self) -> None:
        path = PROJECT_ROOT / "assets" / "hourglass.tgs"
        self.assertTrue(path.exists(), "assets/hourglass.tgs harus ada")
        with gzip.open(path, "rb") as handle:
            data = handle.read()
        self.assertGreater(len(data), 0)

    def test_no_gif_asset(self) -> None:
        self.assertFalse((PROJECT_ROOT / "assets" / "hourglass.gif").exists())

    def test_env_example_documents_sticker(self) -> None:
        content = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")
        for key in ("HOURGLASS_STICKER_FILE_ID", "HOURGLASS_STICKER_PATH", "PROCESSING_DELAY_SECONDS"):
            self.assertIn(key, content)


if __name__ == "__main__":
    unittest.main()
