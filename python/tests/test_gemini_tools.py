import unittest
from unittest.mock import patch
from io import StringIO
from src.aya.gemini_tools import print_to_console

class TestGeminiTools(unittest.TestCase):
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_print_to_console(self, mock_stdout):
        # Test the print_to_console function directly
        message = "Test message"
        result = print_to_console(message)
        
        # Verify the return value
        self.assertEqual(result, {"result": f"Successfully printed: {message}"})
        
        # Verify that the message was printed to stdout
        stdout_content = mock_stdout.getvalue()
        self.assertIn("FUNCTION CALL: print_to_console", stdout_content)
        self.assertIn(f"MESSAGE: {message}", stdout_content)
        
        # Test with different message
        message2 = "Another test message"
        result2 = print_to_console(message2)
        
        # Verify the return value
        self.assertEqual(result2, {"result": f"Successfully printed: {message2}"})
        
        # Verify the second message was also printed
        stdout_content = mock_stdout.getvalue()
        self.assertIn(f"MESSAGE: {message2}", stdout_content)

if __name__ == '__main__':
    unittest.main() 