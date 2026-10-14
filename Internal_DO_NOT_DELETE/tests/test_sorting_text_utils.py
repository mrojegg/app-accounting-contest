from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import sorting_text_utils as stu


class SortingTextUtilsTests(unittest.TestCase):
    def test_normalize_text_keeps_project_specific_replacements(self) -> None:
        normalized = stu.normalize_text("OOO Билаин ИНН/КПП Чеботврев")
        self.assertEqual(normalized, "ооо билайн инн кпп чеботарев")

    def test_parse_russian_number_words_supports_thousands(self) -> None:
        amount = stu.parse_russian_number_words("три тысячи")
        self.assertEqual(amount, 3000)

    def test_normalize_piece_rejects_long_hex_like_garbage(self) -> None:
        normalized = stu.normalize_piece("ABCD_1234_DEAD_BEEF_CAFE_9876_FFFF")
        self.assertEqual(normalized, "")

    def test_normalize_piece_is_windows_safe(self) -> None:
        self.assertEqual(stu.normalize_piece('CON'), "file_con")
        self.assertEqual(stu.normalize_piece('bad<name>.'), "bad_name")


if __name__ == "__main__":
    unittest.main()
