"""Create synthetic payment PDFs for the contest demonstration."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import fitz

PAYMENTS = [
    ("01_salary_testov.pdf", "Тестов Алексей Сергеевич", "14.09.2026", "1000,00", "Выплата заработной платы. НДФЛ удержан."),
    ("02_salary_testov.pdf", "Тестов Алексей Сергеевич", "29.09.2026", "1500,00", "Выплата заработной платы. НДФЛ удержан."),
    ("03_salary_primerov.pdf", "Примеров Борис Андреевич", "14.09.2026", "2000,00", "Выплата заработной платы. НДФЛ удержан."),
    ("04_salary_primerov.pdf", "Примеров Борис Андреевич", "29.09.2026", "2500,00", "Выплата заработной платы. НДФЛ удержан."),
    ("05_unknown_employee.pdf", "Образов Виктор Владимирович", "29.09.2026", "1800,00", "Выплата заработной платы. НДФЛ удержан."),
    ("06_repeated_attempt.pdf", "Тестов Алексей Сергеевич", "16.09.2026", "1000,00", "Выплата заработной платы. НДФЛ удержан."),
    ("07_rent.pdf", "ООО ДЕМОНСТРАЦИОННАЯ АРЕНДА", "14.09.2026", "1234,56", "Оплата аренды офиса по счету 10."),
    ("08_commission.pdf", "БАНК ДЕМОНСТРАЦИЯ", "14.09.2026", "10,00", "Комиссия банка за перевод денежных средств."),
    ("09_commission.pdf", "БАНК ДЕМОНСТРАЦИЯ", "29.09.2026", "20,00", "Комиссия банка за перевод денежных средств."),
    ("10_tax.pdf", "УФК ДЕМОНСТРАЦИЯ", "29.09.2026", "310,00", "Единый налоговый платеж НДФЛ."),
    ("11_insurance.pdf", "ФОНД ДЕМОНСТРАЦИЯ", "29.09.2026", "150,00", "Страховые взносы на обязательное страхование от несчастных случаев."),
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Use a new output directory")
    receipts = args.output / "receipts"
    receipts.mkdir(parents=True)
    font = fitz.Font("cjk")
    for index, (name, person, date, amount, purpose) in enumerate(PAYMENTS, 1):
        with fitz.open() as document:
            page = document.new_page()
            page.insert_font(fontname="demo", fontbuffer=font.buffer)
            text = (f"ПЛАТЕЖНОЕ ПОРУЧЕНИЕ N {index}\n{date}\n"
                    "ООО ДЕМОНСТРАЦИЯ\n"
                    f"Сумма {amount}\n"
                    f"Сч. N 40817000000000000001 {person} Вид оп. 01\n"
                    f"Назначение платежа {purpose}\n\n"
                    "СИНТЕТИЧЕСКИЕ ДАННЫЕ. НЕ БАНКОВСКИЙ ДОКУМЕНТ.")
            page.insert_text((32, 48), text, fontname="demo", fontsize=10)
            document.subset_fonts()
            document.save(receipts / name, deflate=True)
    manifest = {"synthetic": True, "input_count": 11, "expected_after_manual_review": {
        "processed": 10, "excluded_duplicate": 1, "pending": 0,
        "employee_counts": {"201": 1, "202": 2}, "salary_total": "8800.00",
        "commission_total": "30.00", "tax_total": "310.00", "insurance_total": "150.00"},
        "manual_decisions": {"01_salary_testov.pdf": "Confirm salary for office 201",
                             "06_repeated_attempt.pdf": "Exclude repeated attempt; preserve file",
                             "05_unknown_employee.pdf": "Assign employee to office 202 and save rule",
                             "08_commission.pdf": "If prompted, assign commission to office 202",
                             "09_commission.pdf": "If prompted, assign commission to office 202",
                             "10_tax.pdf": "If prompted, assign tax to office 202",
                             "11_insurance.pdf": "If prompted, assign insurance to office 202"}}
    (args.output / "expected.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Created {len(PAYMENTS)} synthetic PDFs in {receipts}")


if __name__ == "__main__":
    main()
