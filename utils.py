"""
Utility functions for the Aya project
"""

import os
from collections import defaultdict

def load_system_message(file_path="system_prompts/default/aya_default.txt"):
    """
    Load a system message from a file path
    
    Args:
        file_path (str): Path to the system message file
        
    Returns:
        str: The system message
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"System message file not found: {file_path}, using backup system message")
        return "You are Aya, an AI assistant with a friendly and helpful personality"

def list_system_messages(base_dir="system_prompts"):
    """
    List all available system messages in the system_prompts directory
    
    Args:
        base_dir (str): Base directory for system prompts
        
    Returns:
        dict: Dictionary with categories as keys and lists of file paths as values
    """
    messages = defaultdict(list)
    
    # Check if base directory exists
    if not os.path.exists(base_dir):
        return {}
    
    # Walk through the directory structure
    for root, _, files in os.walk(base_dir):
        if files:
            # Get the category from the directory structure
            category = os.path.relpath(root, base_dir)
            if category == ".":
                category = "root"
            
            # Add files to the category
            for file in files:
                if file.endswith(".txt"):
                    file_path = os.path.join(root, file)
                    messages[category].append(file_path)
    
    return dict(messages)

if __name__ == "__main__":
    import json
    print(json.dumps(list_system_messages(), indent=2))
