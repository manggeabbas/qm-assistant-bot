#!/usr/bin/env bash
# Setup sekali jalan untuk QM Assistant Bot.
#
#   bash deploy/setup.sh
#
# Yang dilakukan:
#   1. buat virtualenv .venv (fallback: pip --break-system-packages bila
#      python3-venv tidak tersedia)
#   2. install dependensi dari requirements.txt
#   3. buat .env dari .env.example bila belum ada (chmod 600)
#   4. siapkan direktori runtime + jalankan `main.py --check`
#
# Idempoten: aman dijalankan ulang kapan saja.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

echo "== 1/4: virtualenv =="
if [ -d .venv ]; then
  echo ".venv sudah ada, dipakai ulang."
elif python3 -m venv .venv 2>/dev/null; then
  echo ".venv dibuat."
else
  echo "PERINGATAN: 'python3 -m venv' gagal (paket python3-venv mungkin belum"
  echo "terinstal). Lanjut tanpa venv memakai --break-system-packages."
  echo "Di Debian/Ubuntu Anda bisa install dulu: apt install python3-venv"
  NO_VENV=1
fi

if [ "${NO_VENV:-0}" = "1" ]; then
  PY=python3
  PIP=(python3 -m pip install --break-system-packages)
else
  PY=.venv/bin/python
  PIP=(.venv/bin/pip install)
fi

echo "== 2/4: dependensi Python =="
"${PIP[@]}" -r requirements.txt

echo "== 3/4: file .env & direktori runtime =="
if [ -f .env ]; then
  echo ".env sudah ada, tidak diubah."
else
  cp .env.example .env
  chmod 600 .env
  echo ".env dibuat dari .env.example — isi TELEGRAM_BOT_TOKEN dan"
  echo "ALLOWED_TELEGRAM_USER_IDS sebelum menjalankan bot."
fi
mkdir -p output storage/sessions logs

echo "== 4/4: cek environment =="
"$PY" main.py --check || true

echo ""
echo "Selesai."
echo "  Jalankan bot : $PY main.py"
echo "  Cek ulang    : $PY main.py --check"
echo ""
echo "Catatan: konversi DOCX->PDF butuh LibreOffice + poppler"
echo "(Debian/Ubuntu: apt install libreoffice poppler-utils)."
echo "Di Termux, LibreOffice tidak tersedia native — lihat docs/DEPLOYMENT.md."
