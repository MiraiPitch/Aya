"""
Example file demonstrating how to create custom tools for the Gemini Live API.
This shows how to:
1. Register custom functions using the decorator pattern
2. Run the LiveLoop with custom function handling
3. Auto-generated parameters from type hints
"""

import asyncio
import os
from dotenv import load_dotenv
from typing import Optional, List, Dict, Any
from enum import Enum

from google import genai
from google.genai import types

# Import the registry and LiveLoop
from function_registry import FunctionRegistry, get_declarations_for_functions
from live_loop import LiveLoop

# Load environment variables and API key
load_dotenv()
API_KEY_ENV_VAR = "GEMINI_API_KEY"
api_key = os.getenv(API_KEY_ENV_VAR)

# Define and register custom tool functions with auto-generated parameters
@FunctionRegistry.register()
def get_time_info(format: str = "short") -> Dict[str, Any]:
    """
    Returns the current time information in the specified format.
    
    :param format: Format type (short/long) for the time information
    :return: Dictionary with time information
    """
    import datetime
    now = datetime.datetime.now()
    
    if format == "long":
        result = {
            "year": now.year,
            "month": now.month,
            "day": now.day,
            "hour": now.hour,
            "minute": now.minute,
            "second": now.second,
            "weekday": now.strftime("%A"),
            "formatted": now.strftime("%Y-%m-%d %H:%M:%S"),
            "timezone": datetime.datetime.now().astimezone().tzname()
        }
    else:  # short format
        result = {
            "time": now.strftime("%H:%M:%S"),
            "date": now.strftime("%Y-%m-%d")
        }
    
    print(f"\n==== TIME INFO REQUESTED ({format} format) ====")
    print(f"Result: {result}")
    print("="*50 + "\n")
    
    return result

# Define and register custom tool with manual parameters (type annotations in the function signature are technically optional)
# Useful for more complex operations and declaring enums
@FunctionRegistry.register(
    name="calculate",
    description="Performs a simple calculation with the given operation and numbers.",
    parameters={
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["add", "subtract", "multiply", "divide"],
                "description": "The mathematical operation to perform (add, subtract, multiply, divide)",
            },
            "a": {
                "type": "number",
                "description": "First number",
            },
            "b": {
                "type": "number",
                "description": "Second number",
            },
        },
        "required": ["operation", "a", "b"],
    },
)
def calculate(operation: str, a: float, b: float) -> Dict[str, Any]:
    """
    Performs a simple calculation with the given operation and numbers.
    
    :param operation: The mathematical operation to perform (add, subtract, multiply, divide)
    :param a: First number
    :param b: Second number
    :return: Dictionary with calculation result
    """
    result = None
    
    if operation == "add":
        result = a + b
    elif operation == "subtract":
        result = a - b
    elif operation == "multiply":
        result = a * b
    elif operation == "divide":
        if b == 0:
            return {"error": "Cannot divide by zero"}
        result = a / b
    
    print(f"\n==== CALCULATION REQUESTED ====")
    print(f"Operation: {operation}")
    print(f"Values: {a} and {b}")
    print(f"Result: {result}")
    print("="*50 + "\n")
    
    return {"result": result}
# List of functions we want to make available to the model
available_tools = [
    get_time_info,
    calculate,
]

# Configure Gemini Live API
MODEL = "models/gemini-2.0-flash-live-001"
CONFIG = types.LiveConnectConfig(
    response_modalities=["TEXT"],  # Using TEXT for easier testing
    tools=[{
        'function_declarations': get_declarations_for_functions(available_tools)
    }],
    system_instruction=types.Content(
        parts=[types.Part(text="""
        You are a helpful assistant that can calculate, provide time information, and weather forecasts.
        Try using the available tools to help the user with their questions.
        """)]
    )
)

async def main():
    # Create Gemini client
    client = genai.Client(http_options={"api_version": "v1beta"}, api_key=api_key)
    
    # Create and run LiveLoop with the custom function executor
    loop = LiveLoop(
        video_mode="none",
        audio_source="none",
        client=client,
        model=MODEL,
        config=CONFIG,
    )
    
    await loop.run()

if __name__ == "__main__":
    asyncio.run(main()) 