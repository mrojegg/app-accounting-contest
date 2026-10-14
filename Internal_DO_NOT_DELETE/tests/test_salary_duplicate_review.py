from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import sorting_sorter_core as core
from sorting_models import Classification


class SalaryDuplicateReviewTests(unittest.TestCase):
    def classification(
        self,
        archive: Path,
        name: str,
        amount: str,
        person_slug: str = "иванов_иван",
    ) -> Classification:
        return Classification(
            destination=archive / "98" / "Зарплата",
            office="98",
            category="Зарплата",
            entity="ОБРАЗЕЦ",
            reason="зарплатный платеж",
            new_name=f"{person_slug}_{name}_{amount}.pdf",
            confidence=95,
            requires_manual_review=False,
            trace=[],
        )

    def test_two_equal_salary_payments_are_both_sent_to_manual_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            archive = root / "archive"
            first = root / "first.pdf"
            second = root / "second.pdf"
            first.write_text("dummy", encoding="utf-8")
            second.write_text("dummy", encoding="utf-8")
            results = [
                self.classification(archive, "01-06-2026", "50000-00"),
                self.classification(archive, "02-06-2026", "50000-00"),
            ]

            with mock.patch.object(core, "OFFICE_PEOPLE", {"98": ["Иванов Иван"]}):
                marked = core.mark_duplicate_salary_payments([first, second], results, archive)

        self.assertEqual(marked, 2)
        self.assertTrue(all(result.requires_manual_review for result in results))
        self.assertTrue(all(result.destination == archive / "Требует_ручной_проверки" for result in results))
        self.assertTrue(all("Возможный повтор зарплаты" in result.reason for result in results))

    def test_payment_equal_to_already_confirmed_salary_returns_to_manual_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            archive = root / "archive"
            salary = archive / "98" / "Зарплата"
            salary.mkdir(parents=True)
            (salary / "иванов_иван_01-06-2026_50000-00.pdf").write_text("dummy", encoding="utf-8")
            current = root / "retry.pdf"
            current.write_text("dummy", encoding="utf-8")
            results = [self.classification(archive, "02-06-2026", "50000-00")]

            with mock.patch.object(core, "OFFICE_PEOPLE", {"98": ["Иванов Иван"]}):
                marked = core.mark_duplicate_salary_payments([current], results, archive)

        self.assertEqual(marked, 1)
        self.assertTrue(results[0].requires_manual_review)

    def test_payment_equal_to_archived_salary_receipt_returns_to_manual_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            archive = root / "archive"
            salary = archive / "Исходные_чеки" / "98" / "Зарплата"
            salary.mkdir(parents=True)
            (salary / "иванов_иван_01-06-2026_50000-00.pdf").write_text("dummy", encoding="utf-8")
            current = root / "retry.pdf"
            current.write_text("dummy", encoding="utf-8")
            results = [self.classification(archive, "04-06-2026", "50000-00")]

            with mock.patch.object(core, "OFFICE_PEOPLE", {"98": ["Иванов Иван"]}):
                marked = core.mark_duplicate_salary_payments([current], results, archive)

        self.assertEqual(marked, 1)
        self.assertTrue(results[0].requires_manual_review)

    def test_different_salary_amounts_are_not_marked_as_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            archive = root / "archive"
            first = root / "first.pdf"
            second = root / "second.pdf"
            first.write_text("dummy", encoding="utf-8")
            second.write_text("dummy", encoding="utf-8")
            results = [
                self.classification(archive, "01-06-2026", "50000-00"),
                self.classification(archive, "02-06-2026", "30000-00"),
            ]

            with mock.patch.object(core, "OFFICE_PEOPLE", {"98": ["Иванов Иван"]}):
                marked = core.mark_duplicate_salary_payments([first, second], results, archive)

        self.assertEqual(marked, 0)
        self.assertFalse(any(result.requires_manual_review for result in results))

    def test_equal_amounts_for_different_employees_are_not_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            archive = root / "archive"
            first = root / "first.pdf"
            second = root / "second.pdf"
            first.write_text("dummy", encoding="utf-8")
            second.write_text("dummy", encoding="utf-8")
            results = [
                self.classification(archive, "01-06-2026", "50000-00"),
                self.classification(archive, "02-06-2026", "50000-00", "демофамилияагб_петр"),
            ]

            with mock.patch.object(core, "OFFICE_PEOPLE", {"98": ["Иванов Иван", "Демофамилияагб Петр"]}):
                marked = core.mark_duplicate_salary_payments([first, second], results, archive)

        self.assertEqual(marked, 0)
        self.assertFalse(any(result.requires_manual_review for result in results))


if __name__ == "__main__":
    unittest.main()
