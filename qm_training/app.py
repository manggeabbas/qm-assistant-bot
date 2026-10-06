"""Application assembly: settings -> AI provider -> workflow.

Used by ``main.py`` and by the deployment checks.
"""

from __future__ import annotations

from qm_training.ai.factory import create_provider_or_mock
from qm_training.ai.service import AIService
from qm_training.bot import SessionStore, Workflow
from qm_training.core.config import Settings
from qm_training.core.users import UserStore


def access_refusal_reason(settings: Settings | None = None, user_store: UserStore | None = None) -> str | None:
    """Return a refusal message if the bot has no permitted users, else None.

    Fail-closed: without an owner/allowlist (or at least one active user in the
    store), the bot must not run openly unless ALLOW_OPEN_ACCESS is enabled.
    """
    settings = settings or Settings.from_env()
    if settings.allow_open_access:
        return None
    if settings.owner_user_ids or settings.allowed_user_ids:
        return None
    store = user_store or UserStore()
    if any(record.active for record in store.list_users()):
        return None
    return (
        "Tidak ada user yang diberi akses.\n"
        "Set ALLOWED_TELEGRAM_USER_IDS (id Telegram Anda) atau BOT_OWNER_IDS di .env, "
        "atau tambahkan user via /allow setelah owner dikonfigurasi.\n"
        "Untuk mode terbuka (khusus development), set ALLOW_OPEN_ACCESS=true."
    )


def build_workflow(settings: Settings | None = None) -> tuple[Workflow, bool]:
    """Return (workflow, ai_is_mock)."""
    settings = settings or Settings.from_env()
    provider, is_mock = create_provider_or_mock(settings)
    service = AIService(provider, max_retries=settings.ai_max_retries)
    workflow = Workflow(
        store=SessionStore(),
        ai_service=service,
        settings=settings,
        user_store=UserStore(),
    )
    return workflow, is_mock
