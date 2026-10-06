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
