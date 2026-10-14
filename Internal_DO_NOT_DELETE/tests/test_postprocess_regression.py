from __future__ import annotations

import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import build_commission_table_demo_b as demo_b_commission
import build_commission_table as generic_commission
import build_insurance_distribution as demo_a_insurance
import build_insurance_distribution_generic as generic_insurance
import build_insurance_distribution_demo_b as demo_b_insurance
import build_salary_tables as generic_salary
import build_salary_tables_demo_b as demo_b_salary
import build_salary_tables_demo_a as demo_a_salary
import build_tax_distribution_generic as generic_tax
import build_tax_distribution as demo_a_tax
import build_tax_distribution_demo_b as demo_b_tax
import finalize_postprocess
import run_sorting_pipeline
import salary_employee_counts
import sorting_receipt_archive
import sorting_postprocess_settings


class PostprocessRegressionTests(unittest.TestCase):
    def write_rules(self, root: Path, *lines: str) -> Path:
        rules = root / "sorting_rules.md"
        rules.write_text("\n".join(lines), encoding="utf-8")
        return rules

    def test_demo_b_commission_collects_current_filename_format(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "комиссия_втб_13-02-2026_100.pdf"
            path.write_text("dummy", encoding="utf-8")
            with mock.patch.object(demo_b_commission.sd, "file_text", return_value="Дата 13.02.2026 Сумма 81502-00"):
                rows = demo_b_commission.collect_rows(Path(tmpdir))
        self.assertEqual(rows, [("13.02.2026", 81502.0, path.name)])

    def test_dynamic_commission_builder_runs_for_new_office(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_root = Path(tmpdir)
            commission_dir = archive_root / "44" / "Комиссии"
            commission_dir.mkdir(parents=True)
            (commission_dir / "комиссия_01-03-2026_без_номера_1500-00.pdf").write_text("dummy", encoding="utf-8")
            rules = self.write_rules(
                archive_root,
                sorting_postprocess_settings.COMMISSION_EXCEL_RULE,
            )

            with mock.patch.dict("os.environ", {"SORTING_RULES_FILE": str(rules)}), \
                 mock.patch.object(run_sorting_pipeline, "run_module") as run_module:
                run_sorting_pipeline.build_company_outputs(archive_root)

        invocations = [(call.args[0].__name__, call.args[1]) for call in run_module.call_args_list]
        self.assertTrue(
            any(name == "build_commission_table" and "Комиссии_44.xlsx" in " ".join(argv) for name, argv in invocations)
        )

    def test_dynamic_commission_builder_respects_disabled_excel_rule(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_root = Path(tmpdir)
            commission_dir = archive_root / "44" / "Комиссии"
            commission_dir.mkdir(parents=True)
            (commission_dir / "комиссия_01-03-2026_без_номера_1500-00.pdf").write_text("dummy", encoding="utf-8")
            rules = self.write_rules(archive_root, "# no commission excel")

            with mock.patch.dict("os.environ", {"SORTING_RULES_FILE": str(rules)}), \
                 mock.patch.object(run_sorting_pipeline, "run_module") as run_module:
                run_sorting_pipeline.build_company_outputs(archive_root)

        invocations = [(call.args[0].__name__, call.args[1]) for call in run_module.call_args_list]
        self.assertFalse(any(name == "build_commission_table" for name, _ in invocations))

    def test_demo_b_tax_collects_current_filename_format(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "налог_10-04-2026_без_номера_188582-38.pdf"
            path.write_text("dummy", encoding="utf-8")
            with mock.patch.object(demo_b_tax.base.sd, "file_text", return_value="Платежное поручение ЕНП 10.04.2026 сумма 188582-38"):
                rows = demo_b_tax.collect_tax_rows(Path(tmpdir))
        self.assertEqual(rows, [("10.04.2026", 188582.38, path.name)])

    def test_demo_b_insurance_collects_current_filename_format(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "взносы_30-03-2026_201_7143-19.pdf"
            path.write_text("dummy", encoding="utf-8")
            text = (
                "Платежное поручение 30.03.2026 "
                "страховые взносы на обязательное пенсионное страхование "
                "сумма 7143-19"
            )
            with mock.patch.object(demo_b_insurance.base.sd, "file_text", return_value=text):
                rows = demo_b_insurance.collect_rows(Path(tmpdir))
        self.assertEqual(rows, [("30.03.2026", 7143.19, path.name)])

    def test_demo_b_insurance_survives_renamed_filename_without_payment_number(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "79710000000000000001_взносы_02-07-2026_12261-05.pdf"
            path.write_text("dummy", encoding="utf-8")
            text = "Страховые взносы, дата документа 31.07.2026"
            with mock.patch.object(demo_b_insurance.base.sd, "file_text", return_value=text):
                rows = demo_b_insurance.collect_rows(Path(tmpdir))

        self.assertEqual(rows, [("02.07.2026", 12261.05, path.name)])

    def test_demo_b_salary_extracts_amount_from_text_when_name_has_no_amount(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "демофамилияабз_ахмед_абделсалам_12.03-2026_без_суммы.pdf"
            path.write_text("dummy", encoding="utf-8")
            text = (
                "Платежное поручение 12.03.2026 "
                "Сумма Сумма прописью Пятьдесят пять тысяч рублей 47 копеек "
                "Выплата заработной платы"
            )
            with mock.patch.object(demo_b_salary.sd, "file_text", return_value=text):
                parsed = demo_b_salary.parse_payment_name(path)
        self.assertEqual(parsed, ("демофамилияабз ахмед абделсалам", "12-03-2026", Decimal("55000.47")))

    def test_generic_salary_builder_picks_up_new_office_from_runtime_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            salary_dir = root / "44" / "Зарплата"
            salary_dir.mkdir(parents=True)
            path = salary_dir / "иван_иванов_15-04-2026_1000-00.pdf"
            path.write_text("dummy", encoding="utf-8")

            with mock.patch.object(generic_salary.sd, "OFFICES", ["44"]), \
                 mock.patch.object(generic_salary.sd, "OFFICE_PEOPLE", {"44": ["Иван Иванов"]}), \
                 mock.patch.object(generic_salary.sd, "file_text", return_value="Получатель Иван Иванов"), \
                 mock.patch.object(generic_salary.sd, "bank_payment_recipient", return_value="иван иванов"), \
                 mock.patch.object(generic_salary.sd, "normalize_text", side_effect=lambda value: value.lower()):
                office_data, unresolved = generic_salary.collect_office_data(root)

        self.assertEqual(unresolved, [])
        self.assertIn("44", office_data)
        self.assertEqual(len(office_data["44"]), 1)
        self.assertEqual(office_data["44"][0].person, "Иван Иванов")
        self.assertEqual(office_data["44"][0].date, "15-04-2026")

    def test_generic_salary_builder_reads_receipts_archived_outside_office(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            salary_dir = root / "Исходные_чеки" / "44" / "Зарплата"
            salary_dir.mkdir(parents=True)
            path = salary_dir / "иван_иванов_15-04-2026_1000-00.pdf"
            path.write_text("dummy", encoding="utf-8")

            with mock.patch.object(generic_salary.sd, "OFFICES", ["44"]), \
                 mock.patch.object(generic_salary.sd, "OFFICE_PEOPLE", {"44": ["Иван Иванов"]}), \
                 mock.patch.object(generic_salary.sd, "file_text", return_value="Получатель Иван Иванов"), \
                 mock.patch.object(generic_salary.sd, "bank_payment_recipient", return_value="иван иванов"), \
                 mock.patch.object(generic_salary.sd, "normalize_text", side_effect=lambda value: value.lower()):
                office_data, unresolved = generic_salary.collect_office_data(root)

        self.assertEqual(unresolved, [])
        self.assertEqual(office_data["44"][0].source_path, path)

    def test_commission_builder_reads_receipts_archived_outside_office(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            archive = Path(tmpdir)
            commission_root = archive / "44" / "Комиссии"
            commission_root.mkdir(parents=True)
            source = archive / "Исходные_чеки" / "44" / "Комиссии" / "комиссия_01-03-2026_без_номера_1500-00.pdf"
            source.parent.mkdir(parents=True)
            source.write_text("dummy", encoding="utf-8")

            with mock.patch.object(generic_commission.sd, "file_text", return_value="Дата 01.03.2026 Сумма 1500-00"):
                records = generic_commission.collect_records(commission_root)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].source_path, source)

    def test_completed_receipts_are_moved_outside_office_folders(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            archive = Path(tmpdir)
            salary_root = archive / "44" / "Зарплата"
            commission_root = archive / "44" / "Комиссии"
            salary_root.mkdir(parents=True)
            commission_root.mkdir(parents=True)
            salary_receipt = salary_root / "иван_иванов_15-04-2026_1000-00.pdf"
            commission_receipt = commission_root / "комиссия_15-04-2026_100-00.pdf"
            salary_receipt.write_text("salary", encoding="utf-8")
            commission_receipt.write_text("commission", encoding="utf-8")
            (salary_root / "Зарплата_44.xlsx").write_text("table", encoding="utf-8")
            (salary_root / "Зарплата_44_чеки.pdf").write_text("merged", encoding="utf-8")
            (commission_root / "Комиссии_44.xlsx").write_text("table", encoding="utf-8")
            (commission_root / "Комиссии_44_чеки.pdf").write_text("merged", encoding="utf-8")

            moved = sorting_receipt_archive.archive_completed_receipts(archive)

            self.assertEqual(len(moved), 2)
            self.assertFalse(salary_receipt.exists())
            self.assertFalse(commission_receipt.exists())
            self.assertTrue((archive / "Исходные_чеки" / "44" / "Зарплата" / salary_receipt.name).exists())
            self.assertTrue((archive / "Исходные_чеки" / "44" / "Комиссии" / commission_receipt.name).exists())
            self.assertTrue((salary_root / "Зарплата_44.xlsx").exists())
            self.assertTrue((salary_root / "Зарплата_44_чеки.pdf").exists())

    def test_receipts_are_not_archived_when_current_postprocess_did_not_complete_group(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            archive = Path(tmpdir)
            salary_root = archive / "44" / "Зарплата"
            salary_root.mkdir(parents=True)
            receipt = salary_root / "иван_иванов_15-04-2026_1000-00.pdf"
            receipt.write_text("salary", encoding="utf-8")
            (salary_root / "Зарплата_44.xlsx").write_text("old table", encoding="utf-8")
            (salary_root / "Зарплата_44_чеки.pdf").write_text("old merged", encoding="utf-8")

            moved = sorting_receipt_archive.archive_completed_receipts(archive, set())

            self.assertEqual(moved, [])
            self.assertTrue(receipt.exists())

    def test_salary_employee_count_reads_archived_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            archive = Path(tmpdir)
            salary_root = archive / "Исходные_чеки" / "44" / "Зарплата"
            salary_root.mkdir(parents=True)
            (salary_root / "иван_иванов_05-06-2026_1000-00.pdf").write_text("", encoding="utf-8")
            (salary_root / "петр_демофамилияагб_20-06-2026_1200-00.pdf").write_text("", encoding="utf-8")

            count = salary_employee_counts.salary_employee_count(archive, "44", {"2026-06"})

        self.assertEqual(count, 2)

    def test_salary_employee_count_is_zero_when_office_has_no_salary_in_month(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            archive = Path(tmpdir)
            salary_root = archive / "44" / "Зарплата"
            salary_root.mkdir(parents=True)
            (salary_root / "иван_иванов_05-05-2026_1000-00.pdf").write_text("", encoding="utf-8")

            with mock.patch.object(salary_employee_counts.sd, "OFFICE_PEOPLE", {"44": ["Иван Иванов"]}):
                count = salary_employee_counts.salary_employee_count(archive, "44", {"2026-06"})

        self.assertEqual(count, 0)

    def test_generic_salary_builder_creates_columns_by_payment_dates(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            salary_dir = root / "44" / "Зарплата"
            salary_dir.mkdir(parents=True)
            first = salary_dir / "иван_иванов_15-04-2026_1000-00.pdf"
            second = salary_dir / "иван_иванов_16-04-2026_500-00.pdf"
            first.write_text("dummy", encoding="utf-8")
            second.write_text("dummy", encoding="utf-8")

            with mock.patch.object(generic_salary.sd, "OFFICES", ["44"]), \
                 mock.patch.object(generic_salary.sd, "OFFICE_PEOPLE", {"44": ["Иван Иванов"]}), \
                 mock.patch.object(generic_salary.sd, "file_text", return_value="Получатель Иван Иванов"), \
                 mock.patch.object(generic_salary.sd, "bank_payment_recipient", return_value="иван иванов"), \
                 mock.patch.object(generic_salary.sd, "normalize_text", side_effect=lambda value: value.lower()):
                office_data, unresolved = generic_salary.collect_office_data(root)

        self.assertEqual(unresolved, [])
        self.assertEqual(len(office_data["44"]), 2)
        self.assertEqual([row.amount for row in office_data["44"]], [Decimal("1000.00"), Decimal("500.00")])
        columns, matrix = generic_salary.build_employee_matrix(office_data["44"], "44")
        self.assertEqual(columns, ["ФИО", "15-04-2026", "16-04-2026", "Общий итог"])
        self.assertEqual(matrix, [("Иван Иванов", [Decimal("1000.00"), Decimal("500.00"), Decimal("1500.00")])])

    def test_generic_salary_builder_uses_one_column_per_payment_date(self) -> None:
        rows = [
            generic_salary.PaymentRecord("Иван Иванов", "15-05-2026", Decimal("100.00"), "a.pdf"),
            generic_salary.PaymentRecord("Иван Иванов", "15-05-2026", Decimal("200.00"), "b.pdf"),
            generic_salary.PaymentRecord("Иван Иванов", "02-06-2026", Decimal("300.00"), "c.pdf"),
        ]

        columns, matrix = generic_salary.build_employee_matrix(rows, "44")

        self.assertEqual(columns, ["ФИО", "15-05-2026", "02-06-2026", "Общий итог"])
        self.assertEqual(
            matrix,
            [("Иван Иванов", [Decimal("300.00"), Decimal("300.00"), Decimal("600.00")])],
        )

    def test_salary_table_uses_execution_date_from_receipt_instead_of_filename(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "иван_иванов_02-07-2026_1000-00.pdf"
            path.write_text("dummy", encoding="utf-8")
            text = (
                "31.07.2026 31.07.2026\n"
                "ПЛАТЕЖНОЕ ПОРУЧЕНИЕ № 1116 29.07.2026\n"
                "ИСПОЛНЕНО\n31 июля 2026\n"
            )
            with mock.patch.object(generic_salary.sd, "file_text", return_value=text):
                parsed = generic_salary.parse_payment_name(path)

        self.assertEqual(parsed, ("иван иванов", "31-07-2026", Decimal("1000.00")))

    def test_generic_salary_builder_aligns_same_date_in_one_column_for_different_people(self) -> None:
        rows = [
            generic_salary.PaymentRecord("Иван Иванов", "15-05-2026", Decimal("100.00"), "a.pdf"),
            generic_salary.PaymentRecord("Петр Демофамилияагб", "15-05-2026", Decimal("300.00"), "b.pdf"),
            generic_salary.PaymentRecord("Петр Демофамилияагб", "16-05-2026", Decimal("50.00"), "c.pdf"),
        ]

        with mock.patch.object(generic_salary.sd, "OFFICE_PEOPLE", {"44": ["Иван Иванов", "Петр Демофамилияагб"]}):
            columns, matrix = generic_salary.build_employee_matrix(rows, "44")

        self.assertEqual(columns, ["ФИО", "15-05-2026", "16-05-2026", "Общий итог"])
        self.assertEqual(
            matrix,
            [
                ("Иван Иванов", [Decimal("100.00"), None, Decimal("100.00")]),
                ("Петр Демофамилияагб", [Decimal("300.00"), Decimal("50.00"), Decimal("350.00")]),
            ],
        )

    def test_salary_pdf_order_matches_employee_rows_and_keeps_each_person_together(self) -> None:
        rows = [
            generic_salary.PaymentRecord("Петр Демофамилияагб", "16-05-2026", Decimal("400.00"), "petr-2.pdf"),
            generic_salary.PaymentRecord("Иван Иванов", "20-05-2026", Decimal("300.00"), "ivan-3.pdf"),
            generic_salary.PaymentRecord("Петр Демофамилияагб", "15-05-2026", Decimal("200.00"), "petr-1.pdf"),
            generic_salary.PaymentRecord("Иван Иванов", "01-05-2026", Decimal("100.00"), "ivan-1.pdf"),
            generic_salary.PaymentRecord("Иван Иванов", "15-05-2026", Decimal("250.00"), "ivan-2.pdf"),
        ]

        with mock.patch.object(generic_salary.sd, "OFFICE_PEOPLE", {"44": ["Иван Иванов", "Петр Демофамилияагб"]}):
            ordered = generic_salary.ordered_payment_records(rows, "44")

        self.assertEqual(
            [row.source_name for row in ordered],
            ["ivan-1.pdf", "ivan-2.pdf", "ivan-3.pdf", "petr-1.pdf", "petr-2.pdf"],
        )

    def test_salary_outputs_use_the_same_ordered_records_for_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            salary_root = root / "44" / "Зарплата"
            salary_root.mkdir(parents=True)
            first = salary_root / "first.pdf"
            second = salary_root / "second.pdf"
            first.write_text("dummy", encoding="utf-8")
            second.write_text("dummy", encoding="utf-8")
            rows = [
                generic_salary.PaymentRecord("Иван Иванов", "02-05-2026", Decimal("200.00"), second.name),
                generic_salary.PaymentRecord("Иван Иванов", "01-05-2026", Decimal("100.00"), first.name),
            ]

            with mock.patch.object(generic_salary, "write_xlsx", side_effect=lambda path, _: path.touch()), \
                 mock.patch.object(generic_salary.pdf_merge_runtime, "merge_ordered_pdfs", side_effect=lambda _, path: path.touch()) as merge:
                generic_salary.write_office_outputs(
                    root,
                    "44",
                    rows,
                    settings=generic_salary.SalaryTableSettings(),
                )

        self.assertEqual(merge.call_args.args[0], [first, second])

    def test_commission_outputs_use_the_exact_table_row_order_for_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            first = root / "b.pdf"
            second = root / "a.pdf"
            first.write_text("dummy", encoding="utf-8")
            second.write_text("dummy", encoding="utf-8")
            rows = [("02.05.2026", 200.0, first.name), ("01.05.2026", 100.0, second.name)]

            with mock.patch.object(generic_commission, "build_workbook_xlsx"), \
                 mock.patch.object(generic_commission.pdf_merge_runtime, "merge_ordered_pdfs") as merge:
                generic_commission.write_outputs(root, "Комиссии_44.xlsx", rows)

        self.assertEqual(merge.call_args.args[0], [first, second])

    def test_generated_summary_pdfs_are_not_collected_again(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            commission_summary = root / "Комиссии_44_чеки.pdf"
            commission_summary.write_text("dummy", encoding="utf-8")
            with mock.patch.object(generic_commission.sd, "file_text", return_value="01.05.2026 100-00"):
                commission_rows = generic_commission.collect_rows(root)

            salary_root = root / "44" / "Зарплата"
            salary_root.mkdir(parents=True)
            (salary_root / "Зарплата_44_чеки.pdf").write_text("dummy", encoding="utf-8")
            with mock.patch.object(generic_salary.sd, "OFFICES", ["44"]), \
                 mock.patch.object(generic_salary.sd, "OFFICE_PEOPLE", {"44": ["Иван Иванов"]}), \
                 mock.patch.object(generic_salary.sd, "file_text", return_value="Получатель Иван Иванов"):
                salary_rows, unresolved = generic_salary.collect_office_data(root)

        self.assertEqual(commission_rows, [])
        self.assertEqual(salary_rows, {})
        self.assertEqual(unresolved, [])

    def test_generic_salary_sheet_writes_payment_and_employee_count(self) -> None:
        rows = [
            generic_salary.PaymentRecord("Иван Иванов", "15-05-2026", Decimal("100.00"), "a.pdf"),
            generic_salary.PaymentRecord("Иван Иванов", "30-05-2026", Decimal("300.00"), "b.pdf"),
        ]

        with mock.patch.object(generic_salary.sd, "OFFICE_PEOPLE", {"44": ["Иван Иванов"]}):
            sheet = generic_salary.build_sheet_for_office("44", rows)

        self.assertIn("2 строк выплат, 1 сотрудников", sheet)
        self.assertIn('row r="4"', sheet)

    def test_legacy_company_salary_sheets_write_employee_count_same_way(self) -> None:
        rows = {
            "Иван Иванов": {
                "Аванс": Decimal("100.00"),
                "Заработная плата": Decimal("300.00"),
                "Отпуск/увольнение": Decimal("0.00"),
            }
        }

        with mock.patch.object(demo_a_salary.sd, "OFFICE_PEOPLE", {"76": ["Иван Иванов"], "84": ["Иван Иванов"]}):
            demo_a_sheet = demo_a_salary.build_sheet_for_office("76", rows)
            demo_b_sheet = demo_b_salary.build_sheet_for_office("84", rows)

        self.assertIn("1 сотрудников", demo_a_sheet)
        self.assertIn("1 сотрудников", demo_b_sheet)
        self.assertIn('row r="4"', demo_a_sheet)
        self.assertIn('row r="4"', demo_b_sheet)

    def test_generic_tax_builder_does_not_fallback_to_rules_without_archive(self) -> None:
        with mock.patch.object(generic_tax.base.sd, "OFFICE_PEOPLE", {"44": ["Иван Иванов", "Петр Демофамилияагб"]}):
            with self.assertRaisesRegex(ValueError, "архива"):
                generic_tax.office_employee_rows("44")

    def test_generic_tax_builder_uses_all_archive_salary_recipients(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_root = Path(tmpdir)
            tax_dir = archive_root / "44" / "Ндфл и Взносы"
            salary_dir = archive_root / "44" / "Зарплата"
            tax_dir.mkdir(parents=True)
            salary_dir.mkdir(parents=True)
            (salary_dir / "иван_иванов_05-06-2026_1000-00.pdf").write_text("", encoding="utf-8")
            (salary_dir / "петр_демофамилияагб_10-06-2026_1200-00.pdf").write_text("", encoding="utf-8")
            (salary_dir / "петр_демофамилияагб_20-06-2026_300-00.pdf").write_text("", encoding="utf-8")
            (salary_dir / "май_сотрудник_15-05-2026_900-00.pdf").write_text("", encoding="utf-8")

            with mock.patch.object(generic_tax.base.sd, "OFFICE_PEOPLE", {"44": ["Только из правил"]}):
                rows = generic_tax.office_employee_rows("44", tax_dir, [("30.06.2026", 1000.0, "налог.pdf")])

        self.assertEqual(rows, [("44", 3)])

    def test_generic_insurance_builder_does_not_fallback_to_rules_without_archive(self) -> None:
        with mock.patch.object(generic_insurance.base.sd, "OFFICE_PEOPLE", {"44": ["Иван Иванов"]}):
            with self.assertRaisesRegex(ValueError, "архива"):
                generic_insurance.office_employee_rows("44")

    def test_generic_insurance_builder_uses_all_archive_salary_recipients(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_root = Path(tmpdir)
            insurance_dir = archive_root / "44" / "Ндфл и Взносы"
            salary_dir = archive_root / "44" / "Зарплата"
            insurance_dir.mkdir(parents=True)
            salary_dir.mkdir(parents=True)
            (salary_dir / "иван_иванов_05-06-2026_1000-00.pdf").write_text("", encoding="utf-8")
            (salary_dir / "петр_демофамилияагб_10-06-2026_1200-00.pdf").write_text("", encoding="utf-8")
            (salary_dir / "май_сотрудник_15-05-2026_900-00.pdf").write_text("", encoding="utf-8")

            with mock.patch.object(generic_insurance.base.sd, "OFFICE_PEOPLE", {"44": ["Только из правил"]}):
                rows = generic_insurance.office_employee_rows("44", insurance_dir, [("30.06.2026", 1000.0, "взносы.pdf")])

        self.assertEqual(rows, [("44", 3)])

    def test_demo_a_tax_and_insurance_use_unique_salary_recipients_for_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            archive = Path(tmpdir)
            tax_dir = archive / "109" / "Ндфл и Взносы"
            tax_dir.mkdir(parents=True)
            salary_files = {
                "76": [
                    "иван_иванов_05-07-2026_1000-00.pdf",
                    "иван_иванов_20-07-2026_2000-00.pdf",
                    "петр_демофамилияагб_20-07-2026_3000-00.pdf",
                ],
                "93": ["сидор_сидоров_10-07-2026_1000-00.pdf"],
                "102": ["анна_аннова_11-07-2026_1000-00.pdf"],
                "109": [
                    "мария_демофамилияавоа_12-07-2026_1000-00.pdf",
                    "старый_сотрудник_12-06-2026_1000-00.pdf",
                ],
            }
            people = {
                "76": ["Иван Иванов", "Петр Демофамилияагб", "Лишний Из Правил"],
                "93": ["Сидор Сидоров", "Лишний Из Правил"],
                "94": ["Лишний Из Правил"],
                "102": ["Анна Аннова", "Лишний Из Правил"],
                "109": ["Мария Демофамилияавоа", "Старый Сотрудник", "Лишний Из Правил"],
            }
            for office, names in salary_files.items():
                salary_dir = archive / office / "Зарплата"
                salary_dir.mkdir(parents=True)
                for name in names:
                    (salary_dir / name).write_text("", encoding="utf-8")

            rows = [("31.07.2026", 1000.0, "платеж.pdf")]
            with mock.patch.object(demo_a_tax.sd, "OFFICE_PEOPLE", people):
                tax_counts = demo_a_tax.office_employee_rows(tax_dir, rows)
                insurance_counts = demo_a_insurance.office_employee_rows(tax_dir, rows)

        expected = [("76", 2), ("93", 1), ("94", 0), ("102", 1), ("109", 2)]
        self.assertEqual(tax_counts, expected)
        self.assertEqual(insurance_counts, expected)

    def test_demo_b_tax_and_insurance_use_unique_salary_recipients_for_month(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            archive = Path(tmpdir)
            tax_dir = archive / "98" / "Ндфл и Взносы"
            tax_dir.mkdir(parents=True)
            salary_files = {
                "84": [
                    "иван_иванов_05-07-2026_1000-00.pdf",
                    "иван_иванов_20-07-2026_2000-00.pdf",
                ],
                "98": [
                    "петр_демофамилияагб_10-07-2026_1000-00.pdf",
                    "анна_аннова_20-07-2026_1000-00.pdf",
                ],
            }
            people = {
                "84": ["Иван Иванов", "Лишний Из Правил"],
                "98": ["Петр Демофамилияагб", "Анна Аннова", "Лишний Из Правил"],
                "99": ["Лишний Из Правил"],
            }
            for office, names in salary_files.items():
                salary_dir = archive / office / "Зарплата"
                salary_dir.mkdir(parents=True)
                for name in names:
                    (salary_dir / name).write_text("", encoding="utf-8")

            rows = [("31.07.2026", 1000.0, "платеж.pdf")]
            with mock.patch.object(demo_b_tax.base.sd, "OFFICE_PEOPLE", people):
                tax_counts = demo_b_tax.office_employee_rows(tax_dir, rows)
                insurance_counts = demo_b_insurance.office_employee_rows(tax_dir, rows)

        expected = [("84", 1), ("98", 2), ("99", 0)]
        self.assertEqual(tax_counts, expected)
        self.assertEqual(insurance_counts, expected)

    def test_build_company_outputs_respects_disabled_tax_and_insurance_excel_rule(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_root = Path(tmpdir)
            tax_dir = archive_root / "44" / "Ндфл и Взносы"
            tax_dir.mkdir(parents=True)
            (tax_dir / "налог_10-04-2026_без_номера_188582-38.pdf").write_text("dummy", encoding="utf-8")
            rules = self.write_rules(archive_root, "# no tax excel")

            with mock.patch.dict("os.environ", {"SORTING_RULES_FILE": str(rules)}), \
                 mock.patch.object(run_sorting_pipeline, "run_module") as run_module:
                run_sorting_pipeline.build_company_outputs(archive_root)

        invocations = [(call.args[0].__name__, call.args[1]) for call in run_module.call_args_list]
        self.assertFalse(any(name in {"build_tax_distribution_generic", "build_insurance_distribution_generic"} for name, _ in invocations))

    def test_build_company_outputs_runs_tax_and_insurance_when_rule_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_root = Path(tmpdir)
            tax_dir = archive_root / "44" / "Ндфл и Взносы"
            tax_dir.mkdir(parents=True)
            (tax_dir / "налог_10-04-2026_без_номера_188582-38.pdf").write_text("dummy", encoding="utf-8")
            rules = self.write_rules(archive_root, sorting_postprocess_settings.TAX_EXCEL_RULE)

            with mock.patch.dict("os.environ", {"SORTING_RULES_FILE": str(rules)}), \
                 mock.patch.object(run_sorting_pipeline, "run_module") as run_module:
                run_sorting_pipeline.build_company_outputs(archive_root)

        invocations = [(call.args[0].__name__, call.args[1]) for call in run_module.call_args_list]
        self.assertTrue(any(name == "build_tax_distribution_generic" for name, _ in invocations))
        self.assertTrue(any(name == "build_insurance_distribution_generic" for name, _ in invocations))

    def test_company_tax_outputs_use_fixed_company_tax_offices(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_root = Path(tmpdir)
            demo_a_tax_dir = archive_root / "109" / "Ндфл и Взносы"
            demo_b_tax_dir = archive_root / "98" / "Ндфл и Взносы"
            other_demo_a_tax_dir = archive_root / "76" / "Ндфл и Взносы"
            other_demo_b_tax_dir = archive_root / "84" / "Ндфл и Взносы"
            demo_a_tax_dir.mkdir(parents=True)
            demo_b_tax_dir.mkdir(parents=True)
            other_demo_a_tax_dir.mkdir(parents=True)
            other_demo_b_tax_dir.mkdir(parents=True)
            (demo_a_tax_dir / "налог_10-04-2026_без_номера_1000-00.pdf").write_text("dummy", encoding="utf-8")
            (demo_b_tax_dir / "взносы_10-04-2026_без_номера_2000-00.pdf").write_text("dummy", encoding="utf-8")
            (other_demo_a_tax_dir / "налог_10-04-2026_без_номера_3000-00.pdf").write_text("dummy", encoding="utf-8")
            (other_demo_b_tax_dir / "взносы_10-04-2026_без_номера_4000-00.pdf").write_text("dummy", encoding="utf-8")
            rules = self.write_rules(archive_root, sorting_postprocess_settings.TAX_EXCEL_RULE)

            with mock.patch.dict("os.environ", {"SORTING_RULES_FILE": str(rules)}), \
                 mock.patch.object(run_sorting_pipeline, "run_module") as run_module:
                run_sorting_pipeline.build_company_outputs(archive_root)

        invocations = [(call.args[0].__name__, call.args[1]) for call in run_module.call_args_list]
        self.assertTrue(any(name == "build_tax_distribution" and str(demo_a_tax_dir) in argv for name, argv in invocations))
        self.assertTrue(any(name == "build_insurance_distribution" and str(demo_a_tax_dir) in argv for name, argv in invocations))
        self.assertTrue(any(name == "build_tax_distribution_demo_b" and str(demo_b_tax_dir) in argv for name, argv in invocations))
        self.assertTrue(any(name == "build_insurance_distribution_demo_b" and str(demo_b_tax_dir) in argv for name, argv in invocations))
        self.assertFalse(any(str(other_demo_a_tax_dir) in argv for _, argv in invocations))
        self.assertFalse(any(str(other_demo_b_tax_dir) in argv for _, argv in invocations))

    def test_build_company_outputs_respects_disabled_salary_excel_rule(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_root = Path(tmpdir)
            salary_dir = archive_root / "44" / "Зарплата"
            salary_dir.mkdir(parents=True)
            (salary_dir / "иван_иванов_15-04-2026_1000-00.pdf").write_text("dummy", encoding="utf-8")
            rules = self.write_rules(archive_root, "# no salary excel")

            with mock.patch.dict("os.environ", {"SORTING_RULES_FILE": str(rules)}), \
                 mock.patch.object(run_sorting_pipeline, "run_module") as run_module:
                run_sorting_pipeline.build_company_outputs(archive_root)

        invocations = [(call.args[0].__name__, call.args[1]) for call in run_module.call_args_list]
        self.assertFalse(any(name == "build_salary_tables" for name, _ in invocations))

    def test_postprocess_runner_is_blocked_while_manual_review_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_root = Path(tmpdir)
            manual_dir = archive_root / "Требует_ручной_проверки"
            manual_dir.mkdir(parents=True)
            (manual_dir / "problem.pdf").write_text("dummy", encoding="utf-8")

            with mock.patch.object(run_sorting_pipeline, "build_company_outputs") as build_outputs:
                with self.assertRaisesRegex(RuntimeError, "ручной проверке осталось файлов: 1"):
                    run_sorting_pipeline.run_deferred_postprocess(archive_root)

        build_outputs.assert_not_called()

    def test_excluded_salary_duplicate_does_not_block_postprocess(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_root = Path(tmpdir)
            excluded = archive_root / "Требует_ручной_проверки" / "Исключенные_повторы"
            excluded.mkdir(parents=True)
            (excluded / "duplicate.pdf").write_text("dummy", encoding="utf-8")

            self.assertEqual(run_sorting_pipeline.pending_manual_review_count(archive_root), 0)
            self.assertFalse(run_sorting_pipeline.should_defer_postprocess(archive_root))

    def test_postprocess_runner_executes_when_manual_review_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_root = Path(tmpdir)
            manual_dir = archive_root / "Требует_ручной_проверки"
            manual_dir.mkdir(parents=True)
            (manual_dir / "_report.txt").write_text("report", encoding="utf-8")

            with mock.patch.object(run_sorting_pipeline, "build_company_outputs") as build_outputs, \
                 mock.patch.object(run_sorting_pipeline.sorting_windows_delivery, "create_windows_delivery_zip", return_value=archive_root / "archive_windows.zip"):
                run_sorting_pipeline.run_deferred_postprocess(archive_root)

        build_outputs.assert_called_once_with(archive_root)

    def test_pipeline_main_runs_postprocess_when_manual_review_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            output_dir = Path(tmpdir) / "output"
            archive_root = output_dir / "Архив"
            source_dir.mkdir()
            output_dir.mkdir()

            def fake_run_module(module, argv):
                archive_root.mkdir(exist_ok=True)

            with mock.patch.object(run_sorting_pipeline, "run_module", side_effect=fake_run_module), \
                 mock.patch.object(run_sorting_pipeline, "build_company_outputs") as build_outputs, \
                 mock.patch.object(run_sorting_pipeline.sorting_windows_delivery, "create_windows_delivery_zip", return_value=output_dir / "Архив_windows.zip"):
                code = run_sorting_pipeline.main(
                    ["--source", str(source_dir), "--output", str(output_dir), "--archive-name", "Архив"]
                )

        self.assertEqual(code, 0)
        build_outputs.assert_called_once_with(archive_root.resolve())

    def test_finalize_postprocess_blocks_when_manual_review_has_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_root = Path(tmpdir)
            manual_dir = archive_root / "Требует_ручной_проверки"
            manual_dir.mkdir(parents=True)
            (manual_dir / "problem.pdf").write_text("dummy", encoding="utf-8")

            with mock.patch.object(run_sorting_pipeline, "run_deferred_postprocess") as deferred:
                code = finalize_postprocess.main(["--archive-root", str(archive_root)])

        self.assertEqual(code, 2)
        deferred.assert_not_called()

    def test_finalize_postprocess_runs_when_manual_review_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_root = Path(tmpdir)
            manual_dir = archive_root / "Требует_ручной_проверки"
            manual_dir.mkdir(parents=True)
            (manual_dir / "_report.txt").write_text("report", encoding="utf-8")

            with mock.patch.object(run_sorting_pipeline, "run_deferred_postprocess") as deferred:
                code = finalize_postprocess.main(["--archive-root", str(archive_root)])

        self.assertEqual(code, 0)
        deferred.assert_called_once_with(archive_root.resolve())


if __name__ == "__main__":
    unittest.main()
