from __future__ import annotations

import contextlib
import io
import json
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


class CliSummaryContractTests(unittest.TestCase):
    def _summary_events(self, output: str) -> list[dict]:
        events: list[dict] = []
        prefix = "[event-json] "
        for line in output.splitlines():
            if not line.startswith(prefix):
                continue
            payload = json.loads(line[len(prefix):])
            if payload.get("type") == "summary":
                events.append(payload)
        return events

    def test_main_prints_machine_readable_summary_markers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_dir = Path(tmpdir) / "input"
            output_dir = Path(tmpdir) / "output"
            rules_file = Path(tmpdir) / "rules.md"
            input_dir.mkdir()
            output_dir.mkdir()
            rules_file.write_text("### Офис 120\nСотрудники:\n- Иван Иванов\n", encoding="utf-8")
            (input_dir / "doc.txt").write_text("Простой текст документа", encoding="utf-8")

            buffer = io.StringIO()
            argv = [
                "sort_documents.py",
                str(input_dir),
                "--archive-name", "Архив_тест",
                "--output-dir", str(output_dir),
            ]
            with mock.patch.object(sys, "argv", argv), mock.patch.dict(os.environ, {"SORTING_RULES_FILE": str(rules_file)}, clear=False):
                with contextlib.redirect_stdout(buffer):
                    code = sd.main()

        output = buffer.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("[summary] archive_root=", output)
        self.assertIn("[summary] unresolved=", output)
        self.assertIn("[summary] manual_review=", output)
        self.assertIn("[summary] total=", output)
        summary_events = self._summary_events(output)
        self.assertEqual(len(summary_events), 1)
        self.assertIn("archive_root", summary_events[0])

    def test_main_prints_summary_markers_for_empty_input_and_creates_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_dir = Path(tmpdir) / "input"
            output_dir = Path(tmpdir) / "output"
            archive_root = output_dir / "Пустой_архив"
            rules_file = Path(tmpdir) / "rules.md"
            input_dir.mkdir()
            output_dir.mkdir()
            rules_file.write_text("### Офис 120\nСотрудники:\n- Иван Иванов\n", encoding="utf-8")

            buffer = io.StringIO()
            argv = [
                "sort_documents.py",
                str(input_dir),
                "--archive-name", "Пустой_архив",
                "--output-dir", str(output_dir),
                "--apply",
            ]
            with mock.patch.object(sys, "argv", argv), mock.patch.dict(os.environ, {"SORTING_RULES_FILE": str(rules_file)}, clear=False):
                with contextlib.redirect_stdout(buffer):
                    code = sd.main()

            self.assertTrue(archive_root.exists())

        output = buffer.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("[summary] archive_root=", output)
        self.assertIn("[summary] unresolved=0", output)
        self.assertIn("[summary] manual_review=0", output)
        self.assertIn("[summary] total=0", output)
        self.assertEqual(self._summary_events(output)[0]["total"], 0)

    def test_collect_files_skips_current_archive_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_dir = Path(tmpdir) / "input"
            archive_root = input_dir / "Мой_архив"
            input_dir.mkdir()
            archive_root.mkdir()
            (input_dir / "source.txt").write_text("doc", encoding="utf-8")
            (archive_root / "sorted.txt").write_text("sorted", encoding="utf-8")

            files = sd.collect_files(input_dir, archive_root)

        self.assertEqual([path.name for path in files], ["source.txt"])

    def test_collect_files_skips_manual_review_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_dir = Path(tmpdir) / "input"
            archive_root = Path(tmpdir) / "archive"
            manual_review_dir = input_dir / "Требует_ручной_проверки"
            input_dir.mkdir()
            manual_review_dir.mkdir()
            (manual_review_dir / "_report.txt").write_text("report", encoding="utf-8")
            (input_dir / "source.txt").write_text("doc", encoding="utf-8")

            files = sd.collect_files(input_dir, archive_root)

        self.assertEqual([path.name for path in files], ["source.txt"])

    def test_main_fails_on_invalid_rules_before_sorting(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_dir = Path(tmpdir) / "input"
            output_dir = Path(tmpdir) / "output"
            rules_file = Path(tmpdir) / "rules.md"
            input_dir.mkdir()
            output_dir.mkdir()
            rules_file.write_text(
                "### Офис abc\n"
                "Контрагенты:\n"
                "- просто текст\n",
                encoding="utf-8",
            )
            (input_dir / "doc.txt").write_text("Простой текст документа", encoding="utf-8")

            stdout_buffer = io.StringIO()
            stderr_buffer = io.StringIO()
            argv = [
                "sort_documents.py",
                str(input_dir),
                "--archive-name", "Архив_тест",
                "--output-dir", str(output_dir),
            ]
            with mock.patch.object(sys, "argv", argv), mock.patch.dict(os.environ, {"SORTING_RULES_FILE": str(rules_file)}, clear=False):
                with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
                    code = sd.main()

        self.assertEqual(code, 2)
        self.assertIn("Ошибка валидации правил", stderr_buffer.getvalue())
        event_lines = [
            json.loads(line[len("[event-json] "):])
            for line in stdout_buffer.getvalue().splitlines()
            if line.startswith("[event-json] ")
        ]
        self.assertEqual(event_lines[0]["type"], "rules_validation_error")


if __name__ == "__main__":
    unittest.main()
