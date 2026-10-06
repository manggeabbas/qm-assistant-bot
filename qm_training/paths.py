"""Central filesystem paths for the project."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

MASTER_TEMPLATE = PROJECT_ROOT / "templates" / "FORMAT PELATIHAN ADA PERTANYAAN.docx"

# Validated template mapping produced by Phase 1 (Template Laboratory).
TEMPLATE_MAP = PROJECT_ROOT / "template_lab" / "template_map.json"

OUTPUT_DIR = PROJECT_ROOT / "output"
SESSIONS_DIR = PROJECT_ROOT / "storage" / "sessions"
USERS_FILE = PROJECT_ROOT / "storage" / "users.json"
LAB_OUTPUT_DIR = OUTPUT_DIR / "template_lab"
