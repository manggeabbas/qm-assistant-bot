# QM Assistant Bot

Satu bot Telegram, satu token, dua layanan QM:

- 📋 **Form Gulungan** — wizard pembuatan data gulungan (coil): deteksi
  material otomatis, penomoran HAxx, aturan diameter mesin FT/FJ, output
  teks Mandarin. *(hasil port dari
  [qm-ywi-telegram-bot](https://github.com/manggeabbas/qm-ywi-telegram-bot)
  — saat ini skeleton, dalam tahap porting)*
- 📚 **Form Pelatihan** — generate dokumen pelatihan/briefing QM dari materi
  yang diunggah + master template DOCX (5 pertanyaan + kunci jawaban),
  output `.docx` dan `.pdf`. *(penuh, dari
  [formpelatihanQM](https://github.com/manggeabbas/formpelatihanQM))*

Perintah `/start` menjadi **menu router**: pilih layanan, bot mendelegasikan
ke alur yang sesuai. Satu user management untuk kedua layanan.

## Keputusan arsitektur

**Opsi A** — bot gulungan (Node.js + grammy) di-port ke Python, bukan
sebaliknya: engine DOCX Python terlalu berisiko jika di-port ke Node.
Hasil akhir: 1 proses Python, 1 token Telegram.

## Struktur repo

```
main.py              # entrypoint: bangun workflow -> bungkus AssistantRouter
qm_training/         # Form Pelatihan (copy dari formpelatihanQM, TIDAK diubah)
qm_coil/             # Form Gulungan (port bertahap dari src/*.js asli)
qm_assistant/        # router /start + sesi mode per user (menu/training/coil)
tests/
  test_router.py     # test router (baru)
  test_*.py          # test bawaan qm_training (238, tetap jalan)
templates/           # master template DOCX Form Pelatihan
template_lab/        # Template Laboratory (Form Pelatihan)
```

### Mapping port `qm_coil/` ← `qm-ywi-telegram-bot/src/`

| Python (baru)      | JS (asli)         | Status |
|--------------------|-------------------|--------|
| `wizard.py`        | `wizard.js`       | ✅ ported |
| `material.py`      | `material.js`     | ✅ ported |
| `numbering.py`     | `numbering.js`    | ✅ ported |
| `diameter.py`      | `diameter.js`     | ✅ ported |
| `form.py`          | `form.js`         | ✅ ported |
| `validation.py`    | `validation.js`   | ✅ ported |
| `state.py`         | `state.js`        | ✅ ported |
| `registration.py`  | `registration.js` | ✅ ported   |
| `invites.py`       | `invites.js`      | ✅ ported   |
| `users.py`         | `users.js`       | ✅ ported   |
| `employees.py`     | `employees.js`    | ✅ ported   |
| `access.py`        | `access.js`       | ✅ ported   |
| `db.py`            | `db.js`           | ✅ ported   |
| `menu.py`          | `menu.js`         | ✅ ported   |
| `texts.py`         | `texts.js`        | ✅ ported   |
| `admin.py`         | `admin.js`        | ✅ ported |
| `config.py`        | `config.js`       | ✅ ported   |
| `logger.py`        | `logger.js`       | ✅ ported   |

Urutan port yang disarankan (tanpa state dulu): `material` → `numbering`
→ `diameter` → `form` → `validation` → `state` → `registration`/`invites`/
`users`/`employees`/`access` → `db` → `menu`/`texts` → `wizard` → `admin`.

## Cara jalan

**Otomatis (disarankan):**

```bash
bash deploy/setup.sh   # venv + dependensi + .env + cek environment
```

**Manual:**

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # isi TELEGRAM_BOT_TOKEN + ALLOWED_TELEGRAM_USER_IDS
python main.py --check # cek environment
python main.py         # jalankan bot
```

Test:

```bash
python -m pytest tests/ -x -q
```

## Catatan

- `.env` tidak boleh di-commit (sudah di `.gitignore`).
- `qm_training/` mengikuti aturan `AGENTS.md` (fase Template Laboratory →
  Document Generator → dst, jangan merusak master template).
- Aturan main repo `~/AGENTS.md` (milik Ember) juga berlaku untuk workflow kerja.
