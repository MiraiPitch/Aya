"""
Command line interface for Aya AI Assistant
"""

import asyncio
import argparse
import os

from google.genai import types

# Package imports
from aya.live_loop import LiveLoop
from aya.function_registry import get_declarations_for_functions
from aya.utils import (
    list_system_messages,
    create_gemini_config,
    LANGUAGES,
    VOICES,
    MODALITIES,
    AUDIO_SOURCES,
    VIDEO_MODES
)

# Import specific tool functions we want to use
from aya.gemini_tools import print_to_console, get_current_date_and_time

# System message for Gemini Live API
SYSTEM_MESSAGE_PATH = "system_prompts/default/aya_default_tools_cli.txt"

# Initial user message (optional)
# INITIAL_MESSAGE = None
INITIAL_MESSAGE = "[CALL_START]"

# Configure tools
search_tool = {'google_search': {}}
code_execution_tool = {'code_execution': {}}
function_tools = {
    'function_declarations': get_declarations_for_functions([
        print_to_console,
        get_current_date_and_time
        # Add other functions here as needed
    ])
}
tools = [search_tool, code_execution_tool, function_tools]

# Default settings
LANG = "en-US"
VOICE = "Leda"
RESPONSE_MODALITY = "AUDIO"
MODEL = "models/gemini-2.0-flash-live-001"
# MODEL = "models/gemini-2.0-flash-live-preview-04-09" # Use with VertexAI

DEFAULT_MODE = "none"  # none, camera, screen
DEFAULT_AUDIO_SOURCE = "microphone"  # none, microphone, computer, both


def main():
    """Main entry point for the CLI application"""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--video-mode",
        type=str,
        default=DEFAULT_MODE,
        help="pixels to stream from",
        choices=VIDEO_MODES,
    )
    parser.add_argument(
        "--initial-message",
        type=str,
        default=INITIAL_MESSAGE,
        help="initial message to send to the AI at the start of the conversation",
    )
    parser.add_argument(
        "--audio-source",
        type=str,
        default=DEFAULT_AUDIO_SOURCE,
        help="audio input source to use: none, microphone, computer, or both",
        choices=AUDIO_SOURCES,
    )
    parser.add_argument(
        "--system-prompt",
        type=str,
        default=SYSTEM_MESSAGE_PATH,
        help="path to system prompt file to use",
    )
    parser.add_argument(
        "--list-prompts",
        action="store_true",
        help="list all available system prompts",
    )
    parser.add_argument(
        "--voice",
        type=str,
        default=VOICE,
        choices=VOICES,
        help="voice to use for speech output",
    )
    parser.add_argument(
        "--language",
        type=str,
        default=LANG,
        choices=LANGUAGES,
        help="language code for speech (e.g., en-US, de-DE)",
    )
    parser.add_argument(
        "--response-mode",
        type=str,
        default=RESPONSE_MODALITY,
        choices=MODALITIES,
        help="response mode (TEXT or AUDIO)",
    )
    args = parser.parse_args()

    # List available system prompts if requested
    if args.list_prompts:
        prompts = list_system_messages()
        print("Available system prompts:")
        for category, files in prompts.items():
            print(f"\t{category}:")
            for file in files:
                print(f"\t\t{os.path.basename(file)}")
        exit(0)

    # Use the enhanced utility function to create the config
    CONFIG = create_gemini_config(
        system_message_path=args.system_prompt,
        language_code=args.language,
        voice_name=args.voice,
        response_modality=args.response_mode,
        tools=tools,
        temperature=0.05
    )
    
    # Create and run the LiveLoop with the appropriate parameters
    main = LiveLoop(
        video_mode=args.video_mode,
        model=MODEL,
        config=CONFIG,
        initial_message=args.initial_message,
        audio_source=args.audio_source,
        record_conversation=False
    )
    asyncio.run(main.run())


if __name__ == "__main__":
    main()