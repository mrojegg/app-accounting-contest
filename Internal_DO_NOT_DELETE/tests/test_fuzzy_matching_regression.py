from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import sort_documents as sd
import sorting_classification as sc


class FuzzyMatchingRegressionTests(unittest.TestCase):
    def test_office_detects_fuzzy_contractor_match(self) -> None:
        runtime = sd.classification_runtime()
        text = sd.normalize_text("договор на услуги с комитен корп по интернет-каналу")
        result = sc.detect_office_signal(
            text,
            "",
            "ПРИМЕР",
            runtime=runtime,
            bank_payment_recipient=sd.bank_payment_recipient,
            bank_payment_purpose=sd.bank_payment_purpose,
            bounded_confidence=sd.bounded_confidence,
            normalize_text=sd.normalize_text,
        )
        self.assertEqual(result.value, "109")

    def test_extract_invoice_counterparty_fuzzy_match(self) -> None:
        text = sd.normalize_text("оказание услуг по договору с комитен корп")
        self.assertIn(sd.extract_invoice_counterparty(text, "invoice.pdf"), {"комитерн_корп", "комитен_корп"})


if __name__ == "__main__":
    unittest.main()
