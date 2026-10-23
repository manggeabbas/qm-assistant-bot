# QM Assistant Bot

Satu bot Telegram, satu token, tiga layanan QM untuk divisi CRP-YWI:

- 📝 **Form Gulungan** — wizard pembuatan data gulungan (coil): deteksi
  material otomatis, penomoran HAxx, aturan diameter mesin FT/FJ, output
  teks Mandarin. Akses: token undangan + NIK.
- 📚 **Form Pelatihan** — generate dokumen pelatihan/briefing QM dari materi
  yang diunggah + master template DOCX (tepat 5 pertanyaan + kunci jawaban),
  output `.docx` dan `.pdf`. Akses: ID Telegram terdaftar.
- 🔍 **Bantuan QC** — kamus standar cacat (182 kode), panduan kerja, SOP,
  latihan kilat, analisis foto. Akses: ID Telegram terdaftar.

Perintah `/start` membuka **menu tree**:

```text
🤖 QM-YWI Assistant
├─ 🔍 Inspeksi Lapangan
│  ├─ 🏷 Kode Cacat (per bagian: Bahan Baku / Jalur Utama / Luar Jalur)
│  ├─ 📘 Panduan Kerja
│  ├─ 🏭 Inspeksi Jalur Utama (Form Generator + SOP)
│  └─ 🔧 Inspeksi Luar Jalur (SOP FT, SOP FJ, Form Generator FT/FJ)
├─ 🔬 Inspeksi Laboratorium (Lab Mekanik/Fisika, Lab Kimia — dokumen menyusul)
├─ 📚 Form Pelatihan
└─ ❓ Bantuan
```

Tombol **🏠 Menu Utama** selalu tersedia untuk kembali ke menu awal.

## Fitur sorotan

- **Keyword langsung dari layar utama** — ketik kode cacat (`B22`), kata
  kunci (`korosi`, `bagan`), atau nama fitur (`form`, `foto`, `kuis`,
  `panduan`, `sop`, `pelatihan`) tanpa masuk menu dulu. Satu hasil langsung
  dibuka; banyak hasil dikelompokkan (Fitur / Cacat / Panduan / Prosedur).
- **❓ Menu Bantuan** — tombol di menu utama + perintah `/help` &
  `/bantuan` dari mode apa pun; penjelasan cara pakai per layanan +
  daftar keyword & pintasan.
- **Kartu cacat scannable** — kualitas di depan, kriteria per tingkat
  (🟢 L / 🟡 M / 🟠 H / 🔴 S) di dalam box, penanganan, teks Mandarin asli
  + **pinyin** (mis. `划伤 (huà shāng)`). Entri tanpa kriteria menjawab
  "database belum ada" (tidak mengarang).
- **Panduan Kerja (19 topik, data-driven di `qm_bantuan/data/panduan.json`)**:
  4 umum (Kriteria Kualitas, Prinsip Penilaian, Cacat Batch, Kode
  Pencatatan), 5 SOP Mesin FT, 7 Langkah Kerja FT dari tabel Pasal 5 SOP
  TTRI-QM-ZY-34-2025 lengkap dengan foto visualisasi, 3 SOP Jalur Utama
  (Alur Kerja, Tanggung Jawab Inspektur, Bagan Proses Lampiran B).
- **🎯 Latihan kilat** — kuis 5 soal per sesi (tingkat → kualitas).
- **📸 Analisis foto** — kirim foto cacat, AI (Gemini) memberi maks. 3
  kandidat + tingkat keyakinan + checklist ukur; ini pendapat kedua,
  bukan vonis. Bot tidak menebak ukuran milimeter dari foto.
- **Akses terkunci** — Form Pelatihan & Bantuan QC hanya untuk ID Telegram
  terdaftar + owner (diatur lewat menu 👤 User Bot di `/admin`); Form
  Gulungan tetap token undangan + NIK (direktori karyawan).

Panduan lengkap pemakaian: [`docs/PANDUAN_PENGGUNAAN.md`](docs/PANDUAN_PENGGUNAAN.md).

## Keputusan arsitektur

**Opsi A** — bot gulungan (Node.js + grammy) di-port ke Python, bukan
sebaliknya: engine DOCX Python terlalu berisiko jika di-port ke Node.
Hasil akhir: 1 proses Python, 1 token Telegram. Port selesai 100% (18
modul + wiring end-to-end + admin + direktori karyawan).

## Struktur repo

```text
main.py              # entrypoint: bangun workflow -> bungkus AssistantRouter
qm_training/         # Form Pelatihan (dari formpelatihanQM, TIDAK diubah
                     # kecuali untuk kebutuhan Form Pelatihan sendiri)
qm_coil/             # Form Gulungan (port lengkap dari src/*.js asli)
qm_bantuan/          # Bantuan QC (atlas, panduan, kartu, kuis, analisis foto)
  data/              # atlas.json (182 entri), panduan.json (19 topik), gambar
qm_assistant/        # router tree menu + sesi mode per user + admin panel
tests/               # 556 test (unittest)
templates/           # master template DOCX Form Pelatihan
template_lab/        # Template Laboratory (Form Pelatihan)
docs/                # PANDUAN_PENGGUNAAN.md, DEPLOYMENT.md
systemd/             # template unit service qm-assistant-bot
```

### Mapping port `qm_coil/` ← `qm-ywi-telegram-bot/src/` (semua ported)

| Python (baru)      | JS (asli)         | Status |
|--------------------|-------------------|--------|
| `wizard.py`        | `wizard.js`       | ✅ ported |
| `material.py`      | `material.js`     | ✅ ported |
| `numbering.py`     | `numbering.js`    | ✅ ported |
| `diameter.py`      | `diameter.js`     | ✅ ported |
| `form.py`          | `form.js`         | ✅ ported |
| `validation.py`    | `validation.js`   | ✅ ported |
| `state.py`         | `state.js`        | ✅ ported |
| `registration.py`  | `registration.js` | ✅ ported |
| `invites.py`       | `invites.js`      | ✅ ported |
| `users.py`         | `users.js`        | ✅ ported |
| `employees.py`     | `employees.js`    | ✅ ported |
| `access.py`        | `access.js`       | ✅ ported |
| `db.py`            | `db.js`           | ✅ ported |
| `menu.py`          | `menu.js`         | ✅ ported |
| `texts.py`         | `texts.js`        | ✅ ported |
| `admin.py`         | `admin.js`        | ✅ ported |
| `config.py`        | `config.js`       | ✅ ported |
| `logger.py`        | `logger.js`       | ✅ ported |

## Cara jalan

**Otomatis (disarankan):**

```bash
bash deploy/setup.sh   # venv + dependensi + .env + cek environment
```

**Manual:**

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # isi TELEGRAM_BOT_TOKEN + GEMINI_API_KEY + OWNER_TELEGRAM_ID
python main.py --check # cek environment
python main.py         # jalankan bot
```

**Service (produksi):** unit systemd `qm-assistant-bot` (template di
`systemd/`), `systemctl enable --now qm-assistant-bot`. Detail instalasi:
[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

Test:

```bash
.venv/bin/python -m unittest discover -s tests -q   # 556 test
```

## Catatan

- `.env` tidak boleh di-commit (sudah di `.gitignore`). `storage/`
  (database direktori/token/user) bersifat lokal dan tidak di-commit.
- `qm_training/` mengikuti aturan `AGENTS.md` (fase Template Laboratory →
  Document Generator → dst, jangan merusak master template).
- Standar cacat & panduan bersifat data: ganti `qm_bantuan/data/*.json`
  lalu restart bot, tanpa ubah kode (lihat `qm_bantuan/data/README.md`).
