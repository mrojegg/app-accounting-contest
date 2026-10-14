from __future__ import annotations

import os
from pathlib import Path
import re
import sys

import sorting_classification as classification
import sorting_config as config
import sorting_extraction as extraction
import sorting_pattern_config as pattern_config
from sorting_text_utils import normalize_text


DEFAULT_OFFICES = list(config.DEFAULT_OFFICES)
OFFICES = list(DEFAULT_OFFICES)
OFFICE_SUBFOLDERS = ["Зарплата", "Аренда", "Интернет", "Коммунальные", "Услуги", "Прочее"]
ROOT_FOLDERS_ALWAYS: list[str] = []
ROOT_FOLDERS_OPTIONAL = ["УСН"]
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
def _ocr_binary_candidates() -> list[Path]:
    candidates: list[Path] = []
    override = os.environ.get("SORTING_OCR_BINARY", "").strip()
    if override:
        candidates.append(Path(override).expanduser())
    candidates.extend([
        Path(__file__).resolve().parent.parent / "ocr" / "bin" / "pdf_ocr_pkg",
        Path(__file__).resolve().parent.parent / "ocr" / "ocr_package" / ".build-local" / "arm64-apple-macosx" / "debug" / "pdf_ocr_pkg",
        Path(__file__).resolve().parent.parent / "ocr" / "ocr_package" / ".build-local" / "debug" / "pdf_ocr_pkg",
        Path(__file__).resolve().parent.parent / "cache" / ".swift-cache" / "pdf_ocr",
    ])
    return candidates


def _default_cache_root() -> Path:
    override = os.environ.get("SORTING_TEXT_CACHE_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "SortingFilesContestApp" / "text_extract"
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / "SortingFilesContestApp" / "text_extract"
    return Path.home() / ".cache" / "SortingFilesContestApp" / "text_extract"


OCR_BINARY_CANDIDATES = _ocr_binary_candidates()
TEXT_CACHE: dict[Path, str] = {}
MANUAL_REVIEW_HEAVY_OCR_PATHS: set[Path] = set()
COMMAND_EXISTS_CACHE: dict[str, bool] = {}
SWIFT_PDF_SPLITTER = Path(__file__).resolve().parent / "pdf_splitter.swift"
CACHE_ROOT = _default_cache_root()
TEXT_CACHE_VERSION = "v7-ocr-quality"
INFORMATIVE_TEXT_PATTERNS = [
    r"платежное поручение",
    r"банковский ордер",
    r"назначение платежа",
    r"получатель",
    r"выплата заработной платы",
    r"заработн",
    r"ндфл",
    r"\bенп\b",
    r"единый налоговый платеж",
    r"взнос",
    r"счет",
    r"всего к оплате",
    r"сумма к оплате",
    r"инн",
    r"кпп",
    r"бизнес-легион",
    r"таттелеком",
    r"искрателеком",
    r"комитерн",
    r"тестовпоставщик",
    r"демопоставщик",
]

PATTERN_CONFIG = pattern_config.load_pattern_config()
ENTITY_PATTERNS = PATTERN_CONFIG.entity_patterns
ENTITY_ACCOUNT_PATTERNS = PATTERN_CONFIG.entity_account_patterns
ENTITY_SOURCE_HINT_PATTERNS = PATTERN_CONFIG.entity_source_hint_patterns
DEFAULT_OFFICE_PEOPLE = config.DEFAULT_OFFICE_PEOPLE
DEFAULT_OFFICE_CONTRACTORS = config.DEFAULT_OFFICE_CONTRACTORS
DEFAULT_OFFICE_ENTITIES = config.DEFAULT_OFFICE_ENTITIES
DEFAULT_OFFICE_CATEGORIES: dict[str, list[str]] = {}
DEFAULT_RULE_SETTINGS = config.RuntimeRuleSettings()
OFFICE_PEOPLE = {office: list(people) for office, people in DEFAULT_OFFICE_PEOPLE.items()}
OFFICE_CONTRACTORS = {
    office: {category: list(values) for category, values in categories.items()}
    for office, categories in DEFAULT_OFFICE_CONTRACTORS.items()
}
OFFICE_CONTRACTOR_FOLDERS: dict[str, dict[str, dict[str, str]]] = {}
OFFICE_ENTITIES = dict(DEFAULT_OFFICE_ENTITIES)
OFFICE_CATEGORIES: dict[str, list[str]] = {}
RULE_SETTINGS = DEFAULT_RULE_SETTINGS
CATEGORY_PATTERNS = PATTERN_CONFIG.category_patterns
TAX_PATTERNS = PATTERN_CONFIG.tax_patterns
INSURANCE_ACCIDENT_PATTERNS = PATTERN_CONFIG.insurance_accident_patterns
USN_PATTERNS = PATTERN_CONFIG.usn_patterns
BANK_COMMISSION_PATTERNS = PATTERN_CONFIG.bank_commission_patterns


def entity_patterns_with_runtime_entities() -> dict[str, list[str]]:
    merged = {entity: list(patterns) for entity, patterns in ENTITY_PATTERNS.items()}
    for entity in set(OFFICE_ENTITIES.values()):
        if not entity:
            continue
        bucket = merged.setdefault(entity, [])
        escaped = re.escape(entity.lower())
        bucket.extend([
            escaped,
            rf'ооо\s*[«"\']?{escaped}',
            rf'ип\s*[«"\']?{escaped}',
            rf'ао\s*[«"\']?{escaped}',
            rf'пао\s*[«"\']?{escaped}',
        ])
        deduped: list[str] = []
        seen: set[str] = set()
        for pattern in bucket:
            if pattern in seen:
                continue
            seen.add(pattern)
            deduped.append(pattern)
        merged[entity] = deduped
    return merged


def refresh_runtime_config() -> None:
    global OFFICE_PEOPLE, OFFICE_CONTRACTORS, OFFICE_CONTRACTOR_FOLDERS, OFFICE_ENTITIES, OFFICE_CATEGORIES, OFFICES, RULE_SETTINGS
    runtime = config.load_runtime_config(normalize_text=normalize_text)
    OFFICE_PEOPLE = runtime.office_people
    OFFICE_CONTRACTORS = runtime.office_contractors
    OFFICE_CONTRACTOR_FOLDERS = runtime.office_contractor_folders
    OFFICE_ENTITIES = runtime.office_entities
    OFFICE_CATEGORIES = runtime.office_categories
    OFFICES = runtime.offices
    RULE_SETTINGS = runtime.rule_settings


def classification_runtime() -> classification.ClassificationRuntime:
    return classification.ClassificationRuntime(
        entity_patterns=entity_patterns_with_runtime_entities(),
        entity_account_patterns=ENTITY_ACCOUNT_PATTERNS,
        entity_source_hint_patterns=ENTITY_SOURCE_HINT_PATTERNS,
        office_people=OFFICE_PEOPLE,
        office_contractors=OFFICE_CONTRACTORS,
        office_contractor_folders=OFFICE_CONTRACTOR_FOLDERS,
        office_entities=OFFICE_ENTITIES,
        office_categories=OFFICE_CATEGORIES,
        offices=OFFICES,
        category_patterns=CATEGORY_PATTERNS,
        tax_patterns=TAX_PATTERNS,
        insurance_accident_patterns=INSURANCE_ACCIDENT_PATTERNS,
        usn_patterns=USN_PATTERNS,
        bank_commission_patterns=BANK_COMMISSION_PATTERNS,
        rule_settings=RULE_SETTINGS,
    )


def runtime_rule_settings() -> config.RuntimeRuleSettings:
    return RULE_SETTINGS


def extraction_runtime() -> extraction.ExtractionRuntime:
    return extraction.ExtractionRuntime(
        text_cache=TEXT_CACHE,
        manual_review_heavy_ocr_paths=MANUAL_REVIEW_HEAVY_OCR_PATHS,
        command_exists_cache=COMMAND_EXISTS_CACHE,
        ocr_binary_candidates=OCR_BINARY_CANDIDATES,
        swift_pdf_splitter=SWIFT_PDF_SPLITTER,
        cache_root=CACHE_ROOT,
        text_cache_version=TEXT_CACHE_VERSION,
        informative_text_patterns=INFORMATIVE_TEXT_PATTERNS,
        normalize_text=normalize_text,
    )


def heavy_ocr_manual_review_paths() -> set[Path]:
    return MANUAL_REVIEW_HEAVY_OCR_PATHS


__all__ = [name for name in globals() if not name.startswith("_")]
