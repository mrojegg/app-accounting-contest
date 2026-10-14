from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import sort_documents as sd


class NamingRoutingRegressionTests(unittest.TestCase):
    def test_salary_filename_stays_structured(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "salary.txt"
            source.write_text(
                "Платежное поручение\n"
                "Дата 15.04.2026\n"
                "Получатель Иванов Иван Иванович\n"
                "Назначение платежа Выплата заработной платы за апрель 2026\n"
                "Сумма 120000,00\n",
                encoding="utf-8",
            )

            result = sd.safe_filename(source, "98", "Зарплата", "ОБРАЗЕЦ")

        self.assertEqual(result, "иванов_иван_иванович_15-04-2026_120000-00.txt")

    def test_salary_filename_prefers_execution_date_over_wrong_source_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "payment_02-07-2026_106434-96.pdf"
            source.write_text("", encoding="utf-8")
            text = (
                "31.07.2026 31.07.2026\n"
                "ПЛАТЕЖНОЕ ПОРУЧЕНИЕ № 1116 29.07.2026\n"
                "Получатель Иванов Иван Иванович\n"
                "Назначение платежа Заработная плата\n"
                "Сумма 106434-96\n"
                "ИСПОЛНЕНО\n31 июля 2026\n"
            )

            with patch.object(sd.sorter_core, "file_text", return_value=text):
                result = sd.safe_filename(source, "98", "Зарплата", "ОБРАЗЕЦ")

        self.assertEqual(result, "иванов_иван_иванович_31-07-2026_106434-96.pdf")

    def test_special_subfolder_routing_stays_for_iskratelekom(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_root = Path(tmpdir) / "archive"
            source = Path(tmpdir) / "doc.txt"
            source.write_text("Счет Искрателеком", encoding="utf-8")

            destination, reason = sd.destination_for(source, archive_root, "109", "Интернет", "ПРИМЕР")

        self.assertEqual(destination, archive_root / "109" / "Интернет" / "Искрателеком")
        self.assertIn("Искрателеком", reason)

    def test_vtb_commission_filename_does_not_override_rent_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "VTB_Payment_commission_124_13.02.2026_81556_additional_filter.pdf"
            source.write_text("", encoding="utf-8")
            text = (
                "ПЛАТЕЖНОЕ ПОРУЧЕНИЕ № 124\n"
                "ООО ОБРАЗЕЦ\n"
                "40702000000000000002\n"
                "ООО ЛЕНДЛОРД\n"
                "Получатель\n"
                "Оплата по договору аренды №ПМО/4-2024К/С от 27.05.2024\n"
                "Назначение платежа\n"
                "Сумма 9930,16\n"
            )

            with patch.object(sd.sorter_core, "file_text", return_value=text):
                result = sd.safe_filename(source, "99", "Аренда", "ОБРАЗЕЦ")

        self.assertNotIn("vtb_payment_commission", result)
        self.assertNotIn("комиссия_втб", result)
        self.assertIn("13-02-2026", result)
        self.assertEqual(result, "ооо_лендлорд_13-02-2026_9930-16.pdf")

    def test_contractor_payment_filename_uses_counterparty_date_amount(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "525974_сч._n_30101000000000000001_банк_получателя_инн_7700000001_кпп_771_20-05-2026_526_85169-92.pdf"
            source.write_text("", encoding="utf-8")
            text = (
                "Платежное поручение № 526\n"
                "Дата 20.05.2026\n"
                "Получатель ООО ТЕСТ\n"
                "Назначение платежа Оплата аренды\n"
                "Сумма 85169,92\n"
            )

            with patch.object(sd.sorter_core, "file_text", return_value=text):
                result = sd.safe_filename(source, "109", "Аренда", "ПРИМЕР")

        self.assertEqual(result, "ооо_тест_20-05-2026_85169-92.pdf")

    def test_bank_export_payment_filename_falls_back_to_category_without_garbage(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "525974_сч._n_30101000000000000001_банк_получателя_инн_7700000001_кпп_771_20-05-2026_526_85169-92.pdf"
            source.write_text("", encoding="utf-8")

            with patch.object(sd.sorter_core, "file_text", return_value=""):
                result = sd.safe_filename(source, "109", "Аренда", "ПРИМЕР")

        self.assertEqual(result, "аренда_20-05-2026_85169-92.pdf")

    def test_vtb_commission_filename_does_not_override_salary_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "VTB_Payment_commission_101_13.02.2026_81571_additional_filter.pdf"
            source.write_text("", encoding="utf-8")
            text = (
                "Платежное поручение\n"
                "Дата 13.02.2026\n"
                "Получатель Иванов Иван Иванович\n"
                "Назначение платежа Выплата заработной платы за февраль 2026\n"
                "Сумма 120000,00\n"
            )

            with patch.object(sd.sorter_core, "file_text", return_value=text):
                result = sd.safe_filename(source, "98", "Зарплата", "ОБРАЗЕЦ")

        self.assertEqual(result, "иванов_иван_иванович_13-02-2026_120000-00.pdf")


if __name__ == "__main__":
    unittest.main()
