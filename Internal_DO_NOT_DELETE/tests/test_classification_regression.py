from __future__ import annotations

import os
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import sort_documents as sd


@contextmanager
def temporary_rules(content: str):
    previous = os.environ.get("SORTING_RULES_FILE")
    with tempfile.TemporaryDirectory() as tmpdir:
        rules_file = Path(tmpdir) / "sorting_rules.md"
        rules_file.write_text(content, encoding="utf-8")
        os.environ["SORTING_RULES_FILE"] = str(rules_file)
        sd.refresh_runtime_config()
        try:
            yield
        finally:
            if previous is None:
                os.environ.pop("SORTING_RULES_FILE", None)
            else:
                os.environ["SORTING_RULES_FILE"] = previous
            sd.refresh_runtime_config()


TEST_RULES = """
### Офис 84
Юрлицо:
- ООО ОБРАЗЕЦ
Разрешенные категории по умолчанию:
- `Зарплата`
Сотрудники:
- Сотрудник Восемьдесят Четыре

### Офис 98
Юрлицо:
- ООО ОБРАЗЕЦ
Разрешенные категории по умолчанию:
- `Зарплата`
- `Аренда`
Сотрудники:
- Иванов Иван Иванович
- Демофамилияагб Петр Демофамилияагбич

### Офис 99
Юрлицо:
- ООО ОБРАЗЕЦ
Разрешенные категории по умолчанию:
- `Зарплата`
Сотрудники:
- Сидоров Сидор
"""

ENTITY_CONFLICT_RULES = """
### Офис 98
Юрлицо:
- ООО ОБРАЗЕЦ
Разрешенные категории по умолчанию:
- `Услуги`
Сотрудники:

Контрагенты:

### Офис 109
Юрлицо:
- ООО ПРИМЕР
Разрешенные категории по умолчанию:
- `Услуги`
Сотрудники:

Контрагенты:
- `Услуги`: СБ Контур | папка: нет | алиасы: СБ Контур, Контур
"""


class ClassificationRegressionTests(unittest.TestCase):
    def test_counterparty_rule_cannot_route_document_to_other_legal_entity_office(self) -> None:
        with temporary_rules(ENTITY_CONFLICT_RULES), tempfile.TemporaryDirectory() as tmpdir:
            archive_root = Path(tmpdir) / "образец"
            source = Path(tmpdir) / "kontur.txt"
            source.write_text(
                "ПЛАТЕЖНОЕ ПОРУЧЕНИЕ № 1078\n"
                "ООО ОБРАЗЕЦ\n"
                "Сч. № 40702000000000000002\n"
                "Получатель АО ПФ СКБ КОНТУР\n"
                "Оплата по счету за услуги\n"
                "Сумма 18200-00\n",
                encoding="utf-8",
            )

            result = sd.classify(source, archive_root)

        self.assertEqual(result.entity, "ОБРАЗЕЦ")
        self.assertIsNone(result.office)
        self.assertEqual(result.category, "Услуги")
        self.assertTrue(result.requires_manual_review)
        self.assertEqual(result.destination, archive_root / "Требует_ручной_проверки")
        self.assertTrue(any("юрлицо офиса ПРИМЕР не совпадает" in item for item in result.trace))

    def test_counterparty_rule_still_routes_matching_legal_entity(self) -> None:
        with temporary_rules(ENTITY_CONFLICT_RULES):
            text = sd.normalize_text("ооо пример получатель ао пф скб контур оплата услуг")

            office, reason = sd.detect_office(text, "", "ПРИМЕР")

        self.assertEqual(office, "109")
        self.assertEqual(reason, "офис 109")

    def test_filename_alone_does_not_drive_classification(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_root = Path(tmpdir) / "archive"
            source = Path(tmpdir) / "счет_неизвестный_5.pdf"
            source.write_text("", encoding="utf-8")

            result = sd.classify(source, archive_root)

        self.assertIsNone(result.office)
        self.assertEqual(result.category, "Прочее")
        self.assertIsNone(result.entity)
        self.assertEqual(result.new_name, source.name)
        self.assertEqual(result.destination, archive_root / "Требует_ручной_проверки")
        self.assertTrue(result.requires_manual_review)

    def test_salary_payment_classification_stays_on_expected_office(self) -> None:
        with temporary_rules(TEST_RULES), tempfile.TemporaryDirectory() as tmpdir:
            archive_root = Path(tmpdir) / "archive"
            source = Path(tmpdir) / "salary.txt"
            source.write_text(
                "Платежное поручение\n"
                "Дата 15.04.2026\n"
                "Получатель Иванов Иван Иванович\n"
                "Назначение платежа Выплата заработной платы за апрель 2026\n"
                "Сумма 120000,00\n",
                encoding="utf-8",
            )

            result = sd.classify(source, archive_root)

        self.assertEqual(result.office, "98")
        self.assertEqual(result.category, "Зарплата")
        self.assertEqual(result.entity, "ОБРАЗЕЦ")
        self.assertEqual(result.destination, archive_root / "98" / "Зарплата")
        self.assertFalse(result.requires_manual_review)

    def test_employee_in_salary_only_office_defaults_to_salary_category(self) -> None:
        with temporary_rules(TEST_RULES), tempfile.TemporaryDirectory() as tmpdir:
            archive_root = Path(tmpdir) / "archive"
            source = Path(tmpdir) / "office84_employee.txt"
            source.write_text(
                "Платежное поручение\n"
                "Получатель Сотрудник Восемьдесят Четыре\n"
                "Сумма 33333,40\n",
                encoding="utf-8",
            )

            result = sd.classify(source, archive_root)

        self.assertEqual(result.office, "84")
        self.assertEqual(result.category, "Зарплата")
        self.assertEqual(result.destination, archive_root / "84" / "Зарплата")
        self.assertFalse(result.requires_manual_review)

    def test_employee_payment_in_multi_category_office_defaults_to_salary_category(self) -> None:
        with temporary_rules(TEST_RULES), tempfile.TemporaryDirectory() as tmpdir:
            archive_root = Path(tmpdir) / "archive"
            source = Path(tmpdir) / "office98_employee.txt"
            source.write_text(
                "Платежное поручение\n"
                "Получатель Демофамилияагб Петр Демофамилияагбич\n"
                "Сумма 45000,00\n",
                encoding="utf-8",
            )

            result = sd.classify(source, archive_root)

        self.assertEqual(result.office, "98")
        self.assertEqual(result.category, "Зарплата")
        self.assertEqual(result.destination, archive_root / "98" / "Зарплата")
        self.assertFalse(result.requires_manual_review)

    def test_office_detects_employee_from_payment_account_holder_line(self) -> None:
        with temporary_rules(TEST_RULES):
            text = sd.normalize_text(
                "ПЛАТЕЖНОЕ ПОРУЧЕНИЕ N 224 "
                "ООО ОБРАЗЕЦ "
                "Сч. N 40817000000000000001 Иванов Иван Иванович Вид оп. 01 "
                "Рез. поле Выплата заработной платы. НДФЛ удержан. НДС не облагается"
            )

            recipient = sd.bank_payment_recipient(text)
            office, reason = sd.detect_office(text, "", "ОБРАЗЕЦ")

        self.assertEqual(recipient, "иванов иван иванович")
        self.assertEqual(office, "98")
        self.assertEqual(reason, "офис 98")

    def test_office_detects_partial_recipient_match(self) -> None:
        with temporary_rules(TEST_RULES):
            text = sd.normalize_text(
                "ПЛАТЕЖНОЕ ПОРУЧЕНИЕ N 224 "
                "ООО ОБРАЗЕЦ "
                "Сч. N 40817000000000000001 Иванов Иван Вид оп. 01 "
                "Рез. поле Выплата заработной платы. НДФЛ удержан. НДС не облагается"
            )

            office, reason = sd.detect_office(text, "", "ОБРАЗЕЦ")

        self.assertEqual(office, "98")
        self.assertEqual(reason, "офис 98")

    def test_office_detects_declined_employee_name_from_bank_text(self) -> None:
        with temporary_rules(TEST_RULES):
            text = sd.normalize_text(
                "ПЛАТЕЖНОЕ ПОРУЧЕНИЕ N 207 "
                "ООО ОБРАЗЕЦ "
                "Для зачисления на счет Сидора Сидорова "
                "Заработная плата за Март 2026 г."
            )

            office, reason = sd.detect_office(text, "", "ОБРАЗЕЦ")

        self.assertEqual(office, "99")
        self.assertEqual(reason, "офис 99")

    def test_manual_review_keeps_structured_filename_when_text_is_known(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_root = Path(tmpdir) / "archive"
            source = Path(tmpdir) / "page_095.pdf"
            source.write_text("", encoding="utf-8")
            text = (
                "ПЛАТЕЖНОЕ ПОРУЧЕНИЕ N 224\n"
                "ООО ПРИМЕР\n"
                "Сч. N 40817000000000000001 Иванов Иван Иванович Вид оп. 01\n"
                "Назначение платежа Выплата заработной платы. НДФЛ удержан. НДС не облагается\n"
                "Сумма 16190,71\n"
            )
            with mock.patch.object(sd.sorter_core, "file_text", return_value=text):
                result = sd.classify(source, archive_root)

        self.assertTrue(result.requires_manual_review)
        self.assertEqual(result.destination, archive_root / "Требует_ручной_проверки")
        self.assertEqual(result.new_name, "иванов_иван_иванович_без_даты_16190-71.pdf")

    def test_unique_entity_routes_commissions_to_new_office(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_root = Path(tmpdir) / "archive"
            source = Path(tmpdir) / "commission.txt"
            source.write_text("комиссия банка ооо новое", encoding="utf-8")
            runtime = sd.classification_runtime()
            patched_runtime = runtime.__class__(
                entity_patterns={**runtime.entity_patterns, "НОВОЕ": ["новое"]},
                entity_account_patterns=runtime.entity_account_patterns,
                entity_source_hint_patterns=runtime.entity_source_hint_patterns,
                office_people=runtime.office_people,
                office_contractors=runtime.office_contractors,
                office_entities={**runtime.office_entities, "44": "НОВОЕ"},
                office_categories={**runtime.office_categories, "44": ["Комиссии"]},
                offices=[*runtime.offices, "44"],
                category_patterns=runtime.category_patterns,
                tax_patterns=runtime.tax_patterns,
                insurance_accident_patterns=runtime.insurance_accident_patterns,
                usn_patterns=runtime.usn_patterns,
                bank_commission_patterns=runtime.bank_commission_patterns,
            )

            result = sd.classification.classify_document(
                source,
                archive_root,
                runtime=patched_runtime,
                file_text=lambda path: path.read_text(encoding="utf-8"),
                normalize_text=sd.normalize_text,
                match_any=sd.match_any,
                bounded_confidence=sd.bounded_confidence,
                bank_payment_recipient=sd.bank_payment_recipient,
                bank_payment_purpose=sd.bank_payment_purpose,
                safe_filename=sd.safe_filename,
            )

        self.assertEqual(result.entity, "НОВОЕ")
        self.assertEqual(result.category, "Комиссии")
        self.assertEqual(result.destination, archive_root / "44" / "Комиссии")

    def test_split_commission_file_uses_source_hint_for_entity(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_root = Path(tmpdir) / "archive"
            source = Path(tmpdir) / "ПРИМЕР с 12:03 по 15:04 включительно_page_002.pdf"
            source.write_text("", encoding="utf-8")
            with mock.patch.object(sd.sorter_core, "file_text", return_value="комиссия банка"):
                result = sd.classify(source, archive_root)

        self.assertEqual(result.entity, "ПРИМЕР")
        self.assertEqual(result.category, "Комиссии")
        self.assertEqual(result.destination, archive_root / "109" / "Комиссии")
        self.assertFalse(result.requires_manual_review)

    def test_exact_employee_match_overrides_low_advantage_manual_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_root = Path(tmpdir) / "archive"
            source = Path(tmpdir) / "salary_mix.txt"
            source.write_text(
                "Платежное поручение\n"
                "ООО ПРИМЕР\n"
                "Получатель Демофамилияадз Мухаммед\n"
                "Назначение платежа Выплата заработной платы и Бизнес-Легион\n"
                "Сумма 120000,00\n",
                encoding="utf-8",
            )

            result = sd.classify(source, archive_root)

        self.assertEqual(result.office, "94")
        self.assertEqual(result.category, "Зарплата")
        self.assertEqual(result.destination, archive_root / "94" / "Зарплата")
        self.assertFalse(result.requires_manual_review)


if __name__ == "__main__":
    unittest.main()
