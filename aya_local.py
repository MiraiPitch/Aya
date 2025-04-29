"""
Standalone script for Gemini Live API with camera or screen sharing
This script accepts a `--mode` parameter to specify the video input source: 
"camera" (default), "screen" for screen sharing, or "none" for audio-only operation.
"""

import asyncio
import argparse
import os
import sys
from dotenv import load_dotenv

from google import genai
from google.genai import types

# Import the LiveLoop class from the new module
from live_loop import LiveLoop

# Load environment variables and API key
load_dotenv()
API_KEY_ENV_VAR = "GEMINI_API_KEY"
api_key = os.getenv(API_KEY_ENV_VAR)

# Configure tools
search_tool = {'google_search': {}}
tools=[search_tool]

# LANG = "de-DE"
LANG = "en-US"
# VOICE = "Kore"
VOICE = "Puck"

CONFIG = types.LiveConnectConfig(
    response_modalities=["AUDIO"],
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
)
# CONFIG = {"response_modalities": ["AUDIO"], "tools": [search_tool]}
# CONFIG = {"response_modalities": ["AUDIO"]}

MODEL = "models/gemini-2.0-flash-live-001"
# MODEL = "models/gemini-2.0-flash-live-preview-04-09" # Use with VertexAI

DEFAULT_MODE = "none"  # camera, screen

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        type=str,
        default=DEFAULT_MODE,
        help="pixels to stream from",
        choices=["camera", "screen", "none"],
    )
    args = parser.parse_args()
    
    # Create and run the LiveLoop with the appropriate parameters
    client = genai.Client(http_options={"api_version": "v1beta"}, api_key=api_key)
    main = LiveLoop(
        video_mode=args.mode,
        client=client,
        model=MODEL,
        config=CONFIG
    )
    asyncio.run(main.run())