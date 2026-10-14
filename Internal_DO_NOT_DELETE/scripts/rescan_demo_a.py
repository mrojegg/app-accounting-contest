#!/usr/bin/env python3
from __future__ import annotations

import re
import shutil
from pathlib import Path

import sort_documents as sd


ROOT = Path(__file__).resolve().parents[2] / "Пример"
MANUAL = ROOT / "Требует_ручной_проверки"
GENERATED_NAMES = {f"Зарплата_{office}.xlsx" for office in sd.OFFICES}


def all_documents(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.name in GENERATED_NAMES:
            continue
        if path.suffix.lower() not in sd.SUPPORTED_EXTENSIONS and path.suffix.lower() != ".xls":
            continue
        files.append(path)
    return sorted(files)


def canonical_employee(text: str) -> tuple[str | None, str | None]:
    for office, people in sd.OFFICE_PEOPLE.items():
        for person in people:
            if sd.normalize_text(person) in text:
                return person, office
    return None, None


def normalize_amount(raw: str | None) -> str | None:
    if not raw:
        return None
    cleaned = raw.replace("\xa0", " ").replace(" ", "").replace(",", "-")
    cleaned = cleaned.replace(".", "-")
    return cleaned


def payment_order_number(text: str) -> str | None:
    match = re.search(r"платежное поручение\s*n\s*(\d+)", text)
    return match.group(1) if match else None


def payment_order_date(text: str) -> str | None:
    match = re.search(r"платежное поручение\s*n\s*\d+\s*(\d{2}\.\d{2}\.\d{4})", text)
    if match:
        return match.group(1)
    match = re.search(r"\b(\d{2}\.\d{2}\.\d{4})\b", text)
    return match.group(1) if match else None


def payment_order_amount(text: str) -> str | None:
    match = re.search(r"сумма\s+сумма прописью .*? (\d[\d ]*-\d{2})\b", text)
    if match:
        return normalize_amount(match.group(1))
    match = re.search(r"\b(\d[\d ]*,\d{2})\b", text)
    return normalize_amount(match.group(1)) if match else None


def build_salary_name(path: Path, text: str, employee: str) -> str:
    number = payment_order_number(text) or "без_номера"
    date = (payment_order_date(text) or "без_даты").replace(".", "-")
    amount = payment_order_amount(text) or "без_суммы"
    employee_part = re.sub(r"\s+", "_", employee.strip())
    return f"Платежное_поручение_{employee_part}_{number}_{date}_{amount}{path.suffix.lower()}"


def safe_move(source: Path, destination: Path) -> Path:
    if source.resolve() == destination.resolve():
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination = sd.unique_destination(destination)
    shutil.move(str(source), str(destination))
    return destination


def cleanup_empty_dirs(root: Path) -> None:
    for path in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path.is_dir() and path != root:
            try:
                next(path.iterdir())
            except StopIteration:
                path.rmdir()


def main() -> None:
    moved_salary = 0
    rechecked = 0
    manual_count = 0
    files = all_documents(ROOT)

    for path in files:
        if not path.exists():
            continue
        rechecked += 1
        text = sd.normalize_text(sd.file_text(path))
        if not text:
            destination = MANUAL / path.name
            safe_move(path, destination)
            manual_count += 1
            continue

        employee, office = canonical_employee(text)
        if employee and sd.looks_like_salary_payment(text, sd.normalize_text(path.name)):
            destination = ROOT / office / "Зарплата" / build_salary_name(path, text, employee)
            moved = safe_move(path, destination)
            moved_salary += 1
            print(f"SALARY\t{office}\t{employee}\t{moved}")
            continue

        if path.suffix.lower() == ".xls":
            destination = MANUAL / path.name
            safe_move(path, destination)
            manual_count += 1
            continue

        classification = sd.classify(path, ROOT)
        if (
            classification.destination is None
            or classification.category == "Прочее"
            or (classification.office in {"76", "84", "93", "94"} and classification.category != "Зарплата")
        ):
            destination = MANUAL / path.name
            safe_move(path, destination)
            manual_count += 1
            continue

        destination = classification.destination / classification.new_name
        safe_move(path, destination)

    cleanup_empty_dirs(ROOT)
    print(f"RECHECKED\t{rechecked}")
    print(f"SALARY_MOVED\t{moved_salary}")
    print(f"MANUAL\t{sum(1 for p in MANUAL.glob('*') if p.is_file()) if MANUAL.exists() else 0}")


if __name__ == "__main__":
    main()
