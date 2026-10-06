"""Wizard Form Gulungan — STUB.

Port dari: ``src/wizard.js`` (678 baris, modul terbesar).
Tanggung jawab asli: memandu inspector/operator membuat data gulungan
baru secara bertahap (state machine multi-langkah).

TODO port:
  - state machine langkah wizard (lihat src/state.js)
  - validasi tiap langkah (lihat src/validation.js)
  - preview & edit sebelum simpan
  - render output teks Mandarin (lihat form.py)
"""

from __future__ import annotations

from qm_training.bot.adapters.base import IncomingMessage, OutgoingMessage


class CoilWizard:
    """Antarmuka sama seperti Workflow: handle(IncomingMessage)."""

    def handle(self, message: IncomingMessage) -> list[OutgoingMessage]:
        return [
            OutgoingMessage(
                "🛠️ *Form Gulungan* sedang dalam tahap porting ke Python.\n\n"
                "Saat ini baru tersedia:\n"
                "• 📚 Form Pelatihan (penuh, dari bot lama)\n\n"
                "Pilih tombol di bawah untuk pindah layanan, atau kirim /menu."
            )
        ]
