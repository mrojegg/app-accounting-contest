#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
import re
from pathlib import Path
from xml.sax.saxutils import escape

import sort_documents as sd
import pdf_merge_runtime
import sorting_receipt_archive
import sorting_naming
import xlsx_builder
import sorting_review_fields


DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "Пример" / "109" / "Комиссии"
ROOT = DEFAULT_ROOT
OUTPUT = ROOT / "Комиссии_ПРИМЕР.xlsx"


@dataclass
class CommissionRecord:
    date: str
    amount: float
    source_name: str
    source_path: Path


def parse_date(text: str) -> str | None:
    date = sorting_naming.extract_payment_date(text)
    return date.replace("-", ".") if date else None


def parse_amount(text: str) -> float | None:
    amount_token = sd.extract_bank_order_amount(text) or sd.extract_payment_order_amount(text)
    if not amount_token:
        return None
    raw = amount_token.replace(" ", "")
    rub, kop = raw.split("-")
    return float(f"{int(rub)}.{kop}")


def collect_records(root: Path) -> list[CommissionRecord]:
    records: list[CommissionRecord] = []
    for path in sorting_receipt_archive.receipt_pdf_paths_for_category_dir(root):
        text = sd.normalize_text(sd.file_text(path))
        date = parse_date(text)
        amount = parse_amount(text)
        confirmed = sorting_review_fields.confirmed_fields(path)
        if confirmed:
            date = confirmed["date"].replace("-", ".")
            amount = float(confirmed["amount"])
        if not date or amount is None:
            match = re.match(r"(?:Банковский_ордер_.+|комиссия.*)_(\d{2}-\d{2}-\d{4})_(.+)_(\d+-\d{2})\.pdf$", path.name, re.IGNORECASE)
            if match:
                date = match.group(1).replace("-", ".")
                amount = float(match.group(3).replace("-", ".", 1))
        if not date or amount is None:
            raise ValueError(f"Не прочитана дата или сумма комиссии: {path.name}. Итоги не созданы.")
        records.append(CommissionRecord(date, amount, path.name, path))
    return records


def collect_rows(root: Path) -> list[tuple[str, float, str]]:
    return [(record.date, record.amount, record.source_name) for record in collect_records(root)]


def col_letter(index: int) -> str:
    result = ""
    while index:
        index, rem = divmod(index - 1, 26)
        result = chr(65 + rem) + result
    return result


def cell(ref: str, value: str, style: int | None = None, cell_type: str = "inlineStr") -> str:
    style_attr = f' s="{style}"' if style is not None else ""
    if cell_type == "n":
        return f'<c r="{ref}"{style_attr}><v>{value}</v></c>'
    return f'<c r="{ref}" t="inlineStr"{style_attr}><is><t>{escape(value)}</t></is></c>'


def build_sheet(rows: list[tuple[str, float, str]]) -> str:
    xml_rows: list[str] = []
    header = [
        cell("A1", "Дата", style=1),
        cell("B1", "Сумма", style=1),
        cell("C1", "Файл", style=1),
    ]
    xml_rows.append(f'<row r="1">{"".join(header)}</row>')

    total = 0.0
    for row_index, (date, amount, filename) in enumerate(rows, start=2):
        total += amount
        xml_rows.append(
            f'<row r="{row_index}">'
            f'{cell(f"A{row_index}", date)}'
            f'{cell(f"B{row_index}", f"{amount:.2f}", style=2, cell_type="n")}'
            f'{cell(f"C{row_index}", filename)}'
            f"</row>"
        )

    count_row = len(rows) + 2
    total_row = len(rows) + 3
    xml_rows.append(
        f'<row r="{count_row}">'
        f'{cell(f"A{count_row}", "Количество чеков", style=1)}'
        f'{cell(f"B{count_row}", str(len(rows)), style=1, cell_type="n")}'
        f"</row>"
    )
    xml_rows.append(
        f'<row r="{total_row}">'
        f'{cell(f"A{total_row}", "ИТОГО", style=1)}'
        f'{cell(f"B{total_row}", f"{total:.2f}", style=3, cell_type="n")}'
        f"</row>"
    )

    dimension = f"A1:C{total_row}"
    cols = (
        '<cols>'
        '<col min="1" max="1" width="14" customWidth="1"/>'
        '<col min="2" max="2" width="14" customWidth="1"/>'
        '<col min="3" max="3" width="42" customWidth="1"/>'
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


def build_workbook_xlsx(output: Path, rows: list[tuple[str, float, str]]) -> None:
    sheet_xml = build_sheet(rows)
    xlsx_builder.build_workbook_xlsx(output, sheet_xml, "Комиссии")


def write_outputs(
    root: Path,
    output_name: str,
    rows: list[tuple[str, float, str]],
    *,
    source_paths: list[Path] | None = None,
) -> tuple[Path, Path]:
    table_output = root / output_name
    build_workbook_xlsx(table_output, rows)
    merged_output = root / f"{Path(output_name).stem}_чеки.pdf"
    pdf_merge_runtime.merge_ordered_pdfs(
        source_paths or [root / filename for _, _, filename in rows],
        merged_output,
    )
    return table_output, merged_output


def main() -> None:
    global ROOT, OUTPUT
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output-name", default="Комиссии_ПРИМЕР.xlsx")
    args = parser.parse_args()
    ROOT = args.root.expanduser().resolve()
    records = collect_records(ROOT)
    rows = [(record.date, record.amount, record.source_name) for record in records]
    OUTPUT, merged_output = write_outputs(
        ROOT,
        args.output_name,
        rows,
        source_paths=[record.source_path for record in records],
    )
    total = sum(amount for _, amount, _ in rows)
    print(f"rows={len(rows)} total={total:.2f} output={OUTPUT} pdf={merged_output}")


if __name__ == "__main__":
    main()
