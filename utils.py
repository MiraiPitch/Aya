"""
Utility functions for the Aya project
"""

import os
from collections import defaultdict
from google.genai import types

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

def create_gemini_config(system_message_path, language_code, voice_name, response_modality, tools=None):
    """
    Create a Gemini LiveConnectConfig using the provided settings
    
    Args:
        system_message_path (str): Path to the system message file
        language_code (str): Language code for speech
        voice_name (str): Voice name for speech
        response_modality (str): Response modality (TEXT or AUDIO)
        tools (list): List of tool configurations
        
    Returns:
        LiveConnectConfig: Configured Gemini config
    """
    # Load system message
    system_message = load_system_message(system_message_path)
    
    # Create the config
    config = types.LiveConnectConfig(
        temperature=0.05,
        response_modalities=[response_modality],
        tools=tools or [],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name)
            ),
            language_code=language_code,
        ),
        context_window_compression=(
            types.ContextWindowCompressionConfig(
                sliding_window=types.SlidingWindow(),
            )
        ),
        system_instruction=types.Content(
            parts=[types.Part(text=system_message)]
        ),
    )
    
    return config

if __name__ == "__main__":
    import json
    print(json.dumps(list_system_messages(), indent=2))
