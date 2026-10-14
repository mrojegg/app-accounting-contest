from __future__ import annotations

import atexit
import hashlib
import shutil
import re
from pathlib import Path

import sorting_platform as platform_support


SUPPORTED_EXTENSIONS = {
    ".bmp",
    ".csv",
    ".doc",
    ".docx",
    ".eml",
    ".gif",
    ".heic",
    ".avif",
    ".jfif",
    ".jp2",
    ".j2k",
    ".htm",
    ".html",
    ".jpeg",
    ".jpg",
    ".json",
    ".md",
    ".msg",
    ".pdf",
    ".png",
    ".rtf",
    ".tif",
    ".tiff",
    ".tsv",
    ".txt",
    ".webp",
    ".xls",
    ".xlsb",
    ".xlsm",
    ".xlsx",
    ".odt",
    ".ods",
    ".odp",
    ".xml",
}

GENERATED_SOURCE_ROOTS: set[Path] = set()
PRESERVED_MULTIPAGE_PDFS: set[Path] = set()
IGNORED_FILENAMES = {"_report.txt"}


def is_receipt_bundle(path: Path) -> bool:
    if path.suffix.lower() != ".pdf":
        return False
    try:
        import fitz
        with fitz.open(path) as document:
            if len(document) <= 1:
                return False
            PRESERVED_MULTIPAGE_PDFS.add(path)
            texts = [page.get_text().lower() for page in document]
            payment = r"плат[её]жное\s+поручение|банковский\s+ордер"
            if all(re.search(payment, text) and "сумма" in text for text in texts):
                PRESERVED_MULTIPAGE_PDFS.discard(path)
                return True
    except Exception:
        if platform_support.pdf_page_count(path) > 1:
            PRESERVED_MULTIPAGE_PDFS.add(path)
    return False


def split_combined_pdf(
    path: Path,
    *,
    cache_root: Path,
    swift_pdf_splitter: Path,
    run_command,
) -> list[Path]:
    if path.suffix.lower() != ".pdf" or not swift_pdf_splitter.exists():
        split = platform_support.split_pdf_with_pymupdf(path, cache_root / hashlib.sha1(str(path).encode("utf-8")).hexdigest())
        return split or [path]
    mdls_pages = run_command(["mdls", "-raw", "-name", "kMDItemNumberOfPages", str(path)], timeout=20).strip()
    page_count = platform_support.pdf_page_count(path)
    if mdls_pages.isdigit():
        page_count = int(mdls_pages)
    if page_count <= 1:
        return [path]
    split_dir = cache_root / hashlib.sha1(str(path).encode("utf-8")).hexdigest()
    split_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(split_dir.glob("*.pdf"))
    if existing:
        return existing
    result = run_command(["swift", str(swift_pdf_splitter), str(path), str(split_dir)], timeout=180)
    produced = [Path(line.strip()) for line in result.splitlines() if line.strip().endswith(".pdf")]
    return produced or [path]


def collect_files(
    input_dir: Path,
    archive_root: Path,
    *,
    supported_extensions: set[str],
    swift_pdf_splitter: Path,
    run_command,
) -> list[Path]:
    files: list[Path] = []
    split_cache = platform_support.make_temp_dir(prefix="sort_split_")
    GENERATED_SOURCE_ROOTS.add(split_cache)
    atexit.register(lambda p=split_cache: shutil.rmtree(p, ignore_errors=True))
    resolved_archive_root = archive_root.resolve()
    for path in input_dir.rglob("*"):
        if not path.is_file():
            continue
        try:
            path.resolve().relative_to(resolved_archive_root)
            continue
        except ValueError:
            pass
        if any(parent.name.startswith("Архив_документов") for parent in path.parents):
            continue
        if path.name.startswith("."):
            continue
        if path.name in IGNORED_FILENAMES:
            continue
        suffix = path.suffix.lower()
        if suffix not in supported_extensions:
            continue
        if is_receipt_bundle(path):
            files.extend(
                split_combined_pdf(
                    path,
                    cache_root=split_cache,
                    swift_pdf_splitter=swift_pdf_splitter,
                    run_command=run_command,
                )
            )
            continue
        files.append(path)
    return sorted(files)
