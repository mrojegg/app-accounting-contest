#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

import build_tax_distribution as base
import salary_employee_counts


DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "Образец" / "98" / "Ндфл и Взносы"
ROOT = DEFAULT_ROOT
OUTPUT = ROOT / "Распределение_налогов_ОБРАЗЕЦ.xlsx"
OFFICE_ORDER = ["84", "98", "99"]


def office_employee_rows(root: Path | None = None, tax_rows: list[tuple[str, float, str]] | None = None) -> list[tuple[str, int]]:
    archive_root = salary_employee_counts.archive_root_for_tax_root(root) if root else None
    offices = salary_employee_counts.company_offices("ОБРАЗЕЦ", OFFICE_ORDER)
    return salary_employee_counts.office_employee_rows(archive_root, offices)


def collect_tax_rows(root: Path) -> list[tuple[str, float, str]]:
    return base.collect_tax_rows(root)


def main() -> None:
    global ROOT, OUTPUT
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output-name", default="Распределение_налогов_ОБРАЗЕЦ.xlsx")
    args = parser.parse_args()
    ROOT = args.root.expanduser().resolve()
    OUTPUT = ROOT / args.output_name
    tax_rows = collect_tax_rows(ROOT)
    base.write_distribution(ROOT, OUTPUT, tax_rows, lambda rows: office_employee_rows(ROOT, rows))
    total_taxes = sum(amount for _, amount, _ in tax_rows)
    print(
        f"rows={len(tax_rows)} total_taxes={total_taxes:.2f} "
        f"output={OUTPUT}"
    )


if __name__ == "__main__":
    main()
