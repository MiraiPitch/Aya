import unittest
import os
from unittest.mock import patch, mock_open
from src.aya.utils import list_system_messages, get_package_resource_path

class TestUtils(unittest.TestCase):
    
    @patch('src.aya.utils.os.walk')
    @patch('src.aya.utils.os.path.exists')
    @patch('src.aya.utils.get_package_resource_path')
    def test_list_system_messages(self, mock_get_package_path, mock_exists, mock_walk):
        # Mock the get_package_resource_path function
        base_path = '/mock/path/system_prompts'
        mock_get_package_path.return_value = base_path
        
        # Mock that the directory exists
        mock_exists.return_value = True
        
        # Create paths using os.path.join for platform compatibility
        default_dir = os.path.join(base_path, 'default')
        custom_dir = os.path.join(base_path, 'custom')
        default_file1 = os.path.join(default_dir, 'aya_default.txt')
        default_file2 = os.path.join(default_dir, 'aya_default_tools.txt')
        custom_file = os.path.join(custom_dir, 'custom_prompt.txt')
        
        # Set up mock directory structure for os.walk
        mock_walk.return_value = [
            (default_dir, [], ['aya_default.txt', 'aya_default_tools.txt']),
            (custom_dir, [], ['custom_prompt.txt']),
        ]
        
        # Call the function
        result = list_system_messages()
        
        # Verify the results
        self.assertEqual(len(result), 2)
        self.assertIn('default', result)
        self.assertIn('custom', result)
        
        # Check that the default category contains the expected files
        self.assertEqual(len(result['default']), 2)
        self.assertIn(default_file1, result['default'])
        self.assertIn(default_file2, result['default'])
        
        # Check that the custom category contains the expected file
        self.assertEqual(len(result['custom']), 1)
        self.assertIn(custom_file, result['custom'])
        
    def test_list_system_messages_empty_dir(self):
        # Test with non-existent directory
        with patch('src.aya.utils.os.path.exists', return_value=False):
            result = list_system_messages()
            self.assertEqual(result, {})
            
if __name__ == '__main__':
    unittest.main() 