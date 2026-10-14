#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

import build_insurance_distribution as base
import salary_employee_counts


def office_employee_rows(office: str, root: Path | None = None, rows: list[tuple[str, float, str]] | None = None) -> list[tuple[str, int]]:
    archive_root = salary_employee_counts.archive_root_for_tax_root(root) if root else None
    return salary_employee_counts.office_employee_rows(archive_root, salary_employee_counts.related_offices(office))


def collect_rows(root: Path) -> list[tuple[str, float, str]]:
    return base.collect_rows(root)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--office", required=True)
    parser.add_argument("--output-name", default=None)
    args = parser.parse_args()

    root = args.root.expanduser().resolve()
    office = args.office.strip()
    output_name = args.output_name or f"Распределение_взносов_{office}.xlsx"
    output = root / output_name

    rows = collect_rows(root)
    salary_employee_counts.write_archive_distribution(output, rows, lambda payments: office_employee_rows(office, root, payments), base.build_sheet, "Взносы")
    total_value = sum(amount for _, amount, _ in rows)
    print(
        f"office={office} rows={len(rows)} total_value={total_value:.2f} "
        f"output={output}"
    )


if __name__ == "__main__":
    main()
