from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


PATTERNS_FILE = Path(__file__).resolve().parent.parent / "project_rules" / "classification_patterns.json"

DEFAULT_ENTITY_PATTERNS = {
    "ПРИМЕР": [r"пример", r'ооо\s*[«"\']?пример'],
    "ОБРАЗЕЦ": [r"образец", r'ооо\s*[«"\']?образец'],
}

DEFAULT_ENTITY_ACCOUNT_PATTERNS = {
    "ПРИМЕР": [],
    "ОБРАЗЕЦ": [],
}

DEFAULT_ENTITY_SOURCE_HINT_PATTERNS = {
    "ПРИМЕР": [
        r"пример.*page[_ -]?\d+",
        r"пример.*включительно",
    ],
    "ОБРАЗЕЦ": [
        r"\bvtb_payment_commission_\d+",
        r"\bvtb_bank_order_\d+",
        r"образец.*page[_ -]?\d+",
    ],
}

DEFAULT_CATEGORY_PATTERNS = {
    "Аренда": [r"аренд", r"найм помещен", r"субаренд"],
    "Интернет": [r"интернет", r"интернет-услуг", r"доступ к сети интернет", r"провайдер", r"канал связи", r"услуг[аи] связи", r"услуги связи"],
    "Коммунальные": [r"коммунал", r"электроэнерг", r"водоснабжен", r"теплоснабжен", r"эксплуатацион"],
    "Услуги": [r"услуг", r"уборк", r"доставк", r"headhunter", r"head hunter", r"хэдхантер", r"пропуск", r"регсервис"],
    "Зарплата": [r"аванс", r"заработн", r"отпускн", r"увольн", r"зарплат"],
}

DEFAULT_TAX_PATTERNS = [r"ндфл", r"\bенп\b", r"единый\s+налоговый\s+платеж", r"\bвзнос(ы|ов)?\b", r"\bусн\b", r"\bепд\b"]
DEFAULT_INSURANCE_ACCIDENT_PATTERNS = [r"взносы на обязательное страхование от несчастных случаев"]
DEFAULT_USN_PATTERNS = [r"енп\s*\(усн\s*2025г\)", r"единый\s+налоговый\s+платеж.*усн"]
DEFAULT_BANK_COMMISSION_PATTERNS = [r"комисси", r"комиссия\s+банка", r"стоимость\s+пакета\s+услуг", r"пакет\s+услуг", r"все\s+включено", r"платежи\s+плюс"]


@dataclass(frozen=True)
class PatternConfig:
    entity_patterns: dict[str, list[str]]
    entity_account_patterns: dict[str, list[str]]
    entity_source_hint_patterns: dict[str, list[str]]
    category_patterns: dict[str, list[str]]
    tax_patterns: list[str]
    insurance_accident_patterns: list[str]
    usn_patterns: list[str]
    bank_commission_patterns: list[str]


def _defaults() -> PatternConfig:
    return PatternConfig(
        entity_patterns=DEFAULT_ENTITY_PATTERNS,
        entity_account_patterns=DEFAULT_ENTITY_ACCOUNT_PATTERNS,
        entity_source_hint_patterns=DEFAULT_ENTITY_SOURCE_HINT_PATTERNS,
        category_patterns=DEFAULT_CATEGORY_PATTERNS,
        tax_patterns=DEFAULT_TAX_PATTERNS,
        insurance_accident_patterns=DEFAULT_INSURANCE_ACCIDENT_PATTERNS,
        usn_patterns=DEFAULT_USN_PATTERNS,
        bank_commission_patterns=DEFAULT_BANK_COMMISSION_PATTERNS,
    )


def load_pattern_config(patterns_file: Path | None = None) -> PatternConfig:
    if patterns_file is None:
        override = os.environ.get("SORTING_PATTERNS_FILE", "").strip()
        rules = os.environ.get("SORTING_RULES_FILE", "").strip()
        private = Path(rules).expanduser().parent / "classification_patterns.json" if rules else None
        patterns_file = Path(override).expanduser() if override else (private if private and private.is_file() else PATTERNS_FILE)
    defaults = _defaults()
    try:
        payload = json.loads(patterns_file.read_text(encoding="utf-8"))
    except Exception:
        return defaults

    return PatternConfig(
        entity_patterns=payload.get("ENTITY_PATTERNS") or defaults.entity_patterns,
        entity_account_patterns=payload.get("ENTITY_ACCOUNT_PATTERNS") or defaults.entity_account_patterns,
        entity_source_hint_patterns=payload.get("ENTITY_SOURCE_HINT_PATTERNS") or defaults.entity_source_hint_patterns,
        category_patterns=payload.get("CATEGORY_PATTERNS") or defaults.category_patterns,
        tax_patterns=payload.get("TAX_PATTERNS") or defaults.tax_patterns,
        insurance_accident_patterns=payload.get("INSURANCE_ACCIDENT_PATTERNS") or defaults.insurance_accident_patterns,
        usn_patterns=payload.get("USN_PATTERNS") or defaults.usn_patterns,
        bank_commission_patterns=payload.get("BANK_COMMISSION_PATTERNS") or defaults.bank_commission_patterns,
    )
