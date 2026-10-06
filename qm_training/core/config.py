"""Environment-based configuration.

Credentials never live in source code. Values are read from environment
variables, optionally loaded from a local ``.env`` file (never committed).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Single source of truth for the project root (see qm_training.paths).
# Do NOT recompute with __file__ here: this module lives in qm_training/core/,
# where a naive parent.parent would resolve to the package dir, not the root.
from qm_training.paths import PROJECT_ROOT

DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"


def resolve_env_path(path: str | Path | None = None) -> Path:
    """Return the absolute path of the .env file to use."""
    if path is None:
        return DEFAULT_ENV_PATH
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return PROJECT_ROOT / candidate


def _parse_env_lines(text: str):
    """Yield (key, value) pairs, tolerating BOM, CRLF, quotes and 'export '."""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        yield key, value


def load_dotenv(path: str | Path | None = None) -> Path:
    """Load a .env file into the environment and return the resolved path.

    Precedence rules:
    - a non-empty environment variable always wins (real env > .env);
    - a missing OR empty environment variable is filled from .env.

    This avoids an empty exported variable silently shadowing the .env value.
    """
    env_path = resolve_env_path(path)
    if not env_path.exists():
        return env_path
    text = env_path.read_text(encoding="utf-8-sig")
    for key, value in _parse_env_lines(text):
        if not os.environ.get(key):  # missing or empty
            os.environ[key] = value
    return env_path


def env_file_status(path: str | Path | None = None) -> dict:
    """Safe diagnostics about the .env file. Never exposes values."""
    env_path = resolve_env_path(path)
    status = {"path": str(env_path), "exists": env_path.exists(), "keys": {}}
    if not env_path.exists():
        return status
    text = env_path.read_text(encoding="utf-8-sig")
    for key, value in _parse_env_lines(text):
        status["keys"][key] = "non-empty" if value.strip() else "empty"
    return status


@dataclass(frozen=True)
class Settings:
    ai_provider: str = "deepseek"
    deepseek_api_key: str | None = None
    gemini_api_key: str | None = None
    openai_api_key: str | None = None
    ai_model: str | None = None
    ai_timeout_seconds: int = 60
    ai_max_retries: int = 2
    telegram_bot_token: str | None = None
    allowed_user_ids: tuple[str, ...] = ()
    # Owner/admin ids (fallback: the first ALLOWED ids). Owners can manage users.
    owner_user_ids: tuple[str, ...] = ()
    # If True, the bot runs for everyone (development only). Default False.
    allow_open_access: bool = False
    # "Bot is processing" animated sticker (.tgs) indicator
    hourglass_sticker_file_id: str | None = None
    hourglass_sticker_path: str = "assets/hourglass.tgs"
    hourglass_sticker_upload: bool = False
    processing_delay_seconds: float = 0.5
    processing_sticker_min_seconds: float = 0.7

    @classmethod
    def from_env(cls, load_env: bool = True) -> "Settings":
        if load_env:
            load_dotenv()
        allowed = os.environ.get("ALLOWED_TELEGRAM_USER_IDS", "")
        return cls(
            ai_provider=os.environ.get("AI_PROVIDER", "deepseek").strip().lower(),
            deepseek_api_key=os.environ.get("DEEPSEEK_API_KEY") or None,
            gemini_api_key=os.environ.get("GEMINI_API_KEY") or None,
            openai_api_key=os.environ.get("OPENAI_API_KEY") or None,
            ai_model=os.environ.get("AI_MODEL") or None,
            ai_timeout_seconds=int(os.environ.get("AI_TIMEOUT_SECONDS", "60")),
            ai_max_retries=int(os.environ.get("AI_MAX_RETRIES", "2")),
            telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN") or None,
            allowed_user_ids=tuple(x.strip() for x in allowed.split(",") if x.strip()),
            owner_user_ids=tuple(
                x.strip() for x in os.environ.get("BOT_OWNER_IDS", "").split(",") if x.strip()
            ),
            allow_open_access=os.environ.get("ALLOW_OPEN_ACCESS", "false").strip().lower()
            in ("1", "true", "yes", "on"),
            hourglass_sticker_file_id=os.environ.get("HOURGLASS_STICKER_FILE_ID") or None,
            hourglass_sticker_path=os.environ.get("HOURGLASS_STICKER_PATH", "assets/hourglass.tgs"),
            hourglass_sticker_upload=os.environ.get("HOURGLASS_STICKER_UPLOAD", "false").strip().lower() in ("1", "true", "yes", "on"),
            processing_delay_seconds=float(os.environ.get("PROCESSING_DELAY_SECONDS", "0.5")),
            processing_sticker_min_seconds=float(os.environ.get("PROCESSING_STICKER_MIN_SECONDS", "0.7")),
        )

    def api_key_for(self, provider: str) -> str | None:
        return {
            "deepseek": self.deepseek_api_key,
            "gemini": self.gemini_api_key,
            "openai": self.openai_api_key,
            "mock": "mock",
        }.get(provider)
