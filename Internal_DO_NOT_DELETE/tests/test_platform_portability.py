from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock
import sys


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import sorting_extraction as extraction
import sorting_file_collection as file_collection


def extraction_runtime(tmpdir: str) -> extraction.ExtractionRuntime:
    return extraction.ExtractionRuntime(
        text_cache={},
        manual_review_heavy_ocr_paths=set(),
        command_exists_cache={},
        ocr_binary_candidates=[],
        swift_pdf_splitter=Path("missing.swift"),
        cache_root=Path(tmpdir) / "cache",
        text_cache_version="test",
        informative_text_patterns=["счет"],
        normalize_text=lambda value: value.lower(),
    )


class PlatformPortabilityTests(unittest.TestCase):
    def test_read_textutil_text_returns_empty_outside_macos(self) -> None:
        with mock.patch("sorting_platform.is_macos", return_value=False):
            self.assertEqual(extraction.read_textutil_text(Path("file.doc")), "")

    def test_ocr_pdf_by_pages_falls_back_to_pymupdf_splitter(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            runtime = extraction_runtime(tmpdir)
            path = Path(tmpdir) / "scan.pdf"
            path.write_bytes(b"%PDF-1.4")
            page = Path(tmpdir) / "page1.pdf"
            page.write_bytes(b"%PDF-1.4")

            with mock.patch("sorting_platform.split_pdf_with_pymupdf", return_value=[page]), \
                 mock.patch.object(extraction, "extract_pdf_text_layer", return_value=""), \
                 mock.patch.object(extraction, "_run_command", return_value="OCR page"), \
                 mock.patch.object(extraction, "read_quicklook_ocr_text", return_value=""), \
                 mock.patch.object(extraction, "ocr_via_rendered_image", return_value=""):
                text = extraction.ocr_pdf_by_pages(path, Path("ocr-bin"), runtime=runtime)

            self.assertEqual(text, "OCR page")

    def test_split_combined_pdf_falls_back_to_pymupdf_when_swift_splitter_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_root = Path(tmpdir) / "cache"
            cache_root.mkdir()
            path = Path(tmpdir) / "combined.pdf"
            path.write_bytes(b"%PDF-1.4")
            split_page = Path(tmpdir) / "page1.pdf"
            split_page.write_bytes(b"%PDF-1.4")

            with mock.patch("sorting_platform.split_pdf_with_pymupdf", return_value=[split_page]) as split_pdf:
                result = file_collection.split_combined_pdf(
                    path,
                    cache_root=cache_root,
                    swift_pdf_splitter=Path("missing.swift"),
                    run_command=lambda *_args, **_kwargs: "",
                )

            self.assertEqual(result, [split_page])
            split_pdf.assert_called_once()


if __name__ == "__main__":
    unittest.main()
