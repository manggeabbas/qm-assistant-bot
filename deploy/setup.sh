#!/usr/bin/env bash
# Setup sekali jalan untuk QM Assistant Bot.
#
#   bash deploy/setup.sh
#
# Yang dilakukan:
#   0. pre-flight check: python3 ada & versi >= 3.10
#   1. buat virtualenv .venv (fallback: pip --break-system-packages bila
#      python3-venv tidak tersedia)
#   2. install dependensi dari requirements.txt (retry 3x bila gagal,
#      biasanya karena jaringan)
#   3. buat .env dari .env.example bila belum ada (chmod 600)
#   4. siapkan direktori runtime + jalankan `main.py --check`
#
# Idempoten: aman dijalankan ulang kapan saja.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

echo "== 0/4: pre-flight check =="
if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 tidak ditemukan."
  echo "Debian/Ubuntu: apt install python3"
  exit 1
fi
PYVER_NUM=$(python3 -c 'import sys; print(sys.version_info.major * 100 + sys.version_info.minor)')
if [ "$PYVER_NUM" -lt 310 ]; then
  echo "ERROR: butuh Python >= 3.10 (terdeteksi: $(python3 --version 2>&1))."
  exit 1
fi
echo "python3 OK ($(python3 --version 2>&1))."

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
attempt=1
max_attempts=3
while true; do
  if "${PIP[@]}" -r requirements.txt; then
    break
  fi
  if [ "$attempt" -ge "$max_attempts" ]; then
    echo ""
    echo "ERROR: install dependensi gagal setelah ${max_attempts}x percobaan."
    echo "Kemungkinan penyebab: jaringan terputus / PyPI tidak terjangkau."
    echo "Coba lagi nanti:  bash deploy/setup.sh"
    echo "Atau manual:      ${PIP[*]} -r requirements.txt"
    exit 1
  fi
  echo "Percobaan $attempt/$max_attempts gagal, coba lagi dalam 5 detik..."
  sleep 5
  attempt=$((attempt + 1))
done

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
