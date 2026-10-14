from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unicodedata
import unittest
from pathlib import Path

import fitz

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from apply_manual_decision import sanitize_salary_filename, update_office_section
from run_sorting_pipeline import pending_manual_review_count
from sorting_manual_review import (
    METADATA_NAME, load_manual_review_metadata, prune_manual_review_report,
    render_manual_review_report, write_manual_review_report,
)
from sorting_models import Classification
from sorting_postprocess_settings import SALARY_CREATE_RULE


class ManualReviewMetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manual = self.root / "archive" / "Требует_ручной_проверки"
        self.manual.mkdir(parents=True)
        self.items = []
        for day in (1, 2, 4):
            name = f"старый_сотрудник_{day:02}-06-2026_1000-00.pdf"
            path = self.manual / name
            with fitz.open() as doc:
                page = doc.new_page()
                page.insert_text((36, 72), f"Payment {day}")
                doc.save(path)
            self.items.append((path, Classification(
                self.manual, "98", "Зарплата", "ООО ТЕСТ",
                "Возможный повтор зарплаты: сотрудник Старый Сотрудник, сумма 1000,00.",
                name, 40, True, [], salary_duplicate=True,
            )))

    def test_metadata_survives_without_optional_text_report(self):
        write_manual_review_report(self.manual.parent, self.items, False, enabled=False)
        self.assertFalse((self.manual / "_report.txt").exists())
        self.assertEqual(pending_manual_review_count(self.manual.parent), 3)
        self.items[0][0].unlink()
        prune_manual_review_report(self.manual.parent)
        details = load_manual_review_metadata(self.manual)
        self.assertEqual(len(details), 2)
        self.assertTrue(all(item["salary_duplicate"] for item in details.values()))
        self.assertFalse((self.manual / "_report.txt").exists())

    def test_legacy_report_migrates_without_losing_remaining_decisions(self):
        (self.manual / "_report.txt").write_text(render_manual_review_report(self.items), encoding="utf-8")
        (self.manual / METADATA_NAME).write_text("invalid json", encoding="utf-8")
        self.items[0][0].unlink()
        prune_manual_review_report(self.manual.parent)
        details = load_manual_review_metadata(self.manual)
        self.assertEqual(set(details), {path.name for path, _ in self.items[1:]})
        self.assertTrue(all(item["salary_duplicate"] for item in details.values()))
        self.assertNotIn(self.items[0][0].name, (self.manual / "_report.txt").read_text())

    def test_dry_run_does_not_create_metadata(self):
        write_manual_review_report(self.manual.parent, self.items, True)
        self.assertFalse((self.manual / METADATA_NAME).exists())
        self.assertFalse((self.manual / "_report.txt").exists())

    def test_three_sequential_decisions_preserve_other_duplicates_and_finalize_once(self):
        write_manual_review_report(self.manual.parent, self.items, False)
        rules = self.root / "rules.md"
        content = """### Офис 98
Юрлицо:
- `ООО ТЕСТ`
Разрешенные категории по умолчанию:
- `Зарплата`
Сотрудники:
- Старый Сотрудник
Контрагенты:
"""
        content += "\n## 13. Общие специальные правила\n- " + SALARY_CREATE_RULE + "\n"
        rules.write_text(content, encoding="utf-8")
        for index, action in enumerate(("move", "exclude_duplicate", "exclude_duplicate")):
            path = self.items[index][0]
            result = subprocess.run([
                sys.executable, "-B", str(SCRIPTS / "apply_manual_decision.py"),
                "--archive-root", str(self.manual.parent), "--file-name", path.name,
                "--action", action, "--kind", "salary", "--office", "98",
                "--entity", "ООО ТЕСТ", "--category", "Зарплата",
                "--label", "Старый Сотрудник", "--save-to-rules",
            ], env=os.environ | {"SORTING_RULES_FILE": str(rules)}, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(rules.read_text(encoding="utf-8"), content)
            remaining = 2 - index
            self.assertEqual(pending_manual_review_count(self.manual.parent), remaining)
            details = load_manual_review_metadata(self.manual)
            self.assertEqual(len(details), remaining)
            self.assertTrue(all(item["salary_duplicate"] for item in details.values()))
            if remaining:
                self.assertNotIn('"type": "manual_finalize_complete"', result.stdout)
                self.assertFalse((self.manual.parent / "98/Зарплата/Зарплата_98.xlsx").exists())
            else:
                self.assertIn('"type": "manual_finalize_complete"', result.stdout)
        self.assertFalse((self.manual / METADATA_NAME).exists())
        self.assertEqual(len(list((self.manual / "Исключенные_повторы").glob("*.pdf"))), 2)
        with fitz.open(self.manual.parent / "98/Зарплата/Зарплата_98_чеки.pdf") as doc:
            self.assertEqual(doc.page_count, 1)


class ManualRulesUnicodeTests(unittest.TestCase):
    def test_existing_employee_and_counterparty_preserve_rules_byte_for_byte(self):
        content = unicodedata.normalize("NFD", """### Офис 98
Юрлицо:
- `ООО СТРОЙ`
Разрешенные категории по умолчанию:
- `Зарплата`
- `Интернет`
Сотрудники:
- Демофамилияабы Игорь Олегович
Контрагенты:
- `Интернет`: Билайн | папка: нет | алиасы: Билайн

""")
        for kind, category, label in (
            ("salary", "Зарплата", "Демофамилияабы Игорь Олегович"),
            ("contractor", "Интернет", "Билайн"),
        ):
            self.assertEqual(update_office_section(content, "98", "ООО СТРОЙ", kind, category, label), content)

    def test_new_employee_is_normalized_and_repeat_is_idempotent(self):
        content = "### Офис 98\nСотрудники:\n- Старый Сотрудник\n\n"
        label = unicodedata.normalize("NFD", "Демофамилияабы Игорь")
        updated = update_office_section(content, "98", "", "salary", "", label)
        self.assertIn("- Демофамилияабы Игорь", updated)
        self.assertEqual(update_office_section(updated, "98", "", "salary", "", label), updated)

    def test_decomposed_salary_filename_keeps_short_i(self):
        name = "Демофамилияабы_Игорь_01-06-2026_1000-00.pdf"
        self.assertEqual(sanitize_salary_filename(unicodedata.normalize("NFD", name)), name)


if __name__ == "__main__":
    unittest.main()
