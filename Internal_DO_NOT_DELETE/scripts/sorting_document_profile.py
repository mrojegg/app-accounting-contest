from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable

import sorting_platform as platform_support
import sorting_ocr_gate

if TYPE_CHECKING:
    import sorting_extraction as extraction


TEXT_DOCUMENT_EXTENSIONS = {".txt", ".md", ".csv", ".tsv", ".json", ".xml", ".html", ".htm", ".eml", ".rtf"}
OPENXML_DOCUMENT_EXTENSIONS = {".docx", ".xlsx", ".xlsm", ".xlsb", ".odt", ".ods", ".odp"}
IMAGE_DOCUMENT_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".gif", ".heic", ".webp", ".avif", ".jfif", ".jp2", ".j2k"}
LEGACY_DOCUMENT_EXTENSIONS = {".xls", ".doc", ".msg"}


@dataclass(frozen=True)
class DocumentProfile:
    path: Path
    document_type: str
    extension: str
    pdf_page_count: int | None
    has_text_layer: bool
    extracted_text_length: int
    text_quality_score: int
    quality_flags: dict[str, bool]

    @property
    def kind(self) -> str:
        return self.document_type

    @property
    def page_count(self) -> int:
        return self.pdf_page_count or 1

    @property
    def is_scan_like(self) -> bool:
        if self.document_type != "pdf":
            return False
        return not self.has_text_layer or self.text_quality_score < 120 or self.extracted_text_length < 80


def detect_document_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return "pdf"
    if suffix in TEXT_DOCUMENT_EXTENSIONS:
        return "text"
    if suffix in OPENXML_DOCUMENT_EXTENSIONS:
        return "openxml"
    if suffix in IMAGE_DOCUMENT_EXTENSIONS:
        return "image"
    if suffix in LEGACY_DOCUMENT_EXTENSIONS:
        return "legacy"
    return "generic"


def build_quality_flags(
    path: Path,
    text: str,
    *,
    document_type: str,
    page_count: int | None,
    has_text_layer: bool,
    runtime: "extraction.ExtractionRuntime",
) -> dict[str, bool]:
    import sorting_extraction as extraction

    score = extraction.pdf_text_score(text, "profile")
    payment_flags = sorting_ocr_gate.payment_text_quality_flags(text, normalize_text=runtime.normalize_text)
    informative = bool(extraction.informative_text_lines(text, runtime=runtime))
    return {
        "is_pdf": document_type == "pdf",
        "is_payment_like": payment_flags["is_payment_like"],
        "has_text": bool(text.strip()),
        "has_text_layer": has_text_layer,
        "is_multipage_pdf": bool(page_count and page_count > 1),
        "is_garbled": extraction.is_garbled_text(text) if text else False,
        "has_informative_text": informative,
        "should_run_heavy_ocr": extraction.should_run_heavy_ocr(text, score, runtime=runtime),
        "has_recipient": payment_flags["has_recipient"],
        "has_purpose": payment_flags["has_purpose"],
        "has_amount": payment_flags["has_amount"],
        "has_entity_markers": payment_flags["has_entity_markers"],
        "is_low_quality_text": score < 240,
        "is_empty_document": not text.strip(),
        "exists": path.exists(),
    }


def profile_document(
    path: Path,
    *,
    runtime: "extraction.ExtractionRuntime",
    file_text_fn: Callable[[Path], str] | None = None,
    pdf_page_count: int | None = None,
    has_text_layer: bool | None = None,
) -> DocumentProfile:
    import sorting_extraction as extraction

    document_type = detect_document_type(path)
    page_count = pdf_page_count if document_type == "pdf" else None
    if document_type == "pdf" and page_count is None:
        page_count = platform_support.pdf_page_count(path)
    resolved_has_text_layer = has_text_layer if document_type == "pdf" and has_text_layer is not None else False
    if document_type == "pdf" and has_text_layer is None:
        resolved_has_text_layer = platform_support.pdf_has_text_layer(path)
    extract_text = file_text_fn or (lambda target: extraction.file_text(target, runtime=runtime))
    text = extract_text(path)
    text_length = len(text.strip())
    score = extraction.pdf_text_score(text, "profile") if text else -10_000
    flags = build_quality_flags(
        path,
        text,
        document_type=document_type,
        page_count=page_count,
        has_text_layer=resolved_has_text_layer,
        runtime=runtime,
    )
    return DocumentProfile(
        path=path,
        document_type=document_type,
        extension=path.suffix.lower(),
        pdf_page_count=page_count,
        has_text_layer=resolved_has_text_layer,
        extracted_text_length=text_length,
        text_quality_score=score,
        quality_flags=flags,
    )


def build_document_profile(
    path: Path,
    *,
    runtime: "extraction.ExtractionRuntime" | None = None,
    file_text_fn: Callable[[Path], str] | None = None,
    extract_pdf_text_layer: Callable[[Path], str] | None = None,
) -> DocumentProfile:
    import sorting_extraction as extraction
    import sorting_sorter_runtime as sorter_runtime

    runtime = runtime or sorter_runtime.extraction_runtime()
    page_count = platform_support.pdf_page_count(path) if detect_document_type(path) == "pdf" else None
    has_text_layer = False
    if detect_document_type(path) == "pdf":
        if extract_pdf_text_layer is not None:
            try:
                has_text_layer = bool(extract_pdf_text_layer(path).strip())
            except Exception:
                has_text_layer = platform_support.pdf_has_text_layer(path)
        else:
            has_text_layer = platform_support.pdf_has_text_layer(path)
    return profile_document(
        path,
        runtime=runtime,
        file_text_fn=file_text_fn or (lambda target: extraction.file_text(target, runtime=runtime)),
        pdf_page_count=page_count,
        has_text_layer=has_text_layer,
    )
