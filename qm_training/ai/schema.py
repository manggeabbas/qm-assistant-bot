"""Parsing + validation of structured AI output."""

from __future__ import annotations

import json
import re

from qm_training.core.errors import AIValidationError
from qm_training.document.schema import QAPair

QUESTION_COUNT = 5
# Questions must stay short so the T03A form stays on a single page
# (empirically <=80 characters keeps T03A on one page).
MAX_QUESTION_CHARS = 80
# Answers belong to the KUNCI JAWABAN page: aim for 1-3 informative sentences.
MAX_ANSWER_CHARS = 400
_FENCE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")


def extract_json(raw: str) -> dict:
    if raw is None:
        raise AIValidationError("respons AI kosong")
    text = _FENCE.sub("", raw.strip())
    # Ambil objek JSON pertama bila ada teks tambahan.
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise AIValidationError("respons AI bukan JSON")
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise AIValidationError(f"JSON tidak valid: {exc}") from exc
    if not isinstance(payload, dict):
        raise AIValidationError("JSON harus berupa objek")
    return payload


def parse_theme(raw: str) -> str:
    payload = extract_json(raw)
    theme = str(payload.get("theme", "")).strip()
    if not theme:
        raise AIValidationError("field 'theme' kosong")
    return theme


def parse_answer(raw: str) -> str:
    payload = extract_json(raw)
    answer = str(payload.get("answer", "")).strip()
    if not answer:
        raise AIValidationError("field 'answer' kosong")
    if len(answer) > MAX_ANSWER_CHARS:
        raise AIValidationError(
            f"jawaban terlalu panjang ({len(answer)} karakter, maksimal {MAX_ANSWER_CHARS})."
        )
    return answer


def parse_questions(raw: str) -> list[QAPair]:
    payload = extract_json(raw)
    items = payload.get("questions")
    if not isinstance(items, list):
        raise AIValidationError("field 'questions' harus berupa list")
    if len(items) != QUESTION_COUNT:
        raise AIValidationError(f"harus tepat {QUESTION_COUNT} pertanyaan, ditemukan {len(items)}")
    pairs: list[QAPair] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise AIValidationError(f"pertanyaan {index} bukan objek")
        pair = QAPair(str(item.get("question", "")), str(item.get("answer", "")))
        if not pair.question:
            raise AIValidationError(f"pertanyaan {index} kosong")
        if not pair.answer:
            raise AIValidationError(f"jawaban {index} kosong")
        if len(pair.question) > MAX_QUESTION_CHARS:
            raise AIValidationError(
                f"pertanyaan {index} terlalu panjang ({len(pair.question)} karakter, "
                f"maksimal {MAX_QUESTION_CHARS}). Ringkas menjadi satu kalimat pendek."
            )
        if len(pair.answer) > MAX_ANSWER_CHARS:
            raise AIValidationError(
                f"jawaban {index} terlalu panjang ({len(pair.answer)} karakter, "
                f"maksimal {MAX_ANSWER_CHARS}). Ringkas menjadi maksimal dua kalimat pendek."
            )
        pairs.append(pair)
    return pairs
