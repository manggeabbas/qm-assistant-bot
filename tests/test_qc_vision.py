"""Test qm_bantuan.vision: analisis foto cacat via GeminiVision."""

from __future__ import annotations

import base64
import unittest

from qm_bantuan.vision import (
    ALLOWED_IMAGE_MIME_TYPES,
    MAX_IMAGE_BYTES,
    PHOTO_PROMPT,
    PHOTO_SYSTEM,
    GeminiVision,
)
from qm_training.core.errors import AIProviderError


def _ok_response(text: str = "analisis contoh") -> dict:
    return {
        "candidates": [{"content": {"parts": [{"text": text}]}}],
    }


class FakeVision(GeminiVision):
    """GeminiVision dengan _post palsu: merekam payload, mengembalikan JSON canned."""

    def __init__(self, canned: dict):
        super().__init__(api_key="KUNCI-RAHASIA-123", model="gemini-3.6-flash")
        self.canned = canned
        self.last_url = None
        self.last_payload = None

    def _post(self, url, headers, payload):  # noqa: D102 (signature warisan)
        self.last_url = url
        self.last_payload = payload
        return self.canned


class TestAnalyzeImagePayload(unittest.TestCase):
    def setUp(self) -> None:
        self.png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        self.vision = FakeVision(_ok_response("hasil"))

    def test_inline_data_mirrors_bytes(self) -> None:
        text = self.vision.analyze_image(self.png, mime_type="image/png")
        self.assertEqual(text, "hasil")
        part = self.vision.last_payload["contents"][0]["parts"][1]
        self.assertEqual(part["inlineData"]["mimeType"], "image/png")
        self.assertEqual(base64.b64decode(part["inlineData"]["data"]), self.png)

    def test_text_prompt_default_and_custom(self) -> None:
        self.vision.analyze_image(self.png)
        part0 = self.vision.last_payload["contents"][0]["parts"][0]
        self.assertEqual(part0["text"], PHOTO_PROMPT)
        self.vision.analyze_image(self.png, prompt="fokus ke tepi gulungan")
        part0 = self.vision.last_payload["contents"][0]["parts"][0]
        self.assertEqual(part0["text"], "fokus ke tepi gulungan")

    def test_system_instruction_keywords(self) -> None:
        self.vision.analyze_image(self.png)
        system = self.vision.last_payload["systemInstruction"]["parts"][0]["text"]
        self.assertIs(system, PHOTO_SYSTEM)
        for keyword in ("milimeter", "opini kedua", "kepercayaan"):
            self.assertIn(keyword, system)

    def test_url_uses_endpoint_and_key(self) -> None:
        self.vision.analyze_image(self.png)
        self.assertIn("generateContent", self.vision.last_url)
        self.assertIn("gemini-3.6-flash", self.vision.last_url)

    def test_default_mime_is_jpeg(self) -> None:
        self.vision.analyze_image(b"\xff\xd8\xff" + b"\x00" * 10)
        part = self.vision.last_payload["contents"][0]["parts"][1]
        self.assertEqual(part["inlineData"]["mimeType"], "image/jpeg")

    def test_allowed_mime_types(self) -> None:
        self.assertEqual(
            ALLOWED_IMAGE_MIME_TYPES, {"image/jpeg", "image/png", "image/webp"}
        )


class TestAnalyzeImageValidation(unittest.TestCase):
    def setUp(self) -> None:
        self.vision = FakeVision(_ok_response())

    def test_empty_bytes(self) -> None:
        with self.assertRaises(ValueError):
            self.vision.analyze_image(b"")

    def test_too_large(self) -> None:
        with self.assertRaises(ValueError):
            self.vision.analyze_image(b"\x00" * (MAX_IMAGE_BYTES + 1))

    def test_just_under_limit_ok(self) -> None:
        text = self.vision.analyze_image(b"\x00" * MAX_IMAGE_BYTES)
        self.assertEqual(text, "analisis contoh")

    def test_unknown_mime(self) -> None:
        with self.assertRaises(ValueError):
            self.vision.analyze_image(b"GIF89a", mime_type="image/gif")

    def test_missing_api_key(self) -> None:
        no_key = GeminiVision(api_key=None)
        with self.assertRaises(AIProviderError):
            no_key.analyze_image(b"\x00\x01")


class TestMalformedResponse(unittest.TestCase):
    def test_empty_dict(self) -> None:
        with self.assertRaises(AIProviderError):
            FakeVision({}).analyze_image(b"\x00\x01")

    def test_no_candidates(self) -> None:
        with self.assertRaises(AIProviderError):
            FakeVision({"candidates": []}).analyze_image(b"\x00\x01")

    def test_parts_not_list(self) -> None:
        with self.assertRaises(AIProviderError):
            FakeVision({"candidates": [{"content": {}}]}).analyze_image(b"\x00\x01")


class TestPromptConstants(unittest.TestCase):
    def test_photo_system_disclaimer(self) -> None:
        self.assertIn("opini kedua", PHOTO_SYSTEM)
        self.assertIn("inspector manusia", PHOTO_SYSTEM)

    def test_photo_system_no_size_guessing(self) -> None:
        self.assertIn("Jangan", PHOTO_SYSTEM)
        self.assertIn("menebak angka ukuran", PHOTO_SYSTEM)
        self.assertIn("penggaris", PHOTO_SYSTEM)

    def test_photo_system_confidence_levels(self) -> None:
        for word in ("Tinggi", "Sedang", "Rendah", "kepercayaan"):
            self.assertIn(word, PHOTO_SYSTEM)

    def test_photo_system_field_checks(self) -> None:
        # Teknisi diberi tahu apa yang wajib dicek di lini.
        self.assertIn("kaliper", PHOTO_SYSTEM)

    def test_photo_prompt_content(self) -> None:
        self.assertIn("maksimal 3", PHOTO_PROMPT)
        self.assertIn("tingkat kepercayaan", PHOTO_PROMPT.lower())


if __name__ == "__main__":
    unittest.main()
