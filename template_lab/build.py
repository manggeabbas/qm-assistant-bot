"""End-to-end Template Laboratory build: DOCX -> PDF -> PNG.

Contoh:
    .venv/bin/python -m template_lab.build
    .venv/bin/python -m template_lab.build --personnel skip --photos 0
"""

from __future__ import annotations

import argparse
from pathlib import Path

from template_lab import dummy_data
from template_lab.convert_pdf import convert_to_pdf, find_soffice
from template_lab.generator import generate
from template_lab.paths import OUTPUT_DIR
from template_lab.render_pages import pdf_page_count, render_pdf_to_png


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate DOCX/PDF/PNG uji (data dummy).")
    parser.add_argument("--personnel", default="15", help="angka jumlah personil, atau 'skip'")
    parser.add_argument("--photos", type=int, default=3, help="jumlah foto dummy")
    parser.add_argument("--out-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--no-pdf", action="store_true", help="hanya DOCX")
    args = parser.parse_args()

    personnel = None if args.personnel.lower() == "skip" else int(args.personnel)
    data = dummy_data.dummy_data(personnel_count=personnel, photo_count=args.photos)

    docx_path = generate(data, out_dir=args.out_dir)
    print(f"DOCX : {docx_path}")

    if args.no_pdf:
        return 0
    if find_soffice() is None:
        print("PDF  : dilewati (LibreOffice tidak tersedia)")
        return 0

    pdf_path = convert_to_pdf(docx_path, args.out_dir)
    print(f"PDF  : {pdf_path} | pages: {pdf_page_count(pdf_path)}")
    pngs = render_pdf_to_png(pdf_path, args.out_dir / "png")
    print(f"PNG  : {len(pngs)} file -> {pngs[0].parent if pngs else '-'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
