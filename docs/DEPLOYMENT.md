# DEPLOYMENT — FormPelatihan-QM

## 1. Ringkasan

Aplikasi terdiri dari dua bagian:

1. **Core (Python)** — reader materi, AI layer, document engine, workflow, validasi.
2. **Runtime eksternal** — LibreOffice headless (DOCX→PDF) dan Poppler (render/inspeksi PDF).

Linux adalah **reference environment**. Termux didukung untuk core, dengan satu
batasan penting pada konversi PDF (lihat §4).

---

## 2. Linux (reference)

### 2.1 Dependensi sistem

```bash
# Arch / CachyOS
sudo pacman -S python python-pip libreoffice-fresh poppler

# Debian / Ubuntu
sudo apt install python3 python3-venv libreoffice poppler-utils
```

### 2.2 Setup Python

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

### 2.3 Konfigurasi

```bash
cp .env.example .env
# isi AI_PROVIDER + API key + TELEGRAM_BOT_TOKEN
```

### 2.4 Menjalankan

```bash
.venv/bin/python main.py --check     # laporan environment
.venv/bin/python main.py             # jalankan bot Telegram
```

---

## 3. Konversi PDF

DOCX → PDF memakai LibreOffice headless (`soffice`), dijalankan melalui
`qm_training.core.libreoffice`:

```bash
soffice --headless --convert-to pdf --outdir <dir> <file.docx>
```

Jika LibreOffice dipasang sebagai **flatpak**, adapter memakai:

```bash
flatpak run --command=libreoffice --filesystem=home \
  org.libreoffice.LibreOffice --headless --convert-to pdf --outdir <dir> <file>
```

Catatan penting: flatpak tidak dapat mengakses `/tmp` host, sehingga direktori
kerja konversi harus berada di dalam `$HOME` (default: `output/material_tmp`,
profil: `~/.cache/qm-template-lab-lo`).

---

## 4. Termux (Android) — PENDING_TERMUX_VERIFICATION

**Status: PENDING_TERMUX_VERIFICATION** — belum diverifikasi pada perangkat
Android nyata.

### 4.1 Yang dapat berjalan native di Termux

- Python dan seluruh core: reader materi (PDF/DOCX/PPTX/XLSX + legacy via
  konversi), AI layer (HTTP), workflow, document engine (python-docx), dan
  validasi DOCX.
- `poppler` (pdftoppm/pdftotext/pdfinfo) tersedia via paket Termux.
- Mengirim DOCX sudah dapat dilakukan native.

### 4.2 Yang TIDAK tersedia native

- **LibreOffice tidak tersedia native di Termux.** Karena itu konversi
  **DOCX → PDF tidak dapat dijalankan native** dengan pipeline saat ini.

### 4.3 Solusi realistis (pilih salah satu)

1. **Konversi di host/server Linux** (paling andal): bot Termux mengirim DOCX
   ke host yang menjalankan LibreOffice, host mengembalikan PDF. Tidak ada
   perubahan requirement; hanya lokasi konversi.
2. **proot-distro Debian** di dalam Termux, lalu `apt install libreoffice`.
   Berat, lambat, dan belum diuji — bukan rekomendasi utama.

### 4.4 Perintah setup di Termux

```bash
pkg update && pkg upgrade
pkg install python libxml2 libxslt libjpeg-turbo poppler git
python -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

cp .env.example .env
# isi API key; TELEGRAM_BOT_TOKEN
.venv/bin/python main.py --check
```

`main.py --check` akan melaporkan `libreoffice: null` pada Termux — sesuai
ekspektasi. Bagian yang bergantung konversi PDF harus diarahkan ke host
(§4.3). **Jangan mengklaim Termux berhasil sebelum diuji di perangkat nyata.**

---

## 5. Keamanan

- API key/token hanya dari environment variable / `.env`.
- `.env` tidak di-commit (lihat `.gitignore`).
- Credential tidak pernah ditampilkan pada log/laporan.
- File sesi terisolasi per user di `storage/sessions/<user_id>/`.
- Validasi tipe/ukuran file upload (maksimum default 25 MB).

---

## 6. Quality Gate / Regression

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/check_environment.py
```

Test yang membutuhkan credential asli ditandai `PENDING_EXTERNAL_CREDENTIAL`
dan menggunakan mock provider/adapter.
