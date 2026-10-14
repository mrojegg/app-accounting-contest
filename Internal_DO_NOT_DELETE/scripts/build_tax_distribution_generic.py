#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

import build_tax_distribution as base
import salary_employee_counts


def office_employee_rows(office: str, root: Path | None = None, tax_rows: list[tuple[str, float, str]] | None = None) -> list[tuple[str, int]]:
    archive_root = salary_employee_counts.archive_root_for_tax_root(root) if root else None
    return salary_employee_counts.office_employee_rows(archive_root, salary_employee_counts.related_offices(office))


def collect_tax_rows(root: Path) -> list[tuple[str, float, str]]:
    return base.collect_tax_rows(root)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--office", required=True)
    parser.add_argument("--output-name", default=None)
    args = parser.parse_args()

    root = args.root.expanduser().resolve()
    office = args.office.strip()
    output_name = args.output_name or f"Распределение_налогов_{office}.xlsx"
    output = root / output_name

    tax_rows = collect_tax_rows(root)
    base.write_distribution(root, output, tax_rows, lambda rows: office_employee_rows(office, root, rows))
    total_taxes = sum(amount for _, amount, _ in tax_rows)
    print(
        f"office={office} rows={len(tax_rows)} total_taxes={total_taxes:.2f} "
        f"output={output}"
    )


if __name__ == "__main__":
    main()
