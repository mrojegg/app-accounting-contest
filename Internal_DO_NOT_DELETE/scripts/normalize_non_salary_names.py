#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

import sort_documents as sd


def should_process(path: Path, text: str) -> bool:
    if path.name.startswith("Платежное_поручение_"):
        return not sd.looks_like_salary_payment(text, sd.normalize_text(path.name))
    return path.name.startswith("Банковский_ордер_") or path.name.startswith("Счет_")


def build_payment_order_name(path: Path) -> str:
    text = sd.normalize_text(sd.file_text(path))
    number = sd.extract_payment_order_number(text, path.name)
    match = re.match(
        r"^Платежное_поручение_(.+?)_(\d{2}-\d{2}-\d{4}|без_даты)_(\d+(?:-\d{2}|,\d{2}|без_суммы))\.pdf$",
        path.name,
    )
    if match:
        counterparty, date, amount = match.groups()
        parts = ["Платежное_поручение", counterparty, date]
        if number and number != "без_номера":
            parts.append(number)
        parts.append(amount.replace(",", "-"))
        return "_".join(parts) + path.suffix.lower()
    return sd.normalize_structured_filename(path.name, text)


def build_bank_order_name(path: Path) -> str:
    text = sd.normalize_text(sd.file_text(path))
    match = re.match(
        r"^Банковский_ордер_(.+?)_(\d{2}-\d{2}-\d{4}|без_даты)_(\d+(?:-\d{2}|,\d{2}|без_суммы))(?:_(\d+))?\.pdf$",
        path.name,
    )
    if match:
        bank, date, amount, suffix_number = match.groups()
        number = suffix_number or sd.extract_bank_order_number(text, path.name)
        parts = ["Банковский_ордер", bank, date]
        if number and number != "без_номера":
            parts.append(number)
        parts.append(amount.replace(",", "-"))
        return "_".join(parts) + path.suffix.lower()
    return sd.normalize_structured_filename(path.name, text)


def build_invoice_name(path: Path) -> str:
    return sd.normalize_structured_filename(path.name)


def rename_in_place(root: Path, apply: bool) -> tuple[int, int]:
    renamed = 0
    skipped = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        text = sd.normalize_text(sd.file_text(path)) if path.name.startswith("Платежное_поручение_") else ""
        if not should_process(path, text):
            skipped += 1
            continue

        if path.name.startswith("Платежное_поручение_"):
            new_name = build_payment_order_name(path)
        elif path.name.startswith("Банковский_ордер_"):
            new_name = build_bank_order_name(path)
        else:
            new_name = build_invoice_name(path)
        if new_name == path.name:
            skipped += 1
            continue

        destination = sd.unique_destination(path.with_name(new_name))
        if apply:
            path.rename(destination)
        renamed += 1
        print(f"{path} -> {destination}")
    return renamed, skipped


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=str(Path(__file__).resolve().parents[2] / "Пример"))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    renamed, skipped = rename_in_place(Path(args.root).resolve(), args.apply)
    print(f"renamed={renamed}")
    print(f"skipped={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
