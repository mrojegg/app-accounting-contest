#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import build_insurance_distribution as base
import salary_employee_counts


DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "Образец" / "98" / "Ндфл и Взносы"
ROOT = DEFAULT_ROOT
OUTPUT = ROOT / "Распределение_взносов_ОБРАЗЕЦ.xlsx"
OFFICE_ORDER = ["84", "98", "99"]


def office_employee_rows(root: Path | None = None, rows: list[tuple[str, float, str]] | None = None) -> list[tuple[str, int]]:
    archive_root = salary_employee_counts.archive_root_for_tax_root(root) if root else None
    offices = salary_employee_counts.company_offices("ОБРАЗЕЦ", OFFICE_ORDER)
    return salary_employee_counts.office_employee_rows(archive_root, offices)


def collect_rows(root: Path) -> list[tuple[str, float, str]]:
    return base.collect_rows(root)


def main() -> None:
    global ROOT, OUTPUT
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output-name", default="Распределение_взносов_ОБРАЗЕЦ.xlsx")
    args = parser.parse_args()
    ROOT = args.root.expanduser().resolve()
    OUTPUT = ROOT / args.output_name
    rows = collect_rows(ROOT)
    salary_employee_counts.write_archive_distribution(OUTPUT, rows, lambda payments: office_employee_rows(ROOT, payments), base.build_sheet, "Взносы")
    total_value = sum(amount for _, amount, _ in rows)
    print(
        f"rows={len(rows)} total_value={total_value:.2f} "
        f"output={OUTPUT}"
    )


if __name__ == "__main__":
    main()
