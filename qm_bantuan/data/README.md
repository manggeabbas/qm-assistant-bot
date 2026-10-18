# Cara update standar cacat (atlas.json)

Bot Bantuan QC **data-driven**: seluruh nama kode, kriteria tingkat, grade,
aturan, dan catatan dibaca dari `atlas.json` saat bot start. Mengubah standar
**tidak perlu utak-atik kode**.

## Update rutin

1. Siapkan file `atlas.json` baru dengan **skema yang sama** (lihat bawah).
2. Backup yang lama: `cp atlas.json atlas.json.bak`
3. Timpa: `cp /path/ke/atlas-baru.json qm_bantuan/data/atlas.json`
4. Validasi cepat: `.venv/bin/python -c "import json; d=json.load(open('qm_bantuan/data/atlas.json')); print(len(d['defects']))"`
5. Restart bot: `systemctl restart qm-bot` (atau restart manual di Termux).

## Skema entri (jangan diubah strukturnya)

```jsonc
{
  "code": "C11",                 // kode cacat resmi (unik)
  "name_id": "Tergores",         // nama Indonesia (boleh null -> pakai Mandarin)
  "name_cn": "划伤",              // nama Mandarin (acuan bila ragu)
  "section": "asam_dingin",      // bahan_baku | asam_panas | rolling_mill | asam_dingin | penyelesaian
  "jenis": null,                 // info sub-kode bila ada
  "levels": {                    // boleh {} bila hanya aturan / belum ada kriteria
    "L": {"desc": "...", "grade": "A"},
    "M": {"desc": "...", "grade": "A1"}
    // urutan L -> M -> H -> S; grade: A/A1/B/B1/C/R/F/S/TIDAK_DIIZINKAN
  },
  "rule": "...",                 // aturan penanganan (boleh null)
  "notes": "...",                // catatan tambahan (boleh "")
  "variants": [],                // untuk R19/R20/R50/R51: [{jenis, jenis_cn, levels, notes}]
  "flags": [],                   // penanda internal (opsional)
  "superseded_note": "..."       // catatan aturan yang digantikan (opsional)
}
```

Aturan perilaku bot yang dijaga kode (bukan data):

- Entri tanpa `levels` → kartu hanya menampilkan pengertian + aturan;
  pertanyaan soal kriteria dijawab **"database belum ada"**.
- Sub-kode (`R01-1`, `C38-1`, `S01-1`, …) adalah entri terpisah di JSON
  dan otomatis menjadi kartu terpisah di bot.

Sumber penyusunan: `~/workspace/qm-bantuan-qc/atlas/` (VERIFIKASI.md dkk).

---

# Cara update Panduan Kerja (panduan.json)

Menu 📘 *Panduan Kerja* juga **data-driven**: daftar topik dibaca dari
`panduan.json` saat bot start. Mengubah/menambah topik **tidak perlu
utak-atik kode**.

## Update rutin

1. Edit `panduan.json` (tambah/ubah topik).
2. Validasi cepat: `.venv/bin/python -c "import json; d=json.load(open('qm_bantuan/data/panduan.json')); print([t['id'] for t in d['topics']])"`
3. Restart bot.

## Skema topik (jangan diubah strukturnya)

```jsonc
{
  "topics": [
    {
      "id": "grade",          // id unik, dipakai navigasi tombol
      "emoji": "📊",           // emoji sub-topik
      "judul": "Kriteria Grade",
      "isi": "..."            // markdown Telegram klasik (*tebal*, _miring_, `kode`)
    }
  ]
}
```

Sumber konten: `~/workspace/qm-bantuan-qc/atlas/KRITERIA_GRADE_TABEL1.md`
dan `KODE_PENCATATAN.md` — jangan mengarang isi di luar dokumen acuan.

## Pembagian menu per bagian (BAGIAN)

Menu Bantuan QC dibagi per bagian divisi (keputusan user 2026-10-18):

| Bagian (tombol) | Seksi atlas |
|---|---|
| 📦 Bahan Baku | bahan_baku |
| 🏭 Jalur Utama | asam_panas, rolling_mill, asam_dingin |
| 🔧 Luar Jalur | penyelesaian |

Pemetaan ini didefinisikan di `qm_bantuan/data.py` (`BAGIAN`). Cari, daftar,
dan kuis otomatis terbatas pada bagian yang dipilih. Kartu cacat tetap bisa
dibuka global via kode.

## Topik prosedur per area (panduan.json)

Topik panduan bisa dikelompokkan per area/mesin dengan field opsional `grup`
(mis. `"grup": "🔧 Mesin FT"`). Topik bergrup tampil di menu **📋 Prosedur
Kerja** → pilih area → pilih topik. Topik tanpa `grup` tetap tampil di
**📘 Panduan Kerja** seperti biasa.

Menambah area baru (mis. Mesin FJ): tambah topik-topik dengan `grup` baru —
tanpa ubah kode, restart bot saja.
