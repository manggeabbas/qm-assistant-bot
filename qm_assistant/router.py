"""Router /start QM Assistant: 1 bot, 1 token, 3 alur.

Alur pesan:

    /start atau /menu
        -> menu (mode=menu): [📋 Form Gulungan] [📚 Form Pelatihan]
           (menu selalu terbuka; otorisasi dicek per layanan)
    pilih "📚 Form Pelatihan"
        -> mode=training, pesan sintetis "/new_training" diteruskan ke
           workflow qm_training (tidak ada perubahan di qm_training/).
           Otorisasi: owner ids / user store aktif / ALLOWED_TELEGRAM_USER_IDS.
    pilih "📋 Form Gulungan"
        -> mode=coil, diteruskan ke CoilGateway (qm_assistant/coil_gateway.py).
           Otorisasi milik Form Gulungan sendiri (SQLite): owner selalu
           lolos, user NEW redeem token undangan, REGISTRATION
           menyelesaikan NIK, BLOCKED ditolak. Dikelola via /admin.
    pilih "🔍 Bantuan QC"
        -> mode=qc, pesan sintetis "/qc" diteruskan ke QCGateway
           (qm_bantuan/gateway.py): kamus cacat, daftar per tahap,
           latihan kilat, analisis foto. Otorisasi sama seperti
           Form Pelatihan (user terdaftar).
    /cancel atau /batal (mode apa pun)
        -> kembali ke menu
    tombol "🏠 Menu Utama" (mode/layanan apa pun)
        -> kembali ke menu utama (sama seperti /start); router
           menambahkan tombol ini ke setiap pesan mode layanan agar
           user tidak perlu mengetik /start untuk berpindah fungsi.
"""

from __future__ import annotations

from dataclasses import replace

from qm_training.bot.adapters.base import IncomingMessage, OutgoingMessage

from qm_assistant.session import (
    MODE_COIL,
    MODE_MENU,
    MODE_QC,
    MODE_TRAINING,
    AssistantSessionStore,
)

BTN_COIL = "📋 Form Gulungan"
BTN_TRAINING = "📚 Form Pelatihan"
BTN_QC = "🔍 Bantuan QC"
BTN_ADMIN = "🛠 Admin"
BTN_HOME = "🏠 Menu Utama"

# Menu tree QM-YWI Assistant (lihat _tree_menu).
BTN_LAPANGAN = "🔍 Inspeksi Lapangan"
BTN_LAB = "🔬 Inspeksi Laboratorium"
BTN_HELP = "❓ Bantuan"

_MENU_COMMANDS = ("/start", "/menu")
_HELP_COMMANDS = ("/help", "/bantuan")
_CANCEL_COMMANDS = ("/cancel", "/batal")
_ADMIN_COMMANDS = ("/admin",)

# Navigasi tree: callback_data "menu:*" (tampil menu), "goto:*" (masuk
# layanan), "ph:*" (placeholder dokumen menyusul).
_TREE_MENUS = {
    "menu:lapangan": (
        "🔍 *Inspeksi Lapangan*\n\nPilih:",
        [
            [("🏷 Kode Cacat", "goto:qc_kode")],
            [("📘 Panduan Kerja", "goto:qc_panduan")],
            [("🏭 Inspeksi Jalur Utama", "menu:jalur_utama")],
            [("🔧 Inspeksi Luar Jalur", "menu:luar_jalur")],
            [(BTN_HOME, BTN_HOME)],
        ],
    ),
    "menu:jalur_utama": (
        "🏭 *Inspeksi Jalur Utama*\n\nPilih:",
        [
            [("📝 Form Generator", "goto:coil")],
            [("📋 SOP Inspeksi Jalur Utama", "goto:qc_sop_main")],
            [("◀ Inspeksi Lapangan", "menu:lapangan")],
        ],
    ),
    "menu:luar_jalur": (
        "🔧 *Inspeksi Luar Jalur*\n\nPilih:",
        [
            [("📋 SOP Mesin FT", "goto:qc_ft")],
            [("📋 SOP Mesin FJ", "ph:sop_fj")],
            [("📝 Form Generator FT/FJ", "goto:coil")],
            [("◀ Inspeksi Lapangan", "menu:lapangan")],
        ],
    ),
    "menu:lab": (
        "🔬 *Inspeksi Laboratorium*\n\nPilih:",
        [
            [("⚙️ Lab Mekanik/Fisika", "menu:lab_mekanik")],
            [("🧪 Lab Kimia", "menu:lab_kimia")],
            [(BTN_HOME, BTN_HOME)],
        ],
    ),
    "menu:lab_mekanik": (
        "⚙️ *Laboratorium Mekanik/Fisika*\n\nPilih uji:",
        [
            [("🔩 Uji Tarik", "ph:lab_tarik")],
            [("💎 Uji Kekerasan", "ph:lab_kekerasan")],
            [("⚛️ Uji Butiran", "ph:lab_butiran")],
            [("◀ Laboratorium", "menu:lab")],
        ],
    ),
    "menu:lab_kimia": (
        "🧪 *Laboratorium Kimia*\n\nDokumen SOP menyusul.",
        [[("◀ Laboratorium", "menu:lab")]],
    ),
}

_PLACEHOLDERS = {
    "ph:sop_fj": ("📋 SOP Mesin FJ", "menu:luar_jalur"),
    "ph:lab_tarik": ("🔩 Uji Tarik", "menu:lab_mekanik"),
    "ph:lab_kekerasan": ("💎 Uji Kekerasan", "menu:lab_mekanik"),
    "ph:lab_butiran": ("⚛️ Uji Butiran", "menu:lab_mekanik"),
}

# Layar bantuan (help:*): penjelasan cara pakai per layanan. Terbuka untuk
# semua user (hanya menjelaskan cara pakai, tanpa data perusahaan).
_HELP_BACK = ("◀ Bantuan", "help:menu")
_HELP_HOME = (BTN_HOME, BTN_HOME)
_HELP_SCREENS: dict[str, tuple[str, list[list[tuple[str, str]]]]] = {
    "help:menu": (
        "❓ *Bantuan — QM-YWI Assistant*\n\n"
        "Bot ini membantu inspeksi & pelatihan QC di CRP-YWI. "
        "Pilih topik bantuan di bawah.\n\n"
        "*Cara tercepat:* ketik kata kunci langsung di layar utama — "
        "mis. *B22*, *korosi*, *bagan* — tanpa masuk menu dulu.\n\n"
        "*Perintah umum:*\n"
        "• /start atau /menu — kembali ke menu utama\n"
        "• /help — buka bantuan ini\n"
        "• /cancel atau /batal — batalkan alur yang sedang berjalan\n"
        "• 🏠 Menu Utama — selalu ada di bawah pesan layanan",
        [
            [("📋 Form Gulungan", "help:coil")],
            [("🔍 Bantuan QC", "help:qc")],
            [("📚 Form Pelatihan", "help:training")],
            [("⌨️ Keyword & Pintasan", "help:keyword")],
            [_HELP_HOME],
        ],
    ),
    "help:coil": (
        "📋 *Form Gulungan — Form Generator*\n\n"
        "Membuat formulir gulungan (hasil akhir berbahasa Mandarin).\n\n"
        "*Cara pakai:*\n"
        "1. Buka 📝 Form Generator dari menu\n"
        "2. Pertama kali: tempel token undangan dari admin, lalu "
        "masukkan NIK — nama terisi otomatis dari direktori karyawan\n"
        "3. Pilih mesin (FT/FJ), isi data gulungan (material, "
        "spesifikasi, jumlah, nomor awal)\n"
        "4. Periksa preview penomoran & formulir, ubah bila perlu\n"
        "5. Generate — hasil Mandarin bisa disalin atau diunduh\n\n"
        "*Akses:* butuh token undangan + NIK terdaftar. "
        "Minta token ke admin.",
        [
            [("📝 Buka Form Generator", "goto:coil")],
            [_HELP_BACK],
            [_HELP_HOME],
        ],
    ),
    "help:qc": (
        "🔍 *Bantuan QC — Kode Cacat & Panduan*\n\n"
        "*Cara pakai:*\n"
        "• Ketik kode cacat (mis. *B22*) atau kata kunci (mis. "
        "*tergores*) — kartu penjelasan langsung tampil\n"
        "• Pilih bagian dulu (Bahan Baku / Jalur Utama / Luar Jalur) "
        "untuk Cari, Daftar, atau Kuis kilat\n"
        "• Kirim foto cacat untuk analisis: usahakan ada penggaris "
        "atau koin sebagai pembanding; format JPEG/PNG/WebP, "
        "maks 15 MB\n"
        "• 📘 Panduan Kerja: kriteria kualitas, prinsip penilaian, "
        "cacat batch, kode pencatatan\n"
        "• 📋 Prosedur: SOP Mesin FT & SOP Inspeksi Jalur Utama "
        "(+ bagan proses, ketik *bagan*)\n\n"
        "Hasil foto adalah pendapat kedua — keputusan akhir tetap "
        "mengikuti SOP.",
        [
            [("🏷 Buka Kode Cacat", "goto:qc_kode")],
            [_HELP_BACK],
            [_HELP_HOME],
        ],
    ),
    "help:training": (
        "📚 *Form Pelatihan*\n\n"
        "Membuat dokumen pelatihan/briefing QM dari materi yang "
        "diunggah.\n\n"
        "*Cara pakai:*\n"
        "1. Buka Form Pelatihan, kirim materi (teks/dokumen)\n"
        "2. Periksa tema yang dikenali AI — setujui atau ubah\n"
        "3. Lengkapi data: nomor arsip, tanggal, lokasi, trainer, "
        "regu, jumlah peserta\n"
        "4. Periksa 5 soal yang dibuat — setujui bila sudah tepat\n"
        "5. Tambah foto bila perlu, lalu tunggu dokumen jadi "
        "(DOCX & PDF)\n\n"
        "*Akses:* hanya ID Telegram terdaftar. Belum terdaftar? "
        "Minta admin mendaftarkan ID Anda (ID bisa dilihat lewat "
        "@userinfobot).",
        [
            [("📚 Buka Form Pelatihan", BTN_TRAINING)],
            [_HELP_BACK],
            [_HELP_HOME],
        ],
    ),
    "help:keyword": (
        "⌨️ *Keyword & Pintasan*\n\n"
        "Ketik langsung di layar utama (atau di area QC) — tidak "
        "perlu masuk menu:\n\n"
        "• Kode cacat: *B22*, *C11* → kartu cacat\n"
        "• Kata kunci: *korosi*, *kualitas*, *bagan* → hasil "
        "dikelompokkan\n"
        "• Fitur:\n"
        "  - *form / generator / gulungan* → Form Generator\n"
        "  - *foto / analisis* → Analisis Foto\n"
        "  - *kuis / latihan* → Kuis kilat\n"
        "  - *panduan* → Panduan Kerja\n"
        "  - *sop / prosedur* → SOP Mesin FT\n"
        "  - *pelatihan* → Form Pelatihan\n\n"
        "Satu hasil langsung dibuka; banyak hasil ditampilkan "
        "sebagai daftar tombol.",
        [
            [_HELP_BACK],
            [_HELP_HOME],
        ],
    ),
}


class AssistantRouter:
    """Menerima IncomingMessage, mengembalikan list[OutgoingMessage].

    ``training_workflow`` adalah instance ``qm_training.bot.workflow.Workflow``
    (dibangun oleh ``qm_training.app.build_workflow``). ``coil_handler``
    adalah ``qm_assistant.coil_gateway.CoilGateway``. ``qc_handler`` adalah
    ``qm_bantuan.gateway.QCGateway`` (boleh None -> layanan dinonaktifkan).
    """

    def __init__(
        self, training_workflow, coil_handler, qc_handler=None, store: AssistantSessionStore | None = None
    ) -> None:
        self.training = training_workflow
        self.coil = coil_handler
        self.qc = qc_handler
        self.store = store or AssistantSessionStore()

    # -- entrypoint (dipakai TelegramBotAdapter sebagai .handle) ------------- #

    def handle(self, message: IncomingMessage) -> list[OutgoingMessage]:
        text = (message.text or "").strip()
        lowered = text.lower()

        # Menu & batal selalu terbuka: pintu masuk, otorisasi per layanan.
        # Tombol 🏠 Menu Utama juga kembali ke menu dari mana pun.
        if lowered in _MENU_COMMANDS or text == BTN_HOME:
            self.store.reset(message.user_id)
            return [self._menu_message(message.user_id)]

        # Bantuan: perintah /help & /bantuan dari mode apa pun (mode
        # tidak diubah — user bisa kembali lewat tombol 🏠).
        if lowered in _HELP_COMMANDS or text == BTN_HELP:
            return [self._help_screen("help:menu")]

        # Layar bantuan (help:*) dari tombol inline.
        if text.startswith("help:"):
            return [self._help_screen(text)]

        # Navigasi tree menu (menu:* tampil menu, goto:* masuk layanan,
        # ph:* placeholder). Dicegat sebelum dispatch mode agar berlaku
        # dari alur mana pun.
        if text.startswith("menu:"):
            return [self._tree_menu(message.user_id, text)]
        if text.startswith("goto:"):
            return self._tree_goto(message, text)
        if text.startswith("ph:"):
            return [self._placeholder(text)]

        # Callback Bantuan QC ("qc:...") dari tombol inline: selalu
        # diteruskan ke gateway QC — hasil keyword di layar utama memakai
        # tombol ini, jadi harus berfungsi dari mode apa pun.
        if text.startswith("qc:"):
            if not self._authorized(message.user_id):
                return [self._denied_message(message.user_id)]
            self.store.set_mode(message.user_id, MODE_QC)
            if self.qc is None:
                return [OutgoingMessage("Layanan Bantuan QC belum aktif.")]
            return self._with_home(self.qc.handle(message))

        if lowered in _CANCEL_COMMANDS:
            self.store.reset(message.user_id)
            return [
                OutgoingMessage(
                    "Dibatalkan.", inline_buttons=self._menu_inline_buttons(message.user_id)
                )
            ]

        # /admin global: bisa diketik dari mode apa pun. Gateway
        # memverifikasi owner (ADMIN_DENIED bila bukan owner).
        if lowered in _ADMIN_COMMANDS:
            self.store.set_mode(message.user_id, MODE_COIL)
            return self._with_home(self.coil.handle(replace(message, text="/admin")))

        # Menu khusus admin: hanya owner yang melihat tombolnya; gateway
        # memverifikasi ulang (ADMIN_DENIED bila bukan owner).
        if text == BTN_ADMIN:
            self.store.set_mode(message.user_id, MODE_COIL)
            return self._with_home(self.coil.handle(replace(message, text="/admin")))

        # Pindah layanan via tombol: berlaku dari mode apa pun.
        # (Tanpa ini, user yang sedang di mode coil tidak bisa pindah ke
        # Form Pelatihan lewat tombol — terjebak sampai kirim /menu.)
        if text == BTN_TRAINING:
            if not self._authorized(message.user_id):
                return [self._denied_message(message.user_id)]
            self.store.set_mode(message.user_id, MODE_TRAINING)
            # Mulai alur training tanpa menyentuh /start-nya workflow.
            return self._with_home(
                self.training.handle(replace(message, text="/new_training"))
            )
        if text == BTN_COIL:
            self.store.set_mode(message.user_id, MODE_COIL)
            # Masuk coil sebagai perintah "/coil" (bukan label tombol),
            # agar gateway menyambut sesuai status: NEW -> minta token,
            # REGISTRATION -> lanjutkan registrasi, ACTIVE -> menu coil.
            # (Tanpa ini, label "📋 Form Gulungan" dianggap upaya token
            # oleh user NEW dan dijawab "Token tidak valid".)
            return self._with_home(self.coil.handle(replace(message, text="/coil")))

        # Pindah ke Bantuan QC (tombol lama, kompatibilitas): otorisasi
        # sama seperti Form Pelatihan. Gateway menerima "/qc" sintetis.
        if text == BTN_QC:
            if not self._authorized(message.user_id):
                return [self._denied_message(message.user_id)]
            self.store.set_mode(message.user_id, MODE_QC)
            if self.qc is None:
                return [OutgoingMessage("Layanan Bantuan QC belum aktif.")]
            return self._with_home(self.qc.handle(replace(message, text="/qc")))

        mode = self.store.get_mode(message.user_id)

        if mode == MODE_MENU:
            return self._menu_text(message)

        if mode == MODE_TRAINING:
            if not self._authorized(message.user_id):
                return [self._denied_message(message.user_id)]
            return self._with_home(self.training.handle(message))

        if mode == MODE_QC:
            if not self._authorized(message.user_id):
                return [self._denied_message(message.user_id)]
            if self.qc is None:
                return [OutgoingMessage("Layanan Bantuan QC belum aktif.")]
            return self._with_home(self.qc.handle(message))

        # mode == MODE_COIL: otorisasi milik gateway (invite/registrasi/DB).
        return self._with_home(self.coil.handle(message))

    # -- menu tree ------------------------------------------------------------ #

    def _menu_text(self, message: IncomingMessage) -> list[OutgoingMessage]:
        """Teks bebas / foto yang diketik di layar utama (mode menu).

        User terdaftar: keyword langsung dicari lewat pencarian kilat QC
        dan foto langsung dianalisis — tanpa masuk menu dulu. Mode
        berpindah ke QC agar tombol pada hasil tetap berfungsi. Selain
        itu (atau user belum terdaftar) tampilkan menu utama lagi.
        """
        has_input = bool((message.text or "").strip()) or (
            message.photo_path is not None
        )
        if has_input and self.qc is not None and self._authorized(message.user_id):
            self.store.set_mode(message.user_id, MODE_QC)
            return self._with_home(self.qc.handle_from_home(message))
        return [self._menu_message(message.user_id)]

    def _help_screen(self, key: str) -> OutgoingMessage:
        """Satu layar bantuan; kunci tak dikenal -> menu bantuan."""
        text, rows = _HELP_SCREENS.get(key, _HELP_SCREENS["help:menu"])
        return OutgoingMessage(
            text, inline_buttons=[list(r) for r in rows], markdown=True
        )

    def _tree_menu(self, user_id: str, key: str) -> OutgoingMessage:
        """Tampilkan satu level menu tree. Mode direset ke menu."""
        self.store.set_mode(user_id, MODE_MENU)
        text, rows = _TREE_MENUS.get(key, _TREE_MENUS["menu:lapangan"])
        return OutgoingMessage(text, inline_buttons=[list(r) for r in rows], markdown=True)

    def _tree_goto(self, message: IncomingMessage, target: str) -> list[OutgoingMessage]:
        """Masuk layanan dari tree: delegasi ke gateway yang sesuai."""
        user_id = message.user_id
        qc_entries = {
            "goto:qc_kode": "/qc_kode",
            "goto:qc_panduan": "/qc_panduan",
            "goto:qc_ft": "/qc_ft",
            "goto:qc_sop_main": "/qc_sop_main",
        }
        if target in qc_entries:
            if not self._authorized(user_id):
                return [self._denied_message(user_id)]
            self.store.set_mode(user_id, MODE_QC)
            if self.qc is None:
                return [OutgoingMessage("Layanan Bantuan QC belum aktif.")]
            return self._with_home(
                self.qc.handle(replace(message, text=qc_entries[target]))
            )
        if target == "goto:coil":
            self.store.set_mode(user_id, MODE_COIL)
            return self._with_home(self.coil.handle(replace(message, text="/coil")))
        if target == "goto:training":
            if not self._authorized(user_id):
                return [self._denied_message(user_id)]
            self.store.set_mode(user_id, MODE_TRAINING)
            return self._with_home(
                self.training.handle(replace(message, text="/new_training"))
            )
        return [self._menu_message(user_id)]

    def _placeholder(self, key: str) -> OutgoingMessage:
        label, parent = _PLACEHOLDERS.get(key, ("📄 Dokumen", "menu:lapangan"))
        return OutgoingMessage(
            f"{label}\n\n📄 *Dokumen menyusul.*\n\n"
            "SOP untuk bagian ini belum tersedia di bot. "
            "Kirim dokumennya untuk dimasukkan.",
            inline_buttons=[
                [("◀ Kembali", parent)],
                [(BTN_HOME, BTN_HOME)],
            ],
            markdown=True,
        )

    # -- helpers ------------------------------------------------------------ #

    def _menu_buttons(self, user_id: str | None = None) -> list[str]:
        buttons = [BTN_LAPANGAN, BTN_LAB, BTN_TRAINING]
        if user_id is not None and self._is_coil_owner(user_id):
            buttons.append(BTN_ADMIN)
        return buttons

    def _menu_inline_buttons(
        self, user_id: str | None = None
    ) -> list[list[tuple[str, str]]]:
        """Tombol inline menu utama (tree). Cabang memakai callback menu:*;
        Form Pelatihan & Admin memakai labelnya sendiri agar ditangkap
        pengecekan teks yang sudah ada."""
        rows: list[list[tuple[str, str]]] = [
            [(BTN_LAPANGAN, "menu:lapangan")],
            [(BTN_LAB, "menu:lab")],
            [(BTN_TRAINING, BTN_TRAINING)],
            [(BTN_HELP, "help:menu")],
        ]
        if user_id is not None and self._is_coil_owner(user_id):
            rows.append([(BTN_ADMIN, BTN_ADMIN)])
        return rows

    def _is_coil_owner(self, user_id: str) -> bool:
        """Owner Form Gulungan (pengelola /admin)."""
        owner_ids = getattr(self.coil, "owner_ids", None) or ()
        return str(user_id) in {str(o) for o in owner_ids}

    def _menu_message(self, user_id: str | None = None) -> OutgoingMessage:
        return OutgoingMessage(
            "🤖 *QM-YWI Assistant*\n\n"
            "Pilih layanan yang Anda butuhkan:\n\n"
            "💡 Bisa juga ketik kata kunci langsung di sini "
            "(mis. *B22*) atau buka ❓ Bantuan.",
            inline_buttons=self._menu_inline_buttons(user_id),
            markdown=True,
        )

    def _with_home(
        self, messages: list[OutgoingMessage]
    ) -> list[OutgoingMessage]:
        """Tambahkan tombol 🏠 Menu Utama ke pesan mode layanan.

        Router mencegat tombol ini sebelum dispatch (lihat handle()),
        jadi user bisa kembali ke menu utama dari alur mana pun tanpa
        mengetik /start. Tidak ditambahkan ke pesan menu utama itu
        sendiri.

        Untuk pesan bertombol inline, home ditambahkan sebagai baris
        inline (callback_data = teks tombolnya, ditangkap router sama
        seperti tombol reply) agar tidak memunculkan reply keyboard.
        """
        out = []
        for message in messages:
            if message.inline_buttons:
                rows = [list(r) for r in message.inline_buttons]
                if not any(t == BTN_HOME for r in rows for t, _ in r):
                    rows.append([(BTN_HOME, BTN_HOME)])
                out.append(replace(message, inline_buttons=rows))
                continue
            buttons = list(message.buttons or [])
            if BTN_HOME not in buttons:
                buttons.append(BTN_HOME)
            out.append(replace(message, buttons=buttons))
        return out

    def _authorized(self, user_id: str) -> bool:
        """Delegasi ke Workflow.is_authorized (satu aturan untuk semua)."""
        return bool(self.training.is_authorized(user_id))

    def _denied_message(self, user_id: str) -> OutgoingMessage:
        return OutgoingMessage(
            "⛔ Anda belum terdaftar.\n"
            f"ID Telegram Anda: {user_id}\n"
            "Minta admin menambahkan ID ini untuk mendapat akses."
        )
