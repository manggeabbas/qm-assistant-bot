#!/data/data/com.termux/files/usr/bin/bash
# Termux setup helper for FormPelatihan-QM.
# Konversi PDF TIDAK tersedia native di Termux (lihat docs/DEPLOYMENT.md §4).
set -euo pipefail

pkg update -y && pkg upgrade -y
pkg install -y python libxml2 libxslt libjpeg-turbo poppler git

python -m venv --system-site-packages .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Buat .env dari .env.example lalu isi API key dan token Telegram."
fi

echo "Setup selesai. Verifikasi: .venv/bin/python main.py --check"
echo "CATATAN: LibreOffice tidak tersedia native di Termux (PDF conversion -> host)."
