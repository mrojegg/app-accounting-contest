from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

import sorting_windows_delivery


class WindowsDeliveryTests(unittest.TestCase):
    def test_create_windows_delivery_zip_packs_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "Архив"
            nested = root / "98" / "Зарплата"
            nested.mkdir(parents=True)
            pdf = nested / "демофамилияабц_коумбо_иван_карел_26-02-2026_33157-63.pdf"
            pdf.write_bytes(b"%PDF-1.5\nsample\n%%EOF\n")

            zip_path = sorting_windows_delivery.create_windows_delivery_zip(root)

            self.assertTrue(zip_path.exists())
            with zipfile.ZipFile(zip_path) as archive:
                names = archive.namelist()
                self.assertIn("Архив/98/Зарплата/демофамилияабц_коумбо_иван_карел_26-02-2026_33157-63.pdf", names)
                self.assertEqual(
                    archive.read("Архив/98/Зарплата/демофамилияабц_коумбо_иван_карел_26-02-2026_33157-63.pdf"),
                    b"%PDF-1.5\nsample\n%%EOF\n",
                )


if __name__ == "__main__":
    unittest.main()
