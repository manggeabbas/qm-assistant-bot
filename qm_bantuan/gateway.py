"""Gateway layanan Bantuan QC: kamus cacat, daftar per bagian, latihan kilat, analisis foto.

Satu pintu ``handle(IncomingMessage) -> list[OutgoingMessage]`` dipakai router
sebagai ``qc_handler`` (pola yang sama dengan ``CoilGateway``). Otorisasi
ditangani router (user terdaftar, sama seperti layanan lain).

Semua tombol memakai *inline keyboard* (menempel di bawah pesan): tap tombol
TIDAK memposting pesan ke chat, sehingga riwayat chat tetap bersih.
Paginasi daftar mengedit pesan yang sama (editMessageText), bukan
mengirim pesan baru setiap halaman.

Skema callback_data (prefix ``qc:``):
    qc:menu | qc:bag:<bagian_id>
    qc:cari | qc:daftar | qc:kuis            (bagian diambil dari state)
    qc:page:<+1|-1> | qc:card:<kode> | qc:var:<kode>:<idx> | qc:lagi
    qc:foto | qc:panduan | qc:topik:<id>
    qc:prosedur | qc:pgrup:<grup> | qc:ptopik:<id>
    qc:jawab:<idx> | qc:stop
Tombol 🏠 Menu Utama memakai teks tombolnya sendiri sebagai callback_data
agar ditangkap router (aturan yang sama dengan tombol reply biasa).
"""

from __future__ import annotations

from pathlib import Path

from qm_training.bot.adapters.base import IncomingMessage, OutgoingMessage
from qm_training.core.errors import AIProviderError

from qm_bantuan.cards import defect_card, search_line, section_line, variant_summary
from qm_bantuan.data import BAGIAN_NAMES, BAGIAN_SECTIONS, Atlas, Panduan
from qm_bantuan.quiz import Quiz
from qm_bantuan.vision import is_transient_error

_DATA_DIR = Path(__file__).parent / "data"

# -- label tombol -------------------------------------------------------- #
BTN_BAHAN_BAKU = "📦 Bahan Baku"
BTN_JALUR_UTAMA = "🏭 Jalur Utama"
BTN_LUAR_JALUR = "🔧 Luar Jalur"
BTN_PHOTO = "📸 Analisis foto"
BTN_GUIDE = "📘 Panduan Kerja"
BTN_PROSEDUR = "📋 Prosedur Kerja"
BTN_BACK = "◀ Kembali"

_CB_MENU = "qc:menu"
_CB_FOTO = "qc:foto"
_CB_PANDUAN = "qc:panduan"
_CB_PROSEDUR = "qc:prosedur"
_CB_CARI = "qc:cari"
_CB_DAFTAR = "qc:daftar"
_CB_KUIS = "qc:kuis"
_CB_LAGI = "qc:lagi"
_CB_STOP = "qc:stop"

_BAGIAN_BUTTONS = {
    "bahan_baku": BTN_BAHAN_BAKU,
    "jalur_utama": BTN_JALUR_UTAMA,
    "luar_jalur": BTN_LUAR_JALUR,
}

# Keyword -> fitur. Format: (himpunan kata kunci, callback, label).
# Query yang memuat salah satu kata kunci menampilkan fitur terkait.
_FEATURE_KEYWORDS: list[tuple[set[str], str, str]] = [
    ({"form", "generator", "gulungan"}, "goto:coil", "📝 Form Generator"),
    ({"foto", "photo", "analisis", "gambar"}, "qc:foto", "📸 Analisis Foto"),
    ({"kuis", "latihan", "quiz"}, "qc:kuis_pilih", "🎯 Kuis"),
    ({"panduan", "aturan"}, "qc:panduan", "📘 Panduan Kerja"),
    ({"sop", "prosedur"}, "goto:qc_ft", "📋 SOP Mesin FT"),
    ({"pelatihan", "training", "diklat"}, "goto:training", "📚 Form Pelatihan"),
]

_PAGE_SIZE = 10
_QUIZ_N = 5
_MIME_BY_SUFFIX = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def _bagian_rows() -> list[list[tuple[str, str]]]:
    return [[(label, f"qc:bag:{bid}")] for bid, label in _BAGIAN_BUTTONS.items()]


class QCGateway:
    """Satu pintu masuk alur Bantuan QC untuk router."""

    def __init__(self, atlas: Atlas | None = None, ai_provider=None, panduan: Panduan | None = None) -> None:
        self.atlas = atlas or Atlas.bundled()
        self.ai_provider = ai_provider  # butuh .analyze_image(bytes, mime) utk foto
        self.panduan = panduan or Panduan.bundled()
        self._states: dict[str, dict] = {}
        self._seen_updates: dict[str, set] = {}

    # -- entrypoint ------------------------------------------------------ #
    def handle(self, message: IncomingMessage) -> list[OutgoingMessage]:
        user_id = str(message.user_id)

        # Idempotensi: abaikan update duplikat (foto tidak dianalisis 2x).
        if message.update_id is not None:
            seen = self._seen_updates.setdefault(user_id, set())
            if message.update_id in seen:
                return []
            seen.add(message.update_id)
            if len(seen) > 200:
                seen.clear()

        text = (message.text or "").strip()

        # Foto selalu diproses sebagai analisis (di mode QC mana pun).
        if message.photo_path:
            return self._handle_photo(message)

        if text in ("/qc", "/qc_kode"):
            return self._show_menu(user_id)
        if text == "/qc_panduan":
            return self._show_guide_list(user_id)
        if text == "/qc_ft":
            return self._show_ft_topics(user_id)
        if text == "/qc_sop_main":
            return self._show_sop_main_topics(user_id)

        # Tap tombol inline -> callback_data "qc:...".
        if text.startswith("qc:"):
            return self._handle_callback(user_id, message)

        # Tombol 🏠 (inline maupun ketik) selalu kembali ke menu utama.
        if text == BTN_BACK:
            return self._show_menu(user_id)

        # Kompatibilitas: label tombol lama yang diketik manual.
        if text in _BAGIAN_BUTTONS.values():
            bid = next(b for b, l in _BAGIAN_BUTTONS.items() if l == text)
            return self._show_bagian_menu(user_id, bid)

        state = self._states.get(user_id, {}).get("state", "menu")
        if state == "search":
            return self._do_search(user_id, text)
        if state == "photo":
            return [self._photo_prompt()]
        if state == "quiz":
            return [self._menu_hint()]
        if state == "bagian":
            # Pintasan: ketik langsung di submenu bagian = cari di bagian itu.
            return self._do_search(user_id, text)
        # Pencarian kilat lintas semua konten QC (cacat + panduan + prosedur).
        return self._quick_search(user_id, text)

    def _menu_hint(self) -> OutgoingMessage:
        return OutgoingMessage(
            "Pilih tombol di bawah pesan ya.",
            inline_buttons=_bagian_rows(),
        )

    # -- callback ---------------------------------------------------------- #
    def _handle_callback(
        self, user_id: str, message: IncomingMessage
    ) -> list[OutgoingMessage]:
        parts = (message.text or "").split(":")
        action = parts[1] if len(parts) > 1 else ""
        arg = ":".join(parts[2:]) if len(parts) > 2 else ""
        st = self._states.get(user_id, {})
        # ID pesan tempat tombol di-tap — dipakai untuk edit pesan yang
        # sama (paginasi daftar), bukan mengirim pesan baru.
        edit_id = message.callback_message_id

        if action == "menu":
            return self._show_menu(user_id)
        if action == "bag":
            return self._show_bagian_menu(user_id, arg)
        if action == "cari":
            return self._enter_search(user_id, st.get("bagian", ""))
        if action == "daftar":
            return self._show_page(user_id, st.get("bagian", ""), 0)
        if action == "kuis":
            return self._start_quiz(user_id, st.get("bagian", ""))
        if action == "page":
            try:
                delta = int(arg)
            except ValueError:
                delta = 0
            return self._show_page(
                user_id, st.get("bagian", ""), st.get("page", 0) + delta,
                edit_id=edit_id,
            )
        if action == "card":
            return self._show_card(user_id, arg)
        if action == "var":
            code, _, idx = arg.partition(":")
            try:
                return self._show_variant(user_id, code, int(idx))
            except ValueError:
                return self._show_card(user_id, code)
        if action == "lagi":
            return self._enter_search(user_id, st.get("bagian", ""))
        if action == "foto":
            return [self._show_photo_entry(user_id)]
        if action == "panduan":
            return self._show_guide_list(user_id)
        if action == "topik":
            return self._show_guide_topic(user_id, arg)
        if action == "prosedur":
            return self._show_prosedur_groups(user_id)
        if action == "ft":
            return self._show_ft_topics(user_id)
        if action == "main":
            return self._show_sop_main_topics(user_id)
        if action == "pgrup":
            return self._show_prosedur_topics(user_id, arg)
        if action == "ptopik":
            return self._show_prosedur_topic(user_id, arg)
        if action == "jawab":
            try:
                return self._quiz_answer(user_id, int(arg))
            except ValueError:
                return self._show_menu(user_id)
        if action == "stop":
            return self._quiz_finish(user_id)
        return self._show_menu(user_id)

    # -- menu ------------------------------------------------------------ #
    def _show_menu(self, user_id: str) -> list[OutgoingMessage]:
        """Menu Kode Cacat: pilih bagian / analisis foto."""
        self._states[user_id] = {"state": "menu"}
        return [
            OutgoingMessage(
                "🏷 *Kode Cacat*\n\n"
                "Referensi cepat standar cacat QC.\n"
                "Pilih bagian, atau *ketik kata kunci langsung* "
                "(mis. *C11*, *tergores*):",
                inline_buttons=_bagian_rows()
                + [
                    [(BTN_PHOTO, _CB_FOTO)],
                    [("◀ Inspeksi Lapangan", "menu:lapangan")],
                ],
                markdown=True,
            )
        ]

    # -- submenu per bagian ----------------------------------------------- #
    def _bagian_atlas(self, bagian_id: str) -> Atlas:
        return self.atlas.scoped(BAGIAN_SECTIONS.get(bagian_id, []))

    def _show_bagian_menu(self, user_id: str, bagian_id: str) -> list[OutgoingMessage]:
        if bagian_id not in _BAGIAN_BUTTONS:
            return self._show_menu(user_id)
        self._states[user_id] = {"state": "bagian", "bagian": bagian_id}
        nama = BAGIAN_NAMES.get(bagian_id, bagian_id)
        n = len(self._bagian_atlas(bagian_id))
        return [
            OutgoingMessage(
                f"{nama}\n\n{n} kode cacat. Mau apa?",
                inline_buttons=[
                    [("🔍 Cari", _CB_CARI)],
                    [("📖 Daftar", _CB_DAFTAR)],
                    [("🎯 Kuis", _CB_KUIS)],
                    [(BTN_BACK, _CB_MENU)],
                ],
                markdown=True,
            )
        ]

    def _back_to_bagian(self, bagian_id: str) -> list[tuple[str, str]]:
        return [(f"◀ {_BAGIAN_BUTTONS.get(bagian_id, 'Bagian')}", f"qc:bag:{bagian_id}")]

    # -- pencarian --------------------------------------------------------- #
    def _enter_search(self, user_id: str, bagian_id: str) -> list[OutgoingMessage]:
        if bagian_id not in _BAGIAN_BUTTONS:
            return self._show_menu(user_id)
        self._states[user_id] = {"state": "search", "bagian": bagian_id}
        nama = BAGIAN_NAMES.get(bagian_id, bagian_id)
        return [
            OutgoingMessage(
                f"🔍 *Cari cacat — {nama}*\n\n"
                "Ketik kata kunci (mis. *tergores*, *gelombang*) "
                "atau kode (mis. *C11*):",
                inline_buttons=[self._back_to_bagian(bagian_id)],
                markdown=True,
            )
        ]

    def _do_search(self, user_id: str, query: str) -> list[OutgoingMessage]:
        st = self._states.get(user_id, {})
        bagian_id = st.get("bagian", "")
        if not query:
            return self._enter_search(user_id, bagian_id)
        atlas = self._bagian_atlas(bagian_id)
        results = atlas.search(query, limit=8)
        if not results:
            return [
                OutgoingMessage(
                    f"Tidak ditemukan cacat untuk *{query}* "
                    f"di {BAGIAN_NAMES.get(bagian_id, '')}.\n\n"
                    "Coba kata kunci lain (mis. *gores*, *korosi*) "
                    "atau kode (mis. *B11*).",
                    inline_buttons=[
                        [("🔎 Cari lagi", _CB_LAGI)],
                        self._back_to_bagian(bagian_id),
                    ],
                    markdown=True,
                )
            ]
        if len(results) == 1:
            return self._show_card(user_id, results[0]["code"])
        rows = [[(search_line(e)[:38], f"qc:card:{e['code']}")] for e in results]
        rows.append([("🔎 Cari lagi", _CB_LAGI)])
        rows.append(self._back_to_bagian(bagian_id))
        self._states[user_id] = {"state": "search", "bagian": bagian_id}
        lines = "\n".join(f"• {search_line(e)}" for e in results)
        return [
            OutgoingMessage(
                f"Ditemukan {len(results)} cacat:\n\n{lines}\n\nPilih salah satu:",
                inline_buttons=rows,
            )
        ]

    # -- pencarian kilat (lintas semua konten) ----------------------------------- #
    def _feature_hits(self, query: str) -> list[tuple[str, str]]:
        """Fitur yang cocok dengan kata kunci pada query."""
        words = set((query or "").lower().split())
        return [(label, cb) for keys, cb, label in _FEATURE_KEYWORDS if words & keys]

    def _quick_search(self, user_id: str, query: str) -> list[OutgoingMessage]:
        """Ketik kata kunci di mana saja -> fitur + cacat + panduan + prosedur.

        Satu hasil -> langsung tampilkan/jalankan. Banyak -> daftar kelompok.
        """
        if not query:
            return [self._menu_hint()]
        features = self._feature_hits(query)
        defects = self.atlas.search(query, limit=8)
        topics = self.panduan.search(query, limit=6)
        guides = [t for t in topics if not (t.get("grup") or "").strip()]
        procs = [t for t in topics if (t.get("grup") or "").strip()]

        total = len(features) + len(defects) + len(guides) + len(procs)
        if total == 0:
            return [
                OutgoingMessage(
                    f"Tidak ditemukan hasil untuk *{query}*.\n\n"
                    "Coba kata kunci lain (mis. *tergores*, *korosi*, *kualitas*) "
                    "atau kode cacat (mis. *C11*).",
                    inline_buttons=_bagian_rows(),
                    markdown=True,
                )
            ]
        if total == 1:
            if defects:
                return self._show_card(user_id, defects[0]["code"])
            if guides:
                return self._show_guide_topic(user_id, guides[0]["id"])
            if procs:
                return self._show_prosedur_topic(user_id, procs[0]["id"])
            return self._run_feature(user_id, features[0])

        lines = [f'🔍 Hasil untuk *{query}*:\n']
        rows: list[list[tuple[str, str]]] = []
        if features:
            lines.append(f"⚙️ *Fitur* ({len(features)}):")
            for label, cb in features:
                lines.append(f"• {label}")
                rows.append([(label[:38], cb)])
        if defects:
            lines.append(f"\n🏷 *Cacat* ({len(defects)}):")
            for e in defects:
                lines.append(f"• {search_line(e)}")
                rows.append([(search_line(e)[:38], f"qc:card:{e['code']}")])
        if guides:
            lines.append(f"\n📘 *Panduan* ({len(guides)}):")
            for t in guides:
                lines.append(f"• {Panduan.label(t)}")
                rows.append([(Panduan.label(t)[:38], f"qc:topik:{t['id']}")])
        if procs:
            lines.append(f"\n📋 *Prosedur* ({len(procs)}):")
            for t in procs:
                lines.append(f"• {Panduan.label(t)}")
                rows.append([(Panduan.label(t)[:38], f"qc:ptopik:{t['id']}")])
        lines.append("\nPilih salah satu:")
        return [
            OutgoingMessage(
                "\n".join(lines), inline_buttons=rows, markdown=True
            )
        ]

    def _run_feature(
        self, user_id: str, feature: tuple[str, str]
    ) -> list[OutgoingMessage]:
        """Jalankan satu fitur hasil keyword. Fitur QC dijalankan langsung;
        fitur layanan lain ditampilkan sbg satu tombol lanjutan (router
        menangani ganti mode + otorisasinya)."""
        label, cb = feature
        if cb == "qc:foto":
            return [self._show_photo_entry(user_id)]
        if cb == "qc:panduan":
            return self._show_guide_list(user_id)
        if cb == "goto:qc_ft":
            return self._show_ft_topics(user_id)
        if cb == "qc:kuis_pilih":
            return [
                OutgoingMessage(
                    "🎯 *Kuis*\n\nPilih bagian untuk memulai kuis:",
                    inline_buttons=_bagian_rows()
                    + [[(BTN_BACK, _CB_MENU)]],
                    markdown=True,
                )
            ]
        return [
            OutgoingMessage(
                f"{label}\n\nTap tombol di bawah untuk membuka fitur ini:",
                inline_buttons=[[(label, cb)]],
                markdown=True,
            )
        ]

    # -- kartu -------------------------------------------------------------- #
    def _show_card(self, user_id: str, code: str) -> list[OutgoingMessage]:
        entry = self.atlas.get(code)
        if entry is None:
            return [self._menu_hint()]
        self._states[user_id] = {"state": "card", "code": code}
        variants = Atlas.variants(entry)
        if variants and Atlas.has_criteria(entry):
            rows = [
                [(v.get("jenis") or f"Jenis {i + 1}", f"qc:var:{code}:{i}")]
                for i, v in enumerate(variants)
            ]
            rows.append([(BTN_BACK, _CB_MENU)])
            return [
                OutgoingMessage(
                    variant_summary(entry), inline_buttons=rows, markdown=True
                )
            ]
        return [
            OutgoingMessage(
                defect_card(entry),
                inline_buttons=[[(BTN_BACK, _CB_MENU)]],
                markdown=True,
            )
        ]

    def _show_variant(self, user_id: str, code: str, index: int) -> list[OutgoingMessage]:
        entry = self.atlas.get(code)
        variants = Atlas.variants(entry) if entry else []
        if entry is None or not (0 <= index < len(variants)):
            return [self._menu_hint()]
        rows = [
            [(v.get("jenis") or f"Jenis {i + 1}", f"qc:var:{code}:{i}")]
            for i, v in enumerate(variants)
        ]
        rows.append([(BTN_BACK, _CB_MENU)])
        return [
            OutgoingMessage(
                defect_card(entry, variants[index]),
                inline_buttons=rows,
                markdown=True,
            )
        ]

    # -- daftar per bagian ---------------------------------------------------- #
    def _bagian_entries(self, bagian_id: str) -> list[dict]:
        """Semua entri bagian, urutan atlas dipertahankan."""
        entries = []
        for section in BAGIAN_SECTIONS.get(bagian_id, []):
            entries.extend(self.atlas.by_section(section))
        return entries

    def _show_page(
        self, user_id: str, bagian_id: str, page: int, edit_id: int | None = None
    ) -> list[OutgoingMessage]:
        if bagian_id not in _BAGIAN_BUTTONS:
            return self._show_menu(user_id)
        entries = self._bagian_entries(bagian_id)
        n_pages = max(1, (len(entries) + _PAGE_SIZE - 1) // _PAGE_SIZE)
        page = max(0, min(page, n_pages - 1))
        chunk = entries[page * _PAGE_SIZE : (page + 1) * _PAGE_SIZE]
        rows: list[list[tuple[str, str]]] = [
            [(section_line(e)[:38], f"qc:card:{e['code']}")] for e in chunk
        ]
        nav: list[tuple[str, str]] = []
        if page > 0:
            nav.append(("◀", "qc:page:-1"))
        if page < n_pages - 1:
            nav.append(("▶", "qc:page:+1"))
        if nav:
            rows.append(nav)
        rows.append(self._back_to_bagian(bagian_id))
        self._states[user_id] = {"state": "list", "bagian": bagian_id, "page": page}
        nama = BAGIAN_NAMES.get(bagian_id, bagian_id)
        return [
            OutgoingMessage(
                f"📖 *{nama}* — hal. {page + 1}/{n_pages}\n\nPilih kode:",
                inline_buttons=rows,
                markdown=True,
                edit_message_id=edit_id,
            )
        ]

    # -- panduan kerja ------------------------------------------------------------ #
    def _show_guide_list(self, user_id: str) -> list[OutgoingMessage]:
        self._states[user_id] = {"state": "guide"}
        rows = [
            [(Panduan.label(t), f"qc:topik:{t['id']}")] for t in self.panduan.topics()
        ]
        rows.append([("◀ Inspeksi Lapangan", "menu:lapangan")])
        return [
            OutgoingMessage(
                "📘 *Panduan Kerja*\n\n"
                "Aturan & tata cara kerja divisi QC "
                "(untuk karyawan baru maupun penyegaran).\n\n"
                "Pilih topik:",
                inline_buttons=rows,
                markdown=True,
            )
        ]

    def _show_guide_topic(self, user_id: str, topic_id: str) -> list[OutgoingMessage]:
        topic = self.panduan.get(topic_id)
        if topic is None:
            return self._show_guide_list(user_id)
        self._states[user_id] = {"state": "guide_topic", "topic": topic_id}
        # Pertahankan daftar topik agar user bisa pindah topik langsung.
        rows = [
            [(Panduan.label(t), f"qc:topik:{t['id']}")] for t in self.panduan.topics()
        ]
        rows.append([(BTN_BACK, _CB_PANDUAN)])
        title = f"{topic.get('emoji', '📘')} *{topic.get('judul', '')}*"
        return [
            OutgoingMessage(
                f"{title}\n\n{topic.get('isi', '')}",
                inline_buttons=rows,
                documents=self._topic_images(topic),
                markdown=True,
            )
        ]

    # -- prosedur kerja ---------------------------------------------------------- #
    def _show_prosedur_groups(self, user_id: str) -> list[OutgoingMessage]:
        self._states[user_id] = {"state": "prosedur"}
        rows = [[(g, f"qc:pgrup:{g}")] for g in self.panduan.groups()]
        rows.append([(BTN_BACK, _CB_MENU)])
        return [
            OutgoingMessage(
                "📋 *Prosedur Kerja*\n\n"
                "Tata cara inspeksi per area/mesin sesuai SOP.\n\n"
                "Pilih area:",
                inline_buttons=rows,
                markdown=True,
            )
        ]

    def _show_ft_topics(self, user_id: str) -> list[OutgoingMessage]:
        """Topik SOP Mesin FT langsung (pintu dari tree Inspeksi Luar Jalur)."""
        for g in self.panduan.groups():
            if "FT" in g.upper():
                return self._show_prosedur_topics(
                    user_id, g, back=(BTN_BACK, "menu:luar_jalur")
                )
        return self._show_prosedur_groups(user_id)

    def _show_sop_main_topics(self, user_id: str) -> list[OutgoingMessage]:
        """Topik SOP Inspeksi Jalur Utama (pintu dari tree Jalur Utama)."""
        for g in self.panduan.groups():
            if "Jalur Utama" in g:
                return self._show_prosedur_topics(
                    user_id, g, back=(BTN_BACK, "menu:jalur_utama")
                )
        return self._show_prosedur_groups(user_id)

    def _show_prosedur_topics(
        self,
        user_id: str,
        grup: str,
        back: tuple[str, str] | None = None,
    ) -> list[OutgoingMessage]:
        topics = self.panduan.by_group(grup)
        if not topics:
            return self._show_prosedur_groups(user_id)
        self._states[user_id] = {"state": "prosedur_topics", "grup": grup}
        rows = [[(Panduan.label(t), f"qc:ptopik:{t['id']}")] for t in topics]
        rows.append([back or (BTN_BACK, "qc:prosedur")])
        return [
            OutgoingMessage(
                f"📋 *Prosedur Kerja — {grup}*\n\nPilih topik:",
                inline_buttons=rows,
                markdown=True,
            )
        ]

    def _topic_images(self, topic: dict) -> list[Path]:
        """Lampiran gambar topik (mis. bagan) -> Path absolut bila ada."""
        name = (topic.get("gambar") or "").strip()
        if not name:
            return []
        p = _DATA_DIR / Path(name).name
        return [p] if p.is_file() else []

    def _show_prosedur_topic(self, user_id: str, topic_id: str) -> list[OutgoingMessage]:
        topic = self.panduan.get(topic_id)
        if topic is None:
            return self._show_prosedur_groups(user_id)
        grup = (topic.get("grup") or "").strip()
        self._states[user_id] = {"state": "prosedur_topic", "topic": topic_id}
        # Pertahankan daftar topik grup agar user bisa pindah topik langsung.
        rows = [
            [(Panduan.label(t), f"qc:ptopik:{t['id']}")]
            for t in self.panduan.by_group(grup)
        ]
        if "FT" in grup.upper():
            back_cb = "qc:ft"
        elif "Jalur Utama" in grup:
            back_cb = "qc:main"
        else:
            back_cb = "qc:prosedur"
        rows.append([(BTN_BACK, back_cb)])
        title = f"{topic.get('emoji', '📋')} *{topic.get('judul', '')}*"
        return [
            OutgoingMessage(
                f"{title}\n\n{topic.get('isi', '')}",
                inline_buttons=rows,
                documents=self._topic_images(topic),
                markdown=True,
            )
        ]

    # -- kuis ----------------------------------------------------------------- #
    def _start_quiz(self, user_id: str, bagian_id: str) -> list[OutgoingMessage]:
        if bagian_id not in _BAGIAN_BUTTONS:
            return self._show_menu(user_id)
        quiz = Quiz(self._bagian_atlas(bagian_id), n_questions=_QUIZ_N)
        self._states[user_id] = {"state": "quiz", "quiz": quiz, "bagian": bagian_id}
        return self._quiz_next(user_id)

    def _quiz_next(self, user_id: str) -> list[OutgoingMessage]:
        st = self._states.get(user_id, {})
        quiz: Quiz | None = st.get("quiz")
        if quiz is None:
            return self._show_menu(user_id)
        q = quiz.next_question()
        if q is None:
            return self._quiz_finish(user_id)
        st["options"] = list(q["options"])
        rows = [[(opt, f"qc:jawab:{i}")] for i, opt in enumerate(q["options"])]
        rows.append([("⏹ Selesai", _CB_STOP)])
        n = quiz.answered + 1
        nama = BAGIAN_NAMES.get(st.get("bagian", ""), "")
        return [
            OutgoingMessage(
                f"🎯 *Latihan kilat — {nama}* — soal {n}/{_QUIZ_N} (skor: {quiz.score})\n\n"
                f"{q['prompt']}",
                inline_buttons=rows,
                markdown=True,
            )
        ]

    def _quiz_answer(self, user_id: str, index: int) -> list[OutgoingMessage]:
        st = self._states.get(user_id, {})
        quiz: Quiz | None = st.get("quiz")
        options: list = st.get("options", [])
        if quiz is None or not (0 <= index < len(options)):
            return self._show_menu(user_id)
        ok, feedback = quiz.answer(options[index])
        out = [OutgoingMessage(feedback, markdown=True)]
        if quiz.done:
            out.extend(self._quiz_finish(user_id))
        else:
            out.extend(self._quiz_next(user_id))
        return out

    def _quiz_finish(self, user_id: str) -> list[OutgoingMessage]:
        st = self._states.get(user_id, {})
        quiz: Quiz | None = st.get("quiz")
        score = quiz.score if quiz else 0
        total = quiz.answered if quiz else 0
        self._states[user_id] = {"state": "menu"}
        if total == 0:
            text = "🎯 Latihan selesai — belum ada soal dijawab."
        elif score == total:
            text = f"🎯 *Sempurna!* Skor {score}/{total} 🌟"
        elif score * 2 >= total:
            text = f"🎯 Lumayan! Skor {score}/{total}. Terus latihan ya 💪"
        else:
            text = (
                f"🎯 Skor {score}/{total}.\n\n"
                "Coba buka kartu cacatnya lewat 🔍 Cari, "
                "lalu ulangi latihannya."
            )
        return [
            OutgoingMessage(
                text, inline_buttons=_bagian_rows(), markdown=True
            )
        ]

    # -- foto ------------------------------------------------------------------ #
    def _show_photo_entry(self, user_id: str) -> OutgoingMessage:
        self._states[user_id] = {"state": "photo"}
        return self._photo_prompt()

    def _photo_prompt(self) -> OutgoingMessage:
        return OutgoingMessage(
            "📸 *Analisis foto*\n\n"
            "Kirim foto permukaan cacat sebagai gambar (bukan dokumen).\n\n"
            "Tips: close-up, cahaya miring, sertakan penggaris/koin bila bisa.",
            inline_buttons=[[(BTN_BACK, _CB_MENU)]],
            markdown=True,
        )

    def _handle_photo(self, message: IncomingMessage) -> list[OutgoingMessage]:
        user_id = str(message.user_id)
        path = Path(message.photo_path)
        try:
            data = path.read_bytes()
        except OSError:
            return [
                OutgoingMessage(
                    "⚠️ Foto tidak bisa dibaca. Coba kirim ulang.",
                    inline_buttons=_bagian_rows(),
                )
            ]
        provider = self.ai_provider
        if provider is None or not hasattr(provider, "analyze_image"):
            return [
                OutgoingMessage(
                    "📸 Analisis foto belum tersedia — "
                    "AI belum dikonfigurasi di server.",
                    inline_buttons=_bagian_rows(),
                )
            ]
        mime = _MIME_BY_SUFFIX.get(path.suffix.lower(), "image/jpeg")
        self._states[user_id] = {"state": "menu"}
        try:
            result = provider.analyze_image(data, mime)
        except AIProviderError as exc:
            if is_transient_error(exc):
                text = (
                    "⚠️ Gemini sedang sibuk (server Google sedang penuh). "
                    "Sudah dicoba ulang tapi belum berhasil — "
                    "coba kirim ulang fotonya dalam 1–2 menit."
                )
            else:
                text = f"⚠️ Gagal menganalisis foto: {exc}"
            return [OutgoingMessage(text, inline_buttons=_bagian_rows())]
        except ValueError as exc:
            return [OutgoingMessage(f"⚠️ {exc}", inline_buttons=_bagian_rows())]
        return [
            OutgoingMessage(
                f"📸 *Hasil Analisis Foto*\n\n{result}\n\n"
                "⚠️ Ini opini kedua berbasis foto, bukan pengukuran. "
                "Keputusan akhir tetap oleh inspector di lini.",
                inline_buttons=_bagian_rows(),
                markdown=True,
            )
        ]
