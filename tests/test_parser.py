from ast import Param
import os
import sys
import unittest
from unittest.mock import patch

from ..src.parser import ParseURL

# Add the project root to sys.path so that the 'src' package can be imported.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


class TestParseURL(unittest.TestCase):
    @patch("builtins.input", return_value="https://github.com/testowner/testrepo")
    def test_ask_url(self, mock_input):
        # ask_url should parse the GitHub URL correctly.
        parser = ParseURL()
        parser.ask_url()
        self.assertEqual(parser.owner, "testowner")
        self.assertEqual(parser.repo, "testrepo")

    def test_validate_url_invalid(self):
        # _validate_url should raise an error for an invalid URL.
        parser = ParseURL(url="http://invalid.com/testowner/testrepo")
        with self.assertRaises(ValueError):
            parser._validate_url()

    def test_parse_owner_repo_invalid(self):
        # _parse_owner_repo should raise an error if the URL does not contain enough parts.
        parser = ParseURL(url="https://github.com/testowner")
        with self.assertRaises(ValueError):
            parser._parse_owner_repo()


if __name__ == "__main__":
    unittest.main()
