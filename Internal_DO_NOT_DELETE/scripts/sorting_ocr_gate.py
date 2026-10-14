from __future__ import annotations

import re
from typing import Callable


def payment_text_quality_flags(text: str, *, normalize_text: Callable[[str], str]) -> dict[str, bool]:
    normalized = normalize_text(text)
    is_payment_like = "платежное поручение" in normalized or "банковский ордер" in normalized
    return {
        "is_payment_like": is_payment_like,
        "has_recipient": bool(re.search(r"(получатель|408\d{17,23}\s+[а-яa-zё -]{5,160}\s+вид\s+оп)", normalized, re.I)),
        "has_purpose": "назначение платежа" in normalized or "рез. поле" in normalized,
        "has_amount": bool(re.search(r"(сумма|руб(?:лей|ля|ль))", normalized, re.I)),
        "has_entity_markers": bool(re.search(r"(ооо|ип|инн|кпп|4070281\d+)", normalized, re.I)),
    }


def should_run_heavy_ocr(
    text: str,
    score: int,
    *,
    normalize_text: Callable[[str], str],
    is_garbled_text: Callable[[str], bool],
    informative_text_lines: Callable[[str], list[str]],
) -> bool:
    if not text:
        return True
    if is_garbled_text(text):
        return True

    flags = payment_text_quality_flags(text, normalize_text=normalize_text)
    if flags["is_payment_like"]:
        present = sum(1 for key in ("has_recipient", "has_purpose", "has_amount", "has_entity_markers") if flags[key])
        if present < 3:
            return True
        return score < 160

    informative_lines = informative_text_lines(text)
    if informative_lines:
        if len(text) >= 220 and score >= 60:
            return False
        return score < 140 and len(text) < 120

    if len(text) >= 320 and score >= 40:
        return False
    return True
