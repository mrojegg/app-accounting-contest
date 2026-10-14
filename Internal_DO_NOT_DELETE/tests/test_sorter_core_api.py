from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import sorting_sorter_core as core
import sorting_sorter_classification as sorter_classification
import sorting_sorter_naming as sorter_naming
import sorting_sorter_routing as sorter_routing
import sorting_sorter_runtime as sorter_runtime


class SortingSorterCoreApiTests(unittest.TestCase):
    def test_classification_runtime_delegates_to_runtime_module(self) -> None:
        sentinel = object()
        with mock.patch.object(sorter_runtime, "classification_runtime", return_value=sentinel):
            self.assertIs(core.classification_runtime(), sentinel)

    def test_read_pdf_text_preserves_core_api_and_uses_runtime(self) -> None:
        runtime = object()
        path = Path("/tmp/sample.pdf")
        with mock.patch.object(sorter_runtime, "extraction_runtime", return_value=runtime), \
             mock.patch.object(core.extraction, "read_pdf_text", return_value="pdf text") as read_pdf_text:
            self.assertEqual(core.read_pdf_text(path), "pdf text")
        read_pdf_text.assert_called_once_with(path, runtime=runtime)

    def test_classify_preserves_core_api_and_delegates_to_classification_facade(self) -> None:
        runtime = object()
        path = Path("/tmp/sample.pdf")
        archive_root = Path("/tmp/archive")
        sentinel = object()
        with mock.patch.object(sorter_runtime, "classification_runtime", return_value=runtime), \
             mock.patch.object(sorter_classification, "classify", return_value=sentinel) as classify:
            self.assertIs(core.classify(path, archive_root), sentinel)
        classify.assert_called_once()
        self.assertEqual(classify.call_args.args, (path, archive_root))
        self.assertIs(classify.call_args.kwargs["file_text"], core.file_text)
        self.assertIs(classify.call_args.kwargs["safe_filename"], core.safe_filename)
        self.assertIs(classify.call_args.kwargs["runtime_factory"], core.classification_runtime)

    def test_safe_filename_delegates_to_naming_facade(self) -> None:
        path = Path("/tmp/doc.txt")
        with mock.patch.object(sorter_naming, "safe_filename", return_value="renamed.txt") as safe_filename:
            self.assertEqual(core.safe_filename(path, "109", "Услуги", "ПРИМЕР"), "renamed.txt")
        safe_filename.assert_called_once()
        self.assertEqual(safe_filename.call_args.args[:4], (path, "109", "Услуги", "ПРИМЕР"))
        self.assertIsInstance(safe_filename.call_args.kwargs["deps"], sorter_naming.NamingDependencies)

    def test_extract_invoice_date_delegates_to_naming_facade(self) -> None:
        with mock.patch.object(sorter_naming, "extract_invoice_date", return_value="01-04-2026") as extract_invoice_date:
            self.assertEqual(core.extract_invoice_date("body", "file.pdf"), "01-04-2026")
        extract_invoice_date.assert_called_once_with("body", "file.pdf")

    def test_destination_for_delegates_to_routing_facade(self) -> None:
        source = Path("/tmp/doc.txt")
        archive_root = Path("/tmp/archive")
        expected = (archive_root / "109" / "Услуги", "ok")
        with mock.patch.object(sorter_routing, "destination_for", return_value=expected) as destination_for:
            self.assertEqual(core.destination_for(source, archive_root, "109", "Услуги", "ПРИМЕР"), expected)
        destination_for.assert_called_once()
        self.assertEqual(destination_for.call_args.args[:5], (source, archive_root, "109", "Услуги", "ПРИМЕР"))
        self.assertIsInstance(destination_for.call_args.kwargs["deps"], sorter_routing.RoutingDependencies)


if __name__ == "__main__":
    unittest.main()
