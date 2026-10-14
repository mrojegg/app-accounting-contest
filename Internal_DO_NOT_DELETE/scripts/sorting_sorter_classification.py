from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Iterable

import sorting_classification as classification
import sorting_sorter_runtime as sorter_runtime
from sorting_models import Classification, DetectionResult
from sorting_text_utils import bounded_confidence, normalize_piece, normalize_text


def classification_runtime() -> classification.ClassificationRuntime:
    return sorter_runtime.classification_runtime()


def match_any(patterns: Iterable[str], text: str) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def detect_entity(
    text: str,
    name_text: str,
    path_text: str = "",
    *,
    runtime_factory: Callable[[], classification.ClassificationRuntime] = classification_runtime,
    match_any_fn: Callable[[Iterable[str], str], bool] = match_any,
) -> str | None:
    return classification.detect_entity(
        text,
        name_text,
        path_text,
        runtime=runtime_factory(),
        match_any=match_any_fn,
    )


def detect_entity_signal(
    text: str,
    name_text: str,
    path_text: str = "",
    *,
    runtime_factory: Callable[[], classification.ClassificationRuntime] = classification_runtime,
    match_any_fn: Callable[[Iterable[str], str], bool] = match_any,
    bounded_confidence_fn: Callable[[int, int], int] = bounded_confidence,
) -> DetectionResult:
    return classification.detect_entity_signal(
        text,
        name_text,
        path_text,
        runtime=runtime_factory(),
        match_any=match_any_fn,
        bounded_confidence=bounded_confidence_fn,
    )


def bank_payment_recipient(text: str) -> str:
    normalized = normalize_text(text)
    patterns = [
        r"сч\.\s*[n№]\s*408\d{17,23}\s+([а-яa-zё -]{3,160}?)\s+вид\s+оп",
        r"счет\s*[n№]\s*408\d{17,23}\s+([а-яa-zё -]{3,160}?)\s+вид\s+оп",
        r"408\d{17,23}\s+([а-яa-zё -]{3,160}?)\s+вид\s+оп",
        r"получатель\s+([а-яa-z0-9\"«»().,/№ -]{3,160}?)\s+назначение платежа",
        r"получатель\s+([а-яa-z0-9\"«»().,/№ -]{3,160}?)\s+сумма",
        r"(?:поле\s+5|поле\s+3)\s+([а-яa-z0-9\"«»().,/№ -]{3,160}?)\s+получатель",
        r"рез\.\s*поле\s+([а-яa-z0-9\"«»().,/№ -]{3,160}?)\s+получатель",
        r"плательщик\s+банк\s+плательщика\s+банк\s+получателя.*?рез\.\s*поле\s+([а-яa-z0-9\"«»().,/№ -]{3,160}?)\s+получатель",
        r"([а-яa-z0-9\"«»().,/№ -]{3,160}?)\s+получатель\s+инн",
        r"([а-яa-z0-9\"«»().,/№ -]{3,160}?)\s+получатель",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized, re.IGNORECASE | re.S)
        if not match:
            continue
        raw_candidate = match.group(1)
        org_matches = list(re.finditer(r"\b(?:ооо|ип|ао|пао)\b", raw_candidate, re.IGNORECASE))
        for org_match in reversed(org_matches):
            segment = raw_candidate[org_match.start():]
            next_org = re.search(r"\b(?:ооо|ип|ао|пао)\b", segment[org_match.end() - org_match.start():], re.IGNORECASE)
            if next_org:
                segment = segment[:org_match.end() - org_match.start() + next_org.start()]
            if not re.search(r"\d{10,}", segment):
                raw_candidate = segment.strip()
                break

        lines = [normalize_text(line) for line in raw_candidate.splitlines() if normalize_text(line)]
        for line in reversed(lines):
            if re.search(r"\b(?:ооо|ип|ао|пао)\b", line, re.IGNORECASE) and not re.search(r"\d{10,}", line):
                raw_candidate = line
                break
        candidate = normalize_piece(raw_candidate)
        candidate_lower = candidate.lower() if candidate else ""
        if candidate and candidate_lower not in {"плательщик", "банк", "получателя"}:
            if any(token in candidate_lower for token in ["назначение платежа", "рез. поле", "код", "ндс не облагается", "оплата", "договор", "аренд"]):
                continue
            return normalize_text(raw_candidate)
    return ""


def bank_name(text: str) -> str:
    combined = normalize_text(text)
    bank_patterns = [
        r"(?:ф\.акб|пао|ао|пao|ao)\s*[«\"']?([а-яa-z0-9 .()-]*банк[а-яa-z0-9 .()-]*)",
        r"([а-яa-z0-9 .()-]*банк[а-яa-z0-9 .()-]*)",
    ]
    for pattern in bank_patterns:
        match = re.search(pattern, combined, re.IGNORECASE)
        if match:
            candidate = normalize_piece(match.group(1))
            if candidate:
                return candidate
    return "Банк"


def bank_payment_purpose(text: str) -> str:
    match = re.search(
        r"(?:очер\.\s*плат\.\s*\d+\s+)?(.+?)\s+м\.п\.\s+подписи\s+отметки банка\s+назначение платежа",
        text,
        re.IGNORECASE,
    )
    if not match:
        return ""
    return normalize_text(match.group(1))


def detect_office(
    text: str,
    name_text: str,
    entity: str | None,
    *,
    runtime_factory: Callable[[], classification.ClassificationRuntime] = classification_runtime,
    bank_payment_recipient_fn: Callable[[str], str] = bank_payment_recipient,
    bank_payment_purpose_fn: Callable[[str], str] = bank_payment_purpose,
) -> tuple[str | None, str]:
    return classification.detect_office(
        text,
        name_text,
        entity,
        runtime=runtime_factory(),
        bank_payment_recipient=bank_payment_recipient_fn,
        bank_payment_purpose=bank_payment_purpose_fn,
        normalize_text=normalize_text,
    )


def detect_office_signal(
    text: str,
    name_text: str,
    entity: str | None,
    *,
    runtime_factory: Callable[[], classification.ClassificationRuntime] = classification_runtime,
    bank_payment_recipient_fn: Callable[[str], str] = bank_payment_recipient,
    bank_payment_purpose_fn: Callable[[str], str] = bank_payment_purpose,
    bounded_confidence_fn: Callable[[int, int], int] = bounded_confidence,
    normalize_text_fn: Callable[[str], str] = normalize_text,
) -> DetectionResult:
    return classification.detect_office_signal(
        text,
        name_text,
        entity,
        runtime=runtime_factory(),
        bank_payment_recipient=bank_payment_recipient_fn,
        bank_payment_purpose=bank_payment_purpose_fn,
        bounded_confidence=bounded_confidence_fn,
        normalize_text=normalize_text_fn,
    )


def looks_like_salary_payment(
    text: str,
    name_text: str,
    *,
    runtime_factory: Callable[[], classification.ClassificationRuntime] = classification_runtime,
    normalize_text_fn: Callable[[str], str] = normalize_text,
) -> bool:
    return classification.looks_like_salary_payment(
        text,
        runtime=runtime_factory(),
        normalize_text=normalize_text_fn,
    )


def is_payment_order(text: str, name_text: str) -> bool:
    return "платежное поручение" in text


def is_bank_order(text: str) -> bool:
    return "банковский ордер" in text


def detect_category(
    text: str,
    name_text: str,
    *,
    runtime_factory: Callable[[], classification.ClassificationRuntime] = classification_runtime,
    bank_payment_recipient_fn: Callable[[str], str] = bank_payment_recipient,
    bank_payment_purpose_fn: Callable[[str], str] = bank_payment_purpose,
    normalize_text_fn: Callable[[str], str] = normalize_text,
    match_any_fn: Callable[[Iterable[str], str], bool] = match_any,
    bounded_confidence_fn: Callable[[int, int], int] = bounded_confidence,
) -> tuple[str | None, str]:
    return classification.detect_category(
        text,
        name_text,
        runtime=runtime_factory(),
        bank_payment_recipient=bank_payment_recipient_fn,
        bank_payment_purpose=bank_payment_purpose_fn,
        normalize_text=normalize_text_fn,
        match_any=match_any_fn,
        bounded_confidence=bounded_confidence_fn,
    )


def detect_category_signal(
    text: str,
    name_text: str,
    *,
    runtime_factory: Callable[[], classification.ClassificationRuntime] = classification_runtime,
    bank_payment_recipient_fn: Callable[[str], str] = bank_payment_recipient,
    bank_payment_purpose_fn: Callable[[str], str] = bank_payment_purpose,
    normalize_text_fn: Callable[[str], str] = normalize_text,
    match_any_fn: Callable[[Iterable[str], str], bool] = match_any,
    bounded_confidence_fn: Callable[[int, int], int] = bounded_confidence,
) -> DetectionResult:
    return classification.detect_category_signal(
        text,
        name_text,
        runtime=runtime_factory(),
        bank_payment_recipient=bank_payment_recipient_fn,
        bank_payment_purpose=bank_payment_purpose_fn,
        normalize_text=normalize_text_fn,
        match_any=match_any_fn,
        bounded_confidence=bounded_confidence_fn,
    )


def classify(
    path: Path,
    archive_root: Path,
    *,
    file_text: Callable[[Path], str],
    safe_filename: Callable[[Path, str | None, str | None, str | None], str],
    runtime_factory: Callable[[], classification.ClassificationRuntime] = classification_runtime,
    normalize_text_fn: Callable[[str], str] = normalize_text,
    match_any_fn: Callable[[Iterable[str], str], bool] = match_any,
    bounded_confidence_fn: Callable[[int, int], int] = bounded_confidence,
    bank_payment_recipient_fn: Callable[[str], str] = bank_payment_recipient,
    bank_payment_purpose_fn: Callable[[str], str] = bank_payment_purpose,
) -> Classification:
    return classification.classify_document(
        path,
        archive_root,
        runtime=runtime_factory(),
        file_text=file_text,
        normalize_text=normalize_text_fn,
        match_any=match_any_fn,
        bounded_confidence=bounded_confidence_fn,
        bank_payment_recipient=bank_payment_recipient_fn,
        bank_payment_purpose=bank_payment_purpose_fn,
        safe_filename=safe_filename,
    )


__all__ = [name for name in globals() if not name.startswith("_")]
