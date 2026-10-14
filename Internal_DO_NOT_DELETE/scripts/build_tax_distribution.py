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
import build_insurance_distribution as insurance
from sorting_budget_payments import distribution_kind


DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "Пример" / "109" / "Ндфл и Взносы"
ROOT = DEFAULT_ROOT
OUTPUT = ROOT / "Распределение_налогов_ПРИМЕР.xlsx"
OFFICE_ORDER = ["76", "93", "94", "102", "109"]


def parse_date(text: str) -> str | None:
    return insurance.parse_date(text)


def parse_amount(text: str) -> float | None:
    amount_token = sd.extract_payment_order_amount(text) or sd.extract_bank_order_amount(text)
    if not amount_token:
        return None
    raw = amount_token.replace(" ", "")
    rub, kop = raw.split("-")
    return float(f"{int(rub)}.{kop}")


def collect_tax_rows(root: Path, *, kind: str = "tax") -> list[tuple[str, float, str]]:
    rows: list[tuple[str, float, str]] = []
    for path in sorted(root.glob("*.pdf")):
        text = sd.normalize_text(sd.file_text(path))
        category, _ = sd.detect_category(text, sd.normalize_text(path.name))
        if distribution_kind(text, category) != kind:
            continue
        date, amount = insurance.payment_values(path, text)
        rows.append((date, amount, path.name))
    return rows


def write_distribution(root: Path, output: Path, tax_rows: list, resolve_offices) -> None:
    other_rows = collect_tax_rows(root, kind="other")
    extra_sheets = []
    if other_rows:
        extra_sheets.append(("Без распределения", build_other_payments_sheet(other_rows)))
    salary_employee_counts.write_archive_distribution(
        output, tax_rows, resolve_offices, build_sheet, "Налоги", extra_sheets=extra_sheets,
    )
    if other_rows:
        print(f"В листе 'Без распределения': {len(other_rows)} платежей. Они не распределены по сотрудникам.")


def build_other_payments_sheet(rows: list[tuple[str, float, str]]) -> str:
    xml_rows = []
    values = [("Дата", "Сумма", "Файл"), *rows]
    total = sum((Decimal(str(row[1])) for row in rows), Decimal("0.00"))
    values.append(("ИТОГО без распределения", total, ""))
    for index, row in enumerate(values, 1):
        cells = []
        for column, value in zip("ABC", row):
            numeric = column == "B" and index > 1
            cells.append(cell(f"{column}{index}", f"{value:.2f}" if numeric else str(value),
                              style=2 if numeric else (1 if index == 1 else None), cell_type="n" if numeric else "inlineStr"))
        xml_rows.append(f'<row r="{index}">{"".join(cells)}</row>')
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<cols><col min="1" max="1" width="30" customWidth="1"/>'
            '<col min="2" max="2" width="18" customWidth="1"/>'
            '<col min="3" max="3" width="65" customWidth="1"/></cols>'
            '<sheetData>' + ''.join(xml_rows) + '</sheetData></worksheet>')


def office_employee_rows(root: Path | None = None, tax_rows: list[tuple[str, float, str]] | None = None) -> list[tuple[str, int]]:
    archive_root = salary_employee_counts.archive_root_for_tax_root(root) if root else None
    offices = salary_employee_counts.company_offices("ПРИМЕР", OFFICE_ORDER)
    return salary_employee_counts.office_employee_rows(archive_root, offices)


def cell(ref: str, value: str, style: int | None = None, cell_type: str = "inlineStr") -> str:
    style_attr = f' s="{style}"' if style is not None else ""
    if cell_type == "n":
        return f'<c r="{ref}"{style_attr}><v>{value}</v></c>'
    return f'<c r="{ref}" t="inlineStr"{style_attr}><is><t>{escape(value)}</t></is></c>'


def build_sheet(tax_rows: list[tuple[str, float, str]], offices: list[tuple[str, int]]) -> str:
    xml_rows: list[str] = []
    row_num = 1

    header = [
        cell("A1", "Дата", style=1),
        cell("B1", "Сумма", style=1),
        cell("C1", "Файл", style=1),
    ]
    xml_rows.append(f'<row r="{row_num}">{"".join(header)}</row>')

    total_taxes = Decimal("0.00")
    for date, amount, filename in tax_rows:
        row_num += 1
        total_taxes += Decimal(str(amount))
        xml_rows.append(
            f'<row r="{row_num}">'
            f'{cell(f"A{row_num}", date)}'
            f'{cell(f"B{row_num}", f"{amount:.2f}", style=2, cell_type="n")}'
            f'{cell(f"C{row_num}", filename)}'
            f"</row>"
        )

    row_num += 2
    total_employees = sum(count for _, count in offices)
    average_tax = total_taxes / total_employees if total_employees else 0.0
    allocation = salary_employee_counts.allocate_money(total_taxes, offices)

    summary_rows = [
        ("Общий итог налогов", f"{total_taxes:.2f}", "n", 3),
        ("Общее количество сотрудников", str(total_employees), "n", 1),
        ("Средний налог на сотрудника", f"{average_tax:.2f}", "n", 3),
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
        cell(f"C{row_num}", "Средний налог", style=1),
        cell(f"D{row_num}", "Налог офиса", style=1),
    ]
    xml_rows.append(f'<row r="{row_num}">{"".join(office_header)}</row>')

    for office, count in offices:
        row_num += 1
        office_tax = allocation[office]
        xml_rows.append(
            f'<row r="{row_num}">'
            f'{cell(f"A{row_num}", office)}'
            f'{cell(f"B{row_num}", str(count), style=1, cell_type="n")}'
            f'{cell(f"C{row_num}", f"{average_tax:.2f}", style=2, cell_type="n")}'
            f'{cell(f"D{row_num}", f"{office_tax:.2f}", style=2, cell_type="n")}'
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
    xlsx_builder.build_workbook_xlsx(output, sheet_xml, "Налоги")


def main() -> None:
    global ROOT, OUTPUT
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output-name", default="Распределение_налогов_ПРИМЕР.xlsx")
    args = parser.parse_args()
    ROOT = args.root.expanduser().resolve()
    OUTPUT = ROOT / args.output_name
    tax_rows = collect_tax_rows(ROOT)
    write_distribution(ROOT, OUTPUT, tax_rows, lambda rows: office_employee_rows(ROOT, rows))
    total_taxes = sum(amount for _, amount, _ in tax_rows)
    print(
        f"rows={len(tax_rows)} total_taxes={total_taxes:.2f} "
        f"output={OUTPUT}"
    )


if __name__ == "__main__":
    main()
