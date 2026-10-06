"""Shared dataset builders for tests (no AI, no Telegram)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from qm_training.document.schema import QAPair, TrainingData

PHOTO_SPECS = [(1600, 1200), (1200, 1600), (2000, 1000), (1000, 1500), (1400, 1400), (1800, 1200), (1200, 1800)]

SHORT_QUESTIONS = [
    QAPair(
        "Apa tujuan utama briefing keselamatan kerja di area laboratorium?",
        "Mencegah kecelakaan kerja dan memastikan personil memahami prosedur kerja aman.",
    ),
    QAPair(
        "Sebutkan alat pelindung diri yang wajib digunakan di laboratorium.",
        "Jas laboratorium, sarung tangan, kacamata pelindung, dan sepatu tertutup.",
    ),
    QAPair(
        "Apa yang dilakukan bila menemukan bahan kimia tanpa label?",
        "Pisahkan dan laporkan ke penanggung jawab laboratorium untuk diidentifikasi.",
    ),
    QAPair(
        "Mengapa peralatan harus diperiksa sebelum digunakan?",
        "Agar peralatan berfungsi benar dan mencegah kerusakan serta cedera.",
    ),
    QAPair(
        "Apa tindakan saat terjadi tumpahan bahan kimia?",
        "Amankan area, gunakan spill kit sesuai prosedur, lalu laporkan kejadian.",
    ),
]


def long_questions() -> list[QAPair]:
    return [
        QAPair(
            q.question + " Jelaskan secara rinci langkah demi langkah beserta alasan teknis dan dampaknya "
            "terhadap keselamatan personil di area kerja sesuai isi materi pelatihan.",
            q.answer + " Uraian harus mencakup seluruh langkah pada materi, termasuk urutan, alat yang "
            "digunakan, serta tindakan pencegahan yang dianjurkan.",
        )
        for q in SHORT_QUESTIONS
    ]


def make_photos(count: int, out_dir: Path, prefix: str = "photo") -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for index in range(count):
        width, height = PHOTO_SPECS[index % len(PHOTO_SPECS)]
        image = Image.new("RGB", (width, height), (40 + (index * 35) % 180, 95, 165 - (index * 20) % 120))
        draw = ImageDraw.Draw(image)
        draw.rectangle([8, 8, width - 8, height - 8], outline=(255, 255, 255), width=6)
        draw.text((30, 30), f"FOTO {index + 1}\n{width}x{height}", fill=(255, 255, 255))
        path = out_dir / f"{prefix}_{index + 1}.png"
        image.save(path)
        paths.append(path)
    return paths


def dataset(
    personnel_count: int | None = 15,
    photo_count: int = 0,
    *,
    photo_dir: Path,
    use_long_questions: bool = False,
    theme: str = "Keselamatan Kerja di Area Laboratorium Quality Management",
    archive_number: str = "2026-QM-LZ-09-03",
    shift_group: str = "REGU A",
) -> TrainingData:
    return TrainingData(
        theme=theme,
        archive_number=archive_number,
        training_date="03 September 2026",
        location="Ruang Training Quality Management",
        trainer="Budi Santoso",
        shift_group=shift_group,
        personnel_count=personnel_count,
        questions=long_questions() if use_long_questions else list(SHORT_QUESTIONS),
        photos=make_photos(photo_count, photo_dir),
    )
