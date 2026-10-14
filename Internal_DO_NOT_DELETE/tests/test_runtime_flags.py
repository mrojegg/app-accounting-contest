from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import sort_documents as sd
import sorting_config as config


def make_rules(*extra_rules: str, categories: list[str] | None = None) -> str:
    category_lines = "\n".join(f"- `{category}`" for category in (categories or ["Зарплата", "Интернет"]))
    extra = "\n".join(f"- {rule}" for rule in extra_rules)
    if extra:
        extra = f"\n## 13. Общие специальные правила\n{extra}\n"
    return (
        "### Офис 98\n\n"
        "Юрлицо:\n"
        "- `ООО ОБРАЗЕЦ`\n\n"
        "Разрешенные категории по умолчанию:\n"
        f"{category_lines}\n\n"
        "Сотрудники:\n"
        "- Иван Иванов\n\n"
        "Контрагенты:\n"
        "- `Интернет`: Билайн\n"
        f"{extra}"
    )


class RuntimeFlagsTests(unittest.TestCase):
    def with_rules(self, content: str):
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        rules_file = Path(tmpdir.name) / "rules.md"
        rules_file.write_text(content, encoding="utf-8")
        env = mock.patch.dict(os.environ, {"SORTING_RULES_FILE": str(rules_file)}, clear=False)
        env.start()
        sd.refresh_runtime_config()
        self.addCleanup(lambda: (env.stop(), sd.refresh_runtime_config()))
        return Path(tmpdir.name)

    def test_naming_can_use_original_name_instead_of_extracted_text(self) -> None:
        self.with_rules(
            make_rules(
                config.NAMING_ORIGINAL_FALLBACK_RULE,
                config.NAMING_WINDOWS_SAFE_RULE,
                config.NAMING_UNIQUE_SUFFIX_RULE,
            )
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "Билайн?.pdf"
            source.write_text("Получатель Иван Иванов\nСумма 1000,00\n", encoding="utf-8")

            result = sd.safe_filename(source, "98", "Интернет", "ОБРАЗЕЦ")

        self.assertEqual(result, "билайн.pdf")

    def test_naming_without_original_fallback_uses_generated_name(self) -> None:
        self.with_rules(
            make_rules(
                config.NAMING_EXTRACTED_TEXT_RULE,
                config.NAMING_WINDOWS_SAFE_RULE,
                config.NAMING_UNIQUE_SUFFIX_RULE,
            )
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "unknown.txt"
            source.write_text("", encoding="utf-8")

            result = sd.safe_filename(source, None, None, None)

        self.assertNotEqual(result, "unknown.txt")
        self.assertTrue(result.endswith(".txt"))

    def test_windows_safe_naming_can_be_disabled(self) -> None:
        self.with_rules(
            make_rules(
                config.NAMING_ORIGINAL_FALLBACK_RULE,
            )
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "CON.txt"
            source.write_text("", encoding="utf-8")

            result = sd.safe_filename(source, None, None, None)

        self.assertEqual(result, "con.txt")

    def test_windows_safe_naming_can_be_enabled(self) -> None:
        self.with_rules(
            make_rules(
                config.NAMING_ORIGINAL_FALLBACK_RULE,
                config.NAMING_WINDOWS_SAFE_RULE,
            )
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "CON.txt"
            source.write_text("", encoding="utf-8")

            result = sd.safe_filename(source, None, None, None)

        self.assertEqual(result, "file_con.txt")

    def test_conflicting_file_is_preserved_even_when_legacy_suffix_rule_disabled(self) -> None:
        self.with_rules(make_rules(config.MANUAL_CREATE_REPORT_RULE))
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "source.txt"
            destination = Path(tmpdir) / "archive" / "doc.txt"
            source.write_text("new", encoding="utf-8")
            destination.parent.mkdir(parents=True)
            destination.write_text("old", encoding="utf-8")

            sd.move_or_copy(source, destination, "copy", False)

            self.assertEqual(destination.read_text(encoding="utf-8"), "old")
            self.assertEqual((destination.parent / "doc_2.txt").read_text(encoding="utf-8"), "new")

    def test_manual_review_report_can_be_disabled(self) -> None:
        self.with_rules(make_rules(config.NAMING_EXTRACTED_TEXT_RULE))
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_root = Path(tmpdir) / "archive"
            source = Path(tmpdir) / "doc.txt"
            source.write_text("x", encoding="utf-8")
            result = sd.Classification(
                destination=archive_root / "Требует_ручной_проверки",
                office=None,
                category=None,
                entity=None,
                reason="manual",
                new_name="doc.txt",
                confidence=10,
                requires_manual_review=True,
                trace=[],
            )

            sd.write_manual_review_report(archive_root, [(source, result)], False)

            self.assertFalse((archive_root / "Требует_ручной_проверки" / "_report.txt").exists())

    def test_manual_review_report_can_be_enabled(self) -> None:
        self.with_rules(make_rules(config.MANUAL_CREATE_REPORT_RULE))
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_root = Path(tmpdir) / "archive"
            source = Path(tmpdir) / "doc.txt"
            source.write_text("x", encoding="utf-8")
            result = sd.Classification(
                destination=archive_root / "Требует_ручной_проверки",
                office=None,
                category=None,
                entity=None,
                reason="manual",
                new_name="doc.txt",
                confidence=10,
                requires_manual_review=True,
                trace=[],
            )

            sd.write_manual_review_report(archive_root, [(source, result)], False)

            self.assertTrue((archive_root / "Требует_ручной_проверки" / "_report.txt").exists())

    def test_ensure_structure_can_precreate_full_tree(self) -> None:
        self.with_rules(make_rules(config.MANUAL_CREATE_REPORT_RULE, categories=["Зарплата", "Интернет", "Услуги"]))
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_root = Path(tmpdir) / "archive"

            sd.ensure_structure(archive_root, set(), False)

            self.assertTrue((archive_root / "98" / "Зарплата").exists())
            self.assertTrue((archive_root / "98" / "Интернет").exists())
            self.assertTrue((archive_root / "98" / "Услуги").exists())
            self.assertTrue((archive_root / "Требует_ручной_проверки").exists())

    def test_special_subfolders_can_be_disabled(self) -> None:
        self.with_rules(make_rules(config.MANUAL_CREATE_REPORT_RULE))
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_root = Path(tmpdir) / "archive"
            destination = archive_root / "109" / "Интернет" / "Искрателеком"

            effective = sd.effective_destination(destination, archive_root, requires_manual_review=False)

        self.assertEqual(effective, archive_root / "109" / "Интернет")

    def test_special_subfolders_can_be_enabled(self) -> None:
        self.with_rules(make_rules(config.FOLDER_SPECIAL_SUBFOLDERS_RULE))
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_root = Path(tmpdir) / "archive"
            destination = archive_root / "109" / "Интернет" / "Искрателеком"

            effective = sd.effective_destination(destination, archive_root, requires_manual_review=False)

        self.assertEqual(effective, destination)


if __name__ == "__main__":
    unittest.main()
