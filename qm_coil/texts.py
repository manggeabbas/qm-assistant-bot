"""Kumpulan teks pesan access control & registrasi QM-YWI.

Port dari: ``src/texts.js`` (67 baris, qm-ywi-telegram-bot).
Status: PORTED.
"""

from __future__ import annotations


class Texts:
    INVITE_PROMPT: str = """🔐 Akses Terbatas

Bot QM-YWI hanya dapat digunakan oleh pengguna yang memiliki token undangan.

Silakan masukkan token undangan Anda."""

    TOKEN_INVALID: str = """❌ Token tidak valid atau sudah tidak dapat digunakan.

Silakan periksa kembali token Anda atau hubungi administrator."""

    TOKEN_VALID: str = """✅ Token valid.

Sebelum menggunakan bot, silakan lengkapi data diri Anda."""

    REG_PROMPT_NIK: str = """📝 REGISTRASI PENGGUNA

Silakan masukkan NIK (Nomor Induk Karyawan) Anda."""

    REG_CONTINUE_NIK: str = """Registrasi Anda belum selesai.

Silakan masukkan NIK (Nomor Induk Karyawan) Anda."""

    NIK_NOT_REGISTERED: str = """❌ NIK tidak terdaftar pada data karyawan.

Silakan periksa kembali NIK Anda atau hubungi administrator."""

    NIK_INVALID: str = """❌ Format NIK tidak valid.

NIK harus terdiri dari 8 digit angka.
Silakan masukkan kembali."""

    NIK_TAKEN: str = """❌ NIK tersebut sudah terdaftar pada akun lain.

Silakan hubungi administrator."""

    BLOCKED: str = """🚫 Akses Ditolak

Akun Anda tidak memiliki akses ke bot ini.

Silakan hubungi administrator."""

    ADMIN_DENIED: str = "🚫 Anda tidak memiliki akses administrator."

    RESTRICTED_REGISTRATION: str = (
        "Anda harus menyelesaikan registrasi terlebih dahulu "
        "sebelum menggunakan fitur bot."
    )

    @staticmethod
    def register_success(name: str, nik: str) -> str:
        return f"""✅ Registrasi berhasil.

Selamat datang di QM-YWI Telegram Bot.

NAMA : {name}
NIK  : {nik}

Akun Anda sekarang aktif."""

    @staticmethod
    def reg_confirm(name: str, nik: str) -> str:
        return f"""📋 KONFIRMASI DATA

NAMA : {name}
NIK  : {nik}

Apakah data sudah benar?"""


TEXTS = Texts()
