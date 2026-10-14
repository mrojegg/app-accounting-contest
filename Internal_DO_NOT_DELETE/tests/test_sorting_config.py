from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import sorting_config
import sort_documents as sd


def normalize_text(value: str) -> str:
    return value.lower().replace("ё", "е").strip()


class SortingConfigTests(unittest.TestCase):
    def test_resolve_rules_file_prefers_env_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            rules_file = Path(tmpdir) / "embedded_rules.md"
            previous = os.environ.get("SORTING_RULES_FILE")
            os.environ["SORTING_RULES_FILE"] = str(rules_file)
            try:
                self.assertEqual(sorting_config.resolve_rules_file(), rules_file)
            finally:
                if previous is None:
                    os.environ.pop("SORTING_RULES_FILE", None)
                else:
                    os.environ["SORTING_RULES_FILE"] = previous

    def test_parse_office_section_overrides_people_and_contractors(self) -> None:
        content = (
            "### Офис 120\n"
            "Юрлицо:\n"
            "- ООО ПРИМЕР\n"
            "Сотрудники:\n"
            "- Иван Иванов\n"
            "- Петр Демофамилияагб\n"
            "Контрагенты:\n"
            "- `Интернет`: Искрателеком, Комитерн Корп\n"
        )

        people, contractors, entities, categories = sorting_config.parse_office_sections_from_rules(
            content,
            normalize_text=normalize_text,
        )

        self.assertEqual(people["120"], ["Иван Иванов", "Петр Демофамилияагб"])
        self.assertEqual(contractors["120"]["Интернет"], ["искрателеком", "комитерн корп"])
        self.assertEqual(entities["120"], "ПРИМЕР")
        self.assertEqual(categories, {})

    def test_parse_office_section_tolerates_blank_lines_and_notes(self) -> None:
        content = (
            "### Офис 120\n"
            "Юрлицо:\n"
            "- ООО ПРИМЕР\n"
            "Сотрудники:\n"
            "\n"
            "Комментарий для редактора\n"
            "- Иван Иванов\n"
            "\n"
            "- Петр Демофамилияагб\n"
            "Контрагенты:\n"
            "Ниже список контрагентов\n"
            "\n"
            "- `Интернет`: Искрателеком, Комитерн Корп\n"
        )

        people, contractors, entities, categories = sorting_config.parse_office_sections_from_rules(
            content,
            normalize_text=normalize_text,
        )

        self.assertEqual(people["120"], ["Иван Иванов", "Петр Демофамилияагб"])
        self.assertEqual(contractors["120"]["Интернет"], ["искрателеком", "комитерн корп"])
        self.assertEqual(entities["120"], "ПРИМЕР")
        self.assertEqual(categories, {})

    def test_parse_structured_contractor_folder_rules(self) -> None:
        content = (
            "### Офис 98\n"
            "Контрагенты:\n"
            "- `Интернет`: Билайн | папка: да | алиасы: билайн, ПАО ВымпелКом\n"
            "- `Аренда`: ИП Рахматулин | папка: нет | алиасы: ип рахматулин\n"
        )

        people, contractors, entities, categories = sorting_config.parse_office_sections_from_rules(
            content,
            normalize_text=normalize_text,
        )
        folder_rules = sorting_config.parse_office_contractor_folder_rules(content, normalize_text=normalize_text)

        self.assertEqual(contractors["98"]["Интернет"], ["билайн", "пао вымпелком"])
        self.assertEqual(contractors["98"]["Аренда"], ["ип рахматулин"])
        self.assertEqual(folder_rules["98"]["Интернет"]["пао вымпелком"], "Билайн")
        self.assertNotIn("Аренда", folder_rules.get("98", {}))
        self.assertEqual(people, {})
        self.assertEqual(entities, {})
        self.assertEqual(categories, {})

    def test_load_runtime_config_uses_user_rules_without_legacy_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            rules_file = Path(tmpdir) / "sorting_rules.md"
            rules_file.write_text(
                "### Офис 98\n"
                "Юрлицо:\n"
                "- ООО ОБРАЗЕЦ\n"
                "Разрешенные категории по умолчанию:\n"
                "- `Зарплата`\n"
                "- `Комиссии`\n"
                "Сотрудники:\n"
                "- Новый Сотрудник\n"
                "Контрагенты:\n"
                "- `Услуги`: Новый Контрагент\n"
                "### Офис 130\n"
                "Юрлицо:\n"
                "- ООО НОВОЕ\n"
                "Разрешенные категории по умолчанию:\n"
                "- `Интернет`\n"
                "Сотрудники:\n"
                "- Еще Один\n",
                encoding="utf-8",
            )

            runtime = sorting_config.load_runtime_config(
                normalize_text=normalize_text,
                rules_file=rules_file,
            )

        self.assertIn("98", runtime.offices)
        self.assertIn("130", runtime.offices)
        self.assertEqual(runtime.office_people["98"], ["Новый Сотрудник"])
        self.assertEqual(runtime.office_contractors["98"]["Услуги"], ["новый контрагент"])
        self.assertEqual(runtime.office_people["130"], ["Еще Один"])
        self.assertEqual(runtime.office_entities["98"], "ОБРАЗЕЦ")
        self.assertEqual(runtime.office_entities["130"], "НОВОЕ")
        self.assertEqual(runtime.office_categories["98"], ["Зарплата", "Комиссии"])
        self.assertEqual(runtime.office_categories["130"], ["Интернет"])

    def test_validate_rules_content_reports_duplicate_office_and_bad_contractor_line(self) -> None:
        issues = sorting_config.validate_rules_content(
            "### Офис 120\n"
            "Контрагенты:\n"
            "- Просто текст\n"
            "### Офис 120\n"
            "Сотрудники:\n"
            "- Иван Иванов\n"
        )

        messages = [issue.message for issue in issues]
        self.assertTrue(any("повторно" in message for message in messages))
        self.assertTrue(any("контрагента" in message for message in messages))

    def test_validate_rules_content_accepts_normal_rules(self) -> None:
        issues = sorting_config.validate_rules_content(
            "### Офис 120\n"
            "Сотрудники:\n"
            "- Иван Иванов\n"
            "Контрагенты:\n"
            "- `Интернет`: Искрателеком\n"
        )

        self.assertEqual(issues, [])

    def test_validate_rules_content_does_not_treat_general_rules_as_contractors(self) -> None:
        issues = sorting_config.validate_rules_content(
            "### Офис 120\n"
            "Контрагенты:\n"
            "- `Интернет`: Искрателеком\n"
            "\n"
            "## 13. Общие специальные правила\n"
            "- Банковские комиссии всегда идут в `Комиссии`.\n"
        )

        self.assertEqual(issues, [])

    def test_load_runtime_rule_settings_parses_special_rule_toggles(self) -> None:
        content = (
            "## 5. Таблицы\n"
            "- Для любого офиса с папкой `Зарплата` автоматически создается `Зарплата_<офис>.xlsx`.\n"
            "- Если у сотрудника несколько выплат в одну дату, создаются отдельные колонки `(2)`, `(3)` и далее.\n"
            "- Итоговый столбец зарплатной таблицы называется `Итого за месяц`.\n"
            "- Итоговая строка зарплатной таблицы называется `ВСЕГО`.\n"
            "- Для любого офиса с папкой `Комиссии` автоматически создается `Комиссии_<офис>.xlsx`.\n"
            "\n"
            "## 13. Общие специальные правила\n"
            "- Папки офисов и категорий создаются только при первой реальной раскладке документа.\n"
            "- Пустые папки заранее не создаются.\n"
            "- Если текст документа читается, маршрутизация опирается на него раньше, чем на имя файла.\n"
            "- Документы с низкой уверенностью распознавания отправляются в `Требует_ручной_проверки`.\n"
            "- Имя файла собирается из извлеченного текста документа, если полезные поля найдены.\n"
            "- Банковские комиссии определяются по формулировкам платежа и банковским маркерам в тексте.\n"
            "- Налоги, НДФЛ, ЕНП и страховые взносы определяются по платежным формулировкам документа.\n"
            "- Известные провайдеры и телеком-компании приоритетно относятся к категории `Интернет`.\n"
            "- Для контрагентов с включенной настройкой `Создавать папку` приложение создает подпапку внутри категории.\n"
        )

        settings = sorting_config.load_runtime_rule_settings_from_content(content)

        self.assertTrue(settings.salary_table.enabled)
        self.assertTrue(settings.salary_table.split_same_date_payments)
        self.assertEqual(settings.salary_table.total_column_title, "Итого за месяц")
        self.assertEqual(settings.salary_table.totals_row_title, "ВСЕГО")
        self.assertTrue(settings.folder_creation.create_folders_only_when_documents_exist)
        self.assertTrue(settings.folder_creation.do_not_create_empty_folders_in_advance)
        self.assertTrue(settings.routing.route_by_document_text_first)
        self.assertTrue(settings.manual_review.send_low_confidence_documents_to_manual_review)
        self.assertTrue(settings.naming.use_extracted_text_for_naming)
        self.assertTrue(settings.commissions.detect_by_payment_text)
        self.assertTrue(settings.commissions.create_office_excel)
        self.assertTrue(settings.taxes.detect_by_payment_phrases)
        self.assertTrue(settings.internet.prioritize_known_providers)
        self.assertTrue(settings.internet.create_subfolders_by_office_contractors)

    def test_salary_table_uses_one_column_per_execution_date_rule(self) -> None:
        content = (
            f"- {sorting_config.SALARY_CREATE_RULE}\n"
            f"- {sorting_config.SALARY_ONE_COLUMN_PER_DATE_RULE}\n"
        )

        settings = sorting_config.load_runtime_rule_settings_from_content(content)

        self.assertTrue(settings.salary_table.enabled)
        self.assertFalse(settings.salary_table.split_same_date_payments)

    def test_salary_detection_and_recipient_work_on_normalized_text(self) -> None:
        text = sd.normalize_text(
            "Платежное поручение\n"
            "Дата 15.04.2026\n"
            "Получатель Иванов Иван Иванович\n"
            "Назначение платежа Выплата заработной платы за апрель 2026\n"
            "Сумма 120000,00\n"
        )

        self.assertTrue(sd.looks_like_salary_payment(text, "payment.txt"))
        self.assertEqual(sd.bank_payment_recipient(text), "иванов иван иванович")

    def test_choose_best_extracted_text_keeps_best_body_and_adds_useful_lines(self) -> None:
        merged = sd.choose_best_extracted_text([
            ("strings", "abcdef\nqwerty"),
            ("ocr", "Платежное поручение\nПолучатель ООО Пример"),
            ("mdls", "ИНН 1234567890\nКПП 123456789"),
        ])

        self.assertIn("Платежное поручение", merged)
        self.assertIn("Получатель ООО Пример", merged)
        self.assertIn("ИНН 1234567890", merged)


if __name__ == "__main__":
    unittest.main()
