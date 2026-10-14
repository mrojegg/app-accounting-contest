from __future__ import annotations

import re


def is_insurance_payment(text: str) -> bool:
    normalized = text.lower().replace("ё", "е")
    return bool(re.search(
        r"страховые\s+взносы|взносы\s+на\s+обязательное|"
        r"(?:\bенп\b|един(?:ый|ыи)\s+налогов(?:ый|ыи)\s+платеж)[^.!\n]{0,100}\bвзнос(?:ы|ов)\b",
        normalized,
    ))


def distribution_kind(text: str, category: str | None) -> str:
    normalized = text.lower().replace("ё", "е")
    if re.search(r"недоимк|\bпени\b|\bпеня\b|по\s+требованию|ндс\s+по\s+корректировк|"
                 r"\bенп\s*\([^)]*\bндс\b|уплата\s+ндс|налог\s+на\s+добавленную\s+стоимость", normalized) or category == "УСН":
        return "other"
    # A mixed payment cannot be split into taxes and insurance without its amounts.
    insurance = is_insurance_payment(normalized) or category == "Взносы"
    if insurance and re.search(r"\bндфл\b", normalized):
        return "other"
    if insurance:
        return "insurance"
    return "tax" if category == "Налоги" else "other"
