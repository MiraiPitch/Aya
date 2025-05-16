"""
Standalone script for Using Aya in the command line
"""

import asyncio
import argparse
import os
from dotenv import load_dotenv

from google import genai
from google.genai import types

# Local imports
from live_loop import LiveLoop
from function_registry import get_declarations_for_functions
from utils import load_system_message, list_system_messages

# Import specific tool functions we want to use
from gemini_tools import print_to_console

# Load environment variables and API key
load_dotenv()
API_KEY_ENV_VAR = "GEMINI_API_KEY"
api_key = os.getenv(API_KEY_ENV_VAR)

# System message for Gemini Live API
SYSTEM_MESSAGE_PATH = "system_prompts/default/aya_default.txt"

# Initial user message (optional)
# INITIAL_MESSAGE = None
INITIAL_MESSAGE = "[CALL_START]"

# Configure tools
search_tool = {'google_search': {}}
function_tools = {
    'function_declarations': get_declarations_for_functions([
        print_to_console,
        # Add other functions here as needed
    ])
}
tools = [search_tool, function_tools]

# LANG = "de-DE"
LANG = "en-US"

# The Live API supports the following voices: Puck, Charon, Kore, Fenrir, Aoede, Leda, Orus, and Zephyr.
## Male
# VOICE = "Puck"
# VOICE = "Charon"
# VOICE = "Fenrir"
# VOICE = "Orus"
## Female
# VOICE = "Kore"
VOICE = "Leda"
# VOICE = "Zephyr"

# RESPONSE_MODALITIES = ["AUDIO"]
RESPONSE_MODALITIES = ["TEXT"]

# CONFIG = {"response_modalities": ["AUDIO"], "tools": [search_tool]}
# CONFIG = {"response_modalities": ["AUDIO"]}

MODEL = "models/gemini-2.0-flash-live-001"
# MODEL = "models/gemini-2.0-flash-live-preview-04-09" # Use with VertexAI

DEFAULT_MODE = "none"  # none, camera, screen
DEFAULT_AUDIO_SOURCE = "microphone"  # none, microphone, computer, both

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        type=str,
        default=DEFAULT_MODE,
        help="pixels to stream from",
        choices=["camera", "screen", "none"],
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
        choices=["none", "microphone", "computer", "both"],
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

    system_message = load_system_message(args.system_prompt)

    CONFIG = types.LiveConnectConfig(
        response_modalities=RESPONSE_MODALITIES,
        tools=tools,
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=VOICE)
            ),
            language_code=LANG,
        ),
        context_window_compression=(
            # Configures compression with default parameters.
            types.ContextWindowCompressionConfig(
                sliding_window=types.SlidingWindow(),
            )
        ),
        system_instruction=types.Content(
            parts=[types.Part(text=system_message)]
        ),
    ) 
    # Create and run the LiveLoop with the appropriate parameters
    client = genai.Client(http_options={"api_version": "v1beta"}, api_key=api_key)
    main = LiveLoop(
        video_mode=args.mode,
        client=client,
        model=MODEL,
        config=CONFIG,
        initial_message=args.initial_message,
        audio_source=args.audio_source,
        record_conversation=False
    )
    asyncio.run(main.run())