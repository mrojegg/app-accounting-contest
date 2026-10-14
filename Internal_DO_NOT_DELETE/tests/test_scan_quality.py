from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sorting_extraction as se
from test_extraction_pipeline_integration import runtime_for


def payment(entity: str = "ПРИМЕР") -> str:
    return (
        f"Платежное поручение N 10\n15.08.2026\nООО {entity}\n"
        "Получатель Иванов Иван Иванович\nСумма 12345,67\n"
        "Назначение платежа Выплата заработной платы. НДФЛ удержан.\n"
    )


class ScanQualityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sorting-scan-quality-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / "scan.pdf"
        self.path.write_bytes(b"%PDF-1.4")
        self.runtime = runtime_for(self.root / "cache")
        patches = mock.patch.multiple(
            se, extract_pdf_text_layer=mock.DEFAULT, read_pdftotext_text=mock.DEFAULT,
            read_mutool_text=mock.DEFAULT, read_mdls_text=mock.DEFAULT, _run_command=mock.DEFAULT,
        )
        for method in patches.start().values():
            method.return_value = ""
        self.addCleanup(patches.stop)

    def read(self, direct: str, ocr: str):
        with mock.patch.object(se, "read_pymupdf_text", return_value=direct), \
             mock.patch.object(se, "read_pdf_native_ocr_text", return_value=ocr) as native:
            result = se.file_text(self.path, runtime=self.runtime)
        return result, native

    def test_complete_text_keeps_fast_path_for_both_companies(self):
        for entity in ["ПРИМЕР", "ОБРАЗЕЦ"]:
            with self.subTest(entity=entity):
                self.runtime.text_cache.clear()
                with mock.patch.object(se, "load_disk_cached_text", return_value=None):
                    result, native = self.read(payment(entity), "OCR MUST NOT RUN")
                self.assertIn(entity, result)
                native.assert_not_called()
                self.assertNotIn(self.path, self.runtime.manual_review_heavy_ocr_paths)

    def test_nonempty_broken_layer_does_not_stop_ocr(self):
        result, native = self.read("\ufffd" * 100, payment())
        native.assert_called_once()
        self.assertIn("Иванов Иван Иванович", result)
        self.assertNotIn("\ufffd", result)

    def test_short_vector_document_does_not_invoke_scan_ocr(self):
        import fitz
        self.path.unlink()
        with fitz.open() as document:
            document.new_page().insert_text((40, 80), "Payment 1")
            document.save(self.path)
        with mock.patch.object(se, "read_pdf_native_ocr_text", side_effect=AssertionError("unnecessary OCR")):
            self.assertEqual(se.read_pdf_text(self.path, runtime=self.runtime), "Payment 1")

    def test_long_payment_header_missing_fields_does_not_stop_ocr(self):
        broken = "Платежное поручение\nООО ПРИМЕР\n" + "Банковские реквизиты\n" * 25
        result, native = self.read(broken, payment())
        native.assert_called_once()
        self.assertIn("12345,67", result)
        self.assertNotIn("Банковские реквизиты", result)

    def test_damaged_amount_does_not_pass_the_text_layer_quality_check(self):
        result, native = self.read(payment().replace("12345,67", "12345,6łł"), payment())
        native.assert_called_once()
        self.assertIn("12345,67", result)
        self.assertNotIn("6łł", result)

    def test_failed_ocr_is_manual_and_not_disk_cached(self):
        with mock.patch.dict(os.environ, {"SORTING_ALLOW_HEAVY_OCR": "0"}):
            _, native = self.read("Платежное поручение\nООО ПРИМЕР", "")
        native.assert_called_once()
        self.assertIn(self.path, self.runtime.manual_review_heavy_ocr_paths)
        self.assertIsNone(se.load_disk_cached_text(self.path, runtime=self.runtime))

    def test_successful_ocr_is_cached_and_original_is_unchanged(self):
        digest = hashlib.sha256(self.path.read_bytes()).hexdigest()
        result, _ = self.read("\ufffd" * 100, payment())
        self.assertEqual(se.load_disk_cached_text(self.path, runtime=self.runtime), result)
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), digest)

    def test_failed_heavy_ocr_keeps_manual_flag(self):
        with mock.patch.dict(os.environ, {"SORTING_ALLOW_HEAVY_OCR": "1"}), \
             mock.patch.object(se, "read_pymupdf_text", return_value=""), \
             mock.patch.object(se, "read_pdf_native_ocr_text", return_value=""), \
             mock.patch.object(se, "read_tesseract_text", return_value=""), \
             mock.patch.object(se, "read_ocrmypdf_text", return_value=""):
            se.read_pdf_text(self.path, runtime=self.runtime)
        self.assertIn(self.path, self.runtime.manual_review_heavy_ocr_paths)

    def test_native_pass_requests_all_pages_and_forces_quality_ocr(self):
        with mock.patch.object(se, "available_ocr_binary", return_value=Path("helper")), \
             mock.patch.object(se.platform_support, "pdf_page_count", return_value=6), \
             mock.patch.object(se, "_run_command", return_value=payment()) as run:
            se.read_pdf_native_ocr_text(self.path, runtime=self.runtime)
        self.assertEqual(run.call_args.args[0], ["helper", str(self.path), "6", "--force-ocr", "--quality-json"])
        self.assertLessEqual(run.call_args.kwargs["timeout"], 120)

    def test_mixed_pdf_requests_ocr_even_when_other_pages_are_readable(self):
        with mock.patch.object(se, "pdf_has_unreadable_image_pages", return_value=True):
            result, native = self.read(payment(), payment("ОБРАЗЕЦ"))
        native.assert_called_once()
        self.assertIn("ОБРАЗЕЦ", result)
        self.assertNotIn("ПРИМЕР", result)

    def test_native_incomplete_page_is_manual_even_with_other_good_pages(self):
        import json
        text = se.decode_native_ocr_result(
            json.dumps({"text": payment(), "incomplete_pages": [6]}), self.path, runtime=self.runtime,
        )
        self.assertIn("12345,67", text)
        self.assertIn(self.path, self.runtime.manual_review_heavy_ocr_paths)

    def test_malformed_native_quality_report_is_not_used_as_document_text(self):
        self.assertEqual(se.decode_native_ocr_result('{"text":', self.path, runtime=self.runtime), "")
        self.assertIn(self.path, self.runtime.manual_review_heavy_ocr_paths)


@unittest.skipUnless(os.environ.get("SORTING_TEST_OCR"), "requires built macOS Vision helper")
class NativeScanQualityTests(unittest.TestCase):
    def test_mixed_six_page_pdf_reads_last_scan(self):
        import fitz
        with tempfile.TemporaryDirectory(prefix="sorting-mixed-ocr-") as tmp:
            root = Path(tmp)
            path = root / "mixed.pdf"
            font = fitz.Font(fontfile="/System/Library/Fonts/Supplemental/Arial.ttf")
            with fitz.open() as document:
                for _ in range(5):
                    page = document.new_page()
                    page.insert_font(fontname="fixture", fontbuffer=font.buffer)
                    page.insert_text((40, 80), payment(), fontname="fixture", fontsize=12)
                with fitz.open() as source:
                    page = source.new_page()
                    page.insert_font(fontname="fixture", fontbuffer=font.buffer)
                    page.insert_text((40, 80), payment().replace("15.08.2026", "29.08.2026")
                                     .replace("Иванов Иван Иванович", "Демофамилияагб Петр Демофамилияагбич"),
                                     fontname="fixture", fontsize=12)
                    last = document.new_page()
                    last.insert_image(last.rect, stream=page.get_pixmap(matrix=fitz.Matrix(2, 2)).tobytes("png"))
                document.save(path)
            runtime = runtime_for(root / "cache")
            runtime.ocr_binary_candidates = [Path(os.environ["SORTING_TEST_OCR"])]
            text = se.file_text(path, runtime=runtime)
            self.assertIn("29.08.2026", text)
            self.assertIn("Демофамилияагб Петр Демофамилияагбич", text)
            self.assertNotIn(path, runtime.manual_review_heavy_ocr_paths)

    def test_degraded_scans_and_bad_hidden_layers_for_both_companies(self):
        import fitz
        with tempfile.TemporaryDirectory(prefix="sorting-real-ocr-") as tmp:
            root = Path(tmp)
            for entity in ["ПРИМЕР", "ОБРАЗЕЦ"]:
                for degraded in [False, True]:
                    with self.subTest(entity=entity, degraded=degraded):
                        path = root / f"{entity}-{degraded}.pdf"
                        with fitz.open() as source:
                            page = source.new_page()
                            font = Path("/System/Library/Fonts/Supplemental/Arial.ttf")
                            fontbuffer = fitz.Font(fontfile=str(font)).buffer if font.exists() else fitz.Font("cjk").buffer
                            page.insert_font(fontname="fixture", fontbuffer=fontbuffer)
                            page.insert_text((40, 80), payment(entity), fontname="fixture", fontsize=12,
                                             color=(0.55, 0.55, 0.55) if degraded else (0, 0, 0))
                            if degraded:
                                page.draw_line((35, 64), (430, 72), color=(0.75, 0.75, 0.75), width=1)
                            image = page.get_pixmap(matrix=fitz.Matrix(2, 2)).tobytes("png")
                            with fitz.open() as scanned:
                                target = scanned.new_page(width=page.rect.width, height=page.rect.height)
                                target.insert_image(target.rect, stream=image)
                                if degraded:
                                    target.insert_font(fontname="fixture", fontbuffer=fontbuffer)
                                    target.insert_text((40, 40), "Платежное поручение\nООО " + entity + "\n" +
                                                       "Банковские реквизиты " * 10,
                                                       fontname="fixture", fontsize=8, render_mode=3)
                                scanned.save(path)
                        digest = hashlib.sha256(path.read_bytes()).hexdigest()
                        runtime = runtime_for(root / "cache")
                        runtime.ocr_binary_candidates = [Path(os.environ["SORTING_TEST_OCR"])]
                        start = time.monotonic()
                        text = se.file_text(path, runtime=runtime)
                        self.assertIn(entity.lower(), text.lower())
                        self.assertIn("Иванов Иван Иванович", text)
                        self.assertIn("15.08.2026", text)
                        self.assertIn("12345,67", text)
                        self.assertNotIn(path, runtime.manual_review_heavy_ocr_paths)
                        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
                        print(f"Scan quality {entity}, degraded={degraded}: {time.monotonic() - start:.3f}s")

    def test_scanned_salary_pipeline_for_both_companies(self):
        import fitz
        from test_full_workflow_regression import FullWorkflowRegressionTests
        workflow = FullWorkflowRegressionTests("test_both_companies_salary_commissions_taxes_and_repeat")
        workflow.setUp()
        self.addCleanup(workflow.doCleanups)
        workflow.env["SORTING_OCR_BINARY"] = os.environ["SORTING_TEST_OCR"]
        for office in ["98", "109"]:
            entity, person = workflow.people[office]
            for day, amount in [("15", "1000-00"), ("29", "1500-00")]:
                path = workflow.pdf(f"scan-{office}-{day}.pdf", entity, person, f"{day}.08.2026", amount)
                with fitz.open(path) as original, fitz.open() as scanned:
                    page = scanned.new_page(width=original[0].rect.width, height=original[0].rect.height)
                    page.insert_image(page.rect, stream=original[0].get_pixmap(matrix=fitz.Matrix(3, 3)).tobytes("png"))
                    staged = path.with_suffix(".raster.pdf")
                    scanned.save(staged)
                staged.replace(path)
        digests = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in workflow.source.iterdir()}
        workflow.pipeline()
        for office in ["98", "109"]:
            directory = workflow.archive / office / "Зарплата"
            rows = workflow.sheet(directory / f"Зарплата_{office}.xlsx")
            self.assertEqual(next(row for row in rows if row[0] == "ФИО"),
                             ["ФИО", "15-08-2026", "29-08-2026", "Общий итог"])
            self.assertEqual(next(row for row in rows if row[0] == workflow.people[office][1])[1:],
                             [1000, 1500, 2500])
            self.assertIn("1 сотрудников", rows[1][0])
            with fitz.open(directory / f"Зарплата_{office}_чеки.pdf") as merged:
                self.assertEqual(merged.page_count, 2)
        self.assertEqual(digests, {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                                  for path in workflow.source.iterdir()})


if __name__ == "__main__":
    unittest.main()
