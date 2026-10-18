"""Keyboard sekali pilih: tombol hilang setelah ditekan (one_time_keyboard).

Regresi dari masukan user: tombol menu (Form Gulungan / Form Pelatihan)
tampil fix di bawah kolom chat. Sekarang memakai one_time_keyboard agar
keyboard otomatis disembunyikan setelah user memilih.
"""

from __future__ import annotations

import unittest

from qm_training.bot.adapters.base import OutgoingMessage
from qm_training.bot.adapters.telegram import TelegramBotAdapter


class _FakeResponse:
    def json(self):
        return {"ok": True, "result": {}}


class _FakeSession:
    def __init__(self):
        self.posts = []

    def post(self, url, json=None, **kwargs):
        self.posts.append({"url": url, "json": json})
        return _FakeResponse()


class KeyboardTest(unittest.TestCase):
    def _adapter(self):
        adapter = TelegramBotAdapter(token="TEST", workflow=None)
        adapter.session = _FakeSession()
        return adapter

    def test_keyboard_sekali_pilih(self):
        adapter = self._adapter()
        adapter.send_message("1", OutgoingMessage("Pilih:", buttons=["A", "B"]))
        self.assertEqual(len(adapter.session.posts), 1)
        markup = adapter.session.posts[0]["json"]["reply_markup"]
        self.assertTrue(markup["one_time_keyboard"])
        self.assertTrue(markup["resize_keyboard"])
        self.assertEqual(
            markup["keyboard"], [[{"text": "A"}], [{"text": "B"}]]
        )

    def test_tanpa_tombol_tanpa_markup(self):
        adapter = self._adapter()
        adapter.send_message("1", OutgoingMessage("Halo"))
        self.assertNotIn("reply_markup", adapter.session.posts[0]["json"])


if __name__ == "__main__":
    unittest.main()


class InlineKeyboardTest(unittest.TestCase):
    def _adapter(self):
        adapter = TelegramBotAdapter(token="<redacted>", workflow=None)
        adapter.session = _FakeSession()
        return adapter

    def test_inline_buttons_dikirim_sebagai_inline_keyboard(self):
        adapter = self._adapter()
        adapter.send_message(
            "1",
            OutgoingMessage(
                "Pilih:",
                inline_buttons=[[("A", "cb:a")], [("B", "cb:b"), ("C", "cb:c")]],
            ),
        )
        markup = adapter.session.posts[0]["json"]["reply_markup"]
        self.assertEqual(
            markup["inline_keyboard"],
            [
                [{"text": "A", "callback_data": "cb:a"}],
                [{"text": "B", "callback_data": "cb:b"},
                 {"text": "C", "callback_data": "cb:c"}],
            ],
        )
        self.assertNotIn("keyboard", markup)

    def test_inline_lebih_utama_dari_reply_keyboard(self):
        adapter = self._adapter()
        adapter.send_message(
            "1",
            OutgoingMessage("Pilih:", buttons=["X"],
                            inline_buttons=[[("A", "cb:a")]]),
        )
        markup = adapter.session.posts[0]["json"]["reply_markup"]
        self.assertIn("inline_keyboard", markup)
        self.assertNotIn("keyboard", markup)

    def test_callback_query_jadi_incoming_dan_dijawab(self):
        adapter = self._adapter()
        update = {
            "update_id": 5,
            "callback_query": {
                "id": "cb123",
                "from": {"id": 99, "username": "u"},
                "data": "qc:card:B22",
            },
        }
        incoming = adapter._to_incoming(update)
        self.assertTrue(incoming.is_callback)
        self.assertEqual(incoming.callback_id, "cb123")
        self.assertEqual(incoming.text, "qc:card:B22")
        self.assertEqual(incoming.user_id, "99")
        adapter.answer_callback("cb123")
        last = adapter.session.posts[-1]
        self.assertIn("answerCallbackQuery", last["url"])
        self.assertEqual(last["json"]["callback_query_id"], "cb123")


class EditMessageTest(unittest.TestCase):
    def _adapter(self):
        adapter = TelegramBotAdapter(token="<redacted>", workflow=None)
        adapter.session = _FakeSession()
        return adapter

    def test_callback_membawa_message_id(self):
        adapter = self._adapter()
        incoming = adapter._to_incoming({
            "update_id": 6,
            "callback_query": {
                "id": "cb1", "from": {"id": 7}, "data": "qc:page:+1",
                "message": {"message_id": 1234, "chat": {"id": 7}},
            },
        })
        self.assertEqual(incoming.callback_message_id, 1234)

    def test_edit_message_mengirim_editMessageText(self):
        adapter = self._adapter()
        ok = adapter.edit_message(
            "1", 1234,
            OutgoingMessage("hal. 2", inline_buttons=[[("◀", "qc:page:-1")]]),
        )
        self.assertTrue(ok)
        post = adapter.session.posts[0]
        self.assertIn("editMessageText", post["url"])
        self.assertEqual(post["json"]["message_id"], 1234)
        self.assertEqual(post["json"]["text"], "hal. 2")
        self.assertIn("inline_keyboard", post["json"]["reply_markup"])

    def test_edit_gagal_mengembalikan_false(self):
        class FailSession(_FakeSession):
            def post(self, url, json=None, **kwargs):
                self.posts.append({"url": url, "json": json})
                class R:
                    def json(self):
                        return {"ok": False, "description": "message is not modified"}
                return R()
        adapter = self._adapter()
        adapter.session = FailSession()
        self.assertFalse(adapter.edit_message("1", 1234, OutgoingMessage("x")))
