from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import sort_documents as sd


class NamingRegressionTests(unittest.TestCase):
    def test_extract_invoice_date_prefers_document_date_over_contract_date(self) -> None:
        text = sd.normalize_text(
            "Основание: договор от 03.02.2026 "
            "Счет на оплату № 13 от 09.04.2026"
        )
        self.assertEqual(sd.extract_invoice_date(text, "Счет на оплату 13.pdf"), "09-04-2026")

    def test_normalize_structured_filename_dedupes_repeated_tail(self) -> None:
        original = (
            "schet_na_oplatu_krp..49750_31.03.2026_31.03-2026_без_номера_без_суммы"
            "..49750_31.03.2026_31-03-2026_без_номера_без_суммы.pdf"
        )
        self.assertEqual(
            sd.normalize_structured_filename(original),
            "schet_na_oplatu_krp.49750_31.03.2026_31.03-2026_без_номера_без_суммы.pdf",
        )

    def test_canonical_employee_name_matches_declined_bank_recipient(self) -> None:
        text = sd.normalize_text(
            "Для зачисления на счет Тестова Хуссейна Хуссейна "
            "Заработная плата за Март 2026 г."
        )

        self.assertEqual(sd.canonical_employee_name(text), "Тестов Хуссейн Хуссейн")


if __name__ == "__main__":
    unittest.main()
