#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from xml.sax.saxutils import escape

import sort_documents as sd
import xlsx_builder

DEFAULT_ROOT = Path(__file__).resolve().parents[2] / 'Пример'
ROOT = DEFAULT_ROOT
OFFICE_ORDER = ['76', '93', '94', '102', '109']
COLUMNS = ['ФИО', 'Аванс', 'Заработная плата', 'Отпуск/увольнение']


@dataclass
class PaymentRecord:
    person: str
    date: str
    amount: Decimal
    source_name: str


def amount_from_name(raw: str) -> Decimal:
    return Decimal(raw.replace('-', '.', 1))


def parse_payment_name(path: Path) -> tuple[str, str, Decimal] | None:
    match = re.match(r'(.+?)_(\d{2}-\d{2}-\d{4})(?:_(\d+|без_номера))?_(\d+-\d{2})\.pdf$', path.name)
    if not match:
        return None
    return match.group(1).replace('_', ' '), match.group(2), amount_from_name(match.group(4))


def stem(token: str) -> str:
    cleaned = re.sub(r'[^а-яa-zё]', '', sd.normalize_text(token))
    return cleaned[:4]


def canonical_person_for_office(path: Path, office: str, raw_name: str) -> str | None:
    text = sd.normalize_text(sd.file_text(path))
    recipient = sd.bank_payment_recipient(text)
    combined = f'{text} {recipient}'
    for person in sd.OFFICE_PEOPLE[office]:
        if sd.normalize_text(person) in combined:
            return person

    raw_tokens = [stem(part) for part in raw_name.split() if stem(part)]
    if not raw_tokens:
        return None

    best_person = None
    best_score = 0
    for person in sd.OFFICE_PEOPLE[office]:
        person_tokens = [stem(part) for part in person.split() if stem(part)]
        score = sum(1 for token in raw_tokens if token in person_tokens)
        if score > best_score:
            best_score = score
            best_person = person

    if best_person and best_score >= min(2, len(raw_tokens)):
        return best_person
    return None


def classify_window(date: str) -> str:
    day = int(date[:2])
    if day in {14, 15}:
        return 'Аванс'
    if day in {30, 1, 2}:
        return 'Заработная плата'
    return 'Отпуск/увольнение'


def assign_person_totals(records: list[PaymentRecord]) -> dict[str, Decimal]:
    totals = {
        'Аванс': Decimal('0.00'),
        'Заработная плата': Decimal('0.00'),
        'Отпуск/увольнение': Decimal('0.00'),
    }
    groups: dict[str, list[PaymentRecord]] = {
        'Аванс': [],
        'Заработная плата': [],
        'Отпуск/увольнение': [],
    }
    for rec in records:
        groups[classify_window(rec.date)].append(rec)

    for bucket in ('Аванс', 'Заработная плата'):
        items = groups[bucket]
        if not items:
            continue
        primary = max(items, key=lambda item: (item.amount, item.date, item.source_name))
        totals[bucket] += primary.amount
        for item in items:
            if item is primary:
                continue
            totals['Отпуск/увольнение'] += item.amount

    for item in groups['Отпуск/увольнение']:
        totals['Отпуск/увольнение'] += item.amount
    return totals


def collect_office_data() -> tuple[dict[str, dict[str, dict[str, Decimal]]], list[tuple[str, str, str, Decimal]]]:
    office_data: dict[str, dict[str, dict[str, Decimal]]] = {}
    unresolved: list[tuple[str, str, str, Decimal]] = []

    for office in OFFICE_ORDER:
        salary_dir = ROOT / office / 'Зарплата'
        if not salary_dir.exists():
            continue
        per_person_records: dict[str, list[PaymentRecord]] = {}
        for path in sorted(salary_dir.glob('*.pdf')):
            parsed = parse_payment_name(path)
            if not parsed:
                continue
            raw_name, date, amount = parsed
            person = canonical_person_for_office(path, office, raw_name)
            if not person:
                unresolved.append((office, path.name, 'не удалось подтвердить ФИО', amount))
                continue
            per_person_records.setdefault(person, []).append(PaymentRecord(person, date, amount, path.name))
        rows = {person: assign_person_totals(records) for person, records in per_person_records.items()}
        if rows:
            office_data[office] = rows
    return office_data, unresolved


def cell(ref: str, value: str, style: int | None = None, cell_type: str = 'inlineStr', formula: str | None = None) -> str:
    style_attr = f' s="{style}"' if style is not None else ''
    if formula is not None:
        return f'<c r="{ref}"{style_attr}><f>{escape(formula)}</f><v>{value}</v></c>'
    if cell_type == 'n':
        return f'<c r="{ref}"{style_attr}><v>{value}</v></c>'
    return f'<c r="{ref}" t="inlineStr"{style_attr}><is><t>{escape(value)}</t></is></c>'


def build_sheet_for_office(office: str, rows: dict[str, dict[str, Decimal]]) -> str:
    office_people = [fio for fio in sd.OFFICE_PEOPLE[office] if fio in rows]
    xml_rows: list[str] = []
    xml_rows.append(f'<row r="1">{cell("A1", f"Офис {office} - зарплата", style=1)}</row>')
    xml_rows.append(f'<row r="2">{cell("A2", f"{len(office_people)} сотрудников")}</row>')
    xml_rows.append('<row r="4">' + ''.join(cell(f'{chr(65+i)}4', title, style=1) for i, title in enumerate(COLUMNS)) + '</row>')

    current_row = 5
    for fio in office_people:
        values = rows[fio]
        advance = values['Аванс']
        salary = values['Заработная плата']
        extra = values['Отпуск/увольнение']
        xml_rows.append(
            f'<row r="{current_row}">'
            f'{cell(f"A{current_row}", fio)}'
            f'{cell(f"B{current_row}", f"{advance:.2f}", style=2, cell_type="n")}'
            f'{cell(f"C{current_row}", f"{salary:.2f}", style=2, cell_type="n")}'
            f'{cell(f"D{current_row}", f"{extra:.2f}", style=2, cell_type="n")}'
            '</row>'
        )
        current_row += 1

    totals_row = current_row
    total_advance = sum(v['Аванс'] for v in rows.values())
    total_salary = sum(v['Заработная плата'] for v in rows.values())
    total_extra = sum(v['Отпуск/увольнение'] for v in rows.values())
    grand_total = total_advance + total_salary + total_extra
    xml_rows.append(
        f'<row r="{totals_row}">'
        f'{cell(f"A{totals_row}", "ИТОГО", style=1)}'
        f'{cell(f"B{totals_row}", f"{total_advance:.2f}", style=3, cell_type="n", formula=f"SUM(B5:B{totals_row-1})")}'
        f'{cell(f"C{totals_row}", f"{total_salary:.2f}", style=3, cell_type="n", formula=f"SUM(C5:C{totals_row-1})")}'
        f'{cell(f"D{totals_row}", f"{total_extra:.2f}", style=3, cell_type="n", formula=f"SUM(D5:D{totals_row-1})")}'
        '</row>'
    )

    grand_row = totals_row + 1
    xml_rows.append(
        f'<row r="{grand_row}">'
        f'{cell(f"A{grand_row}", "ОБЩИЙ ИТОГ ПО ВСЕМ СОТРУДНИКАМ", style=1)}'
        f'{cell(f"B{grand_row}", f"{grand_total:.2f}", style=3, cell_type="n", formula=f"SUM(B{totals_row}:D{totals_row})")}'
        '</row>'
    )

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<dimension ref="A1:D{grand_row}"/>'
        '<sheetViews><sheetView workbookViewId="0"><pane ySplit="4" topLeftCell="A5" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
        '<cols>'
        '<col min="1" max="1" width="38" customWidth="1"/>'
        '<col min="2" max="4" width="18" customWidth="1"/>'
        '</cols>'
        '<sheetData>' + ''.join(xml_rows) + '</sheetData>'
        '</worksheet>'
    )


def write_xlsx(path: Path, sheet_xml: str) -> None:
    xlsx_builder.build_workbook_xlsx(path, sheet_xml, "Зарплата")


def main() -> None:
    global ROOT
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    ROOT = args.root.expanduser().resolve()
    office_data, unresolved = collect_office_data()
    for office in OFFICE_ORDER:
        rows = office_data.get(office, {})
        if not rows:
            continue
        output = ROOT / office / 'Зарплата' / f'Зарплата_{office}.xlsx'
        write_xlsx(output, build_sheet_for_office(office, rows))
        print(f'{office}\t{output}')
    if unresolved:
        print('UNRESOLVED')
        for office, name, marker, amount in unresolved:
            print(f'{office}\t{name}\t{marker}\t{amount:.2f}')


if __name__ == '__main__':
    main()
