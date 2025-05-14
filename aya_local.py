"""
Standalone script for Gemini Live API with camera or screen sharing
This script accepts a `--mode` parameter to specify the video input source: 
"camera" (default), "screen" for screen sharing, or "none" for audio-only operation.
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

# Import specific tool functions we want to use
from gemini_tools import print_to_console

# Load environment variables and API key
load_dotenv()
API_KEY_ENV_VAR = "GEMINI_API_KEY"
api_key = os.getenv(API_KEY_ENV_VAR)

# System message for Gemini Live API
SYSTEM_MESSAGE = """
You are Aya, an AI assistant with a friendly and helpful personality. 
You should be concise, clear, and engaging in your responses. 
When appropriate, you can use humor and show personality while maintaining professionalism.
Always aim to be helpful while respecting user privacy and safety.
If the call starts with "[CALL_START]", you should greet the user.
"""

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
        parts=[types.Part(text=SYSTEM_MESSAGE)]
    ),
)
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
    args = parser.parse_args()

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