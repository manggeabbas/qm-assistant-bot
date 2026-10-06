"""Environment / dependency report (no secrets are printed).

Credential loading uses the single configuration source in
:mod:`qm_training.core.config` so that ``main.py`` and ``main.py --check``
behave identically.
"""

from __future__ import annotations

import importlib
import json
import os
import shutil
import sys
from pathlib import Path

from qm_training.core.config import DEFAULT_ENV_PATH, PROJECT_ROOT, env_file_status, load_dotenv

REQUIRED_PACKAGES = ("docx", "lxml", "PIL", "pypdf", "pptx", "openpyxl", "requests")
SYSTEM_BINARIES = ("pdftoppm", "pdftotext", "pdfinfo")
CREDENTIAL_KEYS = ("DEEPSEEK_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY", "TELEGRAM_BOT_TOKEN")


def check_environment(project_root: Path | None = None) -> dict:
    project_root = Path(project_root) if project_root else PROJECT_ROOT
    env_path = project_root / ".env" if project_root != PROJECT_ROOT else DEFAULT_ENV_PATH

    # Same loader as the normal startup path (Settings.from_env).
    load_dotenv(env_path)

    packages = {}
    for name in REQUIRED_PACKAGES:
        try:
            module = importlib.import_module(name)
            packages[name] = getattr(module, "__version__", "?") or "?"
        except Exception:  # noqa: BLE001
            packages[name] = None

    from qm_training.core.libreoffice import find_soffice

    credentials = {key: bool(os.environ.get(key)) for key in CREDENTIAL_KEYS}

    return {
        "python": sys.version.split()[0],
        "python_ok": sys.version_info >= (3, 10),
        "packages": packages,
        "packages_ok": all(packages.values()),
        "libreoffice": find_soffice(),
        "binaries": {name: shutil.which(name) for name in SYSTEM_BINARIES},
        "credentials_present": credentials,
        "env_file_present": env_path.exists(),
        "env_example_present": (project_root / ".env.example").exists(),
        "env_file": env_file_status(env_path),
        "ai_provider": os.environ.get("AI_PROVIDER", "deepseek"),
        "ai_model": os.environ.get("AI_MODEL") or "(default)",
    }


def main() -> int:
    report = check_environment()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    ok = report["python_ok"] and report["packages_ok"] and bool(report["libreoffice"])
    print("\nSTATUS:", "READY" if ok else "INCOMPLETE")
    if not report["libreoffice"]:
        print("CATATAN: LibreOffice tidak tersedia -> konversi PDF tidak dapat dijalankan.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
