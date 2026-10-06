"""Test untuk qm_coil/state.py (tidak ada test JS aslinya)."""

from __future__ import annotations

import unittest

from qm_coil.state import (
    CoilSessionStore,
    IdempotencyCache,
    create_initial_state,
)


class StateTest(unittest.TestCase):
    def test_initial_state(self):
        state = create_initial_state()
        self.assertEqual(state["step"], "IDLE")
        self.assertIsNone(state["machine"])
        self.assertIsNone(state["sourceCoil"])
        self.assertEqual(state["generatedCoils"], [])
        self.assertEqual(state["inspections"], [])
        self.assertEqual(state["currentCoilIndex"], 0)
        self.assertEqual(state["currentCoilData"], {})
        self.assertIsNone(state["editTarget"])

    def test_store_get_membuat_baru(self):
        store = CoilSessionStore()
        self.assertFalse(store.has("1"))
        state = store.get("1")
        self.assertTrue(store.has("1"))
        self.assertEqual(state["step"], "IDLE")

    def test_store_set_menggabungkan(self):
        store = CoilSessionStore()
        store.set("1", {"machine": "FT", "step": "ASK_SOURCE"})
        state = store.get("1")
        self.assertEqual(state["machine"], "FT")
        self.assertEqual(state["step"], "ASK_SOURCE")
        self.assertIsNone(state["sourceCoil"])  # field lain tidak hilang

    def test_store_isolasi_antar_user(self):
        store = CoilSessionStore()
        store.set("1", {"machine": "FT"})
        store.set("2", {"machine": "FJ"})
        self.assertEqual(store.get("1")["machine"], "FT")
        self.assertEqual(store.get("2")["machine"], "FJ")

    def test_store_clear(self):
        store = CoilSessionStore()
        store.set("1", {"machine": "FT"})
        store.clear("1")
        self.assertFalse(store.has("1"))
        # get setelah clear membuat state baru lagi
        self.assertEqual(store.get("1")["step"], "IDLE")

    def test_idempotency_add_has(self):
        cache = IdempotencyCache()
        self.assertFalse(cache.has(123))
        cache.add(123)
        self.assertTrue(cache.has(123))
        self.assertTrue(cache.has("123"))  # string dinormalisasi
        cache.add(123)  # duplikat: no-op
        self.assertTrue(cache.has(123))

    def test_idempotency_none_diabaikan(self):
        cache = IdempotencyCache()
        self.assertFalse(cache.has(None))
        cache.add(None)  # tidak error

    def test_idempotency_evict_terlama(self):
        cache = IdempotencyCache(max_size=3)
        for i in (1, 2, 3):
            cache.add(i)
        cache.add(4)  # 1 ter-evict
        self.assertFalse(cache.has(1))
        self.assertTrue(cache.has(4))

    def test_idempotency_clear(self):
        cache = IdempotencyCache()
        cache.add(1)
        cache.clear()
        self.assertFalse(cache.has(1))


if __name__ == "__main__":
    unittest.main()
