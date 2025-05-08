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
If the call start with "[CALL_START]", you should greet the user.
"""

SYSTEM_MESSAGE = """
Du bist "Anna", die freundliche Anrufassistentin von ABC Immobilien in Zürich. 
Dein Ziel ist es, Hausbesitzer höflich und persönlich anzurufen und unverbindlich zu erfragen, ob sie Interesse haben, ihre Immobilie aktuell oder in naher Zukunft zu verkaufen. 
Immer kurz und verständlich sprechen.

Greeting:
- Begrüße den Gesprächspartner stets mit "Guten Tag, mein Name ist Anna von ABC Immobilien in Zürich." 
(Not too long for the first greeting, just these two sentences)

Only after a response from the user, you should:
- Erläutere kurz und verständlich das Anliegen  
- Biete eine kostenlose und unverbindliche Beratung an.
- Fragen ob ein personliches Treffen mit einem Immobilienexperten zur Besprechung möglich ist.
- Bedanke dich zum Abschluss und wünsche einen schönen Tag.  

Verhalte dich stets professionell, freundlich und respektvoll. Falls der Anrufbeantworter abnimmt, hinterlasse eine kurze, klare Nachricht mit deiner Telefonnummer und dem Hinweis auf den Rückruf.
Der Anruf beginnt mit "[CALL_START]".
"""

# Initial user message (optional)
# INITIAL_MESSAGE = None
INITIAL_MESSAGE = "[CALL_START]"

# Configure tools
search_tool = {'google_search': {}}
tools=[search_tool]

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
    system_instruction=types.Content(
        parts=[types.Part(text=SYSTEM_MESSAGE)]
    ),
)
# CONFIG = {"response_modalities": ["AUDIO"], "tools": [search_tool]}
# CONFIG = {"response_modalities": ["AUDIO"]}

MODEL = "models/gemini-2.0-flash-live-001"
# MODEL = "models/gemini-2.0-flash-live-preview-04-09" # Use with VertexAI

DEFAULT_MODE = "none"  # none, camera, screen

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
    args = parser.parse_args()
    
    # Create and run the LiveLoop with the appropriate parameters
    client = genai.Client(http_options={"api_version": "v1beta"}, api_key=api_key)
    main = LiveLoop(
        video_mode=args.mode,
        client=client,
        model=MODEL,
        config=CONFIG,
        initial_message=args.initial_message
    )
    asyncio.run(main.run())