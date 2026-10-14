from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
import sys
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import sorting_windows_export as swe


class WindowsExportValidationTests(unittest.TestCase):
    def test_reserved_name_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "CON.txt").write_text("x", encoding="utf-8")
            issues = swe.validate_windows_paths(root)
        self.assertEqual(len(issues), 1)
        self.assertIn("reserved", issues[0].message)

    def test_valid_pdf_has_no_integrity_issue(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pdf = root / "doc.pdf"
            pdf.write_bytes(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF")
            issues = swe.validate_file_integrity(root)
        self.assertEqual(issues, [])

    def test_broken_pdf_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pdf = root / "doc.pdf"
            pdf.write_bytes(b"not-a-pdf")
            issues = swe.validate_file_integrity(root)
        self.assertEqual(len(issues), 1)
        self.assertIn("PDF header", issues[0].message)

    def test_zip_based_office_file_is_checked(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            xlsx = root / "sheet.xlsx"
            xlsx.write_bytes(b"not-a-zip")
            issues = swe.validate_file_integrity(root)
        self.assertEqual(len(issues), 1)
        self.assertIn("zip-based office file", issues[0].message)
