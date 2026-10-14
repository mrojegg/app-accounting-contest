from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import sorting_naming as naming


@dataclass(frozen=True)
class NamingDependencies:
    file_text: Callable[[Path], str]
    normalize_text: Callable[[str], str]
    normalize_piece: Callable[[str], str]
    office_people: dict[str, list[str]]
    office_contractors: dict[str, dict[str, list[str]]]
    bank_name: Callable[[str], str]
    bank_payment_recipient: Callable[[str], str]
    is_bank_order: Callable[[str], bool]
    is_payment_order: Callable[[str, str], bool]
    looks_like_salary_payment: Callable[[str, str], bool]
    extract_amount_from_words: Callable[[str], str | None]
    extract_invoice_amount: Callable[[str, str], str | None]
    strip_full_dates: Callable[[str], str]
    normalize_amount_token: Callable[[str], str]
    use_extracted_text_for_naming: bool
    fallback_to_original_name_when_no_text: bool
    make_names_windows_safe: bool


def safe_filename(
    source: Path,
    office: str | None,
    category: str | None,
    entity: str | None,
    *,
    deps: NamingDependencies,
) -> str:
    return naming.safe_filename(
        source,
        office,
        category,
        entity,
        file_text=deps.file_text,
        normalize_text=deps.normalize_text,
        normalize_piece=deps.normalize_piece,
        office_people=deps.office_people,
        office_contractors=deps.office_contractors,
        bank_name=deps.bank_name,
        bank_payment_recipient=deps.bank_payment_recipient,
        is_bank_order=deps.is_bank_order,
        is_payment_order=deps.is_payment_order,
        looks_like_salary_payment=deps.looks_like_salary_payment,
        extract_amount_from_words=deps.extract_amount_from_words,
        extract_invoice_amount=deps.extract_invoice_amount,
        strip_full_dates=deps.strip_full_dates,
        normalize_amount_token=deps.normalize_amount_token,
        use_extracted_text_for_naming=deps.use_extracted_text_for_naming,
        fallback_to_original_name_when_no_text=deps.fallback_to_original_name_when_no_text,
        make_names_windows_safe=deps.make_names_windows_safe,
    )


def extract_first_date(text: str) -> str | None:
    return naming.extract_first_date(text)


def extract_date_from_name(name: str) -> str | None:
    return naming.extract_date_from_name(name)


def extract_vtb_filename_metadata(name: str, *, normalize_piece: Callable[[str], str]) -> dict[str, str | None] | None:
    return naming.extract_vtb_filename_metadata(name, normalize_piece=normalize_piece)


def extract_amount_from_name(name: str) -> str | None:
    return naming.extract_amount_from_name(name)


def extract_numeric_suffix(name: str) -> str | None:
    return naming.extract_numeric_suffix(name)


def extract_payment_order_number(
    text: str,
    name: str,
    *,
    normalize_text: Callable[[str], str],
    normalize_piece: Callable[[str], str],
) -> str | None:
    return naming.extract_payment_order_number(text, name, normalize_text=normalize_text, normalize_piece=normalize_piece)


def extract_bank_order_number(text: str, name: str, *, normalize_piece: Callable[[str], str]) -> str | None:
    return naming.extract_bank_order_number(text, name, normalize_piece=normalize_piece)


def extract_invoice_date(text: str, name: str) -> str | None:
    return naming.extract_invoice_date(text, name)


def canonical_employee_name(
    text: str,
    *,
    office_people: dict[str, list[str]],
    normalize_text: Callable[[str], str],
) -> str | None:
    return naming.canonical_employee_name(text, office_people=office_people, normalize_text=normalize_text)


def extract_invoice_counterparty(
    text: str,
    name: str,
    *,
    office_contractors: dict[str, dict[str, list[str]]],
    normalize_text: Callable[[str], str],
    normalize_piece: Callable[[str], str],
) -> str | None:
    return naming.extract_invoice_counterparty(
        text,
        name,
        office_contractors=office_contractors,
        normalize_text=normalize_text,
        normalize_piece=normalize_piece,
    )


def extract_invoice_number(
    text: str,
    name: str,
    *,
    normalize_text: Callable[[str], str],
    normalize_piece: Callable[[str], str],
) -> str | None:
    return naming.extract_invoice_number(text, name, normalize_text=normalize_text, normalize_piece=normalize_piece)


def normalize_date_token(value: str) -> str:
    return naming.normalize_date_token(value)


def normalize_structured_filename(name: str, *, normalize_piece: Callable[[str], str]) -> str:
    return naming.normalize_structured_filename(name, normalize_piece=normalize_piece)


def extract_payment_order_amount(
    text: str,
    *,
    strip_full_dates: Callable[[str], str],
    normalize_amount_token: Callable[[str], str],
    extract_amount_from_words: Callable[[str], str | None],
) -> str | None:
    return naming.extract_payment_order_amount(
        text,
        strip_full_dates=strip_full_dates,
        normalize_amount_token=normalize_amount_token,
        extract_amount_from_words=extract_amount_from_words,
    )


def extract_bank_order_amount(
    text: str,
    *,
    strip_full_dates: Callable[[str], str],
    normalize_amount_token: Callable[[str], str],
    extract_amount_from_words: Callable[[str], str | None],
) -> str | None:
    return naming.extract_bank_order_amount(
        text,
        strip_full_dates=strip_full_dates,
        normalize_amount_token=normalize_amount_token,
        extract_amount_from_words=extract_amount_from_words,
    )
