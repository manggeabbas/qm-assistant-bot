# AGENTS.md — FormPelatihan-QM

## 1. Project Identity

Project name: `FormPelatihan-QM`

Purpose:
Telegram Bot untuk menghasilkan dokumen pelatihan/briefing QM berdasarkan materi yang diunggah user dan master template DOCX.

Target runtime:
- Linux untuk development/testing
- Termux Android untuk deployment

AI development provider:
- DeepSeek

AI provider pada aplikasi harus tetap dibuat interchangeable agar provider lain dapat ditambahkan kemudian.

---

## 2. Source of Truth

Sebelum mengubah atau membuat kode, baca:

1. `PRD/PRD_QM_Training_Bot_v2.0.md`
2. `templates/FORMAT PELATIHAN ADA PERTANYAAN.docx`
3. `AGENTS.md`

Prioritas requirement:

1. Requirement yang sudah dikonfirmasi user
2. PRD v2.0
3. Master template
4. AGENTS.md
5. Implementasi/code

Jika menemukan konflik atau requirement yang ambigu:
- jangan menebak;
- jangan mengubah requirement sendiri;
- jelaskan konflik;
- minta keputusan user jika konflik memengaruhi behavior atau output.

---

## 3. Development Philosophy

Project harus dibangun bertahap.

JANGAN langsung membuat seluruh bot.

Urutan wajib:

1. Template Laboratory
2. Document Generator
3. Material Reader
4. AI Layer
5. Telegram Workflow
6. Validation
7. Termux Deployment

Setiap fase harus dapat diuji sebelum melanjutkan ke fase berikutnya.

---

## 4. Critical Project Rules

### 4.1 AI vs Layout

AI hanya bertanggung jawab terhadap konten:

- ekstraksi tema;
- pertanyaan;
- kunci jawaban;
- analisis materi.

AI TIDAK boleh menentukan:

- koordinat elemen;
- posisi tabel;
- posisi foto;
- ukuran halaman;
- margin;
- font layout;
- page break;
- header/footer;
- struktur XML DOCX.

Layout sepenuhnya dikendalikan oleh document/template engine.

### 4.2 Master Template

File:

`templates/FORMAT PELATIHAN ADA PERTANYAAN.docx`

adalah master template.

Jangan:
- merusak struktur visual;
- mengganti desain tanpa kebutuhan;
- menghapus logo;
- menghapus header/footer;
- mengubah border/tabel secara sembarangan;
- membuat ulang template dari nol jika elemen yang diperlukan dapat dipertahankan dari master.

Jika diperlukan perubahan struktural untuk otomasi, buat mekanisme/template working copy tanpa merusak master original.

### 4.3 Blank Fields

Jangan mengisi field yang ditetapkan kosong dengan asumsi.

T03A:
- Nama = blank
- NIK = blank
- Nilai = blank
- `JAWABAN 答：` = tetap ada, tetapi area jawaban peserta blank

Jangan menggunakan:
- `N/A`
- `-`
- `Unknown`
- `0`
- nilai hasil tebakan

kecuali requirement secara eksplisit memintanya.

---

## 5. Confirmed Data Rules

### T01A

Field:
- Tema
- Tanggal
- Trainer
- Nomor Arsip
- Lokasi
- Personil Absen

Tema:
- diekstrak AI dari materi;
- ditampilkan kepada user;
- user dapat memilih Gunakan atau Edit;
- hasil akhirnya menjadi tema final.

Personil Absen:
- opsional;
- user cukup memasukkan angka;
- `15` harus menjadi `15人`;
- tombol Skip/Lewati menghasilkan field kosong;
- jangan menghasilkan `0人` atau `N/A`.

Nama peserta pada tabel kehadiran tidak diisi otomatis.

### T03A

- Nama = blank
- NIK = blank
- Dept = `QM`
- Workshop/Divisi = `QMYWI`
- Topik = Tema final T01A
- Trainer/Moderator = Trainer T01A
- Tanggal Pelatihan = Tanggal T01A
- Nilai = blank
- Pertanyaan = tepat 5
- `JAWABAN 答：` = blank
- Kunci jawaban = halaman terpisah

### Questions

Harus:
- tepat 5;
- open-ended;
- sederhana;
- jelas;
- berkaitan langsung dengan materi;
- tidak duplikatif;
- jawabannya tersedia dalam materi.

Jangan membuat pertanyaan berdasarkan pengetahuan eksternal jika informasi tersebut tidak didukung materi.

---

## 6. Document Order

Dokumen final wajib memiliki urutan:

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

Semua menjadi satu DOCX.

PDF dibuat dari DOCX final.

---

## 7. Photo Rules

User dapat mengirim foto satu per satu.

Jumlah foto tidak dibatasi secara eksplisit.

Maksimal:
- 2 foto per halaman.

Foto harus:
- masuk ke area template;
- tidak keluar frame;
- tidak menutupi teks;
- tidak overlap;
- mempertahankan kualitas visual;
- di-resize secara otomatis;
- di-crop hanya jika diperlukan oleh area foto.

---

## 8. Filename

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

Shift/Regu digunakan sebagai metadata/nama file sesuai PRD.

---

## 9. AI Provider Architecture

Jangan mengikat business logic langsung ke DeepSeek.

Gunakan abstraction/interface seperti:

```text
AIProvider
├── DeepSeekProvider
├── GeminiProvider
└── OpenAIProvider
```

DeepSeek adalah provider development saat ini.

API key harus berasal dari environment variable.

Jangan hard-code API key.

Jangan commit `.env`.

---

## 10. Structured AI Output

AI output harus berupa structured data.

Contoh:

```json
{
  "theme": "...",
  "questions": [
    {
      "question": "...",
      "answer": "..."
    }
  ]
}
```

Validasi schema harus dilakukan sebelum data diberikan kepada document generator.

Jika AI menghasilkan:
- kurang dari 5 pertanyaan;
- lebih dari 5 pertanyaan;
- JSON invalid;
- jawaban kosong;
- pertanyaan tidak sesuai schema;

maka jangan langsung memasukkan hasil tersebut ke DOCX.

Lakukan retry/repair sesuai mekanisme yang dibuat.

---

## 11. Document Generation Architecture

Gunakan pemisahan:

```text
Input Data
    ↓
Validated Structured Data
    ↓
Template Engine
    ↓
DOCX
    ↓
LibreOffice
    ↓
PDF
    ↓
Validation
```

Jangan mencampur:
- Telegram handler;
- AI call;
- document manipulation;
- PDF conversion;

dalam satu file atau satu fungsi besar.

Gunakan modul yang terpisah.

---

## 12. Validation Is Mandatory

Dokumen tidak boleh dikirim sebelum validation berhasil.

Validasi minimal:

### Layout
- no overlap;
- no overflow;
- no clipped text;
- no photo outside frame;
- no table outside page;
- no photo covering text.

### Pagination
- no unnecessary blank page;
- header tetap;
- footer tetap;
- page break terkendali;
- question block tidak terbelah secara tidak semestinya.

### Structure
- T01A ada;
- T02A ada;
- T03A ada;
- tepat 5 pertanyaan;
- participant answer area kosong;
- answer key ada;
- semua foto masuk.

Pipeline:

```text
DOCX
 ↓
LibreOffice Headless
 ↓
PDF
 ↓
Render pages
 ↓
Validation
```

Jika validation gagal:

```text
Adjust
 ↓
Regenerate
 ↓
Validate
```

Jangan mengirim dokumen yang diketahui gagal validation.

---

## 13. Telegram State

Workflow harus menggunakan state/session.

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

Jangan bergantung pada global mutable state untuk data user.

Session harus terisolasi per user/session.

---

## 14. Security

- API keys melalui environment variable.
- `.env` tidak boleh di-commit.
- Jangan menampilkan credential dalam log.
- Jangan mencampur file sesi antar user.
- File temporary harus memiliki session ID.
- Jangan membocorkan materi user lain.
- Validasi tipe dan ukuran file upload.
- Jangan menjalankan file upload sebagai executable.

---

## 15. Testing Rules

Setiap fase harus memiliki test yang sesuai.

Minimal:

### Template Laboratory
Test:
- placeholder;
- text wrapping;
- table;
- image placement;
- page break.

### Document Generator
Test:
- T01A;
- T02A;
- T03A;
- answer key;
- blank fields;
- multiple photos.

### AI
Test:
- theme extraction;
- exactly 5 questions;
- answer generation;
- malformed response;
- retry.

### Telegram
Test:
- unauthorized user;
- upload;
- state transitions;
- skip personnel count;
- edit theme;
- question review;
- photo loop.

Jangan mengandalkan manual testing saja untuk logic penting.

---

## 16. Coding Style

Prioritaskan:
- kode sederhana;
- fungsi kecil;
- module separation;
- explicit data flow;
- type/schema validation;
- error handling yang jelas.

Hindari:
- giant functions;
- hidden global state;
- duplicated business logic;
- hard-coded secrets;
- hard-coded AI responses;
- magic numbers tanpa penjelasan.

Komentar kode hanya jika membantu menjelaskan alasan teknis yang tidak jelas dari kode.

---

## 17. Dependency Rules

Sebelum menambahkan dependency baru:

1. pastikan memang diperlukan;
2. periksa apakah functionality dapat menggunakan library yang sudah ada;
3. pertimbangkan kompatibilitas Linux dan Termux;
4. dokumentasikan dependency yang membutuhkan system package.

Jangan menambahkan framework besar tanpa alasan.

---

## 18. Git Rules

Jangan melakukan destructive Git operation tanpa persetujuan user.

Jangan:
- `git reset --hard`;
- menghapus branch;
- menghapus file user;
- overwrite perubahan user;

tanpa instruksi eksplisit.

Gunakan commit kecil dan logis jika user meminta agent mengelola commit.

---

## 19. Working Method for OpenCode

Sebelum coding:

1. baca PRD;
2. baca AGENTS.md;
3. inspeksi repository;
4. inspeksi master template bila task berkaitan dengan dokumen;
5. identifikasi dependency;
6. buat rencana singkat;
7. implementasikan satu tahap;
8. jalankan test;
9. periksa hasil;
10. lanjut ke tahap berikutnya.

Jangan mengklaim fitur selesai jika belum diuji.

Jika sebuah requirement belum jelas dan berpengaruh pada hasil akhir, berhenti dan minta klarifikasi.

Jika requirement sudah jelas, jangan meminta konfirmasi berulang kali.

---

## 20. Current Development Target

Tahap pertama saat ini adalah:

# Template Laboratory

Target:

```text
Master DOCX
    ↓
Inspection
    ↓
Identify dynamic fields
    ↓
Create controlled template mechanism
    ↓
Inject test data
    ↓
Generate DOCX
    ↓
Convert to PDF
    ↓
Inspect layout
```

Belum perlu:
- Telegram bot;
- AI;
- DeepSeek integration;
- database user;
- deployment Termux.

Fokus pertama adalah memastikan document generator menghasilkan dokumen yang benar dari master template.

---

## 21. Definition of Done

Sebuah task dianggap selesai hanya jika:

1. implementasi sesuai PRD;
2. tidak melanggar AGENTS.md;
3. test yang relevan berhasil;
4. tidak ada requirement yang diam-diam diubah;
5. output dokumen diperiksa bila task berkaitan dengan document generation;
6. error handling dasar tersedia;
7. perubahan dapat dijelaskan secara singkat.

---

## 22. Final Rule

Jika ada konflik antara "cara yang mudah dibuat" dan requirement dokumen, **requirement dokumen yang berlaku**.

Jangan menyederhanakan behavior dengan mengorbankan:
- layout;
- template;
- data accuracy;
- blank-field rules;
- question/answer separation;
- validation.

---

## 23. QM Assistant (repo gabungan) — addendum

Repo ini menggabungkan `formpelatihanQM` + `qm-ywi-telegram-bot` menjadi 1 bot,
1 token (keputusan: Opsi A, port Node.js → Python).

- **Jangan ubah `qm_training/`** kecuali untuk kebutuhan Form Pelatihan itu
  sendiri; seluruh §1–§22 di atas tetap berlaku penuh untuknya.
- **`qm_coil/`** adalah port bertahap dari `src/*.js` asli (mapping di
  `qm_coil/__init__.py` dan README). Port per modul, satu tahap diuji sebelum
  lanjut — filosofi §3 berlaku juga di sini.
- **`qm_assistant/router.py`** adalah satu-satunya titik penyatuan alur.
  `/start` selalu menjadi menu; jangan mem-bypass router dengan meneruskan
  `/start` mentah ke workflow training.
- Satu user management untuk kedua layanan (saat ini memakai `UserStore`
  milik `qm_training`; panel admin gabungan menyusul setelah port selesai).
