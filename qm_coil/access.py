"""Access guard Form Gulungan.

Port dari: ``src/access.js`` (122 baris, qm-ywi-telegram-bot).
Status: PORTED sebagian — ``is_owner`` penuh (+ test). Middleware grammy
(``accessGuard``) tidak diterjemahkan 1:1; aturannya didokumentasikan di
bawah dan akan diintegrasikan ke ``wizard.py`` / router saat port wizard.

Aturan asli (Telegram Update -> User ID -> Status):
  NEW          -> hanya alur undangan (minta token)
  REGISTRATION -> hanya alur registrasi (minta NIK)
  ACTIVE       -> bot normal (diteruskan)
  BLOCKED      -> ditolak
  Owner        -> selalu diizinkan (agar tidak terkunci dari /admin)
"""

from __future__ import annotations

from qm_coil.users import USER_STATUS, get_user_by_telegram_id


def is_owner(telegram_user_id: object, owner_ids: list[str] | tuple[str, ...]) -> bool:
    """Cek apakah Telegram User ID termasuk owner."""
    if telegram_user_id is None:
        return False
    return str(telegram_user_id).strip() in set(owner_ids)


def resolve_user_status(
    telegram_user_id: object,
    owner_ids: list[str] | tuple[str, ...] = (),
    conn=None,
) -> str:
    """Status akses efektif: OWNER selalu 'ACTIVE' (tidak terkunci).

    Kembalikan salah satu: 'ACTIVE' (owner atau user aktif),
    atau status user dari database ('NEW' default bila belum terdaftar).
    """
    if is_owner(telegram_user_id, owner_ids):
        return USER_STATUS["ACTIVE"]
    user = get_user_by_telegram_id(telegram_user_id, conn)
    return user["status"] if user else USER_STATUS["NEW"]
