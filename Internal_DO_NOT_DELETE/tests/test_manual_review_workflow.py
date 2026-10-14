from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
import zipfile
from pathlib import Path

import fitz


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "Internal_DO_NOT_DELETE" / "scripts"


class ManualReviewWorkflowTests(unittest.TestCase):
    def write_pdf(self, path: Path, text: str = "receipt") -> None:
        document = fitz.open()
        page = document.new_page()
        page.insert_text((36, 72), text)
        document.save(path)
        document.close()

    def write_rules(self, path: Path) -> None:
        path.write_text(
            textwrap.dedent(
                """\
                # Регламент сортировки документов

                ## 11. Офисы

                ### Офис 98

                Юрлицо:
                - `ООО ОБРАЗЕЦ`

                Разрешенные категории по умолчанию:
                - `Зарплата`

                Сотрудники:
                - Старый Сотрудник

                Контрагенты:
                - `Интернет`: Билайн

                ## 13. Общие специальные правила
                - Для любого офиса с папкой `Зарплата` автоматически создается `Зарплата_<офис>.xlsx`.
                """
            ),
            encoding="utf-8",
        )

    def run_script(self, env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-B", str(SCRIPTS_DIR / "apply_manual_decision.py"), *args],
            cwd=ROOT,
            env={**env, "PYTHONDONTWRITEBYTECODE": "1"},
            text=True,
            capture_output=True,
            check=False,
        )

    def test_salary_assignment_learns_employee_and_finalizes_when_manual_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            archive = root / "archive"
            manual = archive / "Требует_ручной_проверки"
            manual.mkdir(parents=True)
            (manual / "_report.txt").write_text("report", encoding="utf-8")
            salary_file = "иванов_иван_15-04-2026_1000-00.pdf"
            self.write_pdf(manual / salary_file, "Ivanov payment")
            rules = root / "sorting_rules.md"
            self.write_rules(rules)
            env = os.environ | {"SORTING_RULES_FILE": str(rules)}

            result = self.run_script(
                env,
                "--archive-root", str(archive),
                "--file-name", salary_file,
                "--action", "move",
                "--kind", "salary",
                "--office", "98",
                "--entity", "ОБРАЗЕЦ",
                "--category", "Зарплата",
                "--label", "Иванов Иван",
                "--save-to-rules",
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertFalse((archive / "98" / "Зарплата" / salary_file).exists())
            self.assertTrue((archive / "Исходные_чеки" / "98" / "Зарплата" / salary_file).exists())
            content = rules.read_text(encoding="utf-8")
            self.assertIn("- Иванов Иван", content)
            salary_xlsx = archive / "98" / "Зарплата" / "Зарплата_98.xlsx"
            salary_pdf = archive / "98" / "Зарплата" / "Зарплата_98_чеки.pdf"
            self.assertTrue(salary_xlsx.exists())
            self.assertTrue(salary_pdf.exists())
            with fitz.open(salary_pdf) as merged:
                self.assertEqual(merged.page_count, 1)
            with zipfile.ZipFile(salary_xlsx) as workbook:
                sheet_xml = workbook.read("xl/worksheets/sheet1.xml").decode("utf-8")
            self.assertIn("1 строк выплат, 1 сотрудников", sheet_xml)
            self.assertIn("Иванов Иван", sheet_xml)
            self.assertIn("1000.00", sheet_xml)
            self.assertIn('"type": "manual_finalize_complete"', result.stdout)
            self.assertTrue((root / "archive_windows.zip").exists())

    def test_contractor_assignment_learns_counterparty(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            archive = root / "archive"
            manual = archive / "Требует_ручной_проверки"
            manual.mkdir(parents=True)
            (manual / "_report.txt").write_text("report", encoding="utf-8")
            (manual / "contractor.pdf").write_bytes(b"%PDF-1.4\n%%EOF")
            rules = root / "sorting_rules.md"
            self.write_rules(rules)
            env = os.environ | {"SORTING_RULES_FILE": str(rules)}

            result = self.run_script(
                env,
                "--archive-root", str(archive),
                "--file-name", "contractor.pdf",
                "--action", "move",
                "--kind", "contractor",
                "--office", "98",
                "--entity", "ОБРАЗЕЦ",
                "--category", "Интернет",
                "--label", "Дилайн",
                "--save-to-rules",
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertTrue((archive / "98" / "Интернет" / "contractor.pdf").exists())
            self.assertFalse((archive / "98" / "Интернет" / "Дилайн").exists())
            content = rules.read_text(encoding="utf-8")
            self.assertIn("- `Интернет`: Билайн, Дилайн", content)

    def test_structured_contractor_rules_are_preserved_when_learning_counterparty(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            archive = root / "archive"
            manual = archive / "Требует_ручной_проверки"
            manual.mkdir(parents=True)
            (manual / "kontur.pdf").write_bytes(b"%PDF-1.4\n%%EOF")
            rules = root / "sorting_rules.md"
            rules.write_text(
                textwrap.dedent(
                    """\
                    ### Офис 98
                    Юрлицо:
                    - `ООО ОБРАЗЕЦ`
                    Разрешенные категории по умолчанию:
                    - `Услуги`
                    Сотрудники:
                    - Иванов Иван
                    - Иванов Иван
                    Контрагенты:
                    - `Интернет`: Билайн | папка: нет | алиасы: билайн, вымпелком
                    - `Услуги`: ООО "ХЭДХАНТЕР" | папка: да | алиасы: headhunter, хэдхантер
                    - `Услуги`: Регсервис | папка: да | алиасы: регсервис, РЕГСЕРВИС
                    """
                ),
                encoding="utf-8",
            )
            before_lines = rules.read_text(encoding="utf-8").splitlines()
            env = os.environ | {"SORTING_RULES_FILE": str(rules)}

            result = self.run_script(
                env,
                "--archive-root", str(archive),
                "--file-name", "kontur.pdf",
                "--action", "move",
                "--kind", "contractor",
                "--office", "98",
                "--entity", "ООО ОБРАЗЕЦ",
                "--category", "Услуги",
                "--label", "СБ Контур",
                "--save-to-rules",
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            content = rules.read_text(encoding="utf-8")
            for line in before_lines:
                self.assertIn(line, content)
            self.assertIn("- `Услуги`: СБ Контур | папка: нет | алиасы: СБ Контур", content)
            self.assertNotIn("Регсервис, СБ Контур", content)

    def test_delete_keeps_manual_pending_until_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            archive = root / "archive"
            manual = archive / "Требует_ручной_проверки"
            manual.mkdir(parents=True)
            (manual / "_report.txt").write_text("report", encoding="utf-8")
            (manual / "junk1.pdf").write_bytes(b"%PDF-1.4\n%%EOF")
            (manual / "junk2.pdf").write_bytes(b"%PDF-1.4\n%%EOF")
            rules = root / "sorting_rules.md"
            self.write_rules(rules)
            env = os.environ | {"SORTING_RULES_FILE": str(rules)}

            first = self.run_script(
                env,
                "--archive-root", str(archive),
                "--file-name", "junk1.pdf",
                "--action", "delete",
            )
            self.assertEqual(first.returncode, 0, msg=first.stderr)
            self.assertIn('"type": "manual_review_pending"', first.stdout)
            self.assertNotIn('"type": "manual_finalize_complete"', first.stdout)

            second = self.run_script(
                env,
                "--archive-root", str(archive),
                "--file-name", "junk2.pdf",
                "--action", "delete",
            )
            self.assertEqual(second.returncode, 0, msg=second.stderr)
            self.assertIn('"type": "manual_finalize_complete"', second.stdout)
            self.assertTrue((root / "archive_windows.zip").exists())

    def test_excluded_duplicate_is_preserved_and_does_not_block_finalization(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            archive = root / "archive"
            manual = archive / "Требует_ручной_проверки"
            manual.mkdir(parents=True)
            duplicate_name = "иванов_иван_15-04-2026_1000-00.pdf"
            self.write_pdf(manual / duplicate_name, "Rejected duplicate")
            rules = root / "sorting_rules.md"
            self.write_rules(rules)
            env = os.environ | {"SORTING_RULES_FILE": str(rules)}

            result = self.run_script(
                env,
                "--archive-root", str(archive),
                "--file-name", duplicate_name,
                "--action", "exclude_duplicate",
            )

            excluded = manual / "Исключенные_повторы" / duplicate_name
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertTrue(excluded.exists())
            self.assertFalse((manual / duplicate_name).exists())
            self.assertIn('"type": "salary_duplicate_excluded"', result.stdout)
            self.assertIn('"type": "manual_finalize_complete"', result.stdout)


if __name__ == "__main__":
    unittest.main()
