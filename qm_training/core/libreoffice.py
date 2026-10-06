"""LibreOffice headless helper (shared by PDF conversion and legacy readers)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

FLATPAK_APP = "org.libreoffice.LibreOffice"
PROFILE_DIR = Path.home() / ".cache" / "qm-template-lab-lo"


def find_soffice() -> str | None:
    for candidate in ("soffice", "libreoffice"):
        found = shutil.which(candidate)
        if found:
            return found
    if shutil.which("flatpak"):
        probe = subprocess.run(["flatpak", "info", FLATPAK_APP], capture_output=True, text=True)
        if probe.returncode == 0:
            return f"flatpak:{FLATPAK_APP}"
    return None


def run_soffice(args: list[str], timeout: int = 300) -> subprocess.CompletedProcess:
    soffice = find_soffice()
    if soffice is None:
        raise RuntimeError(
            "LibreOffice tidak ditemukan. Pasang:\n"
            "  sudo pacman -S libreoffice-fresh\n"
            "atau:\n"
            "  flatpak install --user -y flathub org.libreoffice.LibreOffice"
        )
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    common = [f"-env:UserInstallation=file://{PROFILE_DIR}", *args]
    if soffice.startswith("flatpak:"):
        app = soffice.split(":", 1)[1]
        command = ["flatpak", "run", "--command=libreoffice", "--filesystem=home", app, *common]
    else:
        command = [soffice, *common]
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout)


def convert(source: Path, target: str, out_dir: Path, timeout: int = 300) -> Path:
    """Convert a document and return the produced file path."""
    source = Path(source)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    result = run_soffice(
        ["--headless", "--convert-to", target, "--outdir", str(out_dir), str(source)],
        timeout=timeout,
    )
    extension = target.split(":", 1)[0]
    output = out_dir / f"{source.stem}.{extension}"
    if not output.exists():
        raise RuntimeError(f"konversi gagal ({target}): {result.stderr or result.stdout}")
    return output
