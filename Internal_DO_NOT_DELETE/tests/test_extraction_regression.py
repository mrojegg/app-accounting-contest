from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock
import os

import sys


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import sorting_extraction as se
from sorting_document_profile import build_document_profile
from sorting_extraction_fields import extract_fields


def runtime_for(cache_root: Path) -> se.ExtractionRuntime:
    return se.ExtractionRuntime(
        text_cache={},
        manual_review_heavy_ocr_paths=set(),
        command_exists_cache={},
        ocr_binary_candidates=[],
        swift_pdf_splitter=Path("missing.swift"),
        cache_root=cache_root,
        text_cache_version="test",
        informative_text_patterns=["счет", "получатель"],
        normalize_text=lambda value: value.lower(),
    )


class ExtractionRegressionTests(unittest.TestCase):
    def test_repair_ocr_line_fixes_mixed_script_noise(self) -> None:
        self.assertEqual(se.repair_ocr_line("CЧET AO ИCKPATEЛEKOM"), "СЧЕТ АО ИСКРАТЕЛЕКОМ")

    def test_payment_text_is_enriched_with_structured_fields(self) -> None:
        runtime = runtime_for(Path("/tmp/cache"))
        raw = (
            "ПЛАТЕЖНОЕ ПОРУЧЕНИЕ N 224\n"
            "Сч. N 40817000000000000001 Тестова Мария Александровна Вид оп. 01\n"
            "Рез. поле Выплата заработной платы. НДФЛ удержан. НДС не облагается Назначение платежа\n"
        )

        text = se.enrich_payment_document_text(se.normalize_extracted_text(raw), runtime=runtime)

        self.assertIn("получатель тестова мария александровна", text.lower())
        self.assertIn("Назначение платежа выплата заработной платы", text)

    def test_pdf_uses_disk_cache_across_runtime_instances(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            path = root / "scan.pdf"
            path.write_bytes(b"%PDF-1.4")
            runtime = runtime_for(root / "cache")

            with mock.patch.object(se, "read_pdf_text", return_value="OCR text") as read_pdf_text:
                text = se.file_text(path, runtime=runtime)

            self.assertEqual(text, "OCR text")
            read_pdf_text.assert_called_once()

            fresh_runtime = runtime_for(root / "cache")
            with mock.patch.object(se, "read_pdf_text", side_effect=AssertionError("must use disk cache")):
                cached_text = se.file_text(path, runtime=fresh_runtime)

            self.assertEqual(cached_text, "OCR text")

    def test_plain_text_uses_memory_cache_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            path = root / "note.txt"
            path.write_text("actual text", encoding="utf-8")
            runtime = runtime_for(root / "cache")
            first = se.file_text(path, runtime=runtime)

            with mock.patch.object(Path, "read_text", side_effect=AssertionError("must not reread")):
                second = se.file_text(path, runtime=runtime)

            self.assertEqual(first, "actual text")
            self.assertEqual(second, "actual text")

    def test_plain_text_payment_is_normalized_and_enriched(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            path = root / "payment.txt"
            path.write_text(
                "ПЛАТЕЖНОЕ ПОРУЧЕНИЕ N 224\n"
                "Cч. N 40817000000000000001 Тестова Мария Александровна Вид оп. 01\n"
                "Рез. поле Выплата заработной платы. НДФЛ удержан. НДС не облагается Назначение платежа\n",
                encoding="utf-8",
            )
            runtime = runtime_for(root / "cache")

            text = se.file_text(path, runtime=runtime)

            self.assertIn("получатель тестова мария александровна", text.lower())

    def test_heavy_ocr_gate_skips_second_pass_for_readable_payment(self) -> None:
        runtime = runtime_for(Path("/tmp/cache"))
        text = (
            "Платежное поручение\n"
            "ООО ПРИМЕР\n"
            "Получатель Тестова Мария Александровна\n"
            "Назначение платежа Выплата заработной платы\n"
            "Сумма 16190,71\n"
        )

        self.assertFalse(se.should_run_heavy_ocr(text, 180, runtime=runtime))

    def test_heavy_ocr_gate_runs_when_payment_fields_are_missing(self) -> None:
        runtime = runtime_for(Path("/tmp/cache"))
        text = "Платежное поручение\nООО ПРИМЕР\n"

        self.assertTrue(se.should_run_heavy_ocr(text, 180, runtime=runtime))

    def test_pdf_skips_heavy_ocr_when_gate_says_text_is_enough(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            path = root / "text.pdf"
            path.write_bytes(b"%PDF-1.4")
            runtime = runtime_for(root / "cache")
            readable = (
                "Платежное поручение\n"
                "ООО ПРИМЕР\n"
                "Получатель Тестова Мария Александровна\n"
                "Назначение платежа Выплата заработной платы\n"
                "Сумма 16190,71\n"
            )

            with mock.patch.object(se, "read_pymupdf_text", return_value=readable), \
                 mock.patch.object(se, "extract_pdf_text_layer", return_value=""), \
                 mock.patch.object(se, "read_pdftotext_text", return_value=""), \
                 mock.patch.object(se, "read_mutool_text", return_value=""), \
                 mock.patch.object(se, "read_mdls_text", return_value=""), \
                 mock.patch.object(se, "read_pdf_native_ocr_text", return_value=""), \
                 mock.patch.object(se, "_run_command", side_effect=AssertionError("heavy OCR must not run")):
                text = se.read_pdf_text(path, runtime=runtime)

            self.assertEqual(text, readable.strip())

    def test_disk_cache_helpers_save_load_and_invalidate_by_file_stat(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            path = root / "note.txt"
            path.write_text("actual text", encoding="utf-8")
            runtime = runtime_for(root / "cache")
            cache_path = se.text_cache_path(path, runtime=runtime)

            se.save_disk_cached_text(path, "cached text", runtime=runtime)

            self.assertEqual(se.load_disk_cached_text(path, runtime=runtime), "cached text")
            self.assertTrue(cache_path.exists())

            path.write_text("changed actual text", encoding="utf-8")

            self.assertIsNone(se.load_disk_cached_text(path, runtime=runtime))
            self.assertNotEqual(cache_path, se.text_cache_path(path, runtime=runtime))

    def test_empty_extracted_text_is_not_saved_to_disk_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            path = root / "empty.pdf"
            path.write_bytes(b"%PDF-1.4")
            runtime = runtime_for(root / "cache")
            cache_path = se.text_cache_path(path, runtime=runtime)

            with mock.patch.object(se, "read_pdf_text", return_value=""):
                text = se.file_text(path, runtime=runtime)

            self.assertEqual(text, "")
            self.assertFalse(cache_path.exists())
            self.assertIsNone(se.load_disk_cached_text(path, runtime=runtime))

    def test_pdf_without_text_layer_goes_to_manual_review_before_deep_ocr(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            path = root / "scan.pdf"
            path.write_bytes(b"%PDF-1.4")
            runtime = runtime_for(root / "cache")
            runtime.ocr_binary_candidates = [root / "pdf_ocr_pkg"]
            runtime.ocr_binary_candidates[0].write_text("bin", encoding="utf-8")
            runtime.ocr_binary_candidates[0].chmod(0o755)

            with mock.patch.object(se, "extract_pdf_text_layer", return_value=""), \
                 mock.patch.object(se, "read_pdftotext_text", return_value=""), \
                 mock.patch.object(se, "read_mutool_text", return_value=""), \
                 mock.patch.object(se, "read_mdls_text", return_value=""), \
                 mock.patch.object(se, "read_pdf_native_ocr_text", return_value=""), \
                 mock.patch.object(se, "_run_command", return_value="") as run_command, \
                 mock.patch.object(se, "ocr_via_rendered_image", return_value=""), \
                 mock.patch.object(se, "ocr_pdf_by_pages", return_value=""):
                text = se.read_pdf_text(path, runtime=runtime)

            self.assertEqual(text, "")
            self.assertIn(path, runtime.manual_review_heavy_ocr_paths)
            self.assertFalse(any(str(runtime.ocr_binary_candidates[0]) in " ".join(call.args[0]) for call in run_command.call_args_list))

    def test_pdf_uses_pymupdf_text_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            path = root / "text.pdf"
            path.write_bytes(b"%PDF-1.4")
            runtime = runtime_for(root / "cache")

            readable = "Счет на оплату ООО Дилайн. Получатель Дилайн, ИНН 1234567890. Интернет услуги. Сумма к оплате 12345,67 рублей."
            with mock.patch.object(se, "read_pymupdf_text", return_value=readable), \
                 mock.patch.object(se, "extract_pdf_text_layer", return_value=""), \
                 mock.patch.object(se, "read_pdftotext_text", return_value=""), \
                 mock.patch.object(se, "read_mutool_text", return_value=""):
                text = se.read_pdf_text(path, runtime=runtime)

            self.assertEqual(text, readable)

    def test_available_ocr_binary_prefers_environment_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            env_binary = root / "bundled_pdf_ocr_pkg"
            env_binary.write_text("bin", encoding="utf-8")
            env_binary.chmod(0o755)
            runtime = runtime_for(root / "cache")
            runtime.ocr_binary_candidates = [root / "missing"]

            with mock.patch.dict(os.environ, {"SORTING_OCR_BINARY": str(env_binary)}, clear=False):
                reloaded_runtime = runtime_for(root / "cache")
                self.assertEqual(se.available_ocr_binary(runtime=reloaded_runtime), env_binary)

    def test_xlsx_reads_only_relevant_openxml_parts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "invoice.xlsx"
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("docProps/core.xml", "<coreProperties><title>Счет на оплату</title></coreProperties>")
                archive.writestr("xl/workbook.xml", "<workbook><sheets><sheet name='Лист1'/></sheets></workbook>")
                archive.writestr("xl/sharedStrings.xml", "<sst><si><t>ООО Дилайн</t></si><si><t>Интернет</t></si></sst>")
                archive.writestr("xl/worksheets/sheet1.xml", "<worksheet><sheetData><row><c t='s'><v>0</v></c><c t='s'><v>1</v></c></row></sheetData></worksheet>")
                archive.writestr("xl/theme/theme1.xml", "<theme><t>THEME_NOISE_SHOULD_NOT_BE_READ</t></theme>")

            text = se.read_openxml_text(path, suffix=".xlsx")

            self.assertIn("Счет на оплату", text)
            self.assertIn("ООО Дилайн", text)
            self.assertIn("Интернет", text)
            self.assertNotIn("THEME_NOISE_SHOULD_NOT_BE_READ", text)

    def test_xlsx_skips_oversized_shared_strings_instead_of_loading_everything(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "huge.xlsx"
            large_text = "A" * (se.OPENXML_SHARED_STRINGS_BYTES_LIMIT + 100)
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("xl/sharedStrings.xml", f"<sst><si><t>{large_text}</t></si></sst>")
                archive.writestr("xl/worksheets/sheet1.xml", "<worksheet><sheetData><row><c><v>42</v></c></row></sheetData></worksheet>")

            text = se.read_openxml_text(path, suffix=".xlsx")

            self.assertIn("42", text)
            self.assertLess(len(text), se.OPENXML_TEXT_CHAR_LIMIT + 1)

    def test_binary_container_dump_is_detected(self) -> None:
        dump = ("–œ\x11‡°±\x1a·\x00" * 500) + ("ˇ" * 2000)
        self.assertTrue(se.looks_like_binary_container_dump(dump))

    def test_legacy_document_skips_textutil_binary_dump(self) -> None:
        runtime = runtime_for(Path("/tmp/cache"))
        path = Path("/tmp/fake.xls")

        with mock.patch.object(se, "read_mdls_text", return_value=""), \
             mock.patch.object(se, "read_textutil_text", return_value=("–œ\x11‡°±\x1a·\x00" * 500)), \
             mock.patch.object(se, "read_quicklook_ocr_text", return_value=""), \
             mock.patch.object(se, "_run_command", return_value=("ˇ" * 2000)):
            text = se.read_legacy_document_text(path, runtime=runtime)

        self.assertEqual(text, "")

    def test_extract_legacy_xls_text_reads_utf16_fragments_from_ole_container(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "legacy.xls"
            payload = (
                b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
                + ("Счет на оплату ООО Дилайн Город Москва".encode("utf-16le"))
                + b"\x00\x00\x00\x00"
                + ("Интернет услуги январь 2026".encode("utf-16le"))
            )
            path.write_bytes(payload)

            text = se.extract_legacy_xls_text(path)

            self.assertIn("Счет на оплату", text)
            self.assertIn("ООО Дилайн", text)
            self.assertIn("Интернет услуги январь 2026", text)

    def test_document_profile_detects_pdf_scan_without_text_layer(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "scan.pdf"
            path.write_bytes(b"%PDF-1.4")
            profile = build_document_profile(path, extract_pdf_text_layer=lambda _: "")
            self.assertEqual(profile.kind, "pdf")
            self.assertFalse(profile.has_text_layer)
            self.assertTrue(profile.is_scan_like)

    def test_extract_fields_returns_payment_fields(self) -> None:
        text = (
            "Платежное поручение\n"
            "Сч. N 40817000000000000001 Тестова Мария Александровна Вид оп. 01\n"
            "Рез. поле Выплата заработной платы НДС не облагается Назначение платежа\n"
            "Сумма 16190,71\n"
        )
        fields = extract_fields(text, normalize_text=lambda value: value.lower())
        self.assertEqual(fields.recipient, "тестова мария александровна")
        self.assertIn("выплата заработной платы", fields.purpose or "")
        self.assertEqual(fields.critical_payment_fields_count, 3)

    def test_extraction_gate_decision_skips_heavy_ocr_for_good_text(self) -> None:
        runtime = runtime_for(Path("/tmp/cache"))
        path = Path("/tmp/good.pdf")
        with mock.patch.object(se, "extract_pdf_text_layer", return_value=""):
            decision = se.extraction_gate_decision(
                path,
                "Платежное поручение\nПолучатель Иван Иванов\nНазначение платежа Оплата услуг\nСумма 100,00\n",
                200,
                runtime=runtime,
            )
        self.assertFalse(decision.should_run_heavy_ocr)

    def test_heavy_ocr_candidate_is_marked_for_manual_review(self) -> None:
        runtime = runtime_for(Path("/tmp/cache"))
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "scan.pdf"
            path.write_bytes(b"%PDF-1.4")
            with mock.patch.object(se, "read_pymupdf_text", return_value=""), \
                 mock.patch.object(se, "extract_pdf_text_layer", return_value=""), \
                 mock.patch.object(se, "read_pdftotext_text", return_value=""), \
                 mock.patch.object(se, "read_mutool_text", return_value=""), \
                 mock.patch.object(se, "read_mdls_text", return_value=""), \
                 mock.patch.object(se, "read_pdf_native_ocr_text", return_value=""), \
                 mock.patch.object(se, "_run_command", return_value=""):
                se.read_pdf_text(path, runtime=runtime)
            self.assertIn(path, runtime.manual_review_heavy_ocr_paths)


if __name__ == "__main__":
    unittest.main()
