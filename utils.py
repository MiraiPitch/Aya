"""
Utility functions for the Aya project
"""

import os
import warnings
from collections import defaultdict
from google.genai import types

# Constants moved from aya_gui.py
LANGUAGES = {
    "English (US)": "en-US",
    "English (UK)": "en-GB",
    "German (DE)": "de-DE",
    "French (FR)": "fr-FR",
    "Spanish (ES)": "es-ES",
    "Italian (IT)": "it-IT",
    "Japanese (JP)": "ja-JP",
    "Korean (KR)": "ko-KR",
    "Chinese (CN)": "cmn-CN",
}

VOICES = {
    "Leda (Female)": "Leda",
    "Kore (Female)": "Kore", 
    "Zephyr (Female)": "Zephyr",
    "Puck (Male)": "Puck",
    "Charon (Male)": "Charon",
    "Fenrir (Male)": "Fenrir",
    "Orus (Male)": "Orus"
}

AUDIO_SOURCES = ["none", "microphone", "computer", "both"]
VIDEO_MODES = ["none", "camera", "screen"]
MODALITIES = ["TEXT", "AUDIO"]

# Default values
DEFAULT_LANGUAGE = "en-US"
DEFAULT_VOICE = "Leda"
DEFAULT_MODALITY = "AUDIO"
DEFAULT_TEMPERATURE = 0.05

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

def create_gemini_config(system_message_path, language_code=None, voice_name=None, 
                        response_modality=None, tools=None, temperature=None):
    """
    Create a Gemini LiveConnectConfig using the provided settings
    
    Args:
        system_message_path (str): Path to the system message file
        language_code (str): Language code for speech or display name from LANGUAGES
        voice_name (str): Voice name for speech or display name from VOICES
        response_modality (str): Response modality (TEXT or AUDIO)
        tools (list): List of tool configurations
        temperature (float): Temperature for response generation (0.0 to 1.0)
        
    Returns:
        LiveConnectConfig: Configured Gemini config
    """
    # Load system message
    system_message = load_system_message(system_message_path)
    
    # Process and validate language code
    if language_code:
        # Check if the input is a display name from LANGUAGES
        if language_code in LANGUAGES:
            language_code = LANGUAGES[language_code]
        # Validate language code format (simple check for xx-XX format)
        elif not (isinstance(language_code, str) and len(language_code) >= 5 and '-' in language_code):
            warnings.warn(f"Invalid language code: {language_code}. Using default: {DEFAULT_LANGUAGE}")
            language_code = DEFAULT_LANGUAGE
    else:
        language_code = DEFAULT_LANGUAGE
        
    # Process and validate voice name
    if voice_name:
        # Check if the input is a display name from VOICES
        if voice_name in VOICES:
            voice_name = VOICES[voice_name]
        # Validate voice is in the list of available voices
        elif voice_name not in set(VOICES.values()):
            warnings.warn(f"Invalid voice name: {voice_name}. Using default: {DEFAULT_VOICE}")
            voice_name = DEFAULT_VOICE
    else:
        voice_name = DEFAULT_VOICE
        
    # Validate response modality
    if response_modality:
        if response_modality not in MODALITIES:
            warnings.warn(f"Invalid response modality: {response_modality}. Using default: {DEFAULT_MODALITY}")
            response_modality = DEFAULT_MODALITY
    else:
        response_modality = DEFAULT_MODALITY
        
    # Validate temperature
    if temperature is not None:
        if not isinstance(temperature, (int, float)) or temperature < 0 or temperature > 1.0:
            warnings.warn(f"Invalid temperature: {temperature}. Using default: {DEFAULT_TEMPERATURE}")
            temperature = DEFAULT_TEMPERATURE
    else:
        temperature = DEFAULT_TEMPERATURE
    
    # Create the config
    config = types.LiveConnectConfig(
        temperature=temperature,
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
