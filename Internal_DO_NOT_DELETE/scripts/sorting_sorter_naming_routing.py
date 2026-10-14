from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

import sorting_sorter_naming as sorter_naming
import sorting_sorter_routing as sorter_routing


NamingRoutingDependencies = sorter_naming.NamingDependencies


def destination_for(
    source: Path,
    archive_root: Path,
    office: str | None,
    category: str | None,
    entity: str | None,
    *,
    deps: NamingRoutingDependencies,
) -> tuple[Path | None, str]:
    routing_deps = sorter_routing.RoutingDependencies(
        file_text=deps.file_text,
        normalize_text=deps.normalize_text,
    )
    return sorter_routing.destination_for(source, archive_root, office, category, entity, deps=routing_deps)


def _naming_dependencies(deps: NamingRoutingDependencies) -> sorter_naming.NamingDependencies:
    return deps


def safe_filename(
    source: Path,
    office: str | None,
    category: str | None,
    entity: str | None,
    *,
    deps: NamingRoutingDependencies,
) -> str:
    return sorter_naming.safe_filename(source, office, category, entity, deps=_naming_dependencies(deps))


def extract_first_date(text: str) -> str | None:
    return sorter_naming.extract_first_date(text)


def extract_date_from_name(name: str) -> str | None:
    return sorter_naming.extract_date_from_name(name)


def extract_vtb_filename_metadata(name: str, *, normalize_piece: Callable[[str], str]) -> dict[str, str | None] | None:
    return sorter_naming.extract_vtb_filename_metadata(name, normalize_piece=normalize_piece)


def extract_amount_from_name(name: str) -> str | None:
    return sorter_naming.extract_amount_from_name(name)


def extract_numeric_suffix(name: str) -> str | None:
    return sorter_naming.extract_numeric_suffix(name)


def extract_payment_order_number(
    text: str,
    name: str,
    *,
    normalize_text: Callable[[str], str],
    normalize_piece: Callable[[str], str],
) -> str | None:
    return sorter_naming.extract_payment_order_number(text, name, normalize_text=normalize_text, normalize_piece=normalize_piece)


def extract_bank_order_number(text: str, name: str, *, normalize_piece: Callable[[str], str]) -> str | None:
    return sorter_naming.extract_bank_order_number(text, name, normalize_piece=normalize_piece)


def extract_invoice_date(text: str, name: str) -> str | None:
    return sorter_naming.extract_invoice_date(text, name)


def canonical_employee_name(
    text: str,
    *,
    office_people: dict[str, list[str]],
    normalize_text: Callable[[str], str],
) -> str | None:
    return sorter_naming.canonical_employee_name(text, office_people=office_people, normalize_text=normalize_text)


def extract_invoice_counterparty(
    text: str,
    name: str,
    *,
    office_contractors: dict[str, dict[str, list[str]]],
    normalize_text: Callable[[str], str],
    normalize_piece: Callable[[str], str],
) -> str | None:
    return sorter_naming.extract_invoice_counterparty(
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
    return sorter_naming.extract_invoice_number(text, name, normalize_text=normalize_text, normalize_piece=normalize_piece)


def normalize_date_token(value: str) -> str:
    return sorter_naming.normalize_date_token(value)


def normalize_structured_filename(name: str, *, normalize_piece: Callable[[str], str]) -> str:
    return sorter_naming.normalize_structured_filename(name, normalize_piece=normalize_piece)


def extract_payment_order_amount(
    text: str,
    *,
    strip_full_dates: Callable[[str], str],
    normalize_amount_token: Callable[[str], str],
    extract_amount_from_words: Callable[[str], str | None],
) -> str | None:
    return sorter_naming.extract_payment_order_amount(
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
    return sorter_naming.extract_bank_order_amount(
        text,
        strip_full_dates=strip_full_dates,
        normalize_amount_token=normalize_amount_token,
        extract_amount_from_words=extract_amount_from_words,
    )
