"""AI prompts. The AI produces content only; layout is never mentioned."""

from __future__ import annotations

from qm_training.ai.schema import MAX_ANSWER_CHARS, MAX_QUESTION_CHARS

SYSTEM_PROMPT = (
    "Anda asisten pelatihan Quality Management. Jawab HANYA dengan JSON valid, "
    "tanpa penjelasan tambahan dan tanpa markdown. Jawaban harus ringkas."
)

THEME_INSTRUCTION = (
    "Tentukan satu tema pelatihan singkat dari materi berikut. "
    'Balas dengan JSON: {"theme": "<tema>"}.'
)

QUESTIONS_INSTRUCTION = (
    "Buat tepat 5 pertanyaan terbuka sederhana yang jawabannya tersedia di materi. "
    "Pertanyaan harus jelas, tidak duplikatif, dan tidak membutuhkan pengetahuan di luar materi. "
    "PENTING: buat pertanyaan SANGAT SINGKAT agar formulir tetap muat SATU halaman. "
    f"Setiap pertanyaan maksimal {MAX_QUESTION_CHARS} karakter (satu kalimat, idealnya <= 12 kata). "
    "Untuk KUNCI JAWABAN: buat 1-3 kalimat yang informatif dan langsung menjawab pertanyaan, "
    "menjelaskan inti jawaban, dan HANYA berdasarkan materi yang diberikan "
    "(jangan menambah asumsi, prosedur tambahan, atau fakta yang tidak disebutkan). "
    f"Setiap jawaban maksimal {MAX_ANSWER_CHARS} karakter. "
    'Balas dengan JSON: {"questions": [{"question": "...", "answer": "..."}]} dengan tepat 5 item.'
)

ANSWER_INSTRUCTION = (
    "Buat kunci jawaban yang informatif (1-3 kalimat) dan benar untuk pertanyaan berikut, "
    "berdasarkan materi. Jawaban harus langsung menjawab pertanyaan dan menjelaskan inti jawaban. "
    "JANGAN mengarang: jangan menambah asumsi, prosedur tambahan, atau fakta yang tidak ada di materi. "
    "Jika materi hanya memberi sedikit informasi, jawaban boleh lebih singkat. "
    f"Maksimal {MAX_ANSWER_CHARS} karakter. "
    'Balas dengan JSON: {"answer": "..."}.'
)


def theme_prompt(material_text: str, max_chars: int = 12000) -> str:
    return f"{THEME_INSTRUCTION}\n\nMATERI:\n{material_text[:max_chars]}"


def questions_prompt(material_text: str, theme: str, max_chars: int = 12000) -> str:
    return (
        f"{QUESTIONS_INSTRUCTION}\n\nTEMA: {theme}\n\nMATERI:\n{material_text[:max_chars]}"
    )


def answer_prompt(material_text: str, question: str, max_chars: int = 12000) -> str:
    return f"{ANSWER_INSTRUCTION}\n\nPERTANYAAN: {question}\n\nMATERI:\n{material_text[:max_chars]}"


def repair_note(error: str) -> str:
    return (
        "\n\nRespons sebelumnya TIDAK VALID. "
        f"Alasan: {error}. "
        "Kirim ulang HANYA JSON valid sesuai skema yang diminta."
    )
