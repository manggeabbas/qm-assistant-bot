# DEPLOYMENT — Windows 11

Panduan instalasi bot QM Assistant (@qmywibot: Form Gulungan + Form
Pelatihan + Bantuan QC) di Windows 11.

**Status: BELUM DIVERIFIKASI pada mesin Windows 11 nyata.** Panduan ini
ditulis dari analisis kode (bukan dari uji jalan di Windows). Jangan
mengklaim instalasi Windows berhasil sebelum diuji di perangkat nyata.

Linux tetap menjadi **reference environment** (lihat
[`DEPLOYMENT.md`](DEPLOYMENT.md)). Bagian ini hanya menjelaskan delta
khusus Windows.

---

## 1. Yang sama dengan Linux

Bot ini murni Python: Telegram polling via `requests`, SQLite, dan
`python-docx` untuk dokumen. Tidak ada dependensi pada systemd atau
proxy khusus — dua hal berikut **tidak perlu** dibawa dari instalasi VM:

- `systemd/proxy.env` (proxy egress `hatch-egress-proxy`) — itu khusus
  VM Ember. Di Windows, koneksi ke `api.telegram.org` langsung, tanpa
  proxy.
- `watchdog.sh` / cron watchdog — itu bash + systemd. Di Windows,
  autostart diganti Task Scheduler (§6).

## 2. Prasyarat

| Kebutuhan | Instalasi di Windows |
|---|---|
| Python 3.12+ | Dari [python.org](https://www.python.org/downloads/), centang **Add python.exe to PATH** saat instalasi |
| Git | [Git for Windows](https://git-scm.com/download/win) |
| LibreOffice | [LibreOffice untuk Windows](https://www.libreoffice.org/download/download-libreoffice/) — untuk konversi DOCX → PDF |
| Poppler | [Poppler for Windows](https://github.com/oschwartz10612/poppler-windows/releases/) (file `Release-*.zip`) — untuk `pdfinfo`/`pdftoppm` pada validasi PDF |

## 3. Tambahkan LibreOffice & Poppler ke PATH

Kode mencari `soffice` dan `pdfinfo` lewat `PATH`
(`qm_training/core/libreoffice.py`, `qm_training/document/render.py`).
Secara default keduanya tidak ada di PATH Windows:

1. LibreOffice: tambahkan `C:\Program Files\LibreOffice\program`
   ke PATH (sesuaikan jika instalasi di lokasi lain).
2. Poppler: ekstrak zip-nya (mis. ke `C:\poppler`), lalu tambahkan
   `C:\poppler\Library\bin` ke PATH.

Verifikasi di PowerShell:

```powershell
soffice --version
pdfinfo -v
```

Keduanya harus menampilkan versi, bukan "not recognized".

## 4. Tambalan kode yang WAJIB diterapkan sebelum jalan pertama

### 4.1 Kunci single-instance (`fcntl` tidak ada di Windows)

`qm_training/core/singleton.py` memakai `fcntl.flock`, modul yang hanya
ada di Unix. Tanpa tambalan, bot gagal start di Windows dengan
`ModuleNotFoundError: No module named 'fcntl'`.

Ganti isi `acquire()`/`release()` dengan kunci berbasis `msvcrt`
(Windows) dan tetap memakai `fcntl` di platform lain:

```python
import os
import sys
from pathlib import Path

if os.name == "nt":
    import msvcrt
else:
    import fcntl
```

```python
    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(self.path, "w", encoding="utf-8")
        try:
            if os.name == "nt":
                # Kunci 1 byte pertama file; non-blocking.
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            handle.close()
            raise AlreadyRunningError(str(self.path)) from exc
        handle.write(str(os.getpid()))
        handle.flush()
        self._handle = handle

    def release(self) -> None:
        if self._handle is not None:
            try:
                if os.name == "nt":
                    self._handle.seek(0)
                    msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(self._handle, fcntl.LOCK_UN)
            finally:
                self._handle.close()
                self._handle = None
```

Catatan: `sys` sudah diimpor di beberapa modul; sesuaikan impor dengan
file yang ditambal. Tambalan ini belum masuk ke repo — terapkan saat
instalasi Windows dikerjakan, lalu uji `main.py --check` dan start bot.

### 4.2 Direktori profil LibreOffice

`qm_training/core/libreoffice.py` memakai profil di
`~/.cache/qm-template-lab-lo`. Di Windows, `Path.home()` mengarah ke
`C:\Users\<nama>`, sehingga profil menjadi
`C:\Users\<nama>\.cache\qm-template-lab-lo` — tidak perlu diubah.

## 5. Setup Python & konfigurasi

Di PowerShell, dari folder repo:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Jika PowerShell menolak aktivasi (execution policy), jalankan sekali
sebagai Administrator:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Lalu konfigurasi (jangan pernah commit file ini):

```powershell
Copy-Item .env.example .env
notepad .env
```

Isi minimal:

```text
AI_PROVIDER=gemini
GEMINI_API_KEY=<api-key-gemini>
TELEGRAM_BOT_TOKEN=<token-bot>
OWNER_TELEGRAM_ID=<id-telegram-owner>
ALLOWED_TELEGRAM_USER_IDS=<id-yang-diizinkan, pisahkan koma>
```

Periksa environment:

```powershell
python main.py --check
```

Jalankan bot:

```powershell
python main.py
```

## 6. Autostart (pengganti systemd)

Windows tidak punya systemd. Opsi termudah: **Task Scheduler**.

1. Buka Task Scheduler → Create Basic Task.
2. Trigger: **When I log on** (atau **At startup** bila bot harus jalan
   tanpa login — perlu opsi "Run whether user is logged on or not").
3. Action: **Start a program** dengan:
   - Program: `C:\<path-repo>\.venv\Scripts\python.exe`
   - Arguments: `main.py`
   - Start in: `C:\<path-repo>`
4. Centang **Run with highest privileges** hanya bila diperlukan
   (umumnya tidak perlu).

Alternatif: [NSSM](https://nssm.cc/) bila bot harus berjalan sebagai
Windows Service murni.

## 7. Aturan single-instance (PENTING)

Satu token Telegram = satu proses bot yang polling. **Jangan menjalankan
bot Windows bersamaan dengan bot di laptop/server lain yang memakai
token sama** — akibatnya balasan ganda (tema ganda, preview ganda,
error validasi ganda). Sebelum start di Windows, pastikan instance lain
sudah dimatikan.

## 8. Migrasi data dari instalasi lain (opsional)

Bila bot Windows menggantikan instalasi laptop/server:

- Salin folder `storage/` (database karyawan `qm_coil.sqlite`,
  `users.json`, sesi) ke folder repo Windows **sebelum start pertama**,
  agar direktori karyawan dan daftar user tidak mulai dari kosong.
- Lakukan salinan saat kedua instance mati, dan jangan pernah
  menjalankan keduanya bersamaan (§7).

## 9. Batasan yang diketahui

- Panduan ini belum diuji di Windows 11 nyata (§status di atas).
- Tambalan §4.1 belum masuk ke repo dan belum diuji.
- Tidak ada watchdog otomatis seperti di VM; bila proses mati, Task
  Scheduler tidak me-restart otomatis kecuali diatur "restart on
  failure" di pengaturan task (tab Settings → "If the task fails,
  restart every").
- Performa konversi DOCX → PDF via LibreOffice Windows umumnya lebih
  lambat daripada di Linux; amati timeout konversi (default 300 detik
  di `qm_training/core/libreoffice.py`).
