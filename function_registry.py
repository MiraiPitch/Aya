"""
Module containing the FunctionRegistry class for managing tools for the Gemini Live API.
This module provides a decorator-based registry pattern for registering and managing tools.
"""

import inspect
import warnings
from typing import Dict, Any, Optional, List, Union, get_type_hints, get_origin, get_args, Callable

from google.genai import types

class FunctionRegistry:
    """Registry for Gemini tool functions and their declarations."""
    
    _functions = {}
    
    # Class level configuration
    show_warnings = True  # Whether to output warnings about type detection and descriptions
    
    @classmethod
    def enable_warnings(cls, enabled=True):
        """Enable or disable warnings."""
        cls.show_warnings = enabled
    
    @classmethod
    def _warn(cls, message):
        """Output a warning message if warnings are enabled."""
        if cls.show_warnings:
            warnings.warn(message, UserWarning, stacklevel=3)
    
    @classmethod
    def register(cls, name=None, description=None, parameters=None):
        """
        Decorator to register a function as a Gemini tool.
        
        If parameters are not provided, they will be automatically extracted from
        function type hints and docstrings.
        
        Args:
            name: Custom name for the function (defaults to function name)
            description: Function description (defaults to function docstring)
            parameters: JSON Schema parameters for the function (optional if defined in docstring)
            
        Returns:
            Decorated function that's registered in the registry
        """
        def decorator(func):
            func_name = name or func.__name__
            
            # If parameters are not provided, auto-generate them from type hints
            auto_parameters = parameters
            if auto_parameters is None:
                auto_parameters = cls._generate_parameters_from_function(func)
            
            # Extract clean description from docstring
            func_description = description
            if func_description is None and func.__doc__:
                func_description = cls._extract_description_from_docstring(func.__doc__)
            
            # Warn about empty descriptions
            if not func_description or func_description.strip() == "":
                cls._warn(f"Function '{func_name}' has no description. Add a docstring or description parameter.")
            
            cls._functions[func_name] = {
                "declaration": types.FunctionDeclaration(
                    name=func_name,
                    description=func_description,
                    parameters=auto_parameters
                ),
                "implementation": func
            }
            return func
        return decorator
    
    @classmethod
    def _extract_description_from_docstring(cls, docstring):
        """
        Extract a clean description from a docstring.
        
        The description is everything until the first empty line or a line starting with ":".
        
        Args:
            docstring: The function docstring
            
        Returns:
            Clean function description
        """
        if not docstring:
            return ""
        
        # Strip leading/trailing whitespace and split into lines
        lines = docstring.strip().split('\n')
        description_lines = []
        
        for line in lines:
            stripped_line = line.strip()
            # Stop at empty line or line starting with ":"
            if not stripped_line or stripped_line.startswith(':'):
                break
            description_lines.append(stripped_line)
        
        return ' '.join(description_lines)
    
    @classmethod
    def _generate_parameters_from_function(cls, func):
        """
        Generate parameters schema from function type hints.
        
        Args:
            func: The function to analyze
            
        Returns:
            JSON Schema parameters for the function
        """
        signature = inspect.signature(func)
        
        # Try to get type hints, warn if it fails
        try:
            type_hints = get_type_hints(func)
        except (TypeError, NameError) as e:
            cls._warn(f"Failed to get type hints for function '{func.__name__}': {str(e)}")
            type_hints = {}
        
        properties = {}
        required = []
        
        for param_name, param in signature.parameters.items():
            if param_name == 'self' or param_name == 'cls':
                continue
                
            param_type = type_hints.get(param_name, Any)
            has_default = param.default is not inspect.Parameter.empty
            
            if not has_default:
                required.append(param_name)
            
            # Get property schema for the parameter
            param_schema = cls._get_property_schema(param_name, param_type, param.default, func)
            properties[param_name] = param_schema
        
        return {
            "type": "object",
            "properties": properties,
            "required": required
        }
    
    @classmethod
    def _get_property_schema(cls, name, type_hint, default_value, func):
        """
        Generate a JSON Schema property from a type hint.
        
        Args:
            name: Parameter name
            type_hint: Python type hint
            default_value: Default value for the parameter
            func: The function being analyzed (for docstring extraction)
            
        Returns:
            JSON Schema property definition
        """
        # Extract description from docstring if possible
        description = cls._extract_param_description(name, func)
        
        # Warn about missing parameter descriptions
        if description is None:
            cls._warn(f"Parameter '{name}' in function '{func.__name__}' has no description")
        
        # Start with a basic schema
        schema = {
            "description": description or f"Parameter '{name}'"
        }
        
        # Try to detect type and warn if unrecognized
        type_detected = True
        
        # Handle common Python types
        if type_hint == str:
            schema["type"] = "string"
        elif type_hint == int:
            schema["type"] = "integer"
        elif type_hint == float:
            schema["type"] = "number"
        elif type_hint == bool:
            schema["type"] = "boolean"
        elif type_hint == list or get_origin(type_hint) == list:
            schema["type"] = "array"
            if get_origin(type_hint) == list:
                item_type = get_args(type_hint)[0]
                if item_type == str:
                    schema["items"] = {"type": "string"}
                elif item_type == int:
                    schema["items"] = {"type": "integer"}
                elif item_type == float:
                    schema["items"] = {"type": "number"}
                elif item_type == bool:
                    schema["items"] = {"type": "boolean"}
                else:
                    # We detected it's a list but couldn't determine item type
                    cls._warn(f"Unknown list item type for parameter '{name}' in function '{func.__name__}': {item_type}")
        elif type_hint == dict or get_origin(type_hint) == dict:
            schema["type"] = "object"
        elif type_hint == Any:
            # For Any, don't set a type and let the LLM infer
            pass
        elif hasattr(type_hint, "__origin__") and type_hint.__origin__ is Union:
            # Handle Optional[X] which is Union[X, None]
            args = get_args(type_hint)
            if len(args) == 2 and args[1] is type(None):
                # This is Optional[X]
                inner_schema = cls._get_property_schema(name, args[0], default_value, func)
                schema.update(inner_schema)
            else:
                # It's a more complex Union, which we can't represent well in JSON Schema
                cls._warn(f"Complex Union type for parameter '{name}' in function '{func.__name__}', using generic type")
                type_detected = False
        else:
            # We don't know how to handle this type
            cls._warn(f"Unknown type for parameter '{name}' in function '{func.__name__}': {type_hint}")
            type_detected = False
        
        # Add enum values if the default is an instance of Enum
        if default_value is not inspect.Parameter.empty and hasattr(default_value, "__class__") and hasattr(default_value.__class__, "__members__"):
            schema["enum"] = list(default_value.__class__.__members__.keys())
        
        return schema
    
    @classmethod
    def _extract_param_description(cls, param_name, func):
        """
        Extract parameter description from function docstring.
        
        Args:
            param_name: Name of the parameter
            func: Function to analyze
            
        Returns:
            Description of the parameter or None
        """
        if not func.__doc__:
            return None
            
        # Simple docstring parsing for parameter descriptions
        # This is a basic implementation that could be enhanced
        doc_lines = func.__doc__.split('\n')
        param_marker = f":param {param_name}:" 
        
        for i, line in enumerate(doc_lines):
            line = line.strip()
            if param_marker in line:
                description = line.split(param_marker)[1].strip()
                return description
                
        return None
    
    @classmethod
    def get_declarations(cls):
        """Get all registered function declarations."""
        return [info["declaration"] for info in cls._functions.values()]
    
    @classmethod
    def get_declaration(cls, function_name: str):
        """
        Get the declaration for a specific function by name.
        
        Args:
            function_name: The name of the function
            
        Returns:
            Function declaration or None if the function is not registered
        """
        if function_name in cls._functions:
            return cls._functions[function_name]["declaration"]
        return None
    
    @classmethod
    def get_declarations_for_function_names(cls, functions: List[str]):
        """
        Get declarations for a specific list of function names.
        
        Args:
            functions: List of function names to get declarations for
            
        Returns:
            List of function declarations for registered functions
        """
        return [
            cls._functions[name]["declaration"]
            for name in functions
            if name in cls._functions
        ]
    
    @classmethod
    def get_declarations_for_functions(cls, functions: List[Callable]):
        """
        Get declarations for a list of function objects.
        
        This allows for static analysis and IDE support by using function 
        references instead of string names.
        
        Args:
            functions: List of function objects to get declarations for
            
        Returns:
            List of function declarations for registered functions
        """
        result = []
        for func in functions:
            # Try to find the function in the registry by various means
            if func.__name__ in cls._functions:
                # Found by name
                result.append(cls._functions[func.__name__]["declaration"])
            else:
                # Check if this is the actual implementation function
                for name, info in cls._functions.items():
                    if info["implementation"] == func:
                        result.append(info["declaration"])
                        break
        return result
    
    @classmethod
    def execute(cls, function_name, args):
        """
        Execute a registered function.
        
        Args:
            function_name: The name of the function to execute
            args: Dictionary of arguments to pass to the function
            
        Returns:
            Result of the function execution or an error message
        """
        if function_name in cls._functions:
            return cls._functions[function_name]["implementation"](**args)
        return {"error": f"Unknown function: {function_name}"}

# Helper functions to expose registry functionality
def get_all_declarations():
    """Returns all function declarations for use with Gemini API."""
    return FunctionRegistry.get_declarations()

def get_declaration(function_name: str):
    """Returns a specific function declaration by name."""
    return FunctionRegistry.get_declaration(function_name)

def get_declarations_for_function_names(functions: List[str]):
    """Returns declarations for a list of function names."""
    return FunctionRegistry.get_declarations_for_function_names(functions)

def get_declarations_for_functions(functions: List[Callable]):
    """Returns declarations for a list of function objects (not names)."""
    return FunctionRegistry.get_declarations_for_functions(functions)

def execute_function(function_name, args):
    """Executes a function by name with the provided arguments."""
    return FunctionRegistry.execute(function_name, args) 

if __name__ == "__main__":
    print("""
Declare functions with type hints and either docstrings or manual parameters to use with FunctionRegistry:
        
With docstrings and type hints:
@FunctionRegistry.register()
def my_function(arg1: int, arg2: str) -> None:
    \"""
    My function description
        
    :param arg1: My first argument
    :param arg2: My second argument
    :return: Return description (optional)
    \"""
    pass

With manual parameters:

@FunctionRegistry.register(
        name="my_function",
        description="My function description",
        parameters={
            "type": "object",
            "properties": {
                "arg1": {
                    "type": "integer",
                    "description": "My first argument",
                },
                "arg2": {
                    "type": "string",
                    "description": "My second argument",
                },
            },
            "required": ["arg1", "arg2"],
        },
    )
def my_function(arg1, arg2):
    pass

more info on parameters definition:
https://ai.google.dev/gemini-api/docs/function-calling
    """)