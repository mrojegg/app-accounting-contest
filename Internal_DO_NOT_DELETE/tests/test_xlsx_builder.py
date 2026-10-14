from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import xlsx_builder


class XlsxBuilderTests(unittest.TestCase):
    def test_build_workbook_xlsx_creates_minimal_excel_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "test.xlsx"
            sheet_xml = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                '<sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>ok</t></is></c></row></sheetData>'
                '</worksheet>'
            )

            xlsx_builder.build_workbook_xlsx(output, sheet_xml, "Лист1")

            with zipfile.ZipFile(output) as archive:
                names = set(archive.namelist())
                workbook = archive.read("xl/workbook.xml").decode("utf-8")

        self.assertEqual(
            names,
            {
                "[Content_Types].xml",
                "_rels/.rels",
                "xl/workbook.xml",
                "xl/_rels/workbook.xml.rels",
                "xl/worksheets/sheet1.xml",
                "xl/styles.xml",
            },
        )
        self.assertIn('sheet name="Лист1"', workbook)

    def test_build_multi_sheet_workbook_xlsx_creates_two_sheets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "test.xlsx"
            sheet_xml = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                '<sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>ok</t></is></c></row></sheetData>'
                '</worksheet>'
            )

            xlsx_builder.build_multi_sheet_workbook_xlsx(output, [("Свод", sheet_xml), ("Детализация", sheet_xml)])

            with zipfile.ZipFile(output) as archive:
                names = set(archive.namelist())
                rels = archive.read("xl/_rels/workbook.xml.rels").decode("utf-8")
                workbook = archive.read("xl/workbook.xml").decode("utf-8")

        self.assertIn("xl/worksheets/sheet1.xml", names)
        self.assertIn("xl/worksheets/sheet2.xml", names)
        self.assertIn('sheet name="Свод"', workbook)
        self.assertIn('sheet name="Детализация"', workbook)
        self.assertIn('Id="rId3"', rels)


if __name__ == "__main__":
    unittest.main()
