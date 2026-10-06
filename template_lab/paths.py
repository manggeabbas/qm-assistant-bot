"""Central filesystem paths for the Template Laboratory."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

MASTER_TEMPLATE = PROJECT_ROOT / "templates" / "FORMAT PELATIHAN ADA PERTANYAAN.docx"

OUTPUT_DIR = PROJECT_ROOT / "output" / "template_lab"

# Machine-readable result of the template inspection (STEP 1/2).
TEMPLATE_INVENTORY = OUTPUT_DIR / "template_inventory.json"

# Mapping of logical fields to concrete positions inside the master (STEP 3).
TEMPLATE_MAP = PROJECT_ROOT / "template_lab" / "template_map.json"
