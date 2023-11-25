""" 
Do not use or modify this file if you don't know what you are doing.
This file is used to test the script using unittest and mock.
"""
import unittest
from unittest.mock import Mock, patch
from requests.models import Response
from cls.FileHandler import FileHandler
from cls.AppImageDownloader import AppImageDownloader
from cls.decorators import handle_api_errors

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
    def __init__(self, *args, **kwargs):
        self.url = 'https://api.github.com/repos/owner/repo/releases/latest'

    @patch('cls.decorators.handle_api_errors')
    @patch('requests.get')
    def test_get_response(self, mock_get, mock_handle_api_errors):
        # Create a mock response object
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {'message': 'Bad credentials'}
        
        # Assign the mock response as the result of our patched function
        mock_get.return_value = mock_response

        # Configure the mock handle_api_errors function
        mock_handle_api_errors.side_effect = lambda x: x

        # Create an instance of the AppImageDownloader class
        app_image_downloader = AppImageDownloader()
        app_image_downloader.get_response()
        self.assertEqual(app_image_downloader.get_response(), mock_response)
        mock_get.assert_called_once('https://api.github.com/repos/owner/repo/releases/latest')

if __name__ == '__main__':
    unittest.main()
