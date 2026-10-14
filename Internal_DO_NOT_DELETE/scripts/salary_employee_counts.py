from __future__ import annotations

import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import build_salary_tables as salary_tables
import sort_documents as sd
import sorting_receipt_archive
import xlsx_builder


def company_offices(entity: str, fallback: list[str]) -> list[str]:
    def key(value: str) -> str:
        return re.sub(r"^(?:ооо|ао|пао|ип)\s+", "", sd.normalize_text(value)).strip(' "«»')
    if not sd.OFFICE_ENTITIES:
        return list(fallback)
    return sorted((office for office, value in sd.OFFICE_ENTITIES.items() if key(value) == key(entity)), key=int)


def related_offices(office: str) -> list[str]:
    entity = sd.OFFICE_ENTITIES.get(office, "")
    return company_offices(entity, [office]) if entity else [office]


def allocate_money(total: Decimal | float, offices: list[tuple[str, int]]) -> dict[str, Decimal]:
    cents = int((Decimal(str(total)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    count = sum(value for _, value in offices)
    if cents and not count:
        raise ValueError("В архиве нет подтвержденных получателей зарплаты. Распределение не создано.")
    if not count:
        return {office: Decimal("0.00") for office, _ in offices}
    shares = {office: abs(cents) * value // count for office, value in offices}
    remaining = abs(cents) - sum(shares.values())
    order = sorted(offices, key=lambda item: (-(abs(cents) * item[1] % count), int(item[0])))
    for office, _ in order[:remaining]:
        shares[office] += 1
    sign = -1 if cents < 0 else 1
    return {office: Decimal(value * sign) / 100 for office, value in shares.items()}


def write_archive_distribution(output: Path, rows: list, resolve_offices, build_sheet, title: str, *, extra_sheets: list | None = None) -> None:
    sheets = []
    if rows or not extra_sheets:
        sheets.append((title, build_sheet(rows, resolve_offices(rows))))
    sheets.extend(extra_sheets or [])
    xlsx_builder.build_multi_sheet_workbook_xlsx(output, sheets)


def month_key(value: str) -> str | None:
    match = re.search(r"\b(\d{2})[.-](\d{2})[.-](\d{4})\b", value)
    if not match:
        return None
    _day, month, year = match.groups()
    return f"{year}-{month}"


def archive_root_for_tax_root(root: Path) -> Path:
    if root.name == "Ндфл и Взносы" and root.parent.name.isdigit():
        return root.parent.parent
    return root


def salary_employee_count(archive_root: Path, office: str, months: set[str] | None = None) -> int:
    salary_paths = sorting_receipt_archive.receipt_pdf_paths(archive_root, office, "Зарплата")

    employees: set[str] = set()
    for path in salary_paths:
        parsed = salary_tables.parse_payment_name(path)
        if not parsed:
            raise ValueError(f"Не удалось прочитать зарплатный чек: {path.name}")
        raw_name, date, _amount = parsed
        if months and month_key(date) not in months:
            continue
        person = salary_tables.canonical_person_for_office(path, office, raw_name)
        employee = sd.normalize_text(person or raw_name)
        if employee:
            employees.add(employee)

    return len(employees)


def office_employee_rows(
    archive_root: Path | None,
    offices: list[str],
) -> list[tuple[str, int]]:
    if archive_root is None or not archive_root.is_dir():
        raise ValueError("Для подсчета получателей зарплаты нужна папка обрабатываемого архива.")
    # Distribution uses the entire approved payroll, even across execution months.
    return [(office, salary_employee_count(archive_root, office)) for office in offices]
