"""Tests untuk AssistantRouter (qm_assistant/router.py).

Memakai workflow & coil handler palsu agar tidak butuh token/AI.
Mengikuti konvensi repo: unittest.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from qm_training.bot.adapters.base import IncomingMessage, OutgoingMessage

from qm_assistant import AssistantRouter, AssistantSessionStore, BTN_COIL, BTN_TRAINING
from qm_assistant import BTN_ADMIN
from qm_assistant.session import MODE_COIL, MODE_MENU, MODE_TRAINING


class FakeUsers:
    def __init__(self, active_ids=()) -> None:
        self._active = set(active_ids)

    def is_active(self, user_id: str) -> bool:
        return str(user_id) in self._active


class FakeWorkflow:
    """Meniru atribut publik Workflow yang dipakai router."""

    def __init__(self, allowed_ids=(), owner_ids=(), active_ids=()) -> None:
        self.settings = SimpleNamespace(
            allowed_user_ids=list(allowed_ids),
            owner_user_ids=list(owner_ids),
        )
        self.owner_ids = set(owner_ids or allowed_ids)
        self.users = FakeUsers(active_ids)
        self.received: list[str] = []

    def handle(self, message: IncomingMessage) -> list[OutgoingMessage]:
        self.received.append(message.text)
        return [OutgoingMessage(f"WF:{message.text}")]


class FakeCoil:
    def __init__(self, owner_ids=()) -> None:
        self.owner_ids = list(owner_ids)
        self.received: list[str] = []

    def handle(self, message: IncomingMessage) -> list[OutgoingMessage]:
        self.received.append(message.text)
        return [OutgoingMessage("COIL:stub")]


def make_router(**kwargs) -> AssistantRouter:
    coil_owner_ids = kwargs.pop("coil_owner_ids", ())
    return AssistantRouter(
        training_workflow=FakeWorkflow(**kwargs),
        coil_handler=FakeCoil(owner_ids=coil_owner_ids),
        store=AssistantSessionStore(),
    )


def msg(user_id: str, text: str) -> IncomingMessage:
    return IncomingMessage(user_id=user_id, text=text)


class RouterTest(unittest.TestCase):
    def test_start_menampilkan_menu(self):
        router = make_router()
        out = router.handle(msg("1", "/start"))
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].buttons, [BTN_COIL, BTN_TRAINING])
        self.assertEqual(router.store.get_mode("1"), MODE_MENU)

    def test_pilih_training_mendelegasikan_new_training(self):
        router = make_router()
        router.handle(msg("1", "/start"))
        out = router.handle(msg("1", BTN_TRAINING))
        self.assertEqual(router.store.get_mode("1"), MODE_TRAINING)
        self.assertEqual(router.training.received, ["/new_training"])
        self.assertEqual(out[0].text, "WF:/new_training")

    def test_mode_training_mendelegasikan_semua_pesan(self):
        router = make_router()
        router.handle(msg("1", "/start"))
        router.handle(msg("1", BTN_TRAINING))
        out = router.handle(msg("1", "halo"))
        self.assertEqual(out[0].text, "WF:halo")

    def test_start_di_tengah_training_kembali_ke_menu(self):
        router = make_router()
        router.handle(msg("1", "/start"))
        router.handle(msg("1", BTN_TRAINING))
        out = router.handle(msg("1", "/start"))
        self.assertEqual(router.store.get_mode("1"), MODE_MENU)
        self.assertEqual(out[0].buttons, [BTN_COIL, BTN_TRAINING])

    def test_pilih_coil_masuk_mode_coil(self):
        router = make_router()
        router.handle(msg("1", "/start"))
        out = router.handle(msg("1", BTN_COIL))
        self.assertEqual(router.store.get_mode("1"), MODE_COIL)
        self.assertEqual(out[0].text, "COIL:stub")

    def test_pindah_coil_ke_training_lewat_tombol(self):
        # Regresi dari screenshot user: di mode coil, tap "Form Pelatihan"
        # harus pindah layanan, bukan dijawab stub coil lagi.
        router = make_router()
        router.handle(msg("1", "/start"))
        router.handle(msg("1", BTN_COIL))
        self.assertEqual(router.store.get_mode("1"), MODE_COIL)
        out = router.handle(msg("1", BTN_TRAINING))
        self.assertEqual(router.store.get_mode("1"), MODE_TRAINING)
        self.assertEqual(router.training.received, ["/new_training"])
        self.assertEqual(out[0].text, "WF:/new_training")

    def test_pindah_training_ke_coil_lewat_tombol(self):
        router = make_router()
        router.handle(msg("1", "/start"))
        router.handle(msg("1", BTN_TRAINING))
        out = router.handle(msg("1", BTN_COIL))
        self.assertEqual(router.store.get_mode("1"), MODE_COIL)
        self.assertEqual(out[0].text, "COIL:stub")

    def test_cancel_kembali_ke_menu(self):
        router = make_router()
        router.handle(msg("1", "/start"))
        router.handle(msg("1", BTN_TRAINING))
        out = router.handle(msg("1", "/cancel"))
        self.assertEqual(router.store.get_mode("1"), MODE_MENU)
        self.assertEqual(out[0].buttons, [BTN_COIL, BTN_TRAINING])

    def test_teks_asing_di_menu_menampilkan_menu_lagi(self):
        router = make_router()
        out = router.handle(msg("1", "xyz"))
        self.assertEqual(out[0].buttons, [BTN_COIL, BTN_TRAINING])

    def test_user_tak_terdaftar_ditolak_di_training(self):
        # Menu (/start) terbuka untuk semua; yang digembok adalah layanannya.
        router = make_router(allowed_ids=["999"])
        out = router.handle(msg("123", "/start"))
        self.assertEqual(out[0].buttons, [BTN_COIL, BTN_TRAINING])
        # Form Pelatihan tetap ditolak.
        out = router.handle(msg("123", BTN_TRAINING))
        self.assertIn("belum terdaftar", out[0].text)
        self.assertEqual(router.training.received, [])

    def test_coil_tidak_butuh_otorisasi_training(self):
        # Form Gulungan punya access guard sendiri (gateway), bukan
        # allowlist training.
        router = make_router(allowed_ids=["999"])
        router.handle(msg("123", "/start"))
        out = router.handle(msg("123", BTN_COIL))
        self.assertEqual(router.store.get_mode("123"), MODE_COIL)
        self.assertEqual(out[0].text, "COIL:stub")

    def test_owner_lolos_otorisasi(self):
        router = make_router(allowed_ids=["999"], owner_ids=["999"])
        out = router.handle(msg("999", "/start"))
        self.assertEqual(out[0].buttons, [BTN_COIL, BTN_TRAINING])

    def test_menu_admin_hanya_untuk_owner(self):
        router = make_router(coil_owner_ids=["1"])
        out = router.handle(msg("1", "/start"))
        self.assertEqual(out[0].buttons, [BTN_COIL, BTN_TRAINING, BTN_ADMIN])
        out = router.handle(msg("42", "/start"))
        self.assertEqual(out[0].buttons, [BTN_COIL, BTN_TRAINING])

    def test_tombol_admin_membuka_panel(self):
        router = make_router(coil_owner_ids=["1"])
        router.handle(msg("1", "/start"))
        out = router.handle(msg("1", BTN_ADMIN))
        self.assertEqual(router.store.get_mode("1"), MODE_COIL)
        # Diteruskan ke gateway sebagai perintah /admin.
        self.assertEqual(router.coil.received, ["/admin"])
        self.assertEqual(out[0].text, "COIL:stub")


if __name__ == "__main__":
    unittest.main()
