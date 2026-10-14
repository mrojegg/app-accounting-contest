#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

import sort_documents as sd


def extract_amount_from_name(name: str) -> str | None:
    match = re.search(r"_(\d+(?:-\d{2}|,\d{2}))(?=\.[^.]+$)", name)
    return match.group(1) if match else None


def extract_payment_order_amount_for_audit(text: str) -> str | None:
    search_space = text.replace("\xa0", " ")
    patterns = [
        r"сумма\s+сумма\s+прописью[\s\S]{0,120}?(\d{1,3}(?: \d{3})*-\d{2}|\d+-\d{2}|\d{1,3}(?: \d{3})*[.,]\d{2}|\d+[.,]\d{2})",
        r"сумма\s+прописью[\s\S]{0,120}?(\d{1,3}(?: \d{3})*-\d{2}|\d+-\d{2}|\d{1,3}(?: \d{3})*[.,]\d{2}|\d+[.,]\d{2})",
        r"(?:^|\n)\s*сумма[^0-9]{0,40}(\d{1,3}(?: \d{3})*-\d{2}|\d+-\d{2}|\d{1,3}(?: \d{3})*[.,]\d{2}|\d+[.,]\d{2})",
    ]
    for pattern in patterns:
        match = re.search(pattern, search_space, re.IGNORECASE)
        if match:
            amount = sd.normalize_amount_token(match.group(1))
            if amount:
                return amount
    return sd.extract_payment_order_amount(text)


def iter_target_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if (
            path.name.startswith("Платежное_поручение_")
            or path.name.startswith("Банковский_ордер_")
            or path.name.startswith("Счет_")
        ):
            files.append(path)
    return sorted(files)


def classify(path: Path) -> tuple[str, str | None, str | None]:
    text = sd.normalize_text(sd.file_text(path))
    named_amount = extract_amount_from_name(path.name)
    if path.name.startswith("Платежное_поручение_"):
        text_amount = extract_payment_order_amount_for_audit(text)
    elif path.name.startswith("Банковский_ордер_"):
        text_amount = sd.extract_bank_order_amount(text)
    else:
        text_amount = sd.extract_invoice_amount(text, "")

    if not named_amount:
        return "no_name_amount", named_amount, text_amount
    if not text.strip():
        return "unreadable_text", named_amount, text_amount
    if not text_amount:
        return "no_text_amount", named_amount, text_amount
    if named_amount == text_amount:
        return "matched", named_amount, text_amount
    return "mismatch", named_amount, text_amount


def write_csv(rows: list[dict[str, str]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["status", "type", "name_amount", "text_amount", "path"],
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "root",
        nargs="?",
        default=str(Path(__file__).resolve().parents[2] / "Пример"),
    )
    parser.add_argument(
        "--csv",
        dest="csv_path",
        default=str(Path(__file__).resolve().parents[1] / "cache" / "audit_named_amounts_demo_a.csv"),
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    files = iter_target_files(root)

    summary = {
        "matched": 0,
        "mismatch": 0,
        "no_text_amount": 0,
        "unreadable_text": 0,
        "no_name_amount": 0,
    }
    rows: list[dict[str, str]] = []
    problem_rows: list[dict[str, str]] = []

    for path in files:
        status, named_amount, text_amount = classify(path)
        summary[status] += 1
        row = {
            "status": status,
            "type": (
                "payment_order"
                if path.name.startswith("Платежное_поручение_")
                else "bank_order"
                if path.name.startswith("Банковский_ордер_")
                else "invoice"
            ),
            "name_amount": named_amount or "",
            "text_amount": text_amount or "",
            "path": str(path),
        }
        rows.append(row)
        if status != "matched":
            problem_rows.append(row)

    write_csv(rows, Path(args.csv_path))

    print(f"root={root}")
    print(f"total={len(files)}")
    for key in ["matched", "mismatch", "no_text_amount", "unreadable_text", "no_name_amount"]:
        print(f"{key}={summary[key]}")
    print("---PROBLEMS---")
    for row in problem_rows:
        print(
            "\t".join(
                [
                    row["status"],
                    row["type"],
                    row["name_amount"] or "-",
                    row["text_amount"] or "-",
                    row["path"],
                ]
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
