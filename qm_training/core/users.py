"""Persistent user access store (admin-granted access).

Simple JSON file based store (no database dependency): the admin can allow or
deny users at runtime via Telegram commands, without editing .env or restarting.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from qm_training.paths import USERS_FILE

VALID_ROLES = ("OWNER", "ADMIN", "USER")


@dataclass
class UserRecord:
    user_id: str
    role: str = "USER"
    active: bool = True
    added_at: str | None = None


class UserStore:
    def __init__(self, path: Path = USERS_FILE) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self._users: dict[str, UserRecord] = {}
        self._load()

    # -- persistence ------------------------------------------------------- #

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        for user_id, data in (payload.get("users") or {}).items():
            role = str(data.get("role", "USER")).upper()
            self._users[str(user_id)] = UserRecord(
                user_id=str(user_id),
                role=role if role in VALID_ROLES else "USER",
                active=bool(data.get("active", True)),
                added_at=data.get("added_at"),
            )

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "users": {
                user_id: {"role": record.role, "active": record.active, "added_at": record.added_at}
                for user_id, record in self._users.items()
            }
        }
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # -- queries ----------------------------------------------------------- #

    def is_active(self, user_id: str) -> bool:
        record = self._users.get(str(user_id))
        return bool(record and record.active)

    def role_of(self, user_id: str) -> str | None:
        record = self._users.get(str(user_id))
        return record.role if record else None

    def is_admin(self, user_id: str) -> bool:
        return self.role_of(user_id) in ("OWNER", "ADMIN")

    def list_users(self) -> list[UserRecord]:
        return sorted(self._users.values(), key=lambda r: r.user_id)

    # -- mutations --------------------------------------------------------- #

    def add(self, user_id: str, role: str = "USER") -> UserRecord:
        role = role.upper() if role.upper() in VALID_ROLES else "USER"
        with self._lock:
            record = self._users.get(str(user_id))
            if record is None:
                record = UserRecord(user_id=str(user_id), added_at=datetime.now(timezone.utc).isoformat())
                self._users[str(user_id)] = record
            record.role = role
            record.active = True
            self._save()
            return record

    def set_active(self, user_id: str, active: bool) -> bool:
        with self._lock:
            record = self._users.get(str(user_id))
            if record is None:
                return False
            record.active = active
            self._save()
            return True
