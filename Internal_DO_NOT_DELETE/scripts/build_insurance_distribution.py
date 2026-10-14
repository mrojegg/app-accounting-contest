#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from decimal import Decimal
from pathlib import Path
from xml.sax.saxutils import escape

import sort_documents as sd
import salary_employee_counts
import xlsx_builder
import sorting_naming
import sorting_review_fields
from sorting_budget_payments import distribution_kind, is_insurance_payment


DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "Пример" / "109" / "Ндфл и Взносы"
ROOT = DEFAULT_ROOT
OUTPUT = ROOT / "Распределение_взносов_ПРИМЕР.xlsx"
OFFICE_ORDER = ["76", "93", "94", "102", "109"]


def parse_date(text: str) -> str | None:
    date = sorting_naming.extract_payment_date(text)
    return date.replace("-", ".") if date else None


def parse_amount(text: str) -> float | None:
    token = sd.extract_payment_order_amount(text) or sd.extract_bank_order_amount(text)
    if token:
        return float(token.replace(" ", "").replace("-", ".", 1))
    search_area = text.split("отметки банка")[0]
    matches = re.findall(r"(?:^| )(\d{1,3}(?: \d{3})*-\d{2}|\d+-\d{2})\b", search_area)
    if not matches:
        return None
    raw = matches[-1].replace(" ", "")
    rub, kop = raw.split("-")
    return float(f"{int(rub)}.{kop}")


def parse_filename_date_amount(path: Path) -> tuple[str, float] | None:
    match = re.search(r"_(\d{2}-\d{2}-\d{4})(?:_.+)?_(\d+-\d{2})\.pdf$", path.name, re.IGNORECASE)
    if not match:
        return None
    return match.group(1).replace("-", "."), float(match.group(2).replace("-", ".", 1))


def is_explicit_insurance_document(category: str | None, combined: str) -> bool:
    return category == "Взносы" or is_insurance_payment(combined)


def payment_values(path: Path, text: str) -> tuple[str, float]:
    confirmed = sorting_review_fields.confirmed_fields(path)
    if confirmed:
        return confirmed["date"].replace("-", "."), float(confirmed["amount"])
    date = parse_date(text)
    amount = parse_amount(text)
    if not date or amount is None:
        fallback = parse_filename_date_amount(path)
        if fallback is None:
            raise ValueError(f"Не прочитана дата или сумма платежа: {path.name}")
        fallback_date, fallback_amount = fallback
        date = sorting_naming.extract_payment_execution_date(text)
        date = date.replace("-", ".") if date else fallback_date
        amount = amount if amount is not None else fallback_amount
    return date, amount


def collect_rows(root: Path) -> list[tuple[str, float, str]]:
    rows: list[tuple[str, float, str]] = []
    for path in sorted(root.glob("*.pdf")):
        text = sd.normalize_text(sd.file_text(path))
        category, _ = sd.detect_category(text, sd.normalize_text(path.name))
        if distribution_kind(text, category) != "insurance":
            continue
        date, amount = payment_values(path, text)
        rows.append((date, amount, path.name))
    return rows


def office_employee_rows(root: Path | None = None, rows: list[tuple[str, float, str]] | None = None) -> list[tuple[str, int]]:
    archive_root = salary_employee_counts.archive_root_for_tax_root(root) if root else None
    offices = salary_employee_counts.company_offices("ПРИМЕР", OFFICE_ORDER)
    return salary_employee_counts.office_employee_rows(archive_root, offices)


def cell(ref: str, value: str, style: int | None = None, cell_type: str = "inlineStr") -> str:
    style_attr = f' s="{style}"' if style is not None else ""
    if cell_type == "n":
        return f'<c r="{ref}"{style_attr}><v>{value}</v></c>'
    return f'<c r="{ref}" t="inlineStr"{style_attr}><is><t>{escape(value)}</t></is></c>'


def build_sheet(rows: list[tuple[str, float, str]], offices: list[tuple[str, int]]) -> str:
    xml_rows: list[str] = []
    row_num = 1

    header = [
        cell("A1", "Дата", style=1),
        cell("B1", "Сумма", style=1),
        cell("C1", "Файл", style=1),
    ]
    xml_rows.append(f'<row r="{row_num}">{"".join(header)}</row>')

    total_value = Decimal("0.00")
    for date, amount, filename in rows:
        row_num += 1
        total_value += Decimal(str(amount))
        xml_rows.append(
            f'<row r="{row_num}">'
            f'{cell(f"A{row_num}", date)}'
            f'{cell(f"B{row_num}", f"{amount:.2f}", style=2, cell_type="n")}'
            f'{cell(f"C{row_num}", filename)}'
            f"</row>"
        )

    row_num += 2
    total_employees = sum(count for _, count in offices)
    average_value = total_value / total_employees if total_employees else 0.0
    allocation = salary_employee_counts.allocate_money(total_value, offices)

    summary_rows = [
        ("Общий итог взносов", f"{total_value:.2f}", "n", 3),
        ("Общее количество сотрудников", str(total_employees), "n", 1),
        ("Средний взнос на сотрудника", f"{average_value:.2f}", "n", 3),
    ]
    for label, value, kind, style in summary_rows:
        xml_rows.append(
            f'<row r="{row_num}">'
            f'{cell(f"A{row_num}", label, style=1)}'
            f'{cell(f"B{row_num}", value, style=style, cell_type=kind)}'
            f"</row>"
        )
        row_num += 1

    office_header = [
        cell(f"A{row_num}", "Офис", style=1),
        cell(f"B{row_num}", "Количество сотрудников", style=1),
        cell(f"C{row_num}", "Средний взнос", style=1),
        cell(f"D{row_num}", "Взнос офиса", style=1),
    ]
    xml_rows.append(f'<row r="{row_num}">{"".join(office_header)}</row>')

    for office, count in offices:
        row_num += 1
        office_value = allocation[office]
        xml_rows.append(
            f'<row r="{row_num}">'
            f'{cell(f"A{row_num}", office)}'
            f'{cell(f"B{row_num}", str(count), style=1, cell_type="n")}'
            f'{cell(f"C{row_num}", f"{average_value:.2f}", style=2, cell_type="n")}'
            f'{cell(f"D{row_num}", f"{office_value:.2f}", style=2, cell_type="n")}'
            f"</row>"
        )

    dimension = f"A1:D{row_num}"
    cols = (
        '<cols>'
        '<col min="1" max="1" width="18" customWidth="1"/>'
        '<col min="2" max="2" width="18" customWidth="1"/>'
        '<col min="3" max="3" width="48" customWidth="1"/>'
        '<col min="4" max="4" width="18" customWidth="1"/>'
        "</cols>"
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<dimension ref=\"{dimension}\"/>"
        '<sheetViews><sheetView workbookViewId="0"/></sheetViews>'
        f"{cols}"
        '<sheetData>'
        + "".join(xml_rows)
        + "</sheetData>"
        "</worksheet>"
    )


def build_workbook_xlsx(output: Path, sheet_xml: str) -> None:
    xlsx_builder.build_workbook_xlsx(output, sheet_xml, "Взносы")


def main() -> None:
    global ROOT, OUTPUT
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output-name", default="Распределение_взносов_ПРИМЕР.xlsx")
    args = parser.parse_args()
    ROOT = args.root.expanduser().resolve()
    OUTPUT = ROOT / args.output_name
    rows = collect_rows(ROOT)
    salary_employee_counts.write_archive_distribution(OUTPUT, rows, lambda payments: office_employee_rows(ROOT, payments), build_sheet, "Взносы")
    total_value = sum(amount for _, amount, _ in rows)
    print(
        f"rows={len(rows)} total_value={total_value:.2f} "
        f"output={OUTPUT}"
    )


if __name__ == "__main__":
    main()
