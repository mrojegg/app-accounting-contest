#!/usr/bin/env python3
import argparse
import re
from pathlib import Path

import build_commission_table as base
import sort_documents as sd


DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "Образец" / "98" / "Комиссии"
ROOT = DEFAULT_ROOT
OUTPUT = ROOT / "Комиссии_ОБРАЗЕЦ.xlsx"


def collect_rows(root: Path) -> list[tuple[str, float, str]]:
    rows: list[tuple[str, float, str]] = []
    for path in sorted(root.glob("*.pdf")):
        text = sd.normalize_text(sd.file_text(path))
        date = base.parse_date(text)
        amount = base.parse_amount(text)
        if not date or amount is None:
            match = re.match(r"(?:Банковский_ордер_.+|комиссия.*)_(\d{2}-\d{2}-\d{4})_(.+)_(\d+-\d{2})\.pdf$", path.name)
            if not match:
                continue
            date = match.group(1).replace("-", ".")
            amount = float(match.group(3).replace("-", ".", 1))
        if amount is None:
            continue
        rows.append((date, amount, path.name))
    return rows


def main() -> None:
    global ROOT, OUTPUT
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output-name", default="Комиссии_ОБРАЗЕЦ.xlsx")
    args = parser.parse_args()
    ROOT = args.root.expanduser().resolve()
    OUTPUT = ROOT / args.output_name
    rows = collect_rows(ROOT)
    base.build_workbook_xlsx(OUTPUT, rows)
    total = sum(amount for _, amount, _ in rows)
    print(f"rows={len(rows)} total={total:.2f} output={OUTPUT}")


if __name__ == "__main__":
    main()
