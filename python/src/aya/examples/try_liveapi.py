"""
Install:
``` 
conda create -n gemini-live-api python=3.12 -y
conda activate gemini-live-api
pip install google-genai pyaudio
```
Ensure the `GOOGLE_API_KEY` environment variable is set or in .env file.
"""

import asyncio
import os
import traceback
import pyaudio
from google import genai

from dotenv import load_dotenv
load_dotenv()
API_KEY_ENV_VAR = "GEMINI_API_KEY"
api_key = os.getenv(API_KEY_ENV_VAR)

FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024

SYSTEM_INSTRUCTION = """
You are a helpful AI assistant. Respond concisely and clearly to the user's questions and requests.
""".strip()
MODEL = "models/gemini-2.0-flash-live-001" # More reliable, but lower quality audio
# MODEL = "gemini-2.5-flash-preview-native-audio-dialog" # Use this for better audio quality
CONFIG = {
    "response_modalities": ["AUDIO"],
    "system_instruction": SYSTEM_INSTRUCTION
}

client = genai.Client(http_options={"api_version": "v1beta"}, api_key=api_key)
pya = pyaudio.PyAudio()

class AudioLoop:
    def __init__(self):
        self.audio_in_queue = None
        self.audio_out_queue = None
        self.session = None

    async def send_audio(self):
        while True:
            msg = await self.audio_out_queue.get()
            await self.session.send_realtime_input(audio=msg)

    async def listen_audio(self):
        mic_info = pya.get_default_input_device_info()
        self.audio_stream = await asyncio.to_thread(
            pya.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=SEND_SAMPLE_RATE,
            input=True,
            input_device_index=mic_info["index"],
            frames_per_buffer=CHUNK_SIZE,
        )
        if __debug__:
            kwargs = {"exception_on_overflow": False}
        else:
            kwargs = {}
        while True:
            data = await asyncio.to_thread(self.audio_stream.read, CHUNK_SIZE, **kwargs)
            await self.audio_out_queue.put({"data": data, "mime_type": "audio/pcm"})

    async def receive_audio(self):
        "Background task to reads from the websocket and write pcm chunks to the output queue"
        while True:
            turn = self.session.receive()
            async for response in turn:
                if data := response.data:
                    self.audio_in_queue.put_nowait(data)
                    continue
                if text := response.text:
                    print(text, end="")

            # If you interrupt the model, it sends a turn_complete.
            # So empty out the audio queue: it may have loaded more audio than has played yet.
            while not self.audio_in_queue.empty():
                self.audio_in_queue.get_nowait()

    async def play_audio(self):
        stream = await asyncio.to_thread(
            pya.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=RECEIVE_SAMPLE_RATE,
            output=True,
        )
        while True:
            bytestream = await self.audio_in_queue.get()
            await asyncio.to_thread(stream.write, bytestream)

    async def run(self):
        try:
            async with (
                client.aio.live.connect(model=MODEL, config=CONFIG) as session,
                asyncio.TaskGroup() as tg,
            ):
                self.session = session

                self.audio_in_queue = asyncio.Queue()
                self.audio_out_queue = asyncio.Queue(maxsize=5)

                tg.create_task(self.send_audio())
                tg.create_task(self.listen_audio())
                tg.create_task(self.receive_audio())
                tg.create_task(self.play_audio())

                # Send initial message
                await asyncio.sleep(1)
                await self.session.send_realtime_input(text="Hello!")

                # Wait for KeyboardInterrupt
                await asyncio.Future()

        except asyncio.CancelledError:
            pass
        except ExceptionGroup as EG:
            self.audio_stream.close()
            traceback.print_exception(EG)

if __name__ == "__main__":
    main = AudioLoop()
    asyncio.run(main.run())