from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import fitz

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from pdf_merge_runtime import merge_ordered_pdfs


class PDFMergeProtectionTests(unittest.TestCase):
    def check_protected_inputs(self, binary):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ordinary = root / "ordinary.pdf"
            output = root / "output.pdf"
            with fitz.open() as document:
                document.new_page().insert_text((36, 72), "ORIGINAL PAGE")
                document.save(ordinary)
            output.write_bytes(ordinary.read_bytes())
            original = output.read_bytes()
            for password in ["secret", ""]:
                protected = root / ("locked.pdf" if password else "restricted.pdf")
                with fitz.open(ordinary) as document:
                    document.save(protected, encryption=fitz.PDF_ENCRYPT_AES_256,
                                  owner_pw="owner", user_pw=password, permissions=0)
                protected_bytes = protected.read_bytes()
                with self.assertRaisesRegex(RuntimeError, "защищен"):
                    merge_ordered_pdfs([ordinary, protected], output, binary)
                self.assertEqual(output.read_bytes(), original)
                self.assertEqual(ordinary.read_bytes(), original)
                self.assertEqual(protected.read_bytes(), protected_bytes)
                self.assertEqual(list(root.glob(".*.pdf")), [])
            merge_ordered_pdfs([ordinary, ordinary], output, binary)
            with fitz.open(output) as document:
                self.assertEqual(document.page_count, 2)
                self.assertTrue(all("ORIGINAL PAGE" in page.get_text() for page in document))

    def test_python_fallback_preserves_existing_output_and_sources(self):
        with patch("pdf_merge_runtime.resolve_merger_binary", return_value=None):
            self.check_protected_inputs(None)

    @unittest.skipUnless(os.environ.get("SORTING_PDF_MERGER"), "requires built PDFMergeHelper")
    def test_native_helper_preserves_existing_output_and_sources(self):
        self.check_protected_inputs(Path(os.environ["SORTING_PDF_MERGER"]))


if __name__ == "__main__":
    unittest.main()
