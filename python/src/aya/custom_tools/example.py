"""
Example of custom tool functions for Aya
"""

import asyncio
import os
import sys
import datetime

# Import the function registry
from aya.function_registry import FunctionRegistry

# Register some simple example tools to show how to create your own
@FunctionRegistry.register()
def get_current_time() -> dict:
    """
    Returns the current time.
    
    :return: A dictionary containing the current time
    """
    now = datetime.datetime.now()
    formatted_time = now.strftime("%H:%M:%S")
    
    return {
        "time": formatted_time
    }

@FunctionRegistry.register()
def get_current_date() -> dict:
    """
    Returns the current date.
    
    :return: A dictionary containing the current date
    """
    now = datetime.datetime.now()
    formatted_date = now.strftime("%Y-%m-%d")
    
    return {
        "date": formatted_date
    }

@FunctionRegistry.register()
def add_numbers(a: int, b: int) -> dict:
    """
    Adds two numbers together.
    
    :param a: First number
    :param b: Second number
    :return: A dictionary containing the sum
    """
    result = a + b
    return {
        "sum": result
    }

@FunctionRegistry.register()
def multiply_numbers(a: int, b: int) -> dict:
    """
    Multiplies two numbers.
    
    :param a: First number
    :param b: Second number
    :return: A dictionary containing the product
    """
    result = a * b
    return {
        "product": result
    }

# Example with custom function declaration
@FunctionRegistry.register(
    name="calculate_area", 
    description="Calculates the area of a rectangle.",
    parameters={
        "type": "object",
        "properties": {
            "length": {
                "type": "number",
                "description": "The length of the rectangle"
            },
            "width": {
                "type": "number",
                "description": "The width of the rectangle"
            }
        },
        "required": ["length", "width"]
    }
)
def calculate_rectangle_area(length: float, width: float) -> dict:
    """
    Calculates the area of a rectangle.
    
    :param length: The length of the rectangle
    :param width: The width of the rectangle
    :return: A dictionary containing the area
    """
    area = length * width
    return {
        "area": area,
        "shape": "rectangle",
        "dimensions": {
            "length": length,
            "width": width
        }
    }

# Run a basic text-based example if this file is executed directly
if __name__ == "__main__":
    from aya.live_loop import LiveLoop
    from aya.utils import create_gemini_config
    
    # Configure the available functions
    available_tools = [
        get_current_time,
        get_current_date,
        add_numbers,
        multiply_numbers,
        calculate_rectangle_area
    ]
    
    # Get function declarations for the tools
    from aya.function_registry import get_declarations_for_functions
    function_tools = {
        'function_declarations': get_declarations_for_functions(available_tools)
    }
    
    # Set up the configuration
    CONFIG = create_gemini_config(
        system_message_path="system_prompts/default/aya_default_tools.txt",
        tools=[function_tools],
        temperature=0.2,
        # Set to TEXT to disable audio output
        response_modality="TEXT"
    )
    
    # Create and run the LiveLoop with the appropriate parameters
    main = LiveLoop(
        video_mode="none",  # No video input
        model="models/gemini-2.0-flash-live-001",
        config=CONFIG,
        initial_message="Hello! I have access to custom tools for working with dates, times, and calculations. What would you like to know?",
        audio_source="none",  # No audio input
        record_conversation=False
    )
    
    # Run the LiveLoop
    asyncio.run(main.run()) 