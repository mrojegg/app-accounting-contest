from __future__ import annotations

from dataclasses import dataclass

from sorting_document_profile import DocumentProfile
from sorting_extraction_fields import ExtractedFields


@dataclass(frozen=True)
class OCRGateDecision:
    should_run_heavy_ocr: bool
    should_run_rendered_image_ocr: bool
    should_run_page_by_page_ocr: bool
    should_run_tesseract: bool
    should_run_ocrmypdf: bool
    reason: str


def decide_ocr_gate(
    *,
    profile: DocumentProfile,
    text: str,
    score: int,
    informative_lines: list[str],
    is_garbled_text: bool,
    fields: ExtractedFields,
    is_payment_like: bool,
) -> OCRGateDecision:
    normalized = text.lower()
    if not text:
        return OCRGateDecision(True, True, profile.page_count > 1, True, profile.page_count > 1, "text-empty")
    if is_garbled_text:
        return OCRGateDecision(True, True, profile.page_count > 1, True, profile.page_count > 1, "text-garbled")

    if is_payment_like:
        has_payment_labels = "получател" in normalized and "назначение платеж" in normalized
        if score >= 180 and has_payment_labels and fields.amount_hint:
            return OCRGateDecision(False, False, False, False, False, "payment-labels-sufficient")
        if score >= 180 and len(informative_lines) >= 3 and fields.critical_payment_fields_count >= 2:
            return OCRGateDecision(False, False, False, False, False, "payment-text-sufficient")
        if fields.critical_payment_fields_count >= 3 and score >= 160:
            return OCRGateDecision(False, False, False, False, False, "payment-fields-sufficient")
        return OCRGateDecision(True, True, profile.page_count > 1, True, profile.page_count > 1, "payment-fields-missing")

    if informative_lines:
        if len(text) >= 220 and score >= 60:
            return OCRGateDecision(False, False, False, False, False, "informative-text-sufficient")
        if score < 140 and len(text) < 120:
            return OCRGateDecision(True, True, profile.page_count > 1, True, profile.page_count > 1, "informative-text-weak")
        return OCRGateDecision(False, False, False, False, False, "informative-text-accepted")

    if len(text) >= 320 and score >= 40:
        return OCRGateDecision(False, False, False, False, False, "long-text-accepted")

    page_by_page = profile.kind == "pdf" and profile.page_count > 1
    ocrmypdf = profile.kind == "pdf" and profile.page_count > 1
    return OCRGateDecision(True, True, page_by_page, True, ocrmypdf, "fallback-heavy-ocr")
