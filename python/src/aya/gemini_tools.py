"""
Module containing function declarations and implementations for Gemini Live API tools.
This module defines tool functions with type hints and docstrings for the FunctionRegistry.
Refer to the function_registry.py module for how to register and use custom tools.
"""

from typing import Dict
from datetime import datetime

from aya.function_registry import FunctionRegistry

@FunctionRegistry.register()
def print_to_console(message: str) -> dict:
    """
    Prints a message to the console with formatting.
    
    :param message: The message to print to the console
    :return: Result confirmation
    """
    print("\n" + "="*50)
    print(f"FUNCTION CALL: print_to_console")
    print(f"MESSAGE: {message}")
    print("="*50 + "\n")
    return {"result": f"Successfully printed: {message}"}

@FunctionRegistry.register()
def get_current_date_and_time() -> dict:
    """
    Get the current date and time in the format YYYY-MM-DD HH:MM:SS

    :return: The current date and time in the format YYYY-MM-DD HH:MM:SS
    """
    return {"result": datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

if __name__ == "__main__":
    from aya.function_registry import get_all_declarations, execute_function
    print(get_all_declarations())
    print(execute_function("print_to_console", {"message": "Hello, world!"}))