# Panduan Penggunaan — FormPelatihan-QM

Panduan langkah demi langkah memakai Bot Telegram untuk membuat dokumen
pelatihan/briefing QM dari materi yang Anda unggah.

---

## 1. Ringkasan alur

```
/new_training
   ↓
Upload materi (PDF/DOC/DOCX/PPT/PPTX/XLS/XLSX)
   ↓
Bot menampilkan TEMA (judul Indonesia asli dari dokumen)
   ↓
[✅ Gunakan Tema Ini]  atau  [✏️ Edit Tema]
   ↓
Nomor Arsip → Tanggal → Lokasi → Trainer → Shift/Regu → Jumlah Personil
   ↓
[✅ Konfirmasi] (ringkasan data)
   ↓
Bot menampilkan 5 PERTANYAAN
   ↓
[✏️ Edit Pertanyaan] / [🔄 Generate Ulang] / [✅ Konfirmasi]
   ↓
Upload foto dokumentasi (boleh beberapa) → [✅ Selesai]
   ↓
Bot membuat DOCX + PDF, memvalidasi, lalu mengirim 2 file
```

---

## 2. Persiapan (sekali saja)

1. Siapkan `.env` dari `.env.example`:
   ```bash
   cp .env.example .env
   ```
2. Isi `.env`:
   - `TELEGRAM_BOT_TOKEN` — dari @BotFather
   - `AI_PROVIDER` + API key (mis. `DEEPSEEK_API_KEY`) — jika kosong, bot memakai mock (hasil pertanyaan dummy)
   - `ALLOWED_TELEGRAM_USER_IDS` — **id Telegram Anda** (owner)
3. Jalankan:
   ```bash
   .venv/bin/python main.py --check    # pastikan environment siap
   .venv/bin/python main.py            # jalankan bot
   ```

> Bot **menolak start** bila tidak ada user yang diberi akses. Pastikan
> `ALLOWED_TELEGRAM_USER_IDS` terisi, atau `BOT_OWNER_IDS`, atau sudah ada user
> di `storage/users.json`.

---

## 3. Memulai sesi dokumen

Ketik:

```
/new_training
```

Bot membalas: **"📄 Kirim materi pelatihan."**

---

## 4. Upload materi

Kirim **satu file** materi (PDF/DOC/DOCX/PPT/PPTX/XLS/XLSX).

- Bot membaca materi, lalu menampilkan **Tema** yang diambil dari **judul
  berbahasa Indonesia** di dalam dokumen.
- Jika judul Indonesia tidak ditemukan, bot meminta Anda menuliskan tema
  secara manual (tidak menebak).

```
📚 Tema terdeteksi:

<judul Indonesia>

[✅ Gunakan Tema Ini]   [✏️ Edit Tema]
```

Pilih:
- **✅ Gunakan Tema Ini** → lanjut ke Nomor Arsip.
- **✏️ Edit Tema** → ketik tema baru → lanjut ke Nomor Arsip.

> Bot berhenti menunggu sampai Anda memilih. Mengetik teks biasa tidak akan
> melompat ke Nomor Arsip.

---

## 5. Isi data pelatihan

Bot menanyakan berurutan:

| Pertanyaan | Keterangan |
|---|---|
| Nomor Arsip | wajib |
| Tanggal Pelatihan | tanggal saja (tanpa jam) |
| Lokasi | wajib |
| Trainer | wajib |
| Shift/Regu | mis. `REGU A`, `LABORATORIUM` |
| Jumlah Personil Absen | angka (mis. `15` → `15人`) atau **⏭️ Lewati** (kosong) |

Setelah itu bot menampilkan **📋 KONFIRMASI DATA** dengan tombol
**[✅ Konfirmasi]** dan **[✏️ Edit Data]** (edit per field).

---

## 6. Pertanyaan (QuestionSet)

- Bot membuat **tepat 5 pertanyaan** singkat (≤ 80 karakter) + kunci jawaban
  1–3 kalimat.
- Anda menerima **satu kali** preview:
  ```
  📝 Preview Pertanyaan:
  1. ...
  2. ...
  ...
  ```
- Tombol:
  - **✏️ Edit Pertanyaan** → pilih nomor → kirim pertanyaan baru (kunci jawaban
    ikut disesuaikan).
  - **🔄 Generate Ulang** → membuat 5 pertanyaan baru.
  - **✅ Konfirmasi** → lanjut ke upload foto.

> Satu sesi = satu QuestionSet. Preview dikirim sekali dan dipakai untuk dokumen
> (tidak ada generasi ulang tersembunyi).

---

## 7. Foto dokumentasi

- Kirim foto satu per satu (boleh banyak). Bot menghitung jumlah foto.
- Tekan **✅ Selesai** bila cukup.
- Maksimal **2 foto per halaman**; foto otomatis di-resize agar tidak keluar frame.
- Tidak mengirim foto juga diperbolehkan (dokumen tetap valid).

---

## 8. Hasil

Bot membuat dan memvalidasi dokumen, lalu mengirim:

1. `<NOMOR_ARSIP>_<SHIFT>.docx`
2. `<NOMOR_ARSIP>_<SHIFT>.pdf`

Contoh: `2026-QM-LZ-09-03_REGU-A.docx` dan `.pdf`.

Isi dokumen:
```
T01A (Daftar Hadir) → T02A (Foto) → T03A (Pertanyaan) → KUNCI JAWABAN
```

Jika validasi gagal, bot mengirim **satu** pesan error (dokumen tidak dikirim).

---

## 9. Perintah Telegram

### Untuk semua user
| Perintah | Fungsi |
|---|---|
| `/new_training` (atau `/start`) | mulai sesi baru |
| `/cancel` | batalkan sesi |
| `/whoami` | lihat ID Telegram & role Anda |
| `/help` | bantuan |

### Untuk admin/owner
| Perintah | Fungsi |
|---|---|
| `/users` | daftar user |
| `/allow <id> [admin\|user]` | beri / aktifkan akses user |
| `/deny <id>` | nonaktifkan akses user |

---

## 10. Mengelola akses user lain

1. Minta calon user mengirim pesan ke bot. Bot membalas berisi **ID Telegram**
   mereka.
2. User mengirim ID itu ke Anda.
3. Anda kirim ke bot: `/allow <id>` (mis. `/allow 123456789`).
4. User langsung bisa memakai bot (tanpa restart).
5. Cabut akses dengan `/deny <id>`.

Data user disimpan di `storage/users.json` (lokal).

---

## 11. Indikator "sedang memproses"

- Jika sebuah proses memakan waktu **> 0,5 detik**, bot menampilkan indikator
  agar Anda tahu bot masih bekerja (bukan macet).
- Secara default indikator berupa aksi **"typing"** bawaan Telegram (tanpa file).
- (Opsional) Stiker animasi jam pasir dapat diaktifkan bila Anda punya
  `HOURGLASS_STICKER_FILE_ID` yang valid → set di `.env`.

---

## 12. Troubleshooting

| Gejala | Penyebab & solusi |
|---|---|
| "TELEGRAM_BOT_TOKEN belum diset" | `.env` belum diisi / belum dibuat |
| "Tidak ada user yang diberi akses" | isi `ALLOWED_TELEGRAM_USER_IDS` (id Anda) atau `BOT_OWNER_IDS` |
| "Instance lain sudah berjalan" | hanya satu bot boleh jalan; hentikan instance lain |
| "Materi tidak dapat dibaca" | format tidak didukung/rusak; upload ulang |
| "Judul berbahasa Indonesia tidak ditemukan" | kirim tema manual (Edit/ketik tema) |
| "Dokumen gagal divalidasi" | bot mengirim satu pesan error; coba sesi baru `/new_training` |
| Bot tidak membalas | pastikan proses `main.py` benar-benar berjalan & token valid |

---

## 13. Tips

- Satu bot = satu token; jangan jalankan di dua tempat bersamaan.
- Materi sebaiknya punya **judul Indonesia** yang jelas agar tema otomatis benar.
- Pertanyaan dibuat agar form T03A tetap **1 halaman**; jika Anda menambah
  pertanyaan manual yang panjang, tata letak bisa melebihi satu halaman.
