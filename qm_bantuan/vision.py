"""Analisis foto cacat permukaan coil via Gemini multimodal.

Subclass dari :class:`qm_training.ai.providers.GeminiProvider` — tidak mengubah
``qm_training/`` ataupun ``qm_coil/`` sama sekali; transport HTTP dan redaksi
API key diwarisi dari implementasi di sana.
"""

from __future__ import annotations

import base64

from qm_training.ai.providers import GeminiProvider
from qm_training.core.errors import AIProviderError

# Tipe gambar yang diterima dari Telegram/bot.
ALLOWED_IMAGE_MIME_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})

# Batas ukuran foto agar payload tidak membengkak (Telegram mengirim foto terkompresi).
MAX_IMAGE_BYTES = 15 * 1024 * 1024

# System prompt: aturan main analisis foto untuk inspector QC.
PHOTO_SYSTEM = """\
Kamu adalah asisten QC untuk inspeksi permukaan coil stainless steel di PT TTRI, lini CRP-YWI.
Jawabanmu dalam Bahasa Indonesia, ringkas, berbentuk poin-poin (bukan karangan panjang).

ATURAN WAJIB:
1. Kamu TIDAK BISA mengukur milimeter dari foto. Jangan pernah menebak angka ukuran
   (lebar, panjang, diameter, kedalaman) dari foto. Satu-satunya pengecualian: bila di foto
   tampak jelas benda pembanding seperti koin atau penggaris, kamu boleh memberi PERKIRAAN
   ukuran relatif terhadap benda itu — dan tandai dengan jelas bahwa itu perkiraan.
2. Berikan MAKSIMAL 3 kandidat kode cacat yang paling cocok, masing-masing dengan tingkat
   kepercayaan: Tinggi, Sedang, atau Rendah, disertai alasan visual yang singkat.
3. Sebutkan ciri visual yang benar-benar terlihat di foto: warna, pola, bentuk, lokasi
   cacat. Tekstur/handfeel (halus/kasar, cekung/cembung) tidak bisa dinilai dari foto —
   katakan itu secara eksplisit bila relevan.
4. Sebutkan apa yang HARUS dicek atau diukur teknisi di lini untuk memastikan kesimpulan,
   misalnya: ukur dengan kaliper/penggaris, cek sisi balik coil, amati dengan cahaya miring,
   uji amplas bila disyaratkan.

Akhiri jawaban dengan disclaimer ini, tanpa diubah artinya:
"Catatan: ini opini kedua berbasis foto. Keputusan akhir tetap di tangan inspector manusia di lini."
"""

# Prompt user default bila pemanggil tidak memberi prompt sendiri.
PHOTO_PROMPT = (
    "Analisis foto cacat permukaan coil stainless berikut sesuai aturan yang diberikan. "
    "Berikan kandidat kode cacat (maksimal 3) beserta tingkat kepercayaannya."
)


class GeminiVision(GeminiProvider):
    """Gemini dengan dukungan gambar untuk analisis cacat permukaan coil."""

    def analyze_image(
        self,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        prompt: str | None = None,
    ) -> str:
        """Kirim satu foto ke Gemini, kembalikan analisis teks."""
        if not image_bytes:
            raise ValueError("image_bytes kosong: tidak ada foto untuk dianalisis")
        if len(image_bytes) > MAX_IMAGE_BYTES:
            raise ValueError(
                f"ukuran foto {len(image_bytes)} byte melebihi batas {MAX_IMAGE_BYTES} byte"
            )
        if mime_type not in ALLOWED_IMAGE_MIME_TYPES:
            raise ValueError(
                f"tipe gambar '{mime_type}' tidak didukung "
                f"(didukung: {', '.join(sorted(ALLOWED_IMAGE_MIME_TYPES))})"
            )

        key = self._require_key()
        url = self.endpoint.format(model=self.model) + f"?key={key}"
        payload = {
            "systemInstruction": {"parts": [{"text": PHOTO_SYSTEM}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt or PHOTO_PROMPT},
                        {
                            "inlineData": {
                                "mimeType": mime_type,
                                "data": base64.b64encode(image_bytes).decode("ascii"),
                            }
                        },
                    ],
                }
            ],
        }
        # _post() sudah meredaksi API key dari pesan error (warisan dari GeminiProvider).
        data = self._post(url, {}, payload)
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderError(f"{self.name}: struktur respons tak terduga") from exc
