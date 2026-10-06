"""Structured input schema for document generation.

The AI only produces content; this schema is the contract between the AI /
Telegram layers and the document engine. Validation happens before any DOCX
is touched.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from qm_training.core.errors import SchemaError

QUESTION_COUNT = 5


@dataclass
class QAPair:
    question: str
    answer: str

    def __post_init__(self) -> None:
        self.question = (self.question or "").strip()
        self.answer = (self.answer or "").strip()


@dataclass
class TrainingData:
    theme: str
    archive_number: str
    training_date: str
    location: str
    trainer: str
    shift_group: str
    questions: list[QAPair]
    personnel_count: int | None = None
    photos: list[Path] = field(default_factory=list)

    def validate(self) -> "TrainingData":
        for name in ("theme", "archive_number", "training_date", "location", "trainer", "shift_group"):
            if not str(getattr(self, name) or "").strip():
                raise SchemaError(f"field '{name}' wajib diisi")
        if self.personnel_count is not None:
            if not isinstance(self.personnel_count, int) or isinstance(self.personnel_count, bool):
                raise SchemaError("personnel_count harus integer atau null")
            if self.personnel_count < 0:
                raise SchemaError("personnel_count tidak boleh negatif")
        if len(self.questions) != QUESTION_COUNT:
            raise SchemaError(f"harus tepat {QUESTION_COUNT} pertanyaan, ditemukan {len(self.questions)}")
        for index, qa in enumerate(self.questions, start=1):
            if not qa.question:
                raise SchemaError(f"pertanyaan {index} kosong")
            if not qa.answer:
                raise SchemaError(f"jawaban {index} kosong")
        for photo in self.photos:
            if not Path(photo).exists():
                raise SchemaError(f"foto tidak ditemukan: {photo}")
        return self

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TrainingData":
        questions = [
            item if isinstance(item, QAPair) else QAPair(str(item.get("question", "")), str(item.get("answer", "")))
            for item in payload.get("questions", [])
        ]
        photos = [Path(p) for p in payload.get("photos", [])]
        return cls(
            theme=str(payload.get("theme", "")),
            archive_number=str(payload.get("archive_number", "")),
            training_date=str(payload.get("training_date", "")),
            location=str(payload.get("location", "")),
            trainer=str(payload.get("trainer", "")),
            shift_group=str(payload.get("shift_group", "")),
            personnel_count=payload.get("personnel_count"),
            questions=questions,
            photos=photos,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "theme": self.theme,
            "archive_number": self.archive_number,
            "training_date": self.training_date,
            "location": self.location,
            "trainer": self.trainer,
            "shift_group": self.shift_group,
            "personnel_count": self.personnel_count,
            "questions": [{"question": q.question, "answer": q.answer} for q in self.questions],
            "photos": [str(p) for p in self.photos],
        }

    def output_basename(self) -> str:
        import re

        clean = lambda value: re.sub(r"[^\w.\-]+", "-", str(value).strip()).strip("-")  # noqa: E731
        return f"{clean(self.archive_number)}_{clean(self.shift_group)}"
