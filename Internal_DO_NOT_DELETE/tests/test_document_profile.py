from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import sorting_document_profile as dp
import sorting_extraction as se


def runtime_for(cache_root: Path) -> se.ExtractionRuntime:
    return se.ExtractionRuntime(
        text_cache={},
        manual_review_heavy_ocr_paths=set(),
        command_exists_cache={},
        ocr_binary_candidates=[],
        swift_pdf_splitter=Path("missing.swift"),
        cache_root=cache_root,
        text_cache_version="test",
        informative_text_patterns=["счет", "получатель", "назначение платежа", "сумма"],
        normalize_text=lambda value: value.lower(),
    )


class DocumentProfileTests(unittest.TestCase):
    def test_detect_document_type_by_extension(self) -> None:
        self.assertEqual(dp.detect_document_type(Path("doc.pdf")), "pdf")
        self.assertEqual(dp.detect_document_type(Path("doc.txt")), "text")
        self.assertEqual(dp.detect_document_type(Path("doc.xlsx")), "openxml")
        self.assertEqual(dp.detect_document_type(Path("doc.png")), "image")
        self.assertEqual(dp.detect_document_type(Path("doc.xls")), "legacy")
        self.assertEqual(dp.detect_document_type(Path("doc.bin")), "generic")

    def test_profile_pdf_includes_page_count_and_text_layer(self) -> None:
        runtime = runtime_for(Path("/tmp/cache"))
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.pdf"
            path.write_bytes(b"%PDF-1.4")

            with mock.patch.object(se, "file_text", return_value="Платежное поручение\nСумма 1000,00"), \
                 mock.patch("sorting_document_profile.platform_support.pdf_page_count", return_value=3), \
                 mock.patch("sorting_document_profile.platform_support.pdf_has_text_layer", return_value=True):
                profile = dp.profile_document(path, runtime=runtime)

        self.assertEqual(profile.document_type, "pdf")
        self.assertEqual(profile.pdf_page_count, 3)
        self.assertTrue(profile.has_text_layer)
        self.assertTrue(profile.quality_flags["is_multipage_pdf"])
        self.assertTrue(profile.quality_flags["has_text"])

    def test_profile_payment_quality_flags(self) -> None:
        runtime = runtime_for(Path("/tmp/cache"))
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "payment.txt"
            path.write_text("x", encoding="utf-8")
            profile = dp.profile_document(
                path,
                runtime=runtime,
                file_text_fn=lambda _: (
                    "Платежное поручение\n"
                    "Получатель Иван Иванов\n"
                    "Назначение платежа Выплата заработной платы\n"
                    "Сумма 1000,00\n"
                ),
            )

        self.assertTrue(profile.quality_flags["is_payment_like"])
        self.assertTrue(profile.quality_flags["has_recipient"])
        self.assertTrue(profile.quality_flags["has_purpose"])
        self.assertTrue(profile.quality_flags["has_amount"])
        self.assertFalse(profile.quality_flags["is_empty_document"])

    def test_profile_garbled_text_marks_low_quality(self) -> None:
        runtime = runtime_for(Path("/tmp/cache"))
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "bad.txt"
            path.write_text("x", encoding="utf-8")
            profile = dp.profile_document(
                path,
                runtime=runtime,
                file_text_fn=lambda _: "ɉȺɈ ȼɵɦɩɟɥɄɨɦ ˇœ‡°±·",
            )

        self.assertTrue(profile.quality_flags["is_garbled"])
        self.assertTrue(profile.quality_flags["is_low_quality_text"])


if __name__ == "__main__":
    unittest.main()
