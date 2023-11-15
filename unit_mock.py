import unittest
from unittest.mock import Mock, patch
from requests.models import Response
from cls.FileHandler import FileHandler
from cls.AppImageDownloader import AppImageDownloader

# class TestFileHandler(unittest.TestCase):
# @patch('requests.get')
# def test_get_sha(self, mock_get):
#     mock_response = Response()
#     mock_response.status_code = 404
#     mock_get.return_value = mock_response

#     file_handler = FileHandler()
#     file_handler.get_sha()

#     # Check that get_sha raises an exception, do not care system exit
#     with self.assertRaises(SystemExit):
#         file_handler.get_sha()

class TestAppImagedownloader(unittest.TestCase):
    @patch('builtins.input', side_effect=['3'])
    def test_ask_inputs(self, mock_input):
        with self.assertRaises(ValueError):
            AppImageDownloader().ask_inputs()

if __name__ == '__main__':
    unittest.main()
