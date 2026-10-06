"""Telegram workflow state machine (transport-agnostic).

The workflow consumes :class:`IncomingMessage` and returns
:class:`OutgoingMessage` objects. Transport (real Telegram vs mock) lives in
``qm_training.bot.adapters``.
"""

from __future__ import annotations

import logging
from pathlib import Path

from qm_training.ai.service import AIService
from qm_training.bot.adapters.base import IncomingMessage, OutgoingMessage
from qm_training.bot.session import Session, SessionStore
from qm_training.bot.states import State
from qm_training.core.config import Settings
from qm_training.core.users import UserStore
from qm_training.core.errors import (
    AIProviderError,
    ConversionError,
    DocumentGenerationError,
    MaterialError,
    QMTrainingError,
    SchemaError,
    ValidationError,
)
from qm_training.document.engine import generate as default_generate
from qm_training.document.pdf import convert_to_pdf as default_convert
from qm_training.document.schema import QAPair, TrainingData
from qm_training.material import read_material
from qm_training.material.title import extract_title
from qm_training.validation.docx_validator import missing_questions
from qm_training.validation.pipeline import raise_if_invalid, validate_document

logger = logging.getLogger(__name__)

BTN_USE_THEME = "✅ Gunakan Tema Ini"
BTN_EDIT_THEME = "✏️ Edit Tema"
BTN_CONFIRM = "✅ Konfirmasi"
BTN_EDIT_DATA = "✏️ Edit Data"
BTN_REGENERATE = "🔄 Generate Ulang"
BTN_EDIT_Q = "✏️ Edit Pertanyaan"
BTN_DONE = "✅ Selesai"
BTN_SKIP = "⏭️ Lewati"

_USE_THEME = {BTN_USE_THEME.lower(), "gunakan", "gunakan tema", "1", "ya", "ok"}
_EDIT_THEME = {BTN_EDIT_THEME.lower(), "edit", "edit tema"}
_CONFIRM = {BTN_CONFIRM.lower(), "konfirmasi", "ya", "ok", "lanjut"}
_EDIT_DATA = {BTN_EDIT_DATA.lower(), "edit data"}
_REGENERATE = {BTN_REGENERATE.lower(), "generate ulang", "regenerate", "ulang"}
_EDIT_Q = {BTN_EDIT_Q.lower(), "edit pertanyaan"}
_DONE = {BTN_DONE.lower(), "selesai", "done", "sudah"}
_SKIP = {BTN_SKIP.lower(), "lewati", "skip"}

_DATA_FIELDS = ("theme", "archive_number", "training_date", "location", "trainer", "shift_group", "personnel_count")


class Workflow:
    def __init__(
        self,
        store: SessionStore,
        ai_service: AIService,
        settings: Settings | None = None,
        generate_docx=default_generate,
        convert_pdf=default_convert,
        validate=validate_document,
        user_store: UserStore | None = None,
    ) -> None:
        self.store = store
        self.ai = ai_service
        self.settings = settings or Settings(ai_provider="mock")
        self.generate_docx = generate_docx
        self.convert_pdf = convert_pdf
        self.validate = validate
        self.users = user_store or UserStore()
        # Owners can manage users. Default owners = the ALLOWED ids (bootstrap).
        self.owner_ids = set(self.settings.owner_user_ids or self.settings.allowed_user_ids)

    # -- entrypoint -------------------------------------------------------- #

    def handle(self, message: IncomingMessage) -> list[OutgoingMessage]:
        if not self._authorized(message.user_id):
            logger.info("unauthorized access attempt user_id=%s", message.user_id)
            return [
                OutgoingMessage(
                    "⛔ Anda belum terdaftar.\n"
                    f"ID Telegram Anda: {message.user_id}\n"
                    "Minta admin menambahkan ID ini untuk mendapat akses."
                )
            ]

        session = self.store.get(message.user_id)

        # Idempotency: the same Telegram update must be processed exactly once,
        # even if Telegram redelivers it or the bot restarts with offset=None.
        if self._is_duplicate(session, message):
            return []

        try:
            outgoing = self._route(session, message)
        except QMTrainingError as exc:
            session.state = State.ERROR.value
            session.error = str(exc)
            outgoing = [OutgoingMessage(f"❌ {exc}")]
        except Exception as exc:  # noqa: BLE001 - never let a handler crash the bot
            if session.state == State.PROCESSING_MATERIAL.value:
                session.state = State.WAITING_MATERIAL.value
            else:
                session.state = State.ERROR.value
            session.error = type(exc).__name__
            outgoing = [
                OutgoingMessage(
                    f"❌ Terjadi kesalahan saat memproses permintaan ({type(exc).__name__}).\n"
                    "Silakan coba lagi atau kirim /new_training."
                )
            ]

        self._mark_processed(session, message)
        self.store.save(session)
        return outgoing

    def _route(self, session: Session, message: IncomingMessage) -> list[OutgoingMessage]:
        text = self._norm(message.text)
        if text.startswith("/"):
            command_reply = self._handle_command(message, text)
            if command_reply is not None:
                return command_reply
        if text in ("/start", "/new_training", "/new"):
            session.reset_flow()
            session.state = State.WAITING_MATERIAL.value
            return [self._ask_material()]
        if text in ("/cancel", "/batal"):
            session.reset_flow()
            return [OutgoingMessage("Dibatalkan. Kirim /new_training untuk memulai lagi.")]
        return self._dispatch(session, message, text)

    @staticmethod
    def _is_duplicate(session: Session, message: IncomingMessage) -> bool:
        return message.update_id is not None and message.update_id in session.processed_update_ids

    @staticmethod
    def _mark_processed(session: Session, message: IncomingMessage) -> None:
        if message.update_id is None:
            return
        ids = list(session.processed_update_ids)
        if message.update_id not in ids:
            ids.append(message.update_id)
        session.processed_update_ids = ids[-50:]

    # -- authorization ----------------------------------------------------- #

    def _authorized(self, user_id: str) -> bool:
        uid = str(user_id)
        if uid in self.owner_ids:
            return True
        if self.users.is_active(uid):
            return True
        if not self.settings.allowed_user_ids:
            return True  # open/self-hosted mode (no allowlist configured)
        return uid in self.settings.allowed_user_ids

    def _role(self, user_id: str) -> str:
        uid = str(user_id)
        if uid in self.owner_ids:
            return "OWNER"
        return self.users.role_of(uid) or "USER"

    def _is_admin(self, user_id: str) -> bool:
        uid = str(user_id)
        return uid in self.owner_ids or self.users.is_admin(uid)

    # -- commands (user access management) --------------------------------- #

    def _handle_command(self, message: IncomingMessage, text: str) -> list[OutgoingMessage] | None:
        if text == "/whoami":
            return [OutgoingMessage(f"🆔 ID Anda: {message.user_id}\nRole: {self._role(message.user_id)}")]
        if text in ("/help", "/bantuan"):
            return [OutgoingMessage(self._help_text(message.user_id))]
        if text == "/users":
            return self._cmd_users(message)
        if text.startswith("/allow"):
            return self._cmd_allow(message, text)
        if text.startswith("/deny"):
            return self._cmd_deny(message, text)
        return None

    def _cmd_users(self, message: IncomingMessage) -> list[OutgoingMessage]:
        if not self._is_admin(message.user_id):
            return [OutgoingMessage("⛔ Perintah ini hanya untuk admin.")]
        lines = ["👥 Daftar user:"]
        listed = set()
        for uid in sorted(self.owner_ids):
            lines.append(f"- {uid} (OWNER, aktif)")
            listed.add(uid)
        for record in self.users.list_users():
            if record.user_id in listed:
                continue
            status = "aktif" if record.active else "nonaktif"
            lines.append(f"- {record.user_id} ({record.role}, {status})")
        lines.append("")
        lines.append("Kelola: /allow <id> [admin|user]  |  /deny <id>")
        return [OutgoingMessage("\n".join(lines))]

    def _cmd_allow(self, message: IncomingMessage, text: str) -> list[OutgoingMessage]:
        if not self._is_admin(message.user_id):
            return [OutgoingMessage("⛔ Perintah ini hanya untuk admin.")]
        parts = text.split()
        if len(parts) < 2 or not parts[1].strip():
            return [OutgoingMessage("Format: /allow <user_id> [admin|user]")]
        target = parts[1].strip()
        role = parts[2].upper() if len(parts) > 2 else "USER"
        if role not in ("USER", "ADMIN"):
            role = "USER"
        self.users.add(target, role=role)
        logger.info("user allowed target=%s role=%s by=%s", target, role, message.user_id)
        return [OutgoingMessage(f"✅ Akses diberikan ke `{target}` ({role}, aktif).", )]

    def _cmd_deny(self, message: IncomingMessage, text: str) -> list[OutgoingMessage]:
        if not self._is_admin(message.user_id):
            return [OutgoingMessage("⛔ Perintah ini hanya untuk admin.")]
        parts = text.split()
        if len(parts) < 2 or not parts[1].strip():
            return [OutgoingMessage("Format: /deny <user_id>")]
        target = parts[1].strip()
        if target in self.owner_ids:
            return [OutgoingMessage("⛔ Owner tidak dapat dinonaktifkan.")]
        if not self.users.set_active(target, False):
            return [OutgoingMessage(f"User `{target}` tidak ditemukan.")]
        logger.info("user denied target=%s by=%s", target, message.user_id)
        return [OutgoingMessage(f"🚫 Akses `{target}` dinonaktifkan.")]

    def _help_text(self, user_id: str) -> str:
        lines = [
            "🤖 Perintah tersedia:",
            "/new_training — mulai sesi dokumen baru",
            "/cancel — batalkan sesi",
            "/whoami — lihat ID & role Anda",
        ]
        if self._is_admin(user_id):
            lines += [
                "",
                "Admin:",
                "/users — daftar user",
                "/allow <id> [admin|user] — beri/aktifkan akses",
                "/deny <id> — nonaktifkan akses",
            ]
        return "\n".join(lines)

    # -- dispatch ---------------------------------------------------------- #

    def _dispatch(self, session: Session, message: IncomingMessage, text: str) -> list[OutgoingMessage]:
        state = session.state
        if state in (State.IDLE.value, State.COMPLETED.value, State.ERROR.value):
            return [OutgoingMessage("Kirim /new_training untuk memulai sesi baru.")]
        if state == State.WAITING_MATERIAL.value:
            return self._on_material(session, message)
        if state == State.WAITING_THEME_CONFIRMATION.value:
            return self._on_theme_confirmation(session, message, text)
        if state == State.WAITING_THEME_EDIT.value:
            return self._on_theme_edit(session, message)
        if state == State.WAITING_ARCHIVE.value:
            return self._capture(session, message, "archive_number", State.WAITING_DATE, self._ask_date)
        if state == State.WAITING_DATE.value:
            return self._capture(session, message, "training_date", State.WAITING_LOCATION, self._ask_location)
        if state == State.WAITING_LOCATION.value:
            return self._capture(session, message, "location", State.WAITING_TRAINER, self._ask_trainer)
        if state == State.WAITING_TRAINER.value:
            return self._capture(session, message, "trainer", State.WAITING_SHIFT_GROUP, self._ask_shift)
        if state == State.WAITING_SHIFT_GROUP.value:
            return self._capture(session, message, "shift_group", State.WAITING_PERSONNEL_COUNT, self._ask_personnel)
        if state == State.WAITING_PERSONNEL_COUNT.value:
            return self._on_personnel(session, message, text)
        if state == State.DATA_REVIEW.value:
            return self._on_data_review(session, message, text)
        if state == State.WAITING_QUESTION_CONFIRMATION.value:
            return self._on_question_confirmation(session, message, text)
        if state in (State.QUESTION_CONFIRMED.value, State.PHOTO_UPLOAD.value):
            return self._on_photo(session, message, text)
        return [OutgoingMessage("Status tidak dikenal. Kirim /new_training.")]

    # -- material & theme -------------------------------------------------- #

    def _on_material(self, session: Session, message: IncomingMessage) -> list[OutgoingMessage]:
        if message.document_path is None:
            return [self._ask_material()]
        session.state = State.PROCESSING_MATERIAL.value
        try:
            document = read_material(message.document_path)
        except MaterialError as exc:
            session.state = State.WAITING_MATERIAL.value
            return [
                OutgoingMessage(
                    f"❌ Materi tidak dapat dibaca: {exc}\n\n"
                    "Silakan upload ulang. Format: PDF, DOC, DOCX, PPT, PPTX, XLS, XLSX"
                )
            ]
        session.material_path = str(message.document_path)
        session.material_text = document.text()

        # THEME = ORIGINAL Indonesian title extracted from the document.
        # We never generate/translate/paraphrase a theme here.
        session.theme_extraction_calls += 1
        title, source = extract_title(document)
        if not title:
            session.theme_source = "manual_required"
            session.state = State.WAITING_THEME_EDIT.value
            logger.info("theme_source=manual_required session=%s", session.user_id)
            return [
                OutgoingMessage(
                    "❓ Judul berbahasa Indonesia tidak ditemukan di materi.\n"
                    "Silakan kirim Tema secara manual:"
                )
            ]
        session.theme = title
        session.theme_source = source
        session.theme_messages_sent += 1
        session.state = State.WAITING_THEME_CONFIRMATION.value
        logger.info(
            "theme_source=%s theme_extraction_calls=%s theme_messages_sent=%s session=%s",
            source,
            session.theme_extraction_calls,
            session.theme_messages_sent,
            session.user_id,
        )
        return [self._theme_preview(session)]

    def _on_theme_confirmation(self, session: Session, message: IncomingMessage, text: str) -> list[OutgoingMessage]:
        """Theme is a hard gate: only an explicit choice advances the flow."""
        if text in _USE_THEME:
            session.theme_confirmed = True
            session.state = State.WAITING_ARCHIVE.value
            return [self._ask_archive(session)]
        if text in _EDIT_THEME:
            session.state = State.WAITING_THEME_EDIT.value
            return [OutgoingMessage("✏️ Kirim tema baru:")]
        # Any other input (plain text, empty document update, stray photo) must
        # NOT advance to the archive step.
        return [self._theme_preview(session)]

    def _on_theme_edit(self, session: Session, message: IncomingMessage) -> list[OutgoingMessage]:
        new_theme = (message.text or "").strip()
        if not new_theme:
            return [OutgoingMessage("✏️ Kirim tema baru (teks):")]
        session.theme = new_theme
        session.theme_confirmed = True
        session.state = State.WAITING_ARCHIVE.value
        return [self._ask_archive(session)]

    # -- data capture ------------------------------------------------------ #

    def _capture(self, session: Session, message: IncomingMessage, field: str, next_state, ask_next) -> list[OutgoingMessage]:
        value = message.text.strip()
        if not value:
            return [ask_next(session)]
        setattr(session, field, value)
        session.state = next_state.value
        return [ask_next(session)]

    def _on_personnel(self, session: Session, message: IncomingMessage, text: str) -> list[OutgoingMessage]:
        if text in _SKIP:
            session.personnel_count = None
            session.personnel_set = True
        else:
            try:
                count = int(text)
                if count < 0:
                    raise ValueError
            except ValueError:
                return [OutgoingMessage("Masukkan angka jumlah personil, atau tekan ⏭️ Lewati.", buttons=[BTN_SKIP])]
            session.personnel_count = count
            session.personnel_set = True
        session.state = State.DATA_REVIEW.value
        return [self._data_summary(session)]

    def _on_data_review(self, session: Session, message: IncomingMessage, text: str) -> list[OutgoingMessage]:
        if session.awaiting and session.awaiting.startswith("field:"):
            field = session.awaiting.split(":", 1)[1]
            raw = message.text.strip()
            if field == "personnel_count":
                if raw.lower() in _SKIP:
                    session.personnel_count = None
                else:
                    try:
                        session.personnel_count = int(raw)
                    except ValueError:
                        return [OutgoingMessage("Jumlah personil harus angka atau Lewati.")]
                session.personnel_set = True
            else:
                setattr(session, field, raw)
            session.awaiting = None
            return [self._data_summary(session)]
        if text in _CONFIRM:
            return self._generate_questions(session)
        if text.startswith("edit:"):
            field = text.split(":", 1)[1]
            session.awaiting = f"field:{field}"
            return [OutgoingMessage(f"Kirim nilai baru untuk {field}:")]
        if text in _EDIT_DATA:
            return [self._edit_data_menu(session)]
        return [self._data_summary(session)]

    def _generate_questions(self, session: Session, force: bool = False) -> list[OutgoingMessage]:
        """Create the QuestionSet exactly once per session.

        If a QuestionSet already exists it is reused; the AI is never called a
        second time for the same preview (regeneration is explicit: force=True).
        """
        if session.questions and len(session.questions) == 5 and not force:
            logger.info("reuse question_set session=%s", session.user_id)
            if session.preview_sent >= 1:
                return []  # already previewed; never send a second preview
            session.state = State.WAITING_QUESTION_CONFIRMATION.value
            return [self._question_preview(session)]

        session.state = State.GENERATING_QUESTIONS.value
        try:
            pairs = self.ai.generate_questions(session.material_text or "", session.theme or "")
        except AIProviderError as exc:
            session.state = State.DATA_REVIEW.value
            return [OutgoingMessage(f"❌ Gagal membuat pertanyaan: {exc}")]
        session.questions = [{"question": pair.question, "answer": pair.answer} for pair in pairs]
        session.question_set_created = True
        session.generate_questions_calls += 1
        session.state = State.WAITING_QUESTION_CONFIRMATION.value
        logger.info(
            "question_set created session=%s calls=%s",
            session.user_id,
            session.generate_questions_calls,
        )
        return [self._question_preview(session)]

    def _on_question_confirmation(self, session: Session, message: IncomingMessage, text: str) -> list[OutgoingMessage]:
        if session.awaiting and session.awaiting.startswith("q:"):
            index = int(session.awaiting.split(":", 1)[1])
            new_question = message.text.strip()
            session.questions[index]["question"] = new_question
            try:
                session.questions[index]["answer"] = self.ai.generate_answer(
                    session.material_text or "", new_question
                )
            except AIProviderError:
                pass
            session.awaiting = None
            return [self._question_preview(session)]
        if text in _CONFIRM:
            if session.question_confirmed:
                return []  # idempotent: duplicate confirmation is ignored
            session.question_confirmed = True
            session.state = State.QUESTION_CONFIRMED.value
            logger.info("question confirmed session=%s", session.user_id)
            return [self._ask_photos(session)]
        if text in _REGENERATE:
            return self._generate_questions(session, force=True)
        if text in _EDIT_Q:
            return [
                OutgoingMessage(
                    "Pilih nomor pertanyaan yang ingin diedit:",
                    buttons=[f"edit_q:{i}" for i in range(1, 6)],
                )
            ]
        if text.startswith("edit_q:"):
            index = int(text.split(":", 1)[1]) - 1
            session.awaiting = f"q:{index}"
            return [OutgoingMessage(f"Kirim pertanyaan baru untuk nomor {index + 1}:")]
        # Never send a second "Preview Pertanyaan" on stray input.
        return [self._question_reminder(session)]

    # -- photos & generation ---------------------------------------------- #

    def _on_photo(self, session: Session, message: IncomingMessage, text: str) -> list[OutgoingMessage]:
        if message.photo_path is not None:
            session.photos.append(str(message.photo_path))
            session.state = State.PHOTO_UPLOAD.value
            return [
                OutgoingMessage(
                    f"📷 Foto diterima ({len(session.photos)}). Kirim lagi atau tekan ✅ Selesai.",
                    buttons=[BTN_DONE],
                )
            ]
        if text in _CONFIRM:
            return []  # duplicate question confirmation; ignore silently
        if text in _DONE:
            if session.document_generation >= 1:
                return []  # duplicate "Selesai": document already generated
            return self._finalize(session)
        return [self._ask_photos(session)]

    def _finalize(self, session: Session) -> list[OutgoingMessage]:
        session.state = State.GENERATING_DOCUMENT.value
        session.document_generation += 1
        data = TrainingData(
            theme=session.theme or "",
            archive_number=session.archive_number or "",
            training_date=session.training_date or "",
            location=session.location or "",
            trainer=session.trainer or "",
            shift_group=session.shift_group or "",
            personnel_count=session.personnel_count,
            questions=[QAPair(q["question"], q["answer"]) for q in session.questions],
            photos=[Path(p) for p in session.photos],
        )
        try:
            data.validate()
        except SchemaError as exc:
            session.state = State.PHOTO_UPLOAD.value
            return [OutgoingMessage(f"❌ Data tidak lengkap: {exc}")]

        out_dir = self.store.dir(session.user_id) / "output"
        try:
            docx_path = self.generate_docx(data, out_dir=out_dir)
        except DocumentGenerationError as exc:
            session.state = State.PHOTO_UPLOAD.value
            return [OutgoingMessage(f"❌ Gagal membuat DOCX: {exc}")]
        session.output_docx = str(docx_path)

        session.state = State.VALIDATING_DOCUMENT.value
        session.validation_runs += 1
        try:
            pdf_path = self.convert_pdf(docx_path, out_dir)
            session.output_pdf = str(pdf_path)
            report = self.validate(docx_path, pdf_path)
            # The DOCX itself must contain the confirmed QuestionSet.
            for question in missing_questions(docx_path, [q["question"] for q in session.questions]):
                report.error("QUESTION_MISSING", f"pertanyaan tidak ada di DOCX: {question[:50]}")
            self._log_document_diagnostics(session, pdf_path, report)
            raise_if_invalid(report)
        except (ConversionError, ValidationError) as exc:
            session.state = State.ERROR.value
            session.error = str(exc)
            session.validation_error_messages_sent += 1
            return [OutgoingMessage(f"❌ Dokumen gagal divalidasi: {exc}")]

        logger.info(
            "document generated session=%s generation=%s",
            session.user_id,
            session.document_generation,
        )
        session.state = State.COMPLETED.value
        return [
            OutgoingMessage(
                "✅ Dokumen selesai dan lolos validasi.",
                documents=[docx_path, pdf_path],
            )
        ]

    # -- message builders -------------------------------------------------- #

    @staticmethod
    def _log_document_diagnostics(session: Session, pdf_path, report) -> None:
        """Safe diagnostics only (no credentials, no document content)."""
        try:
            from qm_training.document.render import pdf_page_count

            pages = pdf_page_count(pdf_path)
        except Exception:  # noqa: BLE001
            pages = None
        blank_pages = [issue.message for issue in report.issues if issue.code == "BLANK_PAGE"]
        logger.info(
            "document_generation_calls=%s validation_runs=%s pdf_page_count=%s blank_pages=%s session=%s",
            session.document_generation,
            session.validation_runs,
            pages,
            blank_pages,
            session.user_id,
        )

    def _ask_material(self) -> OutgoingMessage:
        return OutgoingMessage(
            "📄 Kirim materi pelatihan.\nFormat: PDF, DOC, DOCX, PPT, PPTX, XLS, XLSX"
        )

    def _theme_preview(self, session: Session) -> OutgoingMessage:
        return OutgoingMessage(
            f"📚 Tema terdeteksi:\n\n{session.theme}",
            buttons=[BTN_USE_THEME, BTN_EDIT_THEME],
        )

    def _ask_archive(self, session: Session) -> OutgoingMessage:
        return OutgoingMessage("🔢 Masukkan Nomor Arsip:")

    def _ask_date(self, session: Session) -> OutgoingMessage:
        return OutgoingMessage("📅 Masukkan Tanggal Pelatihan (tanggal saja):")

    def _ask_location(self, session: Session) -> OutgoingMessage:
        return OutgoingMessage("📍 Masukkan Lokasi Pelatihan:")

    def _ask_trainer(self, session: Session) -> OutgoingMessage:
        return OutgoingMessage("🎤 Masukkan Trainer:")

    def _ask_shift(self, session: Session) -> OutgoingMessage:
        return OutgoingMessage("👥 Masukkan Shift/Regu:")

    def _ask_personnel(self, session: Session) -> OutgoingMessage:
        return OutgoingMessage("👥 Jumlah Personil Absen? (angka) atau lewati.", buttons=[BTN_SKIP])

    def _data_summary(self, session: Session) -> OutgoingMessage:
        personnel = f"{session.personnel_count}人" if session.personnel_count is not None else "—"
        lines = [
            "📋 KONFIRMASI DATA",
            "",
            f"Tema       : {session.theme}",
            f"No. Arsip  : {session.archive_number}",
            f"Tanggal    : {session.training_date}",
            f"Lokasi     : {session.location}",
            f"Trainer    : {session.trainer}",
            f"Shift/Regu : {session.shift_group}",
            f"Personil   : {personnel}",
        ]
        return OutgoingMessage("\n".join(lines), buttons=[BTN_CONFIRM, BTN_EDIT_DATA])

    def _edit_data_menu(self, session: Session) -> OutgoingMessage:
        return OutgoingMessage(
            "✏️ Pilih field yang ingin diedit:",
            buttons=[f"edit:{field}" for field in _DATA_FIELDS],
        )

    def _question_preview(self, session: Session) -> OutgoingMessage:
        session.preview_sent += 1
        logger.info("preview sent session=%s count=%s", session.user_id, session.preview_sent)
        lines = ["📝 Preview Pertanyaan:", ""]
        for index, item in enumerate(session.questions, start=1):
            lines.append(f"{index}. {item['question']}")
        return OutgoingMessage("\n".join(lines), buttons=[BTN_EDIT_Q, BTN_REGENERATE, BTN_CONFIRM])

    def _question_reminder(self, session: Session) -> OutgoingMessage:
        # Deliberately NOT a "Preview Pertanyaan" message: stray input while
        # waiting for confirmation must not resend the preview.
        return OutgoingMessage(
            "Silakan tekan ✅ Konfirmasi untuk melanjutkan, ✏️ Edit Pertanyaan, atau 🔄 Generate Ulang.",
            buttons=[BTN_EDIT_Q, BTN_REGENERATE, BTN_CONFIRM],
        )

    def _ask_photos(self, session: Session) -> OutgoingMessage:
        return OutgoingMessage(
            f"📷 Kirim foto dokumentasi (saat ini {len(session.photos)}). Tekan ✅ Selesai bila cukup.",
            buttons=[BTN_DONE],
        )

    @staticmethod
    def _norm(text: str) -> str:
        return (text or "").strip().lower()
