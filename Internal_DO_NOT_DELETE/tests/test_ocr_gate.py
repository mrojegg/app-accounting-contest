from __future__ import annotations

import unittest
from pathlib import Path
import sys


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import sorting_ocr_gate as gate


class OCRGateTests(unittest.TestCase):
    def test_payment_flags_detect_critical_fields(self) -> None:
        text = (
            "Платежное поручение\n"
            "ООО ПРИМЕР\n"
            "Получатель Тестова Мария Александровна\n"
            "Назначение платежа Выплата заработной платы\n"
            "Сумма 16190,71\n"
        )

        flags = gate.payment_text_quality_flags(text, normalize_text=str.lower)

        self.assertTrue(flags["is_payment_like"])
        self.assertTrue(flags["has_recipient"])
        self.assertTrue(flags["has_purpose"])
        self.assertTrue(flags["has_amount"])
        self.assertTrue(flags["has_entity_markers"])

    def test_gate_skips_heavy_ocr_for_readable_payment(self) -> None:
        text = (
            "Платежное поручение\n"
            "ООО ПРИМЕР\n"
            "Получатель Тестова Мария Александровна\n"
            "Назначение платежа Выплата заработной платы\n"
            "Сумма 16190,71\n"
        )

        result = gate.should_run_heavy_ocr(
            text,
            180,
            normalize_text=str.lower,
            is_garbled_text=lambda _: False,
            informative_text_lines=lambda _: ["Платежное поручение", "Получатель"],
        )

        self.assertFalse(result)

    def test_gate_runs_heavy_ocr_for_payment_missing_fields(self) -> None:
        text = "Платежное поручение\nООО ПРИМЕР\n"

        result = gate.should_run_heavy_ocr(
            text,
            180,
            normalize_text=str.lower,
            is_garbled_text=lambda _: False,
            informative_text_lines=lambda _: ["Платежное поручение"],
        )

        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
