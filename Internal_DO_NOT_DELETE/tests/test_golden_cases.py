from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import sort_documents as sd


FIXTURES_FILE = Path(__file__).resolve().parent / "fixtures" / "golden_cases.json"


TEST_RULES = """
### Офис 98
Юрлицо:
- ООО ОБРАЗЕЦ
Разрешенные категории по умолчанию:
- `Зарплата`
- `Комиссии`
- `Ндфл и Взносы`
Сотрудники:
- Иванов Иван Иванович

### Офис 109
Юрлицо:
- ООО ПРИМЕР
Разрешенные категории по умолчанию:
- `Аренда`
- `Интернет`
- `Ндфл и Взносы`
Сотрудники:
- Тестовый Сотрудник
Контрагенты:
- `Аренда`: ООО ТЕСТ
- `Интернет`: Искрателеком
"""


def load_cases() -> dict:
    return json.loads(FIXTURES_FILE.read_text(encoding="utf-8"))


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


class GoldenCasesTests(unittest.TestCase):
    def test_classification_cases(self) -> None:
        fixtures = load_cases()["classification"]
        with temporary_rules(TEST_RULES):
            for case in fixtures:
                with self.subTest(case=case["name"]):
                    with tempfile.TemporaryDirectory() as tmpdir:
                        archive_root = Path(tmpdir) / "archive"
                        source = Path(tmpdir) / case["filename"]
                        source.write_text(case["text"], encoding="utf-8")

                        result = sd.classify(source, archive_root)

                    expected = case["expected"]
                    self.assertEqual(result.office, expected["office"])
                    self.assertEqual(result.category, expected["category"])
                    self.assertEqual(result.entity, expected["entity"])
                    self.assertEqual(result.requires_manual_review, expected["requires_manual_review"])
                    self.assertTrue(str(result.destination).endswith(expected["destination_suffix"]))
                    if "new_name" in expected:
                        self.assertEqual(result.new_name, expected["new_name"])

    def test_naming_cases(self) -> None:
        fixtures = load_cases()["naming"]
        for case in fixtures:
            with self.subTest(case=case["name"]):
                with tempfile.TemporaryDirectory() as tmpdir:
                    source = Path(tmpdir) / case["filename"]
                    source.write_text(case["text"], encoding="utf-8")

                    result = sd.safe_filename(source, case["office"], case["category"], case["entity"])

                self.assertEqual(result, case["expected"])


if __name__ == "__main__":
    unittest.main()
