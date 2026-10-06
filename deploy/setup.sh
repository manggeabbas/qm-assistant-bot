#!/usr/bin/env bash
# Setup sekali jalan untuk QM Assistant Bot.
#
#   bash deploy/setup.sh
#
# Yang dilakukan:
#   0. pre-flight check: python3 ada & versi >= 3.10; hindari Python Termux
#      (platform android) bila ada Python Debian di /usr/bin/python3, karena
#      Pillow tidak menyediakan wheel untuk Android (pip akan compile dari
#      source dan gagal).
#   1. pakai venv yang sudah aktif bila cocok; pakai ulang .venv bila cocok;
#      bila .venv rusak/berbasis Python Termux -> dibuat ulang otomatis.
#      Fallback: pip --break-system-packages bila python3-venv tidak tersedia.
#   2. install dependensi dari requirements.txt (retry 3x bila gagal,
#      biasanya karena jaringan)
#   3. buat .env dari .env.example bila belum ada (chmod 600)
#   4. siapkan direktori runtime + jalankan `main.py --check`
#
# Idempoten: aman dijalankan ulang kapan saja.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

# -- helper --------------------------------------------------------------- #

# Cetak "android"/"linux"/... atau "broken" bila interpreter tak bisa jalan.
py_platform() {
  "$1" -c 'import sys; print(sys.platform)' 2>/dev/null || echo "broken"
}

# Pilih interpreter: hindari Python Termux (platform android) bila ada
# Python non-android di /usr/bin/python3 (kasus umum: proot Debian di Termux).
pick_python() {
  if [ -x /usr/bin/python3 ] && [ "$(py_platform /usr/bin/python3)" != "android" ]; then
    echo /usr/bin/python3
    return
  fi
  echo python3
}

# -- 0/4: pre-flight ------------------------------------------------------ #

PYBIN="$(pick_python)"

echo "== 0/4: pre-flight check =="
if ! command -v "$PYBIN" >/dev/null 2>&1; then
  echo "ERROR: $PYBIN tidak ditemukan."
  echo "Debian/Ubuntu (di dalam proot): apt install python3 python3-venv"
  exit 1
fi
PYVER_NUM=$("$PYBIN" -c 'import sys; print(sys.version_info.major * 100 + sys.version_info.minor)')
if [ "$PYVER_NUM" -lt 310 ]; then
  echo "ERROR: butuh Python >= 3.10 (terdeteksi: $("$PYBIN" --version 2>&1))."
  exit 1
fi
PLATFORM="$(py_platform "$PYBIN")"
echo "$PYBIN OK ($("$PYBIN" --version 2>&1), platform $PLATFORM)."
if [ "$PLATFORM" = "android" ]; then
  echo "PERINGATAN: ini Python Termux (android). Pillow tidak menyediakan wheel"
  echo "untuk Android sehingga pip akan compile dari source (umumnya gagal)."
  echo "Disarankan di dalam proot Debian: apt install python3 python3-venv"
  echo "lalu jalankan ulang script ini."
fi

# -- 1/4: virtualenv ------------------------------------------------------ #

echo "== 1/4: virtualenv =="
ACTIVE_PLAT="$(py_platform "${VIRTUAL_ENV:-/nonexistent}/bin/python")"
LOCAL_PLAT="$(py_platform .venv/bin/python)"

if [ -n "${VIRTUAL_ENV:-}" ] && [ "$ACTIVE_PLAT" != "android" ] && [ "$ACTIVE_PLAT" != "broken" ]; then
  echo "venv aktif terdeteksi ($VIRTUAL_ENV) — dipakai langsung."
  PY="$VIRTUAL_ENV/bin/python"
  PIP=("$VIRTUAL_ENV/bin/pip" install)
elif [ "$LOCAL_PLAT" != "android" ] && [ "$LOCAL_PLAT" != "broken" ]; then
  echo ".venv sudah ada dan cocok — dipakai ulang."
  PY=.venv/bin/python
  PIP=(.venv/bin/pip install)
else
  if [ -d .venv ]; then
    echo ".venv lama tidak cocok (platform: $LOCAL_PLAT) — dibuat ulang dengan $PYBIN."
    rm -rf .venv
  fi
  if "$PYBIN" -m venv .venv 2>/dev/null; then
    echo ".venv dibuat dengan $PYBIN."
    PY=.venv/bin/python
    PIP=(.venv/bin/pip install)
  else
    echo "PERINGATAN: '$PYBIN -m venv' gagal (paket python3-venv mungkin belum"
    echo "terinstal). Lanjut tanpa venv memakai --break-system-packages."
    echo "Di Debian/Ubuntu: apt install python3-venv"
    PY="$PYBIN"
    PIP=("$PYBIN" -m pip install --break-system-packages)
  fi
fi

# -- 2/4: dependensi ------------------------------------------------------- #

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
    if [ "$(py_platform "$PY")" = "android" ]; then
      echo "Catatan: Python Termux (android) tidak didukung untuk Pillow."
      echo "Di dalam proot Debian: apt install python3 python3-venv,"
      echo "hapus .venv, lalu jalankan ulang script ini."
    fi
    echo "Coba lagi nanti:  bash deploy/setup.sh"
    echo "Atau manual:      ${PIP[*]} -r requirements.txt"
    exit 1
  fi
  echo "Percobaan $attempt/$max_attempts gagal, coba lagi dalam 5 detik..."
  sleep 5
  attempt=$((attempt + 1))
done

# -- 3/4: .env & direktori ------------------------------------------------- #

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

# -- 4/4: cek -------------------------------------------------------------- #

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
