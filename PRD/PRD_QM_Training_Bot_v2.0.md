# PRD v2.0 — Telegram Bot Generator Dokumen Pelatihan QM

**Status:** Ready for implementation  
**Tanggal:** 25 September 2026  
**Platform:** Telegram Bot  
**Target runtime:** Linux (testing) dan Termux Android (deployment)

---

## 1. Ringkasan

Bot Telegram ini digunakan untuk membuat paket dokumentasi pelatihan/briefing berdasarkan materi yang diunggah user dan **master template DOCX resmi** yang telah dirapikan.

Bot menghasilkan satu paket dokumen yang terdiri dari:

```text
T01A — Daftar Hadir
        ↓
T02A — Dokumentasi Foto
        ↓
T03A — Pertanyaan Peserta
        ↓
PAGE BREAK
        ↓
KUNCI JAWABAN
```

Output akhir:

- 1 file `.docx`
- 1 file `.pdf`

Prinsip arsitektur:

> **AI mengatur konten; template engine mengatur layout.**

AI tidak boleh menentukan posisi elemen secara bebas.

---

# 2. Tujuan

## 2.1 Tujuan utama

Mengurangi pekerjaan manual dalam pembuatan dokumen pelatihan QM dengan cara:

1. membaca materi pelatihan;
2. mengambil dan mengonfirmasi tema;
3. menerima data administrasi;
4. membuat 5 pertanyaan terbuka sederhana;
5. membuat kunci jawaban berdasarkan materi;
6. menerima foto dokumentasi dalam jumlah fleksibel;
7. mengisi master template;
8. memvalidasi layout;
9. menghasilkan DOCX dan PDF.

## 2.2 Tujuan teknis

Sistem harus:

- mempertahankan identitas visual master template;
- mempertahankan bahasa Indonesia/Mandarin pada template;
- mempertahankan struktur T01A/T02A/T03A;
- menjaga header, footer, logo, border, tabel, dan margin;
- mengendalikan page break;
- mencegah overlap/overflow;
- menghasilkan PDF yang merepresentasikan DOCX final.

---

# 3. Scope Versi 1

### Termasuk

- Telegram bot
- user registration
- upload materi
- ekstraksi materi
- AI theme extraction
- konfirmasi/edit tema
- input data pelatihan
- 5 pertanyaan terbuka
- review/edit/regenerate pertanyaan
- upload foto fleksibel
- generate DOCX
- generate PDF
- layout validation
- Linux
- Termux

### Belum termasuk

- OCR sebagai kebutuhan utama
- arsip/history permanen
- dashboard web
- cloud storage permanen
- penilaian otomatis peserta
- pengisian nama/NIK peserta secara otomatis

---

# 4. Hak Akses

Bot hanya dapat digunakan oleh user terdaftar.

Role:

```text
OWNER / ADMIN
USER
```

Owner/admin awal adalah developer.

Admin dapat:

- menambah user;
- menonaktifkan user;
- melihat daftar user;
- mengatur provider/model AI;
- melihat status sistem.

---

# 5. Master Template

Master template adalah **dokumen mentah yang telah dirapikan oleh user** dan menjadi acuan utama visual/layout.

Template memiliki bagian:

- T01A — Formulir Pendaftaran Pelatihan/Daftar Hadir;
- T02A — Dokumentasi Foto;
- T03A — Formulir Pertanyaan;
- Kunci Jawaban pada bagian halaman terpisah.

T01A memuat tema, nomor arsip, tanggal/waktu pelatihan, lokasi, trainer, dan tabel personil. fileciteturn0file0L3-L41

T02A menyediakan area dokumentasi foto. fileciteturn0file0L58-L66

T03A memuat identitas peserta, trainer/moderator, tanggal, divisi, topik, nilai, pertanyaan, dan area jawaban. fileciteturn0file0L69-L117

Dokumen sumber juga menunjukkan jawaban pada halaman terpisah. fileciteturn0file0L118-L135

Template tidak boleh didesain ulang tanpa kebutuhan. Kode hanya mengisi/mengulang bagian dinamis yang diperlukan.

---

# 6. Input Materi

Format minimum:

- PDF
- DOC
- DOCX
- PPT
- PPTX
- XLS
- XLSX

Alur:

```text
Telegram
 ↓
Download
 ↓
Validasi
 ↓
Extract
 ↓
Normalize
 ↓
AI Material Analyzer
```

Untuk Excel, struktur sheet, baris, kolom, dan tabel harus dipertahankan semaksimal mungkin.

Materi yang seluruhnya berupa scan/gambar belum menjadi kebutuhan utama. OCR dapat ditambahkan kemudian.

---

# 7. Penyimpanan File

Selama sesi:

```text
sessions/<session_id>/
├── input/
├── extracted/
├── photos/
├── working/
└── output/
```

File input dan hasil kerja bersifat sementara untuk versi 1.

Arsip/history permanen belum diwajibkan.

---

# 8. Provider AI

Provider harus dapat diganti tanpa mengubah workflow utama.

Contoh provider:

```text
Gemini
DeepSeek
OpenAI API
```

Gunakan abstraction layer:

```text
AIProvider
├── GeminiProvider
├── DeepSeekProvider
└── OpenAIProvider
```

Catatan: akses ChatGPT Go tidak dianggap sebagai kredit OpenAI API. API billing/access ditangani terpisah.

---

# 9. Data Training Session

Struktur data minimum:

```json
{
  "theme": "",
  "archive_number": "",
  "training_date": "",
  "location": "",
  "trainer": "",
  "shift_group": "",
  "personnel_count": null,
  "questions": [],
  "answer_key": [],
  "photos": []
}
```

Field `personnel_count` boleh `null`.

---

# 10. Mapping T01A

Data yang berasal dari user:

| Field | Sumber | Aturan |
|---|---|---|
| Tema | AI → user confirm/edit | Final theme |
| Tanggal | User | Wajib |
| Trainer | User | Wajib |
| Nomor Arsip | User | Wajib |
| Lokasi | User | Wajib |
| Personil Absen | User | Opsional |

### Personil Absen

Bot meminta jumlah personil:

```text
Jumlah Personil Absen?
```

User cukup memasukkan angka.

Contoh:

```text
15
```

Bot mengisi:

```text
15人
```

Jika user memilih:

```text
⏭️ Lewati
```

maka field tetap kosong.

Tidak boleh mengubahnya menjadi `0人`, `N/A`, atau nilai lain.

Nama peserta pada tabel kehadiran **tidak diisi otomatis oleh bot**.

---

# 11. Mapping T03A

| Field | Nilai |
|---|---|
| Nama | Left Blank |
| NIK | Left Blank |
| Dept | `QM` |
| Workshop/Divisi | `QMYWI` |
| Topik | Sama dengan Tema T01A |
| Trainer/Moderator | Sama dengan Trainer T01A |
| Tanggal Pelatihan | Sama dengan Tanggal T01A |
| Nilai | Left Blank |
| Pertanyaan 1–5 | AI |
| `JAWABAN 答：` | Tetap tampil, tetapi kosong |
| Kunci Jawaban | AI, halaman terpisah |

Nilai peserta tidak diisi otomatis.

---

# 12. Tema

Setelah materi dianalisis, bot menampilkan tema:

```text
📚 Tema terdeteksi:

<TEMA>

[✅ Gunakan Tema Ini]
[✏️ Edit Tema]
```

Tema yang dikonfirmasi/diedit menjadi **tema final**.

Tema final digunakan pada:

- T01A;
- T03A Topik;
- metadata internal dokumen bila diperlukan.

---

# 13. Pertanyaan

AI wajib membuat **tepat 5 pertanyaan**.

Karakteristik:

- open-ended;
- sederhana;
- jelas;
- langsung berkaitan dengan materi;
- tidak duplikatif;
- jawaban tersedia di materi;
- tidak bergantung pada pengetahuan eksternal.

Contoh bentuk:

```text
1. Apa yang dimaksud dengan ...?
2. Sebutkan ... berdasarkan materi.
3. Apa yang harus dilakukan ...?
4. Mengapa ... penting?
5. Apa tindakan yang dilakukan apabila ...?
```

AI juga membuat kunci jawaban untuk masing-masing pertanyaan.

---

# 14. Review Pertanyaan

Bot menampilkan preview 5 pertanyaan.

User dapat:

```text
[✏️ Edit Pertanyaan]
[🔄 Generate Ulang]
[✅ Konfirmasi]
```

Edit idealnya mendukung pertanyaan individual.

Jika generate ulang, sistem menghasilkan kembali 5 pertanyaan berdasarkan materi yang sama.

Kunci jawaban harus ikut disesuaikan apabila pertanyaan berubah.

---

# 15. Foto Dokumentasi

User dapat mengirim foto satu per satu.

Contoh:

```text
📷 Silakan kirim foto dokumentasi.

Setelah selesai:
[✅ Selesai]
```

Jumlah foto tidak dibatasi secara eksplisit.

Jika tidak ada foto, sistem harus menangani kondisi tersebut tanpa crash. Perilaku T02A untuk 0 foto mengikuti struktur master template dan harus tetap menghasilkan dokumen yang valid.

Aturan layout:

- maksimal 2 foto per halaman;
- foto masuk ke area yang tersedia;
- auto resize;
- crop hanya bila diperlukan;
- menjaga kualitas visual;
- tidak keluar frame;
- tidak menutupi teks.

---

# 16. Shift/Regu

Bot meminta shift/regu.

Nilai digunakan sebagai metadata dan bagian nama file.

Contoh:

```text
REGU A
REGU B
REGU C
LABORATORIUM
```

Nama file:

```text
<ARCHIVE>_<SHIFT_GROUP>.docx
<ARCHIVE>_<SHIFT_GROUP>.pdf
```

Contoh:

```text
2026-QM-LZ-09-03_REGU-A.docx
2026-QM-LZ-09-03_REGU-A.pdf
```

Shift/regu tidak otomatis ditambahkan ke dokumen kecuali terdapat field yang memang disediakan master template.

---

# 17. Tanggal

Bot hanya meminta **tanggal**.

Bot tidak meminta jam/waktu pelatihan.

User dapat memasukkan tanggal, kemudian sistem menormalisasi format sesuai kebutuhan template.

---

# 18. Nomor Arsip

Nomor arsip diinput user.

Versi 1 tidak boleh mengarang nomor arsip.

Jika validasi format diterapkan, aturan format harus dikonfigurasi secara eksplisit dan tidak boleh mengubah nilai user secara diam-diam.

---

# 19. Konfirmasi Data

Sebelum AI membuat pertanyaan, bot menampilkan ringkasan:

```text
📋 KONFIRMASI DATA

Tema       : ...
No. Arsip  : ...
Tanggal    : ...
Lokasi     : ...
Trainer    : ...
Shift/Regu : ...
Personil   : 15人
```

Jika Personil Absen dilewati:

```text
Personil   : —
```

Menu:

```text
[✅ Konfirmasi]
[✏️ Edit Data]
```

Edit dilakukan per-field.

---

# 20. Workflow Telegram

```text
/new_training
      ↓
Upload material
      ↓
Validate
      ↓
Extract + normalize
      ↓
AI theme extraction
      ↓
Theme preview
 ┌────┴─────┐
Use        Edit
 └────┬─────┘
      ↓
Archive Number
      ↓
Date
      ↓
Location
      ↓
Trainer
      ↓
Shift/Regu
      ↓
Personnel Count
      ├── Input number → <number>人
      └── Skip → blank
      ↓
Confirmation
      ↓
Generate 5 questions + answer key
      ↓
Question review
 ┌────┼─────────────┐
Edit  Regenerate   Confirm
 └────┴─────────────┘
      ↓
Photo upload loop
      ↓
Done
      ↓
Generate document
      ↓
Layout validation
      ↓
DOCX
      ↓
PDF
      ↓
Send files
```

---

# 21. State Machine

Contoh state:

```text
IDLE
WAITING_MATERIAL
PROCESSING_MATERIAL
THEME_REVIEW
WAITING_ARCHIVE
WAITING_DATE
WAITING_LOCATION
WAITING_TRAINER
WAITING_SHIFT_GROUP
WAITING_PERSONNEL_COUNT
DATA_REVIEW
GENERATING_QUESTIONS
QUESTION_REVIEW
PHOTO_UPLOAD
GENERATING_DOCUMENT
VALIDATING_DOCUMENT
COMPLETED
ERROR
```

State harus disimpan per user/session agar proses dapat dilanjutkan jika terjadi input bertahap.

---

# 22. Arsitektur Modul

Struktur yang disarankan:

```text
qm-training-bot/
├── bot/
│   ├── handlers/
│   ├── keyboards/
│   └── states/
│
├── core/
│   ├── session/
│   ├── config/
│   └── permissions/
│
├── ai/
│   ├── base.py
│   ├── gemini.py
│   ├── deepseek.py
│   └── openai.py
│
├── extractors/
│   ├── pdf.py
│   ├── doc.py
│   ├── ppt.py
│   └── xls.py
│
├── document/
│   ├── template.py
│   ├── t01a.py
│   ├── t02a.py
│   ├── t03a.py
│   ├── answer_key.py
│   ├── photos.py
│   └── assembly.py
│
├── validation/
│   ├── docx.py
│   ├── pdf.py
│   └── visual.py
│
├── templates/
│   └── master.docx
│
├── storage/
│   ├── sessions/
│   └── output/
│
├── tests/
├── .env
├── requirements.txt
└── main.py
```

Struktur dapat disesuaikan saat implementasi.

---

# 23. Template Engine

Template engine bertanggung jawab atas:

- placeholder;
- font;
- wrapping;
- tabel;
- gambar;
- page break;
- header;
- footer;
- margin;
- ukuran area;
- layout.

Contoh placeholder internal:

```text
{{THEME}}
{{ARCHIVE_NUMBER}}
{{TRAINING_DATE}}
{{LOCATION}}
{{TRAINER}}
{{PERSONNEL_COUNT}}
{{QUESTION_1}}
{{QUESTION_2}}
{{QUESTION_3}}
{{QUESTION_4}}
{{QUESTION_5}}
{{ANSWER_1}}
...
```

AI tidak boleh menulis XML/DOCX layout secara langsung.

---

# 24. Document Assembly

Urutan wajib:

```text
T01A
 ↓
T02A
 ↓
T03A
 ↓
PAGE BREAK
 ↓
KUNCI JAWABAN
```

Semua berada dalam **satu DOCX** dan **satu PDF**.

Pada T03A:

```text
PERTANYAAN
JAWABAN 答：

[AREA KOSONG]
```

Kunci jawaban tidak boleh ditempatkan pada area jawaban peserta.

---

# 25. Layout Safety

Sistem harus mencegah:

```text
❌ overlap
❌ overflow
❌ teks terpotong
❌ foto keluar frame
❌ foto menutupi teks
❌ tabel keluar halaman
❌ header tertimpa
❌ footer tertimpa
❌ halaman kosong yang tidak diperlukan
```

Konten panjang ditangani dengan:

- wrapping;
- penyesuaian tinggi;
- penyesuaian font dalam batas aman;
- page break;
- pemindahan blok utuh ke halaman berikutnya.

Pertanyaan dan area jawabannya dianggap sebagai satu blok visual.

---

# 26. Validasi Dokumen

Pipeline:

```text
DOCX
 ↓
LibreOffice Headless
 ↓
PDF
 ↓
Render PDF pages
 ↓
Visual/layout validation
```

Validasi:

### Layout
- object keluar halaman;
- overlap;
- teks terpotong;
- foto keluar frame;
- tabel terpotong.

### Pagination
- halaman kosong;
- header/footer hilang;
- page break abnormal;
- blok pertanyaan terbelah secara tidak semestinya.

### Struktur
- T01A ada;
- T02A ada;
- T03A ada;
- tepat 5 pertanyaan;
- jawaban peserta kosong;
- kunci jawaban ada;
- semua foto masuk.

Jika gagal:

```text
Adjust
 ↓
Render ulang
 ↓
Validate ulang
```

Sistem tidak boleh mengirim dokumen yang diketahui gagal validasi.

---

# 27. Output

Format:

```text
<ARCHIVE>_<SHIFT_GROUP>.docx
<ARCHIVE>_<SHIFT_GROUP>.pdf
```

Contoh:

```text
2026-QM-LZ-09-03_REGU-A.docx
2026-QM-LZ-09-03_REGU-A.pdf
```

PDF harus berasal dari DOCX final yang telah divalidasi.

---

# 28. Error Handling

Bot harus menangani minimal:

- file tidak didukung;
- file gagal di-download;
- ekstraksi gagal;
- materi kosong;
- AI timeout;
- AI provider error;
- respons AI tidak sesuai schema;
- pertanyaan kurang dari 5;
- foto rusak;
- DOCX generation gagal;
- PDF conversion gagal;
- layout validation gagal.

Pesan error harus ringkas dan memberi tindakan berikutnya.

Contoh:

```text
❌ Materi tidak dapat dibaca.

Silakan upload ulang file atau gunakan format:
PDF, DOC, DOCX, PPT, PPTX, XLS, XLSX
```

---

# 29. Security & Data Handling

- Hanya user terdaftar yang dapat menggunakan bot.
- File sesi dipisahkan berdasarkan session ID.
- API key disimpan di environment variable.
- Jangan menaruh API key di source code.
- File sementara dihapus setelah sesi selesai sesuai kebijakan cleanup.
- Bot tidak boleh membocorkan materi satu user kepada user lain.

---

# 30. Deployment

## Linux

Digunakan untuk:

- development;
- debugging;
- template testing;
- layout validation.

## Termux

Digunakan untuk:

- deployment;
- menjalankan bot secara lokal di Android.

Dependensi yang membutuhkan binary/system package harus didokumentasikan.

LibreOffice headless harus tersedia pada environment yang melakukan PDF conversion.

---

# 31. Tahapan Implementasi

## Fase 1 — Template Laboratory

- gunakan master template;
- identifikasi T01A/T02A/T03A;
- tentukan placeholder;
- uji pengisian data;
- uji foto;
- uji page break.

## Fase 2 — Document Generator

```text
JSON
 ↓
Template Engine
 ↓
DOCX
 ↓
PDF
```

Tanpa Telegram dan AI terlebih dahulu.

## Fase 3 — Material Reader

Implementasi parser:

- PDF;
- DOC/DOCX;
- PPT/PPTX;
- XLS/XLSX.

## Fase 4 — AI Layer

Implementasi:

- theme extraction;
- question generation;
- answer generation;
- review/edit/regenerate.

## Fase 5 — Telegram Workflow

Integrasikan:

- authentication;
- state machine;
- upload;
- input data;
- review;
- photo collection;
- output.

## Fase 6 — Validation

- DOCX → PDF;
- render;
- layout validation;
- automatic adjustment.

## Fase 7 — Termux

Uji:

- Linux;
- Termux;
- Android.

---

# 32. Acceptance Criteria

## Input

- [ ] User dapat mengunggah materi.
- [ ] PDF dapat dibaca.
- [ ] DOC/DOCX dapat dibaca.
- [ ] PPT/PPTX dapat dibaca.
- [ ] XLS/XLSX dapat dibaca.

## Data

- [ ] Tema dapat diekstrak.
- [ ] Tema ditampilkan kepada user.
- [ ] Tema dapat diedit.
- [ ] Nomor arsip diminta.
- [ ] Tanggal diminta.
- [ ] Lokasi diminta.
- [ ] Trainer diminta.
- [ ] Shift/Regu diminta.
- [ ] Personil Absen bersifat opsional.
- [ ] Input `15` menghasilkan `15人`.
- [ ] Skip menghasilkan field kosong.
- [ ] Nama peserta tidak diisi otomatis.

## T03A

- [ ] Nama kosong.
- [ ] NIK kosong.
- [ ] Dept = QM.
- [ ] Workshop/Divisi = QMYWI.
- [ ] Topik = Tema.
- [ ] Trainer/Moderator = Trainer.
- [ ] Tanggal Pelatihan = Tanggal.
- [ ] Nilai kosong.
- [ ] Tepat 5 pertanyaan.
- [ ] Pertanyaan terbuka sederhana.
- [ ] Pertanyaan berbasis materi.
- [ ] Area `JAWABAN 答：` tetap kosong.
- [ ] Kunci jawaban berada di halaman terpisah.

## Foto

- [ ] User dapat mengirim banyak foto.
- [ ] Ada tombol Selesai.
- [ ] Maksimal 2 foto per halaman.
- [ ] Foto tidak keluar frame.
- [ ] Foto tidak menutupi elemen lain.

## Dokumen

- [ ] T01A dibuat.
- [ ] T02A dibuat.
- [ ] T03A dibuat.
- [ ] Kunci jawaban dibuat.
- [ ] Semua bagian berada dalam satu DOCX.
- [ ] PDF dibuat dari DOCX final.

## Layout

- [ ] Tidak ada overlap.
- [ ] Tidak ada overflow.
- [ ] Tidak ada teks terpotong.
- [ ] Tidak ada foto keluar frame.
- [ ] Header tetap.
- [ ] Footer tetap.
- [ ] Logo tetap.
- [ ] Page break terkendali.
- [ ] Tidak ada halaman kosong yang tidak diperlukan.

## Deployment

- [ ] Berjalan di Linux.
- [ ] Dapat dijalankan di Termux.

---

# 33. Prinsip Implementasi

1. **Jangan mulai dari Telegram.** Bangun dan uji document generator terlebih dahulu.
2. **Jangan membuat layout dengan AI.**
3. **Master template adalah sumber visual utama.**
4. **Konten AI harus terstruktur/JSON sebelum masuk template.**
5. **Validasi layout adalah bagian dari generation pipeline, bukan langkah opsional.**
6. **Semua field yang belum diisi user harus tetap kosong, bukan diisi asumsi.**
7. **Pertanyaan dan kunci jawaban harus berasal dari materi yang diberikan.**
8. **Provider AI harus dapat diganti melalui konfigurasi.**

---

# 34. Status PRD

**PRD v2.0 — READY FOR IMPLEMENTATION**

Tahap berikutnya:

```text
PRD v2.0
   ↓
Project scaffold
   ↓
Template Laboratory
   ↓
Document Generator
   ↓
Material Reader
   ↓
AI Layer
   ↓
Telegram Bot
   ↓
Validation
   ↓
Linux + Termux
```
