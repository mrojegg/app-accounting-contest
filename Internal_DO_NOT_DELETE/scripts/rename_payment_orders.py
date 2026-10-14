#!/usr/bin/env python3
from __future__ import annotations

import re
import shutil
from pathlib import Path

import sort_documents as sd


ROOT = Path(__file__).resolve().parents[2] / "Пример"


def parse_number(text: str) -> str | None:
    match = re.search(r"платежное поручение\s*n\s*(\d+)", text)
    return match.group(1) if match else None


def parse_date(text: str) -> str | None:
    match = re.search(r"\b(\d{2}\.\d{2}\.\d{4})\b", text)
    return match.group(1).replace(".", "-") if match else None


def parse_amount(text: str) -> str | None:
    search_area = text.split("отметки банка")[0]
    matches = re.findall(r"(?:^| )(\d{1,3}(?: \d{3})*-\d{2}|\d+-\d{2})\b", search_area)
    if not matches:
        return None
    return matches[-1].replace(" ", "")


def normalize_piece(value: str) -> str:
    value = value.strip().replace('"', "")
    value = re.sub(r"[^\w\s.-]+", "_", value, flags=re.UNICODE)
    value = re.sub(r"\s+", "_", value)
    return value.strip("._")


def new_name_for(path: Path) -> str | None:
    text = sd.normalize_text(sd.file_text(path))
    if not sd.is_payment_order(text, sd.normalize_text(path.name)):
        return None
    recipient = sd.bank_payment_recipient(text)
    number = parse_number(text) or "без_номера"
    date = parse_date(text) or "без_даты"
    amount = parse_amount(text) or "без_суммы"

    if recipient:
        recipient_name = normalize_piece(recipient)
    else:
        stem = path.stem
        stem = re.sub(r"^(ПП_|Платежное_поручение_)", "", stem)
        recipient_name = normalize_piece(stem) or "Документ"

    return f"Платежное_поручение_{recipient_name}_{number}_{date}_{amount}{path.suffix.lower()}"


def main() -> None:
    for path in sorted(ROOT.rglob("*.pdf")):
        if path.name.startswith("Платежное_поручение_"):
            continue
        new_name = new_name_for(path)
        if not new_name:
            continue
        destination = sd.unique_destination(path.with_name(new_name))
        shutil.move(str(path), str(destination))
        print(f"{path} -> {destination}")


if __name__ == "__main__":
    main()
