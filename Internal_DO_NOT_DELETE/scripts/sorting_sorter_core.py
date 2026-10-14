#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import re
from dataclasses import replace
from pathlib import Path
from typing import Iterable

import sorting_classification as classification
import sorting_extraction as extraction
import sorting_file_collection as file_collection
import sorting_file_ops as file_ops
import sorting_receipt_archive
import sorting_manual_review as manual_review
import sorting_document_profile as document_profile
import sorting_sorter_classification as sorter_classification
import sorting_sorter_naming as sorter_naming
import sorting_sorter_routing as sorter_routing
import sorting_sorter_runtime as sorter_runtime
from sorting_models import Classification
from sorting_text_utils import (
    bounded_confidence,
    extract_amount_from_words,
    normalize_amount_token,
    normalize_piece,
    normalize_text,
    parse_russian_number_words,
    strip_full_dates,
)


GENERATED_SOURCE_ROOTS = file_collection.GENERATED_SOURCE_ROOTS


def naming_dependencies() -> sorter_naming.NamingDependencies:
    return sorter_naming.NamingDependencies(
        file_text=file_text,
        normalize_text=normalize_text,
        normalize_piece=normalize_piece,
        office_people=OFFICE_PEOPLE,
        office_contractors=OFFICE_CONTRACTORS,
        bank_name=bank_name,
        bank_payment_recipient=bank_payment_recipient,
        is_bank_order=is_bank_order,
        is_payment_order=is_payment_order,
        looks_like_salary_payment=looks_like_salary_payment,
        extract_amount_from_words=extract_amount_from_words,
        extract_invoice_amount=extract_invoice_amount,
        strip_full_dates=strip_full_dates,
        normalize_amount_token=normalize_amount_token,
        use_extracted_text_for_naming=RULE_SETTINGS.naming.use_extracted_text_for_naming,
        fallback_to_original_name_when_no_text=RULE_SETTINGS.naming.fallback_to_original_name_when_no_text,
        make_names_windows_safe=RULE_SETTINGS.naming.make_names_windows_safe,
    )


def routing_dependencies() -> sorter_routing.RoutingDependencies:
    return sorter_routing.RoutingDependencies(
        file_text=file_text,
        normalize_text=normalize_text,
    )


def _sync_runtime_exports() -> None:
    global DEFAULT_OFFICES, OFFICES, OFFICE_SUBFOLDERS, ROOT_FOLDERS_ALWAYS, ROOT_FOLDERS_OPTIONAL
    global SUPPORTED_EXTENSIONS, OCR_BINARY_CANDIDATES, TEXT_CACHE, COMMAND_EXISTS_CACHE
    global SWIFT_PDF_SPLITTER, CACHE_ROOT, TEXT_CACHE_VERSION, INFORMATIVE_TEXT_PATTERNS
    global PATTERN_CONFIG, ENTITY_PATTERNS, ENTITY_ACCOUNT_PATTERNS, ENTITY_SOURCE_HINT_PATTERNS
    global DEFAULT_OFFICE_PEOPLE, DEFAULT_OFFICE_CONTRACTORS, DEFAULT_OFFICE_ENTITIES
    global OFFICE_PEOPLE, OFFICE_CONTRACTORS, OFFICE_CONTRACTOR_FOLDERS, OFFICE_ENTITIES, OFFICE_CATEGORIES, RULE_SETTINGS
    global CATEGORY_PATTERNS, TAX_PATTERNS, INSURANCE_ACCIDENT_PATTERNS, USN_PATTERNS, BANK_COMMISSION_PATTERNS

    DEFAULT_OFFICES = sorter_runtime.DEFAULT_OFFICES
    OFFICES = sorter_runtime.OFFICES
    OFFICE_SUBFOLDERS = sorter_runtime.OFFICE_SUBFOLDERS
    ROOT_FOLDERS_ALWAYS = sorter_runtime.ROOT_FOLDERS_ALWAYS
    ROOT_FOLDERS_OPTIONAL = sorter_runtime.ROOT_FOLDERS_OPTIONAL
    SUPPORTED_EXTENSIONS = sorter_runtime.SUPPORTED_EXTENSIONS
    OCR_BINARY_CANDIDATES = sorter_runtime.OCR_BINARY_CANDIDATES
    TEXT_CACHE = sorter_runtime.TEXT_CACHE
    COMMAND_EXISTS_CACHE = sorter_runtime.COMMAND_EXISTS_CACHE
    SWIFT_PDF_SPLITTER = sorter_runtime.SWIFT_PDF_SPLITTER
    CACHE_ROOT = sorter_runtime.CACHE_ROOT
    TEXT_CACHE_VERSION = sorter_runtime.TEXT_CACHE_VERSION
    INFORMATIVE_TEXT_PATTERNS = sorter_runtime.INFORMATIVE_TEXT_PATTERNS
    PATTERN_CONFIG = sorter_runtime.PATTERN_CONFIG
    ENTITY_PATTERNS = sorter_runtime.ENTITY_PATTERNS
    ENTITY_ACCOUNT_PATTERNS = sorter_runtime.ENTITY_ACCOUNT_PATTERNS
    ENTITY_SOURCE_HINT_PATTERNS = sorter_runtime.ENTITY_SOURCE_HINT_PATTERNS
    DEFAULT_OFFICE_PEOPLE = sorter_runtime.DEFAULT_OFFICE_PEOPLE
    DEFAULT_OFFICE_CONTRACTORS = sorter_runtime.DEFAULT_OFFICE_CONTRACTORS
    DEFAULT_OFFICE_ENTITIES = sorter_runtime.DEFAULT_OFFICE_ENTITIES
    OFFICE_PEOPLE = sorter_runtime.OFFICE_PEOPLE
    OFFICE_CONTRACTORS = sorter_runtime.OFFICE_CONTRACTORS
    OFFICE_CONTRACTOR_FOLDERS = sorter_runtime.OFFICE_CONTRACTOR_FOLDERS
    OFFICE_ENTITIES = sorter_runtime.OFFICE_ENTITIES
    OFFICE_CATEGORIES = sorter_runtime.OFFICE_CATEGORIES
    RULE_SETTINGS = sorter_runtime.RULE_SETTINGS
    CATEGORY_PATTERNS = sorter_runtime.CATEGORY_PATTERNS
    TAX_PATTERNS = sorter_runtime.TAX_PATTERNS
    INSURANCE_ACCIDENT_PATTERNS = sorter_runtime.INSURANCE_ACCIDENT_PATTERNS
    USN_PATTERNS = sorter_runtime.USN_PATTERNS
    BANK_COMMISSION_PATTERNS = sorter_runtime.BANK_COMMISSION_PATTERNS


_sync_runtime_exports()


def refresh_runtime_config() -> None:
    sorter_runtime.refresh_runtime_config()
    _sync_runtime_exports()


def classification_runtime() -> classification.ClassificationRuntime:
    return sorter_runtime.classification_runtime()


def extraction_runtime() -> extraction.ExtractionRuntime:
    return sorter_runtime.extraction_runtime()


def profile_document(path: Path) -> document_profile.DocumentProfile:
    return document_profile.profile_document(path, runtime=extraction_runtime(), file_text_fn=file_text)


def extract_invoice_amount(text: str, source_name: str) -> str | None:
    existing = re.search(r"_(\d+(?:-\d{2}))(?=\.[^.]+$)", source_name)
    search_space = text.replace("\xa0", " ")
    patterns = [
        r"(?:всего\s*к\s*оплате|сумма\s*к\s*оплате|итого\s*с\s*ндс)\D{0,40}(\d{1,3}(?: \d{3})*[.,]\d{2}|\d+[.,]\d{2})",
        r"(?:к\s*оплате|итого)\D{0,40}(\d{1,3}(?: \d{3})*[.,]\d{2}|\d+[.,]\d{2})",
        r"(?:amount\s+due|total\s+amount|total)\D{0,40}(\d{1,3}(?: \d{3})*[.,]\d{2}|\d+[.,]\d{2})",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, search_space, re.IGNORECASE):
            amount = normalize_amount_token(match.group(1))
            if amount:
                return amount
    return existing.group(1) if existing else None


def match_any(patterns: Iterable[str], text: str) -> bool:
    return sorter_classification.match_any(patterns, text)


def file_text(path: Path) -> str:
    return extraction.file_text(path, runtime=extraction_runtime())


def text_cache_path(path: Path) -> Path:
    return extraction.text_cache_path(path, runtime=extraction_runtime())


def load_disk_cached_text(path: Path) -> str | None:
    return extraction.load_disk_cached_text(path, runtime=extraction_runtime())


def save_disk_cached_text(path: Path, text: str) -> None:
    extraction.save_disk_cached_text(path, text, runtime=extraction_runtime())


def normalize_extracted_text(text: str) -> str:
    return extraction.normalize_extracted_text(text)


def looks_like_pdf_source_dump(text: str) -> bool:
    return extraction.looks_like_pdf_source_dump(text)


def informative_text_lines(text: str) -> list[str]:
    return extraction.informative_text_lines(text, runtime=extraction_runtime())


def choose_best_extracted_text(candidates: list[tuple[str, str]]) -> str:
    return extraction.choose_best_extracted_text(candidates, runtime=extraction_runtime())


def best_candidate_quality(candidates: list[tuple[str, str]]) -> tuple[str, int]:
    return extraction.best_candidate_quality(candidates, runtime=extraction_runtime())


def extracted_text_is_good(text: str, score: int, *, min_score: int = 240) -> bool:
    return extraction.extracted_text_is_good(text, score, runtime=extraction_runtime(), min_score=min_score)


read_openxml_text = extraction.read_openxml_text
read_textutil_text = extraction.read_textutil_text
normalize_extracted_text = extraction.normalize_extracted_text
looks_like_pdf_source_dump = extraction.looks_like_pdf_source_dump
read_mdls_text = extraction.read_mdls_text
parse_pdf_cmap = extraction.parse_pdf_cmap
extract_pdf_strings = extraction.extract_pdf_strings
decode_pdf_string = extraction.decode_pdf_string
pdf_unescape = extraction.pdf_unescape
is_garbled_text = extraction.is_garbled_text
pdf_text_score = extraction.pdf_text_score
run_command = extraction.run_command


def read_sips_ocr_text(path: Path) -> str:
    return extraction.read_sips_ocr_text(path, runtime=extraction_runtime())


def read_pdf_native_ocr_text(path: Path) -> str:
    return extraction.read_pdf_native_ocr_text(path, runtime=extraction_runtime())


def read_image_text(path: Path) -> str:
    return extraction.read_image_text(path, runtime=extraction_runtime())


def read_legacy_document_text(path: Path) -> str:
    return extraction.read_legacy_document_text(path, runtime=extraction_runtime())


def read_generic_document_text(path: Path) -> str:
    return extraction.read_generic_document_text(path, runtime=extraction_runtime())


def ocr_pdf_by_pages(path: Path, ocr_binary: Path) -> str:
    return extraction.ocr_pdf_by_pages(path, ocr_binary, runtime=extraction_runtime())


def read_pdf_text(path: Path) -> str:
    return extraction.read_pdf_text(path, runtime=extraction_runtime())


def command_exists(name: str) -> bool:
    return extraction.command_exists(name, runtime=extraction_runtime())


def read_pdftotext_text(path: Path) -> str:
    return extraction.read_pdftotext_text(path, runtime=extraction_runtime())


def read_mutool_text(path: Path) -> str:
    return extraction.read_mutool_text(path, runtime=extraction_runtime())


def read_tesseract_text(path: Path) -> str:
    return extraction.read_tesseract_text(path, runtime=extraction_runtime())


def read_ocrmypdf_text(path: Path) -> str:
    return extraction.read_ocrmypdf_text(path, runtime=extraction_runtime())


def available_ocr_binary() -> Path | None:
    return extraction.available_ocr_binary(runtime=extraction_runtime())


def ocr_via_rendered_image(path: Path, ocr_binary: Path) -> str:
    return extraction.ocr_via_rendered_image(path, ocr_binary)


def read_quicklook_ocr_text(path: Path) -> str:
    return extraction.read_quicklook_ocr_text(path, runtime=extraction_runtime())


def extract_pdf_text_layer(path: Path) -> str:
    return extraction.extract_pdf_text_layer(path)


def detect_entity(text: str, name_text: str, path_text: str = "") -> str | None:
    return sorter_classification.detect_entity(
        text,
        name_text,
        path_text,
        runtime_factory=classification_runtime,
        match_any_fn=match_any,
    )


def detect_entity_signal(text: str, name_text: str, path_text: str = ""):
    return sorter_classification.detect_entity_signal(
        text,
        name_text,
        path_text,
        runtime_factory=classification_runtime,
        match_any_fn=match_any,
        bounded_confidence_fn=bounded_confidence,
    )


def bank_payment_recipient(text: str) -> str:
    return sorter_classification.bank_payment_recipient(text)


def bank_name(text: str) -> str:
    return sorter_classification.bank_name(text)


def bank_payment_purpose(text: str) -> str:
    return sorter_classification.bank_payment_purpose(text)


def detect_office(text: str, name_text: str, entity: str | None) -> tuple[str | None, str]:
    return sorter_classification.detect_office(
        text,
        name_text,
        entity,
        runtime_factory=classification_runtime,
        bank_payment_recipient_fn=bank_payment_recipient,
        bank_payment_purpose_fn=bank_payment_purpose,
    )


def detect_office_signal(text: str, name_text: str, entity: str | None):
    return sorter_classification.detect_office_signal(
        text,
        name_text,
        entity,
        runtime_factory=classification_runtime,
        bank_payment_recipient_fn=bank_payment_recipient,
        bank_payment_purpose_fn=bank_payment_purpose,
        bounded_confidence_fn=bounded_confidence,
        normalize_text_fn=normalize_text,
    )


def looks_like_salary_payment(text: str, name_text: str) -> bool:
    return sorter_classification.looks_like_salary_payment(
        text,
        name_text,
        runtime_factory=classification_runtime,
        normalize_text_fn=normalize_text,
    )


def is_payment_order(text: str, name_text: str) -> bool:
    return "платежное поручение" in text


def is_bank_order(text: str) -> bool:
    return "банковский ордер" in text


def detect_category(text: str, name_text: str) -> tuple[str | None, str]:
    return sorter_classification.detect_category(
        text,
        name_text,
        runtime_factory=classification_runtime,
        bank_payment_recipient_fn=bank_payment_recipient,
        bank_payment_purpose_fn=bank_payment_purpose,
        normalize_text_fn=normalize_text,
        match_any_fn=match_any,
        bounded_confidence_fn=bounded_confidence,
    )


def detect_category_signal(text: str, name_text: str):
    return sorter_classification.detect_category_signal(
        text,
        name_text,
        runtime_factory=classification_runtime,
        bank_payment_recipient_fn=bank_payment_recipient,
        bank_payment_purpose_fn=bank_payment_purpose,
        normalize_text_fn=normalize_text,
        match_any_fn=match_any,
        bounded_confidence_fn=bounded_confidence,
    )


def destination_for(
    source: Path,
    archive_root: Path,
    office: str | None,
    category: str | None,
    entity: str | None,
) -> tuple[Path | None, str]:
    return sorter_routing.destination_for(source, archive_root, office, category, entity, deps=routing_dependencies())


def safe_filename(source: Path, office: str | None, category: str | None, entity: str | None) -> str:
    return sorter_naming.safe_filename(source, office, category, entity, deps=naming_dependencies())


def extract_first_date(text: str) -> str | None:
    return sorter_naming.extract_first_date(text)


def extract_date_from_name(name: str) -> str | None:
    return sorter_naming.extract_date_from_name(name)


def extract_vtb_filename_metadata(name: str) -> dict[str, str | None] | None:
    return sorter_naming.extract_vtb_filename_metadata(name, normalize_piece=normalize_piece)


def extract_amount_from_name(name: str) -> str | None:
    return sorter_naming.extract_amount_from_name(name)


def extract_numeric_suffix(name: str) -> str | None:
    return sorter_naming.extract_numeric_suffix(name)


def extract_payment_order_number(text: str, name: str) -> str | None:
    return sorter_naming.extract_payment_order_number(text, name, normalize_text=normalize_text, normalize_piece=normalize_piece)


def extract_bank_order_number(text: str, name: str) -> str | None:
    return sorter_naming.extract_bank_order_number(text, name, normalize_piece=normalize_piece)


def extract_invoice_date(text: str, name: str) -> str | None:
    return sorter_naming.extract_invoice_date(text, name)


def canonical_employee_name(text: str) -> str | None:
    return sorter_naming.canonical_employee_name(text, office_people=OFFICE_PEOPLE, normalize_text=normalize_text)


def extract_invoice_counterparty(text: str, name: str) -> str | None:
    return sorter_naming.extract_invoice_counterparty(
        text,
        name,
        office_contractors=OFFICE_CONTRACTORS,
        normalize_text=normalize_text,
        normalize_piece=normalize_piece,
    )


def extract_invoice_number(text: str, name: str) -> str | None:
    return sorter_naming.extract_invoice_number(text, name, normalize_text=normalize_text, normalize_piece=normalize_piece)


def normalize_date_token(value: str) -> str:
    return sorter_naming.normalize_date_token(value)


def normalize_structured_filename(name: str, text: str = "") -> str:
    return sorter_naming.normalize_structured_filename(name, normalize_piece=normalize_piece)


def extract_payment_order_amount(text: str) -> str | None:
    return sorter_naming.extract_payment_order_amount(
        text,
        strip_full_dates=strip_full_dates,
        normalize_amount_token=normalize_amount_token,
        extract_amount_from_words=extract_amount_from_words,
    )


def extract_bank_order_amount(text: str) -> str | None:
    return sorter_naming.extract_bank_order_amount(
        text,
        strip_full_dates=strip_full_dates,
        normalize_amount_token=normalize_amount_token,
        extract_amount_from_words=extract_amount_from_words,
    )


def classify(path: Path, archive_root: Path) -> Classification:
    result = sorter_classification.classify(
        path,
        archive_root,
        file_text=file_text,
        safe_filename=safe_filename,
        runtime_factory=classification_runtime,
        normalize_text_fn=normalize_text,
        match_any_fn=match_any,
        bounded_confidence_fn=bounded_confidence,
        bank_payment_recipient_fn=bank_payment_recipient,
        bank_payment_purpose_fn=bank_payment_purpose,
    )
    if path in file_collection.PRESERVED_MULTIPAGE_PDFS and result.category in {"Зарплата", "Комиссии", "Налоги", "Взносы"}:
        return replace(result, destination=archive_root / "Требует_ручной_проверки", new_name=path.name,
                       confidence=40, requires_manual_review=True,
                       reason="Многостраничный платежный документ: проверьте состав выплат; при необходимости используйте Разбивку PDF.")
    if path in sorter_runtime.heavy_ocr_manual_review_paths():
        cached_text = sorter_runtime.extraction_runtime().text_cache.get(path, "")
        if not normalize_text(cached_text).strip():
            new_name = path.name
        else:
            new_name = result.new_name
        return Classification(
            destination=Path(archive_root) / "Требует_ручной_проверки",
            office=result.office,
            category=result.category,
            entity=result.entity,
            reason=f"{result.reason}; файл отправлен в ручную проверку вместо тяжелого OCR",
            new_name=new_name,
            confidence=min(result.confidence, 30),
            requires_manual_review=True,
            trace=result.trace + ["heavy OCR отключен, файл отправлен в ручную проверку"],
        )
    return result


refresh_runtime_config()


def ensure_structure(archive_root: Path, optional_roots: set[str], dry_run: bool) -> None:
    file_ops.ensure_structure(
        archive_root,
        optional_roots,
        dry_run,
        offices=OFFICES,
        office_categories=OFFICE_CATEGORIES,
        create_folders_only_when_documents_exist=RULE_SETTINGS.folder_creation.create_folders_only_when_documents_exist,
        do_not_create_empty_folders_in_advance=RULE_SETTINGS.folder_creation.do_not_create_empty_folders_in_advance,
        create_manual_review_folder_only_when_needed=RULE_SETTINGS.folder_creation.create_manual_review_folder_only_when_needed,
    )


def move_or_copy(source: Path, destination: Path, mode: str, dry_run: bool) -> Path:
    return file_ops.move_or_copy(
        source,
        destination,
        mode,
        dry_run,
        unique_destination_fn=unique_destination,
        generated_source_roots=GENERATED_SOURCE_ROOTS,
        keep_unique_suffix_on_conflict=RULE_SETTINGS.naming.keep_unique_suffix_on_conflict and RULE_SETTINGS.folder_creation.protect_existing_files_with_unique_suffix,
    )


def salary_payment_identity(path: Path, result: Classification) -> tuple[tuple[str, str, str], str] | None:
    office = (result.office or "").strip()
    if result.category != "Зарплата" or not office:
        return None

    name_text = normalize_text(Path(result.new_name).stem.replace("_", " "))
    person = next(
        (candidate for candidate in OFFICE_PEOPLE.get(office, []) if normalize_text(candidate) in name_text),
        None,
    )
    text = ""
    if person is None:
        text = normalize_text(file_text(path))
        person = sorter_naming.canonical_employee_name(
            text,
            office_people={office: OFFICE_PEOPLE.get(office, [])},
            normalize_text=normalize_text,
        )
    if person is None:
        return None

    amount = extract_amount_from_name(result.new_name)
    if amount is None:
        if not text:
            text = normalize_text(file_text(path))
        amount = extract_payment_order_amount(text) or extract_bank_order_amount(text)
    if amount is None:
        return None

    return (office, normalize_text(person), amount), person


def existing_salary_payment_keys(archive_root: Path) -> set[tuple[str, str, str]]:
    keys: set[tuple[str, str, str]] = set()
    if not archive_root.exists():
        return keys
    for office in sorting_receipt_archive.offices_with_receipts(archive_root, "Зарплата"):
        for path in sorting_receipt_archive.receipt_pdf_paths(archive_root, office, "Зарплата"):
            result = Classification(
                destination=archive_root / office / "Зарплата",
                office=office,
                category="Зарплата",
                entity=None,
                reason="",
                new_name=path.name,
                confidence=100,
                requires_manual_review=False,
                trace=[],
            )
            identity = salary_payment_identity(path, result)
            if identity is not None:
                keys.add(identity[0])
    return keys


def mark_duplicate_salary_payments(
    files: list[Path],
    classifications: list[Classification],
    archive_root: Path,
) -> int:
    grouped: dict[tuple[str, str, str], list[tuple[int, str]]] = {}
    for index, (path, result) in enumerate(zip(files, classifications)):
        identity = salary_payment_identity(path, result)
        if identity is None:
            continue
        key, person = identity
        grouped.setdefault(key, []).append((index, person))

    existing = existing_salary_payment_keys(archive_root)
    duplicate_keys = {key for key, values in grouped.items() if len(values) > 1 or key in existing}
    marked = 0
    for key in duplicate_keys:
        _, _, amount = key
        display_amount = amount.replace("-", ",")
        for index, person in grouped[key]:
            result = classifications[index]
            duplicate_reason = (
                f"Возможный повтор зарплаты: сотрудник {person}, сумма {display_amount}. "
                "Откройте чеки и выберите: оставить как реальную выплату или сохранить как исключенный повтор."
            )
            reason = duplicate_reason if not result.requires_manual_review else f"{result.reason}; {duplicate_reason}"
            classifications[index] = replace(
                result,
                destination=Path(archive_root) / "Требует_ручной_проверки",
                reason=reason,
                confidence=min(result.confidence, 40),
                requires_manual_review=True,
                salary_duplicate=True,
                trace=[*result.trace, f"совпали сотрудник и сумма: {person}, {display_amount}"],
            )
            marked += 1
    return marked


def unique_destination(destination: Path, *, keep_unique_suffix_on_conflict: bool = True) -> Path:
    return file_ops.unique_destination(destination, keep_unique_suffix_on_conflict=keep_unique_suffix_on_conflict)


def split_combined_pdf(path: Path, cache_root: Path) -> list[Path]:
    return file_collection.split_combined_pdf(
        path,
        cache_root=cache_root,
        swift_pdf_splitter=SWIFT_PDF_SPLITTER,
        run_command=run_command,
    )


def collect_files(input_dir: Path, archive_root: Path) -> list[Path]:
    return file_collection.collect_files(
        input_dir,
        archive_root,
        supported_extensions=SUPPORTED_EXTENSIONS,
        swift_pdf_splitter=SWIFT_PDF_SPLITTER,
        run_command=run_command,
    )


def write_manual_review_report(archive_root: Path, items: list[tuple[Path, Classification]], dry_run: bool) -> None:
    manual_review.write_manual_review_report(
        archive_root,
        items,
        dry_run,
        enabled=RULE_SETTINGS.manual_review.create_manual_review_report,
    )


def effective_destination(destination: Path, archive_root: Path, *, requires_manual_review: bool = False) -> Path:
    return file_ops.effective_destination(
        destination,
        archive_root,
        create_special_subfolders_by_routing_rules=RULE_SETTINGS.folder_creation.create_special_subfolders_by_routing_rules,
        requires_manual_review=requires_manual_review,
    )


__all__ = [name for name in globals() if not name.startswith("_")]
