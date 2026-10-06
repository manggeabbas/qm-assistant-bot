"""Dummy data for the Template Laboratory (tanpa AI/Telegram)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from template_lab.generator import QAPair, TrainingData
from template_lab.paths import OUTPUT_DIR

_PHOTO_SPECS = [
    (1600, 1200),
    (1200, 1600),
    (2000, 1000),
    (1000, 1500),
    (1400, 1400),
    (1800, 1200),
    (1200, 1800),
]


def make_dummy_photos(count: int, out_dir: Path) -> list[Path]:
    """Foto dummy buatan sendiri (bukan foto contoh master)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for index in range(count):
        width, height = _PHOTO_SPECS[index % len(_PHOTO_SPECS)]
        image = Image.new("RGB", (width, height), (40 + (index * 35) % 180, 95, 165 - (index * 20) % 120))
        draw = ImageDraw.Draw(image)
        draw.rectangle([8, 8, width - 8, height - 8], outline=(255, 255, 255), width=6)
        draw.text((30, 30), f"FOTO DUMMY {index + 1}\n{width}x{height}", fill=(255, 255, 255))
        path = out_dir / f"dummy_photo_{index + 1}.png"
        image.save(path)
        paths.append(path)
    return paths


_DUMMY_QUESTIONS = [
    QAPair(
        "Apa tujuan utama briefing keselamatan kerja di area laboratorium Quality Management?",
        "Tujuan utamanya adalah mencegah kecelakaan kerja dan memastikan setiap personil memahami prosedur kerja aman.",
    ),
    QAPair(
        "Sebutkan alat pelindung diri yang wajib digunakan saat berada di area laboratorium.",
        "Alat pelindung diri meliputi jas laboratorium, sarung tangan, kacamata pelindung, dan sepatu tertutup.",
    ),
    QAPair(
        "Apa yang harus dilakukan apabila menemukan bahan kimia yang tidak diberi label?",
        "Bahan kimia tanpa label harus segera dipisahkan dan dilaporkan kepada penanggung jawab laboratorium untuk diidentifikasi.",
    ),
    QAPair(
        "Mengapa penting melakukan pengecekan peralatan sebelum digunakan?",
        "Pengecekan memastikan peralatan berfungsi dengan benar sehingga mencegah kerusakan alat dan risiko cedera.",
    ),
    QAPair(
        "Apa tindakan yang dilakukan apabila terjadi tumpahan bahan kimia di lantai?",
        "Segera amankan area, gunakan spill kit sesuai prosedur, lalu laporkan kejadian kepada atasan dan petugas K3.",
    ),
]


def dummy_data(personnel_count: int | None = 15, photo_count: int = 3) -> TrainingData:
    photos = make_dummy_photos(photo_count, OUTPUT_DIR / "dummy_photos") if photo_count else []
    return TrainingData(
        theme="Keselamatan Kerja di Area Laboratorium Quality Management",
        archive_number="2026-QM-LZ-09-03",
        training_date="03 September 2026",
        location="Ruang Training Quality Management",
        trainer="Budi Santoso",
        shift_group="REGU A",
        personnel_count=personnel_count,
        questions=list(_DUMMY_QUESTIONS),
        photos=photos,
    )
