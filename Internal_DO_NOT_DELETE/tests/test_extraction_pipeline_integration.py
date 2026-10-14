from __future__ import annotations

import tempfile
import unittest
import zlib
import zipfile
import os
from pathlib import Path
from unittest import mock
import sys


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import sorting_extraction as se


def runtime_for(cache_root: Path, *, informative_patterns: list[str] | None = None) -> se.ExtractionRuntime:
    return se.ExtractionRuntime(
        text_cache={},
        manual_review_heavy_ocr_paths=set(),
        command_exists_cache={},
        ocr_binary_candidates=[],
        swift_pdf_splitter=Path("missing.swift"),
        cache_root=cache_root,
        text_cache_version="integration-test",
        informative_text_patterns=informative_patterns or ["счет", "получатель", "дилайн", "интернет"],
        normalize_text=lambda value: value.lower(),
    )


def write_text_layer_pdf(path: Path, text: str) -> None:
    content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("utf-8")
    stream = zlib.compress(content)
    pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >> endobj\n"
        + f"4 0 obj << /Length {len(stream)} /Filter /FlateDecode >> stream\n".encode("ascii")
        + stream
        + b"\nendstream endobj\n"
        b"trailer << /Root 1 0 R >>\n%%EOF"
    )
    path.write_bytes(pdf)


class ExtractionPipelineIntegrationTests(unittest.TestCase):
    def test_legacy_xls_with_good_text_should_not_invoke_ocr(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            path = root / "economical.xls"
            runtime = runtime_for(root / "cache")
            payload = (
                b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
                + "Счет на оплату ООО Дилайн".encode("utf-16le")
                + b"\x00\x00\x00\x00"
                + "Интернет услуги апрель 2026".encode("utf-16le")
            )
            path.write_bytes(payload)

            with mock.patch.object(se, "read_mdls_text", return_value=""), \
                 mock.patch.object(se, "read_textutil_text", return_value=""), \
                 mock.patch.object(se, "read_quicklook_ocr_text", return_value="OCR SHOULD NOT RUN") as quicklook_ocr, \
                 mock.patch.object(se, "_run_command", return_value=""):
                text = se.file_text(path, runtime=runtime)

            self.assertIn("ооо дилайн", text.lower())
            quicklook_ocr.assert_not_called()

    def test_fast_pdf_text_layer_returns_without_ocr(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pdf = root / "fast.pdf"
            write_text_layer_pdf(
                pdf,
                "Счет ООО Дилайн Интернет услуги получатель Дилайн сумма 12345 назначение платежа Интернет за март 2026",
            )
            runtime = runtime_for(root / "cache")

            with mock.patch.object(se, "read_pymupdf_text", return_value=""), \
                 mock.patch.object(se, "read_pdftotext_text", return_value=""), \
                 mock.patch.object(se, "read_mutool_text", return_value=""), \
                 mock.patch.object(se, "read_mdls_text", return_value=""), \
                 mock.patch.object(se, "read_pdf_native_ocr_text", return_value=""), \
                 mock.patch.object(se, "_run_command", side_effect=AssertionError("OCR should not run for fast PDF")):
                text = se.read_pdf_text(pdf, runtime=runtime)

            self.assertIn("счет", text.lower())
            self.assertIn("дилайн", text.lower())

    def test_gated_ocr_skip_stops_before_heavy_ocr_when_native_text_is_good(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pdf = root / "gated.pdf"
            pdf.write_bytes(b"%PDF-1.4")
            runtime = runtime_for(root / "cache")
            readable_text = (
                "Платежное поручение\n"
                "ООО ПРИМЕР\n"
                "Получатель Дилайн Сервис\n"
                "Назначение платежа Интернет услуги март 2026\n"
                "Сумма 17791,67\n"
            )

            with mock.patch.object(se, "read_pymupdf_text", return_value=""), \
                 mock.patch.object(se, "extract_pdf_text_layer", return_value=""), \
                 mock.patch.object(se, "read_pdftotext_text", return_value=""), \
                 mock.patch.object(se, "read_mutool_text", return_value=""), \
                 mock.patch.object(se, "read_mdls_text", return_value=""), \
                 mock.patch.object(se, "read_pdf_native_ocr_text", return_value=readable_text), \
                 mock.patch.object(se, "_run_command", side_effect=AssertionError("Heavy OCR must stay gated off")):
                text = se.read_pdf_text(pdf, runtime=runtime)

            self.assertIn("получатель дилайн сервис", text.lower())
            self.assertIn("интернет услуги", text.lower())

    def test_single_page_bad_pdf_goes_to_manual_review_instead_of_heavy_ocr(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pdf = root / "bad-single-page.pdf"
            pdf.write_bytes(b"%PDF-1.4")
            runtime = runtime_for(root / "cache")
            with mock.patch.object(se, "read_pymupdf_text", return_value=""), \
                 mock.patch.object(se, "extract_pdf_text_layer", return_value=""), \
                 mock.patch.object(se, "read_pdftotext_text", return_value=""), \
                 mock.patch.object(se, "read_mutool_text", return_value=""), \
                 mock.patch.object(se, "read_mdls_text", return_value=""), \
                 mock.patch.object(se, "read_pdf_native_ocr_text", return_value=""), \
                 mock.patch.object(se, "_run_command", return_value=""), \
                 mock.patch.object(se, "ocr_via_rendered_image", side_effect=AssertionError("rendered OCR must not run")), \
                 mock.patch.object(se, "ocr_pdf_by_pages", side_effect=AssertionError("page-by-page OCR must not run")):
                se.read_pdf_text(pdf, runtime=runtime)

            self.assertIn(pdf, runtime.manual_review_heavy_ocr_paths)

    def test_heavy_ocr_path_marks_pdf_for_manual_review_when_text_sources_are_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pdf = root / "scan.pdf"
            pdf.write_bytes(b"%PDF-1.4")
            runtime = runtime_for(root / "cache")

            with mock.patch.object(se, "read_pymupdf_text", return_value=""), \
                 mock.patch.object(se, "extract_pdf_text_layer", return_value=""), \
                 mock.patch.object(se, "read_pdftotext_text", return_value=""), \
                 mock.patch.object(se, "read_mutool_text", return_value=""), \
                 mock.patch.object(se, "read_mdls_text", return_value=""), \
                 mock.patch.object(se, "read_pdf_native_ocr_text", return_value=""), \
                 mock.patch.object(se, "_run_command", return_value="") as run_command:
                text = se.read_pdf_text(pdf, runtime=runtime)

            self.assertEqual(text, "")
            self.assertIn(pdf, runtime.manual_review_heavy_ocr_paths)
            self.assertTrue(all(call.args[0][0] != "strings" or call.args[0][0] == "strings" for call in run_command.call_args_list))

    def test_sorting_ocr_binary_env_override_does_not_run_when_heavy_ocr_is_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pdf = root / "env-heavy.pdf"
            pdf.write_bytes(b"%PDF-1.4")
            runtime = runtime_for(root / "cache")
            env_binary = root / "bundled_pdf_ocr_pkg"
            env_binary.write_text("bin", encoding="utf-8")
            env_binary.chmod(0o755)
            runtime.ocr_binary_candidates = []

            def fake_run(args: list[str], timeout: int = 20) -> str:
                if args and args[0] == str(env_binary):
                    return "Счет ООО Дилайн Интернет услуги за август 2026. Сумма к оплате 1000,00 рублей."
                if args and args[0] == "strings":
                    return ""
                return ""

            with mock.patch.dict(os.environ, {"SORTING_OCR_BINARY": str(env_binary)}, clear=False), \
                 mock.patch.object(se, "read_pymupdf_text", return_value=""), \
                 mock.patch.object(se, "extract_pdf_text_layer", return_value=""), \
                 mock.patch.object(se, "read_pdftotext_text", return_value=""), \
                 mock.patch.object(se, "read_mutool_text", return_value=""), \
                 mock.patch.object(se, "read_mdls_text", return_value=""), \
                 mock.patch.object(se, "read_pdf_native_ocr_text", return_value=""), \
                 mock.patch.object(se, "_run_command", side_effect=fake_run) as run_command:
                text = se.read_pdf_text(pdf, runtime=runtime)

            self.assertEqual(text, "")
            self.assertIn(pdf, runtime.manual_review_heavy_ocr_paths)
            self.assertFalse(any(call.args[0][0] == str(env_binary) for call in run_command.call_args_list))

    def test_sorting_ocr_binary_env_override_runs_when_heavy_ocr_is_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pdf = root / "env-heavy.pdf"
            pdf.write_bytes(b"%PDF-1.4")
            runtime = runtime_for(root / "cache")
            env_binary = root / "bundled_pdf_ocr_pkg"
            env_binary.write_text("bin", encoding="utf-8")
            env_binary.chmod(0o755)
            runtime.ocr_binary_candidates = []

            def fake_run(args: list[str], timeout: int = 20) -> str:
                if args and args[0] == str(env_binary):
                    return "Счет ООО Дилайн Интернет услуги за август 2026. Сумма к оплате 1000,00 рублей."
                if args and args[0] == "strings":
                    return ""
                return ""

            with mock.patch.dict(os.environ, {"SORTING_OCR_BINARY": str(env_binary), "SORTING_ALLOW_HEAVY_OCR": "1"}, clear=False), \
                 mock.patch.object(se, "read_pymupdf_text", return_value=""), \
                 mock.patch.object(se, "extract_pdf_text_layer", return_value=""), \
                 mock.patch.object(se, "read_pdftotext_text", return_value=""), \
                 mock.patch.object(se, "read_mutool_text", return_value=""), \
                 mock.patch.object(se, "read_mdls_text", return_value=""), \
                 mock.patch.object(se, "read_pdf_native_ocr_text", return_value=""), \
                 mock.patch.object(se, "ocr_via_rendered_image", return_value=""), \
                 mock.patch.object(se, "ocr_pdf_by_pages", return_value=""), \
                 mock.patch.object(se, "_run_command", side_effect=fake_run) as run_command:
                text = se.read_pdf_text(pdf, runtime=runtime)

            self.assertIn("ооо дилайн", text.lower())
            self.assertFalse(pdf in runtime.manual_review_heavy_ocr_paths)
            self.assertTrue(any(call.args[0][0] == str(env_binary) for call in run_command.call_args_list))

    def test_xlsx_file_text_extracts_business_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            path = root / "invoice.xlsx"
            runtime = runtime_for(root / "cache")
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("docProps/core.xml", "<coreProperties><title>Счет на оплату</title></coreProperties>")
                archive.writestr("xl/workbook.xml", "<workbook><sheets><sheet name='Лист1'/></sheets></workbook>")
                archive.writestr("xl/sharedStrings.xml", "<sst><si><t>ООО Дилайн</t></si><si><t>Интернет</t></si></sst>")
                archive.writestr("xl/worksheets/sheet1.xml", "<worksheet><sheetData><row><c t='s'><v>0</v></c><c t='s'><v>1</v></c></row></sheetData></worksheet>")

            text = se.file_text(path, runtime=runtime)

            self.assertIn("счет на оплату", text.lower())
            self.assertIn("ооо дилайн", text.lower())
            self.assertIn("интернет", text.lower())

    def test_legacy_xls_file_text_extracts_utf16_fragments(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            path = root / "legacy.xls"
            runtime = runtime_for(root / "cache")
            payload = (
                b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
                + "Счет на оплату ООО Дилайн".encode("utf-16le")
                + b"\x00\x00\x00\x00"
                + "Интернет услуги апрель 2026".encode("utf-16le")
            )
            path.write_bytes(payload)

            with mock.patch.object(se, "read_mdls_text", return_value=""), \
                 mock.patch.object(se, "read_textutil_text", return_value=""), \
                 mock.patch.object(se, "read_quicklook_ocr_text", return_value=""), \
                 mock.patch.object(se, "_run_command", return_value=""):
                text = se.file_text(path, runtime=runtime)

            self.assertIn("счет на оплату", text.lower())
            self.assertIn("ооо дилайн", text.lower())
            self.assertIn("интернет услуги", text.lower())


if __name__ == "__main__":
    unittest.main()
