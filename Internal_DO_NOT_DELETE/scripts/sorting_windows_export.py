from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import zipfile


WINDOWS_RESERVED_NAMES = {
    "con", "prn", "aux", "nul",
    "com1", "com2", "com3", "com4", "com5", "com6", "com7", "com8", "com9",
    "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9",
}
WINDOWS_FORBIDDEN_CHARS = set('<>:"/\\|?*')
ZIP_BASED_EXTENSIONS = {".docx", ".xlsx", ".xlsm", ".odt", ".ods", ".odp"}
TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".tsv", ".json", ".xml", ".html", ".htm", ".eml", ".rtf"}
IMAGE_SIGNATURES = {
    ".jpg": [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
    ".png": [b"\x89PNG\r\n\x1a\n"],
    ".gif": [b"GIF87a", b"GIF89a"],
    ".bmp": [b"BM"],
    ".tif": [b"II*\x00", b"MM\x00*"],
    ".tiff": [b"II*\x00", b"MM\x00*"],
    ".webp": [b"RIFF"],
}


@dataclass(frozen=True)
class ValidationIssue:
    path: str
    message: str


def _is_windows_safe_component(component: str) -> str | None:
    if any(ch in WINDOWS_FORBIDDEN_CHARS for ch in component):
        return "contains Windows-forbidden characters"
    if component.rstrip(" .") != component:
        return "has trailing space or dot"
    stem = Path(component).stem.lower()
    if stem in WINDOWS_RESERVED_NAMES:
        return "uses Windows reserved filename"
    return None


def validate_windows_paths(root: Path) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        rel_str = str(rel)
        if len(rel_str) > 240:
            issues.append(ValidationIssue(rel_str, "relative path is too long for safe Windows export"))
        for component in rel.parts:
            reason = _is_windows_safe_component(component)
            if reason:
                issues.append(ValidationIssue(rel_str, reason))
                break
    return issues


def _validate_pdf(path: Path) -> str | None:
    data = path.read_bytes()
    if not data.startswith(b"%PDF"):
        return "PDF header is missing"
    if b"%%EOF" not in data[-2048:]:
        return "PDF EOF marker is missing"
    return None


def _validate_zip_container(path: Path) -> str | None:
    try:
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None:
                return "zip-based office file has a corrupted member"
            if not archive.namelist():
                return "zip-based office file is empty"
    except zipfile.BadZipFile:
        return "zip-based office file is not readable"
    return None


def _validate_text_file(path: Path) -> str | None:
    data = path.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "cp1251"):
        try:
            data.decode(encoding)
            return None
        except UnicodeDecodeError:
            continue
    return "text file is not decodable as utf-8/cp1251"


def _validate_image(path: Path) -> str | None:
    data = path.read_bytes()[:16]
    signatures = IMAGE_SIGNATURES.get(path.suffix.lower(), [])
    if not signatures:
        return None
    if not any(data.startswith(signature) for signature in signatures):
        return "image signature is invalid"
    if path.suffix.lower() == ".webp" and data[8:12] != b"WEBP":
        return "WEBP signature is invalid"
    return None


def validate_file_integrity(root: Path) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = str(path.relative_to(root))
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            reason = _validate_pdf(path)
        elif suffix in ZIP_BASED_EXTENSIONS:
            reason = _validate_zip_container(path)
        elif suffix in TEXT_EXTENSIONS:
            reason = _validate_text_file(path)
        elif suffix in IMAGE_SIGNATURES:
            reason = _validate_image(path)
        else:
            reason = None
        if reason:
            issues.append(ValidationIssue(rel, reason))
    return issues


def validate_windows_export(root: Path) -> list[ValidationIssue]:
    return validate_windows_paths(root) + validate_file_integrity(root)


def issues_as_json(issues: list[ValidationIssue]) -> str:
    return json.dumps([issue.__dict__ for issue in issues], ensure_ascii=False, indent=2)
