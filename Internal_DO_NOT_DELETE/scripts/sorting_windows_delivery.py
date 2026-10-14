from __future__ import annotations

import unicodedata
import zipfile
from pathlib import Path


def windows_delivery_zip_path(archive_root: Path) -> Path:
    return archive_root.parent / f"{archive_root.name}_windows.zip"


def create_windows_delivery_zip(archive_root: Path) -> Path:
    archive_root = archive_root.resolve()
    zip_path = windows_delivery_zip_path(archive_root)
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in sorted(archive_root.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(archive_root.parent)
            arcname = _zip_arcname(relative)
            info = zipfile.ZipInfo(arcname)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 0
            info.flag_bits |= 0x800  # UTF-8 filenames for Windows unzip tools.
            with path.open("rb") as source:
                zf.writestr(info, source.read())
    return zip_path


def _zip_arcname(relative_path: Path) -> str:
    parts = []
    for part in relative_path.parts:
        normalized = unicodedata.normalize("NFC", part).replace("\\", "_")
        parts.append(normalized)
    return "/".join(parts)
