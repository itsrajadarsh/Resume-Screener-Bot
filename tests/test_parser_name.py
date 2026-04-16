import sys
import os
import unittest
from unittest.mock import MagicMock

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'resume_screener')))

# Mock fitz and utils since they are not available or not needed for this unit test
sys.modules['fitz'] = MagicMock()
sys.modules['utils'] = MagicMock()

from parser import _extract_name

class TestParserName(unittest.TestCase):
    def test_extract_name(self):
        test_cases = [
            ("John Doe\nSoftware Engineer", "John Doe"),
            ("\n  \nJane Smith\n123 Street", "Jane Smith"),
            ("OnlyOneWord\nReal Name", "Real Name"),
            ("No valid name here", "No valid name here"),
            ("  Leading Spaces Name  \nMore text", "Leading Spaces Name"),
            ("", None),
            ("\n\n", None),
        ]

        for text, expected in test_cases:
            with self.subTest(text=text):
                result = _extract_name(text)
                self.assertEqual(result, expected)

if __name__ == "__main__":
    unittest.main()
