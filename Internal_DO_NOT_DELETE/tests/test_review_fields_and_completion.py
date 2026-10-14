from __future__ import annotations

from decimal import Decimal
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

import fitz

SCRIPTS = Path(os.environ.get("SORTING_TEST_SCRIPTS", Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(SCRIPTS))
import sorting_review_fields as fields
import sorting_completion_report as completion
import sorting_manual_review
import build_salary_tables as salary
import build_insurance_distribution as insurance
import build_commission_table as commission
import sorting_windows_delivery


class ReviewFieldsTests(unittest.TestCase):
    def test_validation_rejects_bad_money_date_and_label(self):
        for label, date, amount in [("Иван", "31-02-2026", "100"), ("Иван", "01-08-2026", "-1"),
                                    ("Иван", "01-08-2026", "NaN"), ("Иван", "01-08-2026", "1.234"),
                                    ("", "01-08-2026", "1"), ("Иван", "01-08-2026", "0")]:
            with self.subTest(amount=amount, date=date), self.assertRaises(ValueError):
                fields.validate_fields(label, date, amount)
        self.assertEqual(fields.validate_fields("Иван", "01.08.2026", "1 234,50")["amount"], "1234.50")

    def test_confirmation_survives_rename_and_archiving_and_overrides_ocr(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "bad.pdf"
            path.write_bytes(b"original payment")
            before = fields.fingerprint(path)
            fields.save_confirmation(root, path, fields.validate_fields("Иван Иванов", "15-08-2026", "1500,00"))
            archive = root / "Исходные_чеки/98/Зарплата"
            archive.mkdir(parents=True)
            renamed = archive / "wrong_01-08-2026_1000-00.pdf"
            path.rename(renamed)
            with mock.patch.object(salary.sd, "file_text", side_effect=AssertionError("OCR must not override confirmation")):
                self.assertEqual(salary.parse_payment_name(renamed), ("Иван Иванов", "15-08-2026", Decimal("1500.00")))
                self.assertEqual(insurance.payment_values(renamed, "Дата 01.08.2026 Сумма 1000,00"), ("15.08.2026", 1500.0))
            self.assertEqual(fields.fingerprint(renamed), before)
            with mock.patch.object(commission.sorting_receipt_archive, "receipt_pdf_paths_for_category_dir", return_value=[renamed]), \
                 mock.patch.object(commission.sd, "file_text", return_value="Дата 01.08.2026 Сумма 1000,00"):
                result = commission.collect_records(archive)[0]
                self.assertEqual((result.date, result.amount), ("15.08.2026", 1500.0))

    def test_corrupted_confirmation_does_not_silently_use_old_amount(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "a.pdf"
            path.write_bytes(b"a")
            (root / fields.CONFIRMED_NAME).write_text("broken", encoding="utf-8")
            with self.assertRaises(ValueError):
                salary.parse_payment_name(path)

    def test_identical_receipts_keep_independent_manual_corrections(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = root / "98/Зарплата"
            folder.mkdir(parents=True)
            first, second = folder / "one.pdf", folder / "two.pdf"
            first.write_bytes(b"identical receipt")
            second.write_bytes(first.read_bytes())
            fields.save_confirmation(root, first, fields.validate_fields("Иван Иванов", "01-08-2026", "1000"))
            fields.save_confirmation(root, second, fields.validate_fields("Иван Иванов", "03-08-2026", "1000"))
            originals = root / "Исходные_чеки/98/Зарплата"
            originals.mkdir(parents=True)
            first.rename(originals / first.name)
            second.rename(originals / second.name)
            self.assertEqual(salary.parse_payment_name(originals / "one.pdf")[1], "01-08-2026")
            self.assertEqual(salary.parse_payment_name(originals / "two.pdf")[1], "03-08-2026")
            (originals / "one.pdf").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "изменен"):
                salary.parse_payment_name(originals / "one.pdf")

    def test_complete_manual_flow_both_companies_blocks_until_last_file(self):
        for office, entity in [("98", "ОБРАЗЕЦ"), ("109", "ПРИМЕР")]:
            with self.subTest(entity=entity), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                archive = root / "archive"
                manual = archive / "Требует_ручной_проверки"
                manual.mkdir(parents=True)
                rules = root / "rules.md"
                rules.write_text(f"# Правила\n## 11. Офисы\n### Офис {office}\nЮрлицо:\n- `ООО {entity}`\nРазрешенные категории по умолчанию:\n- `Зарплата`\nСотрудники:\n- Старый Сотрудник\nКонтрагенты:\n\n## 13. Общие специальные правила\n- Для любого офиса с папкой `Зарплата` автоматически создается `Зарплата_<офис>.xlsx`.\n", encoding="utf-8")
                for name in ("bad.pdf", "pending.pdf"):
                    doc = fitz.open()
                    doc.new_page().insert_text((36, 72), name)
                    doc.save(manual / name)
                    doc.close()
                hashes = {p.name: fields.fingerprint(p) for p in manual.glob("*.pdf")}
                completion.start_inputs(archive, list(manual.glob("*.pdf")))
                for path in manual.glob("*.pdf"):
                    completion.record_destination(archive, path, path)
                command = [sys.executable, "-B", str(SCRIPTS / "apply_manual_decision.py"), "--archive-root", str(archive),
                           "--action", "move", "--kind", "salary", "--office", office, "--entity", entity,
                           "--category", "Зарплата", "--label", "Новый Сотрудник", "--save-to-rules"]
                env = os.environ | {"SORTING_RULES_FILE": str(rules), "PYTHONDONTWRITEBYTECODE": "1"}
                bad = subprocess.run(command + ["--file-name", "bad.pdf", "--payment-date", "31-02-2026", "--payment-amount", "1000"], env=env, capture_output=True, text=True)
                self.assertNotEqual(bad.returncode, 0)
                self.assertTrue((manual / "bad.pdf").exists())
                self.assertNotIn("Новый Сотрудник", rules.read_text(encoding="utf-8"))
                for name, date, amount in [("bad.pdf", "14-08-2026", "1000"), ("pending.pdf", "29-08-2026", "1500")]:
                    result = subprocess.run(command + ["--file-name", name, "--payment-date", date, "--payment-amount", amount], env=env, capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    xlsx = archive / office / "Зарплата" / f"Зарплата_{office}.xlsx"
                    if name == "bad.pdf":
                        self.assertFalse(xlsx.exists())
                    else:
                        with zipfile.ZipFile(xlsx) as workbook:
                            text = workbook.read("xl/worksheets/sheet1.xml").decode()
                        for token in ("14-08-2026", "29-08-2026", "2500.00", "2 строк выплат, 1 сотрудников"):
                            self.assertIn(token, text)
                originals = list((archive / "Исходные_чеки" / office / "Зарплата").glob("*.pdf"))
                self.assertEqual({fields.fingerprint(p) for p in originals}, set(hashes.values()))
                report = json.loads((archive / completion.REPORT_NAME).read_text())
                self.assertEqual((report["input_count"], report["processed"], report["pending"]), (2, 2, 0))
                self.assertTrue(report["complete"])
                with zipfile.ZipFile(root / "archive_windows.zip") as bundle:
                    self.assertEqual(json.loads(bundle.read("archive/" + completion.REPORT_NAME)), report)


class CompletionReportTests(unittest.TestCase):
    def test_report_tracks_triplicate_exclusions_pending_and_missing_without_generated_totals(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            files = [source / f"{index}.pdf" for index in range(6)]
            for index, path in enumerate(files):
                path.write_bytes(b"same" if index < 3 else str(index).encode())
            archive = root / "archive"
            completion.start_inputs(archive, files)
            paths = [archive / "98/Зарплата/normal.pdf", archive / "Требует_ручной_проверки/Исключенные_повторы/one.pdf",
                     archive / "Требует_ручной_проверки/Исключенные_повторы/two.pdf", archive / "Требует_ручной_проверки/bad.pdf",
                     archive / "98/Услуги/lost.pdf"]
            for source_path, target in zip(files, paths):
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source_path, target)
                completion.record_destination(archive, source_path, target)
            paths[-1].unlink()
            (archive / "Требует_ручной_проверки/.manual_review.json").write_text(json.dumps({"bad.pdf": {"review_fields": {"label": "", "date": "", "amount": ""}, "reason": "Не прочитан"}}))
            report = completion.write_report(archive, final=True)
            self.assertEqual([report[k] for k in ("input_count", "processed", "excluded_duplicate", "pending", "missing", "unresolved", "unreadable")], [6, 1, 2, 1, 1, 1, 1])
            self.assertFalse(report["complete"])
            originals = archive / "Исходные_чеки/98/Зарплата"
            originals.mkdir(parents=True)
            paths[0].rename(originals / paths[0].name)
            (archive / "98/Зарплата/Зарплата_98_чеки.pdf").write_bytes(b"generated combined")
            again = completion.write_report(archive)
            self.assertEqual(again["processed"], 1)
            self.assertEqual(again["input_count"], 6)


if __name__ == "__main__":
    unittest.main()
