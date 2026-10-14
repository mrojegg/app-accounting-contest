from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class ExtractedFields:
    recipient: str | None = None
    purpose: str | None = None
    amount_hint: str | None = None
    entity_hint: str | None = None
    invoice_hint: str | None = None

    @property
    def critical_payment_fields_count(self) -> int:
        return sum(1 for value in (self.recipient, self.purpose, self.amount_hint, self.entity_hint) if value)


def extract_fields(text: str, *, normalize_text: Callable[[str], str]) -> ExtractedFields:
    normalized = normalize_text(text)
    recipient = None
    purpose = None
    amount_hint = None
    entity_hint = None
    invoice_hint = None

    recipient_match = re.search(r"(?:сч\.?\s*[n№]?|счет\s*[n№]?)\s*408\d{17,23}\s+([а-яa-zё -]{5,160}?)\s+вид\s+оп", normalized, re.I)
    if recipient_match:
        recipient = recipient_match.group(1).strip()

    purpose_patterns = [
        r"рез\.\s*поле\s+(.+?)\s+назначение платежа",
        r"код\s+рез\.\s*поле\s+(.+?)\s+назначение платежа",
        r"назначение платежа\s+(.+?)\s+(?:подписи|отметки банка|м\.п\.)",
    ]
    for pattern in purpose_patterns:
        purpose_match = re.search(pattern, normalized, re.I | re.S)
        if not purpose_match:
            continue
        candidate = re.sub(r"\s+", " ", purpose_match.group(1)).strip()
        if len(candidate) >= 10:
            purpose = candidate
            break

    amount_match = re.search(r"(?:сумма|всего к оплате|сумма к оплате)\D{0,40}(\d{1,3}(?: \d{3})*[.,-]\d{2}|\d+[.,-]\d{2})", normalized, re.I)
    if amount_match:
        amount_hint = amount_match.group(1).strip()

    entity_match = re.search(r"\b(ооо|ип|ао|пао)\s+[«\"\']?([а-яa-zё0-9 .-]{3,120})", normalized, re.I)
    if entity_match:
        entity_hint = f"{entity_match.group(1)} {entity_match.group(2).strip()}"

    invoice_match = re.search(r"(?:счет(?:\s+на\s+оплату)?)[^\n]{0,80}(?:№|n|nº)?\s*([a-zа-я0-9./-]{1,40})", normalized, re.I)
    if invoice_match:
        invoice_hint = invoice_match.group(1).strip()

    return ExtractedFields(
        recipient=recipient,
        purpose=purpose,
        amount_hint=amount_hint,
        entity_hint=entity_hint,
        invoice_hint=invoice_hint,
    )


def enrich_text_from_fields(text: str, fields: ExtractedFields, *, normalize_text: Callable[[str], str]) -> str:
    additions: list[str] = []
    if fields.recipient:
        additions.append(f"Получатель {fields.recipient}")
    if fields.purpose:
        additions.append(f"Назначение платежа {fields.purpose}")
    if fields.amount_hint:
        additions.append(f"Сумма {fields.amount_hint}")
    if fields.entity_hint:
        additions.append(f"Юрлицо {fields.entity_hint}")
    if not additions:
        return text

    existing = {normalize_text(line) for line in text.splitlines() if line.strip()}
    merged = [text]
    for line in additions:
        if normalize_text(line) in existing:
            continue
        merged.append(line)
    return "\n".join(part for part in merged if part.strip())
