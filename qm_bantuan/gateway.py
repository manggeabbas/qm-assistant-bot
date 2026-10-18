"""Gateway layanan Bantuan QC: kamus cacat, daftar per bagian, latihan kilat, analisis foto.

Satu pintu ``handle(IncomingMessage) -> list[OutgoingMessage]`` dipakai router
sebagai ``qc_handler`` (pola yang sama dengan ``CoilGateway``). Otorisasi
ditangani router (user terdaftar, sama seperti layanan lain).

Alur (tombol = reply keyboard teks biasa):
    /qc -> menu: [📦 Bahan Baku] [🏭 Jalur Utama] [🔧 Luar Jalur]
                 [📸 Analisis foto] [📘 Panduan Kerja] [📋 Prosedur Kerja]
    bagian -> submenu: [🔍 Cari] [📖 Daftar] [🎯 Kuis] (terbatas pada bagian itu)
    🔍 -> ketik kata kunci/kode -> kartu (atau daftar pilihan bila banyak)
    📖 -> halaman kode (10/hal.) -> kartu
    🎯 -> kuis 5 soal acak dari bagian itu, skor sesi
    📸 -> kirim foto -> analisis Gemini (opini kedua, manusia memutuskan)
    📘 -> pilih topik -> isi panduan kerja (data-driven dari panduan.json)
    📋 -> pilih area (mis. Mesin FT) -> pilih topik prosedur
"""

from __future__ import annotations

from pathlib import Path

from qm_training.bot.adapters.base import IncomingMessage, OutgoingMessage
from qm_training.core.errors import AIProviderError

from qm_bantuan.cards import defect_card, search_line, section_line, variant_summary
from qm_bantuan.data import BAGIAN_NAMES, BAGIAN_SECTIONS, Atlas, Panduan
from qm_bantuan.quiz import Quiz
from qm_bantuan.vision import is_transient_error

# -- label tombol -------------------------------------------------------- #
BTN_BAHAN_BAKU = "📦 Bahan Baku"
BTN_JALUR_UTAMA = "🏭 Jalur Utama"
BTN_LUAR_JALUR = "🔧 Luar Jalur"
BTN_PHOTO = "📸 Analisis foto"
BTN_GUIDE = "📘 Panduan Kerja"
BTN_PROSEDUR = "📋 Prosedur Kerja"
BTN_BACK = "◀ Kembali"
BTN_SEARCH_AGAIN = "🔎 Cari lagi"
BTN_BAGIAN = "📑 Bagian"
BTN_PREV = "◀"
BTN_NEXT = "▶"
BTN_QUIZ_STOP = "⏹ Selesai"
# Submenu per bagian:
BTN_BAGIAN_SEARCH = "🔍 Cari"
BTN_BAGIAN_LIST = "📖 Daftar"
BTN_BAGIAN_QUIZ = "🎯 Kuis"

_MENU_BUTTONS = [BTN_BAHAN_BAKU, BTN_JALUR_UTAMA, BTN_LUAR_JALUR,
                 BTN_PHOTO, BTN_GUIDE, BTN_PROSEDUR]
_BAGIAN_BUTTONS = [BTN_BAGIAN_SEARCH, BTN_BAGIAN_LIST, BTN_BAGIAN_QUIZ]
_BAGIAN_BY_BUTTON = {
    BTN_BAHAN_BAKU: "bahan_baku",
    BTN_JALUR_UTAMA: "jalur_utama",
    BTN_LUAR_JALUR: "luar_jalur",
}
_PAGE_SIZE = 10
_QUIZ_N = 5
_MIME_BY_SUFFIX = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


class QCGateway:
    """Satu pintu masuk alur Bantuan QC untuk router."""

    def __init__(self, atlas: Atlas | None = None, ai_provider=None, panduan: Panduan | None = None) -> None:
        self.atlas = atlas or Atlas.bundled()
        self.ai_provider = ai_provider  # butuh .analyze_image(bytes, mime) utk foto
        self.panduan = panduan or Panduan.bundled()
        self._states: dict[str, dict] = {}
        self._labels: dict[str, dict[str, tuple]] = {}
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

        if text == "/qc":
            return self._show_menu(user_id)

        state = self._states.get(user_id, {}).get("state", "menu")

        # Tombol global antar-submenu.
        if text == BTN_BACK:
            return self._show_menu(user_id)

        # Tombol menu utama QC berlaku dari sub-state mana pun
        # (navigasi memaafkan: user tak perlu kembali dulu).
        if text in _MENU_BUTTONS:
            return self._enter(user_id, text)

        label_map = self._labels.get(user_id, {})
        if text in label_map:
            return self._handle_action(user_id, label_map[text])

        if state == "menu":
            if text in _MENU_BUTTONS:
                return self._enter(user_id, text)
            return [self._menu_hint()]

        if state == "search":
            return self._do_search(user_id, text)
        if state == "photo":
            return [
                OutgoingMessage(
                    "📸 Kirim *foto* permukaan cacat sebagai gambar "
                    "(bukan dokumen).\n\n"
                    "Tips: foto close-up, cahaya miring, sertakan "
                    "penggaris/koin sebagai pembanding bila bisa.",
                    buttons=[BTN_BACK],
                    markdown=True,
                )
            ]
        # state quiz/list/card: hanya via tombol.
        return [self._menu_hint()]

    # -- menu ------------------------------------------------------------ #
    def _show_menu(self, user_id: str) -> list[OutgoingMessage]:
        self._states[user_id] = {"state": "menu"}
        self._labels[user_id] = {}
        return [
            OutgoingMessage(
                "🔍 *Bantuan QC*\n\n"
                "Referensi cepat standar cacat & prosedur kerja QC.\n"
                "Pilih bagian dulu:",
                buttons=list(_MENU_BUTTONS),
                markdown=True,
            )
        ]

    def _menu_hint(self) -> OutgoingMessage:
        return OutgoingMessage(
            "Pilih salah satu tombol di bawah ya.",
            buttons=list(_MENU_BUTTONS),
        )

    def _enter(self, user_id: str, button: str) -> list[OutgoingMessage]:
        if button in _BAGIAN_BY_BUTTON:
            return self._show_bagian_menu(user_id, _BAGIAN_BY_BUTTON[button])
        if button == BTN_PHOTO:
            self._states[user_id] = {"state": "photo"}
            self._labels[user_id] = {}
            return [
                OutgoingMessage(
                    "📸 *Analisis foto*\n\n"
                    "Kirim foto permukaan cacat.\n\n"
                    "Tips: close-up, cahaya miring, sertakan "
                    "penggaris/koin bila bisa.",
                    buttons=[BTN_BACK],
                    markdown=True,
                )
            ]
        if button == BTN_GUIDE:
            return self._show_guide_list(user_id)
        if button == BTN_PROSEDUR:
            return self._show_prosedur_groups(user_id)
        return self._show_menu(user_id)

    # -- submenu per bagian ----------------------------------------------- #
    def _bagian_atlas(self, bagian_id: str) -> Atlas:
        return self.atlas.scoped(BAGIAN_SECTIONS.get(bagian_id, []))

    def _show_bagian_menu(self, user_id: str, bagian_id: str) -> list[OutgoingMessage]:
        self._states[user_id] = {"state": "bagian", "bagian": bagian_id}
        labels = {
            BTN_BAGIAN_SEARCH: ("bagian_search", bagian_id),
            BTN_BAGIAN_LIST: ("bagian_list", bagian_id),
            BTN_BAGIAN_QUIZ: ("bagian_quiz", bagian_id),
        }
        self._labels[user_id] = labels
        nama = BAGIAN_NAMES.get(bagian_id, bagian_id)
        n = len(self._bagian_atlas(bagian_id))
        return [
            OutgoingMessage(
                f"{nama}\n\n"
                f"{n} kode cacat. Mau apa?",
                buttons=list(_BAGIAN_BUTTONS) + [BTN_BACK],
                markdown=True,
            )
        ]

    def _enter_search(self, user_id: str, bagian_id: str) -> list[OutgoingMessage]:
        self._states[user_id] = {"state": "search", "bagian": bagian_id}
        self._labels[user_id] = {}
        nama = BAGIAN_NAMES.get(bagian_id, bagian_id)
        return [
            OutgoingMessage(
                f"🔍 *Cari cacat — {nama}*\n\n"
                "Ketik kata kunci (mis. *tergores*, *gelombang*) "
                "atau kode (mis. *C11*):",
                buttons=[BTN_BACK],
                markdown=True,
            )
        ]

    # -- aksi tombol (label map) ------------------------------------------ #
    def _handle_action(self, user_id: str, action: tuple) -> list[OutgoingMessage]:
        kind = action[0]
        if kind == "menu":
            return self._enter(user_id, action[1])
        if kind == "bagian":
            return self._show_bagian_menu(user_id, action[1])
        if kind == "bagian_search":
            return self._enter_search(user_id, action[1])
        if kind == "bagian_list":
            return self._show_page(user_id, action[1], 0)
        if kind == "bagian_quiz":
            return self._start_quiz(user_id, action[1])
        if kind == "search_again":
            st = self._states.get(user_id, {})
            return self._enter_search(user_id, st.get("bagian", ""))
        if kind == "card":
            return self._show_card(user_id, action[1])
        if kind == "variant":
            return self._show_variant(user_id, action[1], action[2])
        if kind == "page":
            st = self._states.get(user_id, {})
            return self._show_page(user_id, st.get("bagian", ""), st.get("page", 0) + action[1])
        if kind == "quiz_opt":
            return self._quiz_answer(user_id, action[1])
        if kind == "quiz_stop":
            return self._quiz_finish(user_id)
        if kind == "guide_topic":
            return self._show_guide_topic(user_id, action[1])
        if kind == "prosedur_group":
            return self._show_prosedur_topics(user_id, action[1])
        if kind == "prosedur_topic":
            return self._show_prosedur_topic(user_id, action[1])
        return self._show_menu(user_id)

    # -- pencarian --------------------------------------------------------- #
    def _do_search(self, user_id: str, query: str) -> list[OutgoingMessage]:
        st = self._states.get(user_id, {})
        bagian_id = st.get("bagian", "")
        if not query:
            return self._enter_search(user_id, bagian_id)
        atlas = self._bagian_atlas(bagian_id)
        results = atlas.search(query, limit=8)
        if not results:
            self._labels[user_id] = {"🔎 Cari lagi": ("search_again",)}
            return [
                OutgoingMessage(
                    f"Tidak ditemukan cacat untuk *{query}* "
                    f"di {BAGIAN_NAMES.get(bagian_id, '')}.\n\n"
                    "Coba kata kunci lain (mis. *gores*, *korosi*) "
                    "atau kode (mis. *B11*).",
                    buttons=["🔎 Cari lagi", BTN_BACK],
                    markdown=True,
                )
            ]
        if len(results) == 1:
            return self._show_card(user_id, results[0]["code"])
        labels: dict[str, tuple] = {}
        buttons = []
        for e in results:
            label = search_line(e)
            if len(label) > 40:
                label = label[:37] + "…"
            labels[label] = ("card", e["code"])
            buttons.append(label)
        labels["🔎 Cari lagi"] = ("search_again",)
        self._labels[user_id] = labels
        self._states[user_id] = {"state": "search_results"}
        lines = "\n".join(f"• {search_line(e)}" for e in results)
        return [
            OutgoingMessage(
                f"Ditemukan {len(results)} cacat:\n\n{lines}\n\nPilih salah satu:",
                buttons=buttons + ["🔎 Cari lagi", BTN_BACK],
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
            labels = {}
            buttons = []
            for i, v in enumerate(variants):
                label = v.get("jenis") or f"Jenis {i + 1}"
                labels[label] = ("variant", code, i)
                buttons.append(label)
            self._labels[user_id] = labels
            return [
                OutgoingMessage(
                    variant_summary(entry), buttons=buttons + [BTN_BACK], markdown=True
                )
            ]
        self._labels[user_id] = {}
        return [OutgoingMessage(defect_card(entry), buttons=[BTN_BACK], markdown=True)]

    def _show_variant(self, user_id: str, code: str, index: int) -> list[OutgoingMessage]:
        entry = self.atlas.get(code)
        variants = Atlas.variants(entry) if entry else []
        if entry is None or not (0 <= index < len(variants)):
            return [self._menu_hint()]
        labels = {}
        buttons = []
        for i, v in enumerate(variants):
            label = v.get("jenis") or f"Jenis {i + 1}"
            labels[label] = ("variant", code, i)
            buttons.append(label)
        self._labels[user_id] = labels
        return [
            OutgoingMessage(
                defect_card(entry, variants[index]),
                buttons=buttons + [BTN_BACK],
                markdown=True,
            )
        ]

    # -- daftar per bagian ---------------------------------------------------- #
    def _bagian_entries(self, bagian_id: str) -> list[dict]:
        """Semua entri bagian, urutan atlas dipertahankan."""
        sections = BAGIAN_SECTIONS.get(bagian_id, [])
        entries = []
        for section in sections:
            entries.extend(self.atlas.by_section(section))
        return entries

    def _show_page(self, user_id: str, bagian_id: str, page: int) -> list[OutgoingMessage]:
        entries = self._bagian_entries(bagian_id)
        n_pages = max(1, (len(entries) + _PAGE_SIZE - 1) // _PAGE_SIZE)
        page = max(0, min(page, n_pages - 1))
        chunk = entries[page * _PAGE_SIZE : (page + 1) * _PAGE_SIZE]
        labels: dict[str, tuple] = {}
        buttons = []
        for e in chunk:
            label = section_line(e)
            if len(label) > 40:
                label = label[:37] + "…"
            labels[label] = ("card", e["code"])
            buttons.append(label)
        nav = []
        if page > 0:
            labels[BTN_PREV] = ("page", -1)
            nav.append(BTN_PREV)
        if page < n_pages - 1:
            labels[BTN_NEXT] = ("page", +1)
            nav.append(BTN_NEXT)
        labels[BTN_BAGIAN] = ("bagian", bagian_id)
        self._labels[user_id] = labels
        self._states[user_id] = {"state": "list", "bagian": bagian_id, "page": page}
        nama = BAGIAN_NAMES.get(bagian_id, bagian_id)
        return [
            OutgoingMessage(
                f"📖 *{nama}* — hal. {page + 1}/{n_pages}\n\nPilih kode:",
                buttons=buttons + nav + [BTN_BAGIAN, BTN_BACK],
                markdown=True,
            )
        ]

    # -- panduan kerja ------------------------------------------------------------ #
    def _show_guide_list(self, user_id: str) -> list[OutgoingMessage]:
        self._states[user_id] = {"state": "guide"}
        labels: dict[str, tuple] = {}
        buttons = []
        for t in self.panduan.topics():
            label = Panduan.label(t)
            labels[label] = ("guide_topic", t["id"])
            buttons.append(label)
        self._labels[user_id] = labels
        return [
            OutgoingMessage(
                "📘 *Panduan Kerja*\n\n"
                "Aturan & tata cara kerja divisi QC "
                "(untuk karyawan baru maupun penyegaran).\n\n"
                "Pilih topik:",
                buttons=buttons + [BTN_BACK],
                markdown=True,
            )
        ]

    def _show_guide_topic(self, user_id: str, topic_id: str) -> list[OutgoingMessage]:
        topic = self.panduan.get(topic_id)
        if topic is None:
            return self._show_guide_list(user_id)
        self._states[user_id] = {"state": "guide_topic", "topic": topic_id}
        # Pertahankan daftar topik agar user bisa pindah topik langsung.
        labels: dict[str, tuple] = {}
        buttons = []
        for t in self.panduan.topics():
            label = Panduan.label(t)
            labels[label] = ("guide_topic", t["id"])
            buttons.append(label)
        self._labels[user_id] = labels
        title = f"{topic.get('emoji', '📘')} *{topic.get('judul', '')}*"
        return [
            OutgoingMessage(
                f"{title}\n\n{topic.get('isi', '')}",
                buttons=buttons + [BTN_BACK],
                markdown=True,
            )
        ]

    # -- kuis ----------------------------------------------------------------- #
    def _start_quiz(self, user_id: str, bagian_id: str) -> list[OutgoingMessage]:
        quiz = Quiz(self._bagian_atlas(bagian_id), n_questions=_QUIZ_N)
        self._states[user_id] = {"state": "quiz", "quiz": quiz, "bagian": bagian_id}
        return self._quiz_next(user_id)

    def _quiz_next(self, user_id: str) -> list[OutgoingMessage]:
        st = self._states.get(user_id, {})
        quiz: Quiz = st["quiz"]
        q = quiz.next_question()
        if q is None:
            return self._quiz_finish(user_id)
        labels = {}
        buttons = []
        for opt in q["options"]:
            labels[opt] = ("quiz_opt", opt)
            buttons.append(opt)
        labels[BTN_QUIZ_STOP] = ("quiz_stop",)
        self._labels[user_id] = labels
        n = quiz.answered + 1
        nama = BAGIAN_NAMES.get(st.get("bagian", ""), "")
        return [
            OutgoingMessage(
                f"🎯 *Latihan kilat — {nama}* — soal {n}/{_QUIZ_N} (skor: {quiz.score})\n\n"
                f"{q['prompt']}",
                buttons=buttons + [BTN_QUIZ_STOP],
                markdown=True,
            )
        ]

    def _quiz_answer(self, user_id: str, choice: str) -> list[OutgoingMessage]:
        st = self._states.get(user_id, {})
        quiz: Quiz | None = st.get("quiz")
        if quiz is None:
            return self._show_menu(user_id)
        ok, feedback = quiz.answer(choice)
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
        self._labels[user_id] = {}
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
        return [OutgoingMessage(text, buttons=list(_MENU_BUTTONS), markdown=True)]

    # -- prosedur kerja ---------------------------------------------------------- #
    def _show_prosedur_groups(self, user_id: str) -> list[OutgoingMessage]:
        self._states[user_id] = {"state": "prosedur"}
        labels: dict[str, tuple] = {}
        buttons = []
        for grup in self.panduan.groups():
            labels[grup] = ("prosedur_group", grup)
            buttons.append(grup)
        self._labels[user_id] = labels
        return [
            OutgoingMessage(
                "📋 *Prosedur Kerja*\n\n"
                "Tata cara inspeksi per area/mesin sesuai SOP.\n\n"
                "Pilih area:",
                buttons=buttons + [BTN_BACK],
                markdown=True,
            )
        ]

    def _show_prosedur_topics(self, user_id: str, grup: str) -> list[OutgoingMessage]:
        topics = self.panduan.by_group(grup)
        if not topics:
            return self._show_prosedur_groups(user_id)
        self._states[user_id] = {"state": "prosedur_topics", "grup": grup}
        labels: dict[str, tuple] = {}
        buttons = []
        for t in topics:
            label = Panduan.label(t)
            labels[label] = ("prosedur_topic", t["id"])
            buttons.append(label)
        self._labels[user_id] = labels
        return [
            OutgoingMessage(
                f"📋 *Prosedur Kerja — {grup}*\n\nPilih topik:",
                buttons=buttons + [BTN_BACK],
                markdown=True,
            )
        ]

    def _show_prosedur_topic(self, user_id: str, topic_id: str) -> list[OutgoingMessage]:
        topic = self.panduan.get(topic_id)
        if topic is None:
            return self._show_prosedur_groups(user_id)
        grup = (topic.get("grup") or "").strip()
        self._states[user_id] = {"state": "prosedur_topic", "topic": topic_id}
        # Pertahankan daftar topik grup agar user bisa pindah topik langsung.
        labels: dict[str, tuple] = {}
        buttons = []
        for t in self.panduan.by_group(grup):
            label = Panduan.label(t)
            labels[label] = ("prosedur_topic", t["id"])
            buttons.append(label)
        self._labels[user_id] = labels
        title = f"{topic.get('emoji', '📋')} *{topic.get('judul', '')}*"
        return [
            OutgoingMessage(
                f"{title}\n\n{topic.get('isi', '')}",
                buttons=buttons + [BTN_BACK],
                markdown=True,
            )
        ]

    # -- foto ------------------------------------------------------------------ #
    def _handle_photo(self, message: IncomingMessage) -> list[OutgoingMessage]:
        user_id = str(message.user_id)
        path = Path(message.photo_path)
        try:
            data = path.read_bytes()
        except OSError:
            return [
                OutgoingMessage(
                    "⚠️ Foto tidak bisa dibaca. Coba kirim ulang.",
                    buttons=list(_MENU_BUTTONS),
                )
            ]
        provider = self.ai_provider
        if provider is None or not hasattr(provider, "analyze_image"):
            return [
                OutgoingMessage(
                    "📸 Analisis foto belum tersedia — "
                    "AI belum dikonfigurasi di server.",
                    buttons=list(_MENU_BUTTONS),
                )
            ]
        mime = _MIME_BY_SUFFIX.get(path.suffix.lower(), "image/jpeg")
        self._states[user_id] = {"state": "menu"}
        self._labels[user_id] = {}
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
            return [
                OutgoingMessage(
                    text,
                    buttons=list(_MENU_BUTTONS),
                )
            ]
        except ValueError as exc:
            return [OutgoingMessage(f"⚠️ {exc}", buttons=list(_MENU_BUTTONS))]
        return [
            OutgoingMessage(
                f"📸 *Hasil Analisis Foto*\n\n{result}\n\n"
                "⚠️ Ini opini kedua berbasis foto, bukan pengukuran. "
                "Keputusan akhir tetap oleh inspector di lini.",
                buttons=list(_MENU_BUTTONS),
                markdown=True,
            )
        ]
