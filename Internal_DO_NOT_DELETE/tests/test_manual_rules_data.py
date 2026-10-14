from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import sorting_rules_data as srd


class ManualRulesDataTests(unittest.TestCase):
    def test_load_manual_file_rules_reads_external_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "manual.json"
            path.write_text(
                '{'
                '"Test.PDF":{'
                '"office":"1",'
                '"category":"Прочее",'
                '"entity":"X",'
                '"new_name":"a.pdf",'
                '"reason":"b"'
                '}'
                '}',
                encoding="utf-8",
            )

            rules = srd.load_manual_file_rules(path)

        self.assertIn("test.pdf", rules)
        self.assertEqual(rules["test.pdf"]["office"], "1")
        self.assertEqual(rules["test.pdf"]["new_name"], "a.pdf")


if __name__ == "__main__":
    unittest.main()
