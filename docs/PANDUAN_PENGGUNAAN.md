# Panduan Penggunaan — QM Assistant Bot

Bot Telegram satu pintu untuk kebutuhan divisi QM: membuat form, melihat
standar cacat, dan belajar aturan kerja. Buka bot, ketik `/start`:

| Menu | Isi |
|---|---|
| 🔍 Inspeksi Lapangan | 🏷 Kode Cacat, 📘 Panduan Kerja, 🏭 Inspeksi Jalur Utama (Form Generator + SOP), 🔧 Inspeksi Luar Jalur (SOP FT, SOP FJ, Form Generator FT/FJ) |
| 🔬 Inspeksi Laboratorium | Lab Mekanik/Fisika (Uji Tarik/Kekerasan/Butiran) dan Lab Kimia — dokumen SOP menyusul |
| 📚 Form Pelatihan | Membuat dokumen pelatihan/briefing QM (DOCX + PDF) |
| ❓ Bantuan | Penjelasan cara pakai per layanan + daftar keyword & pintasan |

> Tombol **🏠 Menu Utama** selalu tersedia untuk kembali ke menu awal.
> Perintah umum: `/start` atau `/menu` (menu utama), `/help` atau
> `/bantuan` (menu bantuan), `/cancel` atau `/batal` (batalkan alur).
>
> **Cara tercepat:** ketik kata kunci langsung di layar utama — kode cacat
> (`B22`), kata kunci (`korosi`, `bagan`), atau nama fitur (`form`,
> `foto`, `kuis`, `panduan`, `sop`, `pelatihan`) — tanpa masuk menu dulu
> (lihat C.6).
>
> **Akses:** Form Pelatihan & Bantuan QC hanya untuk ID Telegram terdaftar
> + owner (admin mendaftarkan lewat menu 👤 User Bot di `/admin`). Form
> Gulungan memakai token undangan + NIK (lihat A.1).

---

# Bagian A — 📄 Form Gulungan

Membuat form gulungan baru QM-YWI dengan output format Mandarin untuk
workplace.

## A.1. Pendaftaran (sekali saja)

1. Minta **token undangan** ke admin, lalu kirim token itu ke bot.
2. Masukkan **NIK** Anda, lalu konfirmasi nama yang muncul.
3. Setelah terdaftar, menu Form Gulungan terbuka penuh.

## A.2. Membuat form baru

Ketik `/new` atau tekan **🚀 Mulai Buat Form**, lalu ikuti langkah bot:

1. Pilih Mesin (`FT` atau `FJ`)
2. Masukkan Nomor Gulungan Asal (contoh: `QH2608K2531HA10`)
3. Konfirmasi deteksi material otomatis (mis. S30403)
4. Masukkan Spesifikasi (contoh: `1.24*1524`)
5. Masukkan Jumlah Gulungan (contoh: `3`)
6. Masukkan Digit Awal Suffix HA (contoh: `1`)
7. Cek preview penomoran coil hasil
8. Input data per coil: Grade (A1/B/B1/R/S), Cacat Utama, Remark, Panjang, Diameter
9. Preview seluruh data → konfirmasi
10. Terima format final Mandarin, siap salin/tempel ke workplace

Contoh hasil akhir:

```text
机组：FT
QH2608K2531HA10
要生成新卷号

QH2608K2531HA11
S30403
1.24*1524
等级: A1
主缺陷: B22
备注: -
目前内径: 610
是否需改内径: Tidak Perlu
长度: 955米
```

## A.3. Perintah Form Gulungan

| Perintah | Fungsi |
|---|---|
| `/new` | mulai pembuatan form gulungan baru |
| `/cancel` | batalkan sesi aktif |
| `/material` | tabel referensi kode material (Z/K/G) |
| `/example` | contoh alur input dan hasil output |
| `/help` | panduan bantuan |
| `/about` | informasi bot |

## A.4. Untuk admin

| Perintah | Fungsi |
|---|---|
| `/admin` | panel admin |
| `/buat_token` | buat token undangan baru |
| `/daftar_token` | lihat token yang aktif |
| `/daftar_user` | lihat user terdaftar |

---

# Bagian B — 📝 Form Pelatihan

Membuat dokumen pelatihan/briefing QM dari materi yang Anda unggah
(DOCX + PDF).

## B.1. Ringkasan alur

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

## B.2. Memulai sesi dokumen

Ketik `/new_training`. Bot membalas: **"📄 Kirim materi pelatihan."**

## B.3. Upload materi

Kirim **satu file** materi (PDF/DOC/DOCX/PPT/PPTX/XLS/XLSX).

- Bot membaca materi, lalu menampilkan **Tema** dari **judul berbahasa
  Indonesia** di dalam dokumen.
- Jika judul Indonesia tidak ditemukan, bot meminta Anda menuliskan tema
  secara manual (tidak menebak).

Pilih **✅ Gunakan Tema Ini** untuk lanjut, atau **✏️ Edit Tema** untuk
mengubahnya. Bot menunggu sampai Anda memilih.

## B.4. Isi data pelatihan

Bot menanyakan berurutan:

| Pertanyaan | Keterangan |
|---|---|
| Nomor Arsip | wajib |
| Tanggal Pelatihan | tanggal saja (tanpa jam) |
| Lokasi | wajib |
| Trainer | wajib |
| Shift/Regu | mis. `REGU A`, `LABORATORIUM` |
| Jumlah Personil Absen | angka (mis. `15` → `15人`) atau **⏭️ Lewati** (kosong) |

Lalu bot menampilkan **📋 KONFIRMASI DATA** dengan tombol
**[✅ Konfirmasi]** dan **[✏️ Edit Data]** (edit per field).

## B.5. Pertanyaan

- Bot membuat **tepat 5 pertanyaan** singkat (≤ 80 karakter) + kunci jawaban
  1–3 kalimat, lalu menampilkan satu kali preview.
- Tombol: **✏️ Edit Pertanyaan** (pilih nomor → kirim pertanyaan baru),
  **🔄 Generate Ulang**, **✅ Konfirmasi**.

> Satu sesi = satu QuestionSet. Preview dikirim sekali dan dipakai untuk
> dokumen (tidak ada generasi ulang tersembunyi).

## B.6. Foto dokumentasi

- Kirim foto satu per satu (boleh banyak); tekan **✅ Selesai** bila cukup.
- Maksimal **2 foto per halaman**; foto otomatis di-resize.
- Tidak mengirim foto juga diperbolehkan (dokumen tetap valid).

## B.7. Hasil

Bot mengirim 2 file: `<NOMOR_ARSIP>_<SHIFT>.docx` dan `.pdf`
(contoh: `2026-QM-LZ-09-03_REGU-A.docx`).

Isi dokumen: T01A (Daftar Hadir) → T02A (Foto) → T03A (Pertanyaan) →
KUNCI JAWABAN. Jika validasi gagal, bot mengirim **satu** pesan error
(dokumen tidak dikirim).

## B.8. Perintah Form Pelatihan

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

## B.9. Mengelola akses user lain

1. Calon user mengirim pesan ke bot → bot membalas berisi **ID Telegram**
   mereka.
2. User mengirim ID itu ke Anda.
3. Anda kirim ke bot: `/allow <id>` (mis. `/allow 123456789`).
4. User langsung bisa memakai bot (tanpa restart). Cabut akses dengan
   `/deny <id>`.

Data user disimpan di `storage/users.json` (lokal).

---

# Bagian C — 🔍 Bantuan QC

Referensi standar cacat cold-rolled stainless (acuan: daftar kode resmi
CRP Yong Wang + SOP TTRI-QM-ZY-35-2026 + Prosedur TTRI-QM-ZY-35-2025).
Dirancang untuk ritme inspeksi 4–7 menit per gulungan: jawaban berupa kartu
singkat dengan keputusan di depan.

## C.1. 🔍 Cari Cacat

Ketik kode cacat (mis. `B22`, `R01-1`, `C38-2`) atau sebagian nama
(mis. `gores`, `karat`). Bot menampilkan kartu:

- **Kualitas** hasil (A/A1/B/B1/C/R/F/S) di baris paling atas
- 📋 Kriteria per tingkat (🟢 L / 🟡 M / 🟠 H / 🔴 S) — penjelasan tiap
  tingkat di-highlight
- 📏 Penanganan (mis. perlu diamplas / dipotong / scrap)
- 🇨🇳 Teks Mandarin asli di bawah penjelasan Indonesia (acuan bila ada
  perbedaan), disertai **pinyin** — mis. `划伤 (huà shāng)`
- Penjelasan tiap tingkat di-highlight dalam box; entri tanpa kriteria
  menjawab "database belum ada" (bot tidak mengarang)

Kode pecahan (`R01-1`, `R01-2`, `R01-3`, dst.) dicari persis seperti
tertulis di daftar resmi.

## C.2. 📖 Daftar Cacat

Pilih bagian dulu, lalu jelajahi dengan tombol Cari / Daftar / Kuis:

| Bagian | Isi |
|---|---|
| 📦 Bahan Baku | Kode S, F, R, W + D03/D21/D38/F16 |
| 🏭 Jalur Utama | Asam Panas (A) → Rolling Mill (B) → Asam Dingin (C) |
| 🔧 Luar Jalur | Penyelesaian (D01, D02, D04–D20) |

Daftar tampil 10 kode per halaman dengan tombol navigasi; pesan
diperbarui di tempat (edit, bukan kirim baru).

## C.3. 🎯 Latihan Kilat

Kuis pilihan ganda 5 soal per sesi: diberikan penjelasan kriteria suatu
cacat, Anda menebak **tingkat & kualitas** yang tepat (mis. `M → A1`).
Skor ditampilkan di akhir sesi. Cocok untuk penyegaran sebelum shift.

## C.4. 📸 Analisis Foto

Kirim foto permukaan plat yang cacat. Bot (AI) memberikan:

- maksimal 3 kandidat cacat + tingkat keyakinan
  (Tinggi/Sedang/Rendah),
- checklist apa yang perlu diukur (panjang/lebar/kedalaman cacat),
- penegasan bahwa ini **pendapat kedua** — keputusan akhir tetap di
  tangan inspektur sesuai SOP.

> Bot tidak menebak ukuran dalam milimeter dari foto. Ukur langsung
> dengan alat.

## C.5. 📘 Panduan Kerja

Materi aturan divisi untuk karyawan baru maupun penyegaran (19 topik):

**Umum (Prosedur TTRI-QM-ZY-35-2025):**

| Topik | Isi |
|---|---|
| 📊 Kriteria Kualitas | Arti tiap kualitas A/A1/B/B1/C/R/F/S + syaratnya |
| ⚖️ Prinsip Penilaian | Langsung downgrade; konsisten antar shift |
| 🚨 Cacat Batch & Peringatan | Aturan peringatan kuning/merah & tahan pengiriman |
| 🔢 Kode Pencatatan Cacat | Format kode `R13TD07900800H` dan cara membacanya |

**SOP Mesin FT (TTRI-QM-ZY-34-2025):**

| Topik | Isi |
|---|---|
| 🦺 Persiapan & APD | APD wajib, cek peralatan, kalibrasi mikrometer |
| 🔍 Inspeksi Permukaan | Area QM, cara periksa tiap gulungan, foto pakai penggaris |
| 📏 Inspeksi Dimensi & Sampel | Titik ukur lebar/tebal/sambungan, aturan sampel |
| 📦 Tepi, Kertas Alas & Pasca-Jalur | Cacat tepi, kertas alas, pelabelan Packing/No Packing |
| 🚨 Keselamatan & Darurat | Jarak aman, larangan keras, hak berhenti saat darurat |

**Langkah Kerja FT (tabel Pasal 5 SOP TTRI-QM-ZY-34-2025, lengkap dengan
foto visualisasi):** Persiapan Sebelum Kerja, Dalam Pekerjaan,
Pemeriksaan Permukaan, Pemeriksaan Dimensi, Pemeriksaan Bentuk Plat,
Pemeriksaan Tepi & Kertas Alas, Pasca Turun Jalur & Nomor Gulungan.

**SOP Inspeksi Jalur Utama (TTRI-QM-ZY-35-2025):** Alur Kerja Inspeksi
(pasal 5.1), Tanggung Jawab Inspektur (pasal 3.1–3.11), dan Bagan Proses
Pengecekan (Lampiran B, dilampirkan versi gambar ulang + bagan asli).

## C.6. ⌨️ Keyword & Pintasan

Ketik langsung di layar utama (atau di area QC) — tidak perlu masuk menu:

| Ketik | Hasil |
|---|---|
| Kode cacat (`B22`, `C11`) | Kartu cacat langsung dibuka |
| Kata kunci (`korosi`, `kualitas`, `bagan`) | Hasil dikelompokkan (Fitur / Cacat / Panduan / Prosedur) |
| `form` / `generator` / `gulungan` | 📝 Form Generator |
| `foto` / `analisis` | 📸 Analisis Foto |
| `kuis` / `latihan` | 🎯 Kuis kilat (pilih bagian dulu) |
| `panduan` | 📘 Panduan Kerja |
| `sop` / `prosedur` | 📋 SOP Mesin FT |
| `pelatihan` | 📚 Form Pelatihan |

Satu hasil langsung dibuka; banyak hasil ditampilkan sebagai daftar
tombol. Di dalam submenu bagian, pencarian terbatas pada bagian itu.

## C.7. ❓ Bantuan

Tombol **❓ Bantuan** di menu utama, atau perintah `/help` / `/bantuan`
dari mode apa pun. Isinya: gambaran bot, perintah umum, dan penjelasan
cara pakai tiap layanan (Form Gulungan, Bantuan QC, Form Pelatihan,
Keyword & Pintasan) — masing-masing dengan tombol Buka Layanan. Menu
bantuan terbuka untuk semua user (hanya cara pakai, tanpa data
perusahaan).

---

# Persiapan & Instalasi (sekali saja, untuk admin server)

1. Siapkan `.env` dari `.env.example`:
   ```bash
   cp .env.example .env
   ```
2. Isi `.env`:
   - `TELEGRAM_BOT_TOKEN` — dari @BotFather
   - `GEMINI_API_KEY` — untuk AI (Form Pelatihan & Analisis Foto). Jika
     kosong, kedua fitur AI berjalan sebagai mock / tidak tersedia.
   - `AI_MODEL` — mis. `gemini-3.6-flash`
   - `OWNER_TELEGRAM_ID` dan `BOT_OWNER_IDS` — **id Telegram Anda**
   - `ALLOWED_TELEGRAM_USER_IDS` — id user yang diberi akses
3. Jalankan:
   ```bash
   .venv/bin/python main.py --check    # pastikan environment siap
   .venv/bin/python main.py            # jalankan bot
   ```

> Bot **menolak start** bila tidak ada user yang diberi akses. Pastikan
> `ALLOWED_TELEGRAM_USER_IDS` terisi, atau `BOT_OWNER_IDS`, atau sudah ada
> user di `storage/users.json`.

# Indikator "sedang memproses"

- Jika sebuah proses memakan waktu **> 0,5 detik**, bot menampilkan
  indikator "typing" agar Anda tahu bot masih bekerja (bukan macet).

# Troubleshooting

| Gejala | Penyebab & solusi |
|---|---|
| "TELEGRAM_BOT_TOKEN belum diset" | `.env` belum diisi / belum dibuat |
| "Tidak ada user yang diberi akses" | isi `ALLOWED_TELEGRAM_USER_IDS` (id Anda) atau `BOT_OWNER_IDS` |
| "Instance lain sudah berjalan" | hanya satu bot boleh jalan; hentikan instance lain |
| "Materi tidak dapat dibaca" | format tidak didukung/rusak; upload ulang |
| "Judul berbahasa Indonesia tidak ditemukan" | kirim tema manual (Edit/ketik tema) |
| "Dokumen gagal divalidasi" | bot mengirim satu pesan error; coba sesi baru `/new_training` |
| Analisis foto "belum tersedia" | `GEMINI_API_KEY` belum diisi di `.env` |
| Bot tidak membalas | pastikan proses `main.py` benar-benar berjalan & token valid |

# Tips

- Satu bot = satu token; jangan jalankan di dua tempat bersamaan.
- Untuk Bantuan QC: hafalkan kode cacat yang sering muncul di lini Anda,
  lalu pakai 🔍 Cari untuk cek cepat kriterianya saat inspeksi.
- Materi pelatihan sebaiknya punya **judul Indonesia** yang jelas agar
  tema otomatis benar.
- Pertanyaan dibuat agar form T03A tetap **1 halaman**; jika Anda menambah
  pertanyaan manual yang panjang, tata letak bisa melebihi satu halaman.
