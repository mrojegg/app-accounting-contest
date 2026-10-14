from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import sort_documents as sd


class ClassificationDocumentTypesTests(unittest.TestCase):
    def test_efs_form_goes_to_manual_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_root = Path(tmpdir) / "archive"
            source = Path(tmpdir) / "efs.pdf"
            source.write_text("dummy", encoding="utf-8")
            text = (
                'Форма ЕФС-1 Единая форма "Сведения для ведения индивидуального '
                'учета и сведения о начисленных страховых взносах"'
            )
            with mock.patch.object(sd, "file_text", return_value=text):
                result = sd.classify(source, archive_root)

        self.assertTrue(result.requires_manual_review)
        self.assertEqual(result.destination, archive_root / "Требует_ручной_проверки")
        self.assertEqual(result.new_name, source.name)


if __name__ == "__main__":
    unittest.main()
