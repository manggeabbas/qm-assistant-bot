"""Per-user session state.

Sessions are isolated by user id and persisted as JSON so an interrupted flow
can be resumed.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from qm_training.bot.states import State
from qm_training.paths import SESSIONS_DIR

SUB_DIRS = ("input", "extracted", "photos", "working", "output")


@dataclass
class Session:
    user_id: str
    state: str = State.IDLE.value
    material_path: str | None = None
    material_text: str | None = None
    theme: str | None = None
    theme_source: str | None = None
    theme_confirmed: bool = False
    archive_number: str | None = None
    training_date: str | None = None
    location: str | None = None
    trainer: str | None = None
    shift_group: str | None = None
    personnel_count: int | None = None
    personnel_set: bool = False
    questions: list[dict] = field(default_factory=list)
    question_confirmed: bool = False
    photos: list[str] = field(default_factory=list)
    awaiting: str | None = None
    output_docx: str | None = None
    output_pdf: str | None = None
    error: str | None = None
    # Idempotency: ids of Telegram updates already processed for this session.
    processed_update_ids: list[int] = field(default_factory=list)
    # Safe diagnostics counters (no secrets). One session = one QuestionSet.
    generate_questions_calls: int = 0
    preview_sent: int = 0
    question_set_created: bool = False
    document_generation: int = 0
    theme_extraction_calls: int = 0
    theme_messages_sent: int = 0
    validation_runs: int = 0
    validation_error_messages_sent: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "Session":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in payload.items() if k in known})

    def reset_flow(self) -> None:
        fresh = Session(user_id=self.user_id)
        for name in self.__dataclass_fields__:
            setattr(self, name, getattr(fresh, name))


class SessionStore:
    def __init__(self, root: Path = SESSIONS_DIR) -> None:
        self.root = Path(root)

    def dir(self, user_id: str) -> Path:
        directory = self.root / str(user_id)
        for sub in SUB_DIRS:
            (directory / sub).mkdir(parents=True, exist_ok=True)
        return directory

    def _file(self, user_id: str) -> Path:
        return self.dir(user_id) / "session.json"

    def get(self, user_id: str) -> Session:
        path = self._file(user_id)
        if path.exists():
            try:
                return Session.from_dict(json.loads(path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, TypeError):
                pass
        return Session(user_id=str(user_id))

    def save(self, session: Session) -> None:
        self._file(session.user_id).write_text(
            json.dumps(session.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def reset(self, user_id: str) -> Session:
        session = Session(user_id=str(user_id))
        self.save(session)
        return session
