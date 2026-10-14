#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime
import re
from dataclasses import dataclass
from decimal import Decimal
import os
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape

import sort_documents as sd
import pdf_merge_runtime
import sorting_config as config
import sorting_naming
import sorting_receipt_archive
import xlsx_builder
import sorting_review_fields

DEFAULT_ROOT = Path(__file__).resolve().parents[2]
ROOT = DEFAULT_ROOT


@dataclass
class PaymentRecord:
    person: str
    date: str
    amount: Decimal
    source_name: str
    source_path: Path | None = None


SalaryTableSettings = config.SalaryTableSettings


def office_order(root: Path) -> list[str]:
    known = list(sd.OFFICES)
    receipt_offices = sorting_receipt_archive.offices_with_receipts(root, "Зарплата")
    existing = [office for office in known if office in receipt_offices]
    extra = [office for office in receipt_offices if office not in known]
    return [*existing, *extra]


def amount_from_name(raw: str) -> Decimal:
    return Decimal(raw.replace("-", ".", 1))


def amount_from_text(path: Path) -> Decimal | None:
    raw_text = sd.file_text(path)
    text = sd.normalize_text(raw_text)
    amount_token = sd.extract_payment_order_amount(text) or sd.extract_bank_order_amount(text)
    if not amount_token:
        word_match = re.search(
            r"сумма\s+прописью\s+([а-яё\s-]+?)\s+руб(?:ль|ля|лей)\s+(\d{1,2}|[а-яё\s-]+?)\s+коп",
            raw_text,
            re.IGNORECASE,
        )
        if word_match:
            rub = sd.parse_russian_number_words(word_match.group(1))
            kop_text = word_match.group(2).strip()
            kop_digits = re.sub(r"\D", "", kop_text)
            if kop_digits:
                kop = int(kop_digits[:2].ljust(2, "0"))
            else:
                parsed_kop = sd.parse_russian_number_words(kop_text)
                kop = parsed_kop if parsed_kop is not None else None
            if rub is not None and kop is not None:
                return Decimal(f"{rub}.{int(kop):02d}")
        return None
    rub, kop = amount_token.replace(" ", "").split("-")
    return Decimal(f"{int(rub)}.{kop}")


def parse_payment_name(path: Path) -> tuple[str, str, Decimal] | None:
    confirmed = sorting_review_fields.confirmed_fields(path)
    if confirmed:
        return confirmed["label"], confirmed["date"], Decimal(confirmed["amount"])
    match = re.match(r"(.+?)_(\d{2}-\d{2}-\d{4})(?:_(\d+|без_номера))?_(\d+-\d{2})(?:_\d+)?\.pdf$", path.name, re.I)
    if not match:
        match = re.match(r"(.+?)_(\d{2}\.\d{2}-\d{4}|\d{2}\.\d{2}\.\d{4})(?:_(\d+|без_номера))?_без_суммы\.pdf$", path.name)
        if not match:
            raw_text = sd.file_text(path)
            date = sorting_naming.extract_payment_execution_date(raw_text) or sorting_naming.extract_first_date(raw_text)
            amount = amount_from_text(path)
            person = sd.bank_payment_recipient(sd.normalize_text(raw_text))
            if not date or amount is None or not person:
                return None
            return person, date, amount
        raw_name = match.group(1).replace("_", " ")
        filename_date = match.group(2).replace(".", "-")
        raw_text = sd.file_text(path)
        date = sorting_naming.extract_payment_execution_date(raw_text) or sorting_naming.extract_first_date(raw_text) or filename_date
        amount = amount_from_text(path)
        if amount is None:
            return None
        return raw_name, date, amount
    raw_name = match.group(1).replace("_", " ")
    filename_date = match.group(2)
    raw_text = sd.file_text(path)
    payment_date = sorting_naming.extract_payment_execution_date(raw_text) or sorting_naming.extract_first_date(raw_text)
    return raw_name, payment_date or filename_date, amount_from_name(match.group(4))


def stem(token: str) -> str:
    cleaned = re.sub(r"[^а-яa-zё]", "", sd.normalize_text(token))
    return cleaned[:4]


def canonical_person_for_office(path: Path, office: str, raw_name: str) -> str | None:
    office_people = sd.OFFICE_PEOPLE.get(office, [])
    if not office_people:
        return None

    confirmed = sorting_review_fields.confirmed_fields(path)
    if confirmed:
        return next((person for person in office_people if sd.normalize_text(person) == sd.normalize_text(confirmed["label"])), None)

    text = sd.normalize_text(sd.file_text(path))
    recipient = sd.bank_payment_recipient(text)
    combined = f"{text} {recipient}"
    exact = [person for person in office_people if sd.normalize_text(person) == sd.normalize_text(raw_name)]
    if len(exact) == 1:
        return exact[0]
    matches = [person for person in office_people if sd.normalize_text(person) in combined]
    if len(matches) == 1:
        return matches[0]

    raw_tokens = [stem(part) for part in raw_name.split() if stem(part)]
    if not raw_tokens:
        return None

    best_people = []
    best_score = 0
    for person in office_people:
        person_tokens = [stem(part) for part in person.split() if stem(part)]
        score = sum(1 for token in raw_tokens if token in person_tokens)
        if score > best_score:
            best_score = score
            best_people = [person]
        elif score == best_score:
            best_people.append(person)

    if len(best_people) == 1 and best_score >= 2:
        return best_people[0]
    return None


def parse_payment_date(date: str) -> datetime:
    if "." in date:
        return datetime.strptime(date, "%d.%m-%Y")
    return datetime.strptime(date, "%d-%m-%Y")


def column_letter(index: int) -> str:
    result = []
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        result.append(chr(65 + remainder))
    return "".join(reversed(result))


def rules_file_path() -> Path:
    override = os.environ.get("SORTING_RULES_FILE", "").strip()
    if override:
        return Path(override).expanduser()
    return Path(__file__).resolve().parents[1] / "project_rules" / "sorting_rules.md"


def load_salary_table_settings() -> SalaryTableSettings:
    return config.load_runtime_rule_settings(rules_file_path()).salary_table


def collect_office_data(root: Path) -> tuple[dict[str, list[PaymentRecord]], list[tuple[str, str, str, Decimal]]]:
    office_data: dict[str, list[PaymentRecord]] = {}
    unresolved: list[tuple[str, str, str, Decimal]] = []

    for office in office_order(root):
        office_records: list[PaymentRecord] = []
        for path in sorting_receipt_archive.receipt_pdf_paths(root, office, "Зарплата"):
            parsed = parse_payment_name(path)
            if not parsed:
                unresolved.append((office, path.name, "не распознаны ФИО, дата или сумма", Decimal("0.00")))
                continue
            raw_name, date, amount = parsed
            try:
                parse_payment_date(date)
            except ValueError:
                unresolved.append((office, path.name, "некорректная дата платежа", amount))
                continue
            person = canonical_person_for_office(path, office, raw_name)
            if not person:
                unresolved.append((office, path.name, "не удалось подтвердить ФИО", amount))
                continue
            office_records.append(PaymentRecord(person, date, amount, path.name, path))

        if office_records:
            office_data[office] = office_records

    return office_data, unresolved


def ordered_payment_records(rows: list[PaymentRecord], office: str) -> list[PaymentRecord]:
    office_people = [fio for fio in sd.OFFICE_PEOPLE.get(office, []) if any(row.person == fio for row in rows)]
    office_people.extend(sorted({row.person for row in rows if row.person not in office_people}))
    order_by_person = {person: index for index, person in enumerate(office_people)}
    return sorted(
        rows,
        key=lambda row: (
            order_by_person.get(row.person, len(office_people)),
            parse_payment_date(row.date),
            row.source_name,
        ),
    )


def build_employee_matrix(rows: list[PaymentRecord], office: str, *, settings: SalaryTableSettings | None = None) -> tuple[list[str], list[tuple[str, list[Decimal | None]]]]:
    settings = settings or SalaryTableSettings()
    office_people = [fio for fio in sd.OFFICE_PEOPLE.get(office, []) if any(row.person == fio for row in rows)]
    office_people.extend(sorted({row.person for row in rows if row.person not in office_people}))
    ordered_rows = ordered_payment_records(rows, office)

    grouped: dict[str, list[PaymentRecord]] = {person: [] for person in office_people}
    for row in ordered_rows:
        grouped.setdefault(row.person, []).append(row)

    per_person_by_date: dict[str, dict[str, list[PaymentRecord]]] = {}
    for person in office_people:
        payments_by_date: dict[str, list[PaymentRecord]] = defaultdict(list)
        for payment in grouped.get(person, []):
            payments_by_date[payment.date].append(payment)
        per_person_by_date[person] = payments_by_date

    sorted_dates = sorted({row.date for row in ordered_rows}, key=parse_payment_date)
    columns = ["ФИО", *sorted_dates, settings.total_column_title]

    normalized_rows: list[tuple[str, list[Decimal | None]]] = []
    for person in office_people:
        values: list[Decimal | None] = []
        person_total = Decimal("0.00")
        payments_by_date = per_person_by_date.get(person, {})
        for date in sorted_dates:
            payments = payments_by_date.get(date, [])
            value = sum((payment.amount for payment in payments), Decimal("0.00")) if payments else None
            values.append(value)
            if value is not None:
                person_total += value
        values.append(person_total)
        normalized_rows.append((person, values))
    return columns, normalized_rows


def cell(ref: str, value: str, style: int | None = None, cell_type: str = "inlineStr", formula: str | None = None) -> str:
    style_attr = f' s="{style}"' if style is not None else ""
    if formula is not None:
        return f'<c r="{ref}"{style_attr}><f>{escape(formula)}</f><v>{value}</v></c>'
    if cell_type == "n":
        return f'<c r="{ref}"{style_attr}><v>{value}</v></c>'
    return f'<c r="{ref}" t="inlineStr"{style_attr}><is><t>{escape(value)}</t></is></c>'


def build_sheet_for_office(office: str, rows: list[PaymentRecord], *, settings: SalaryTableSettings | None = None) -> str:
    settings = settings or SalaryTableSettings()
    columns, matrix = build_employee_matrix(rows, office, settings=settings)
    xml_rows: list[str] = []
    xml_rows.append(f'<row r="1">{cell("A1", f"Офис {office} - зарплата", style=1)}</row>')
    xml_rows.append(f'<row r="2">{cell("A2", f"{len(rows)} строк выплат, {len(matrix)} сотрудников")}</row>')
    xml_rows.append(
        "<row r=\"4\">"
        + "".join(cell(f"{column_letter(i + 1)}4", title, style=1) for i, title in enumerate(columns))
        + "</row>"
    )

    current_row = 5
    for person, values in matrix:
        row_cells = [cell(f"A{current_row}", person)]
        for index, value in enumerate(values, start=2):
            column = column_letter(index)
            row_cells.append(
                cell(
                    f"{column}{current_row}",
                    "" if value is None else f"{value:.2f}",
                    style=2 if value is not None else None,
                    cell_type="n" if value is not None else "inlineStr",
                )
            )
        xml_rows.append(f"<row r=\"{current_row}\">{''.join(row_cells)}</row>")
        current_row += 1

    totals_row = current_row
    total_cells = [cell(f"A{totals_row}", settings.totals_row_title, style=1)]
    for index in range(2, len(columns) + 1):
        col = column_letter(index)
        values = [row_values[index - 2] for _, row_values in matrix if row_values[index - 2] is not None]
        total = sum(values, Decimal("0.00"))
        total_cells.append(cell(f"{col}{totals_row}", f"{total:.2f}", style=3, cell_type="n"))
    xml_rows.append(f"<row r=\"{totals_row}\">{''.join(total_cells)}</row>")
    last_column = column_letter(len(columns))

    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<worksheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\">"
        f"<dimension ref=\"A1:{last_column}{totals_row}\"/>"
        "<sheetViews><sheetView workbookViewId=\"0\"><pane ySplit=\"4\" topLeftCell=\"A5\" activePane=\"bottomLeft\" state=\"frozen\"/></sheetView></sheetViews>"
        "<cols>"
        f'<col min="1" max="1" width="34" customWidth="1"/>'
        f'<col min="2" max="{len(columns)}" width="18" customWidth="1"/>'
        "</cols>"
        "<sheetData>" + "".join(xml_rows) + "</sheetData>"
        "</worksheet>"
    )


def write_xlsx(path: Path, sheet_xml: str) -> None:
    xlsx_builder.build_workbook_xlsx(path, sheet_xml, "Зарплата")


def write_office_outputs(
    root: Path,
    office: str,
    rows: list[PaymentRecord],
    *,
    settings: SalaryTableSettings,
) -> tuple[Path, Path]:
    salary_root = root / office / "Зарплата"
    salary_root.mkdir(parents=True, exist_ok=True)
    table_output = salary_root / f"Зарплата_{office}.xlsx"
    merged_output = salary_root / f"Зарплата_{office}_чеки.pdf"
    ordered_rows = ordered_payment_records(rows, office)
    with tempfile.TemporaryDirectory(prefix=".salary-", dir=salary_root) as temporary:
        staged_table = Path(temporary) / table_output.name
        staged_pdf = Path(temporary) / merged_output.name
        write_xlsx(staged_table, build_sheet_for_office(office, rows, settings=settings))
        pdf_merge_runtime.merge_ordered_pdfs(
            [record.source_path or salary_root / record.source_name for record in ordered_rows], staged_pdf,
        )
        staged_pdf.replace(merged_output)
        staged_table.replace(table_output)
    return table_output, merged_output


def main() -> None:
    global ROOT
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    ROOT = args.root.expanduser().resolve()
    settings = load_salary_table_settings()
    if not settings.enabled:
        return
    office_data, unresolved = collect_office_data(ROOT)
    if unresolved:
        details = "\n".join(f"Офис {office}: {name}: {marker}" for office, name, marker, _ in unresolved)
        raise ValueError("Зарплатные итоги не созданы: требуется проверить все чеки.\n" + details)
    for office in office_order(ROOT):
        rows = office_data.get(office, [])
        if not rows:
            continue
        output, merged_output = write_office_outputs(ROOT, office, rows, settings=settings)
        print(f"{office}\t{output}")
        print(f"{office}\t{merged_output}")


if __name__ == "__main__":
    main()
