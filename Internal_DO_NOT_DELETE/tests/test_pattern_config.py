from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import sorting_pattern_config as spc


class PatternConfigTests(unittest.TestCase):
    def test_load_pattern_config_reads_external_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "patterns.json"
            path.write_text(
                '{'
                '"ENTITY_PATTERNS":{"X":["abc"]},'
                '"CATEGORY_PATTERNS":{"Y":["def"]},'
                '"TAX_PATTERNS":["tax"]'
                '}',
                encoding="utf-8",
            )

            config = spc.load_pattern_config(path)

        self.assertEqual(config.entity_patterns["X"], ["abc"])
        self.assertEqual(config.category_patterns["Y"], ["def"])
        self.assertEqual(config.tax_patterns, ["tax"])
        self.assertIn("ПРИМЕР", config.entity_account_patterns)


if __name__ == "__main__":
    unittest.main()
