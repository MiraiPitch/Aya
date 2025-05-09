"""
Module containing the LiveLoop class for handling real-time audio/video communication
with the Gemini Live API.
"""

import asyncio
import base64
import io
import os
import traceback

import cv2
import pyaudio
import PIL.Image
import mss

from google import genai
from google.genai import types

# Local imports
from function_registry import execute_function

# Compatibility for Python < 3.11
import sys
if sys.version_info < (3, 11, 0):
    import taskgroup, exceptiongroup
    asyncio.TaskGroup = taskgroup.TaskGroup
    asyncio.ExceptionGroup = exceptiongroup.ExceptionGroup

# Constants
FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024

DEFAULT_MODE = "none"  # screen, camera
DEFAULT_CONFIG = {"response_modalities": ["AUDIO"]}

# Initialize PyAudio
pya = pyaudio.PyAudio()


class LiveLoop:
    def __init__(self, video_mode=DEFAULT_MODE, client=None, model=None, config=DEFAULT_CONFIG, 
                 initial_message=None, function_executor=None):
        self.video_mode = video_mode
        self.client = client
        self.model = model
        self.config = config
        self.initial_message = initial_message
        # Function executor is a callable that takes function_name and args
        # and returns a result. If None, the default execute_function from function_registry is used
        self.function_executor = function_executor or execute_function

        self.audio_in_queue = None
        self.out_queue = None

        self.session = None
        self.audio_stream = None

        self.send_text_task = None
        self.receive_audio_task = None
        self.play_audio_task = None

    async def send_text(self):
        while True:
            text = await asyncio.to_thread(
                input,
                "message > ",
            )
            if text.lower() == "q":
                break
            await self.session.send(input=text or ".", end_of_turn=True)
            # await self.session.send_realtime_input(input=text or ".", end_of_turn=True)

    def _get_frame(self, cap):
        # Read the frame
        ret, frame = cap.read()
        # Check if the frame was read successfully
        if not ret:
            return None
        # Fix: Convert BGR to RGB color space
        # OpenCV captures in BGR but PIL expects RGB format
        # This prevents the blue tint in the video feed
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = PIL.Image.fromarray(frame_rgb)  # Now using RGB frame
        img.thumbnail([1024, 1024])

        image_io = io.BytesIO()
        img.save(image_io, format="jpeg")
        image_io.seek(0)

        mime_type = "image/jpeg"
        image_bytes = image_io.read()
        return {"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode()}

    async def get_frames(self):
        # This takes about a second, and will block the whole program
        # causing the audio pipeline to overflow if you don't to_thread it.
        cap = await asyncio.to_thread(
            cv2.VideoCapture, 0
        )  # 0 represents the default camera

        while True:
            frame = await asyncio.to_thread(self._get_frame, cap)
            if frame is None:
                break

            await asyncio.sleep(1.0)

            await self.out_queue.put(frame)

        # Release the VideoCapture object
        cap.release()

    def _get_screen(self):
        sct = mss.mss()
        monitor = sct.monitors[0]

        i = sct.grab(monitor)

        mime_type = "image/jpeg"
        image_bytes = mss.tools.to_png(i.rgb, i.size)
        img = PIL.Image.open(io.BytesIO(image_bytes))

        image_io = io.BytesIO()
        img.save(image_io, format="jpeg")
        image_io.seek(0)

        image_bytes = image_io.read()
        return {"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode()}

    async def get_screen(self):
        while True:
            frame = await asyncio.to_thread(self._get_screen)
            if frame is None:
                break

            await asyncio.sleep(1.0)

            await self.out_queue.put(frame)

    async def send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            await self.session.send(input=msg)
            # await self.session.send_realtime_input(input=msg)

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
            await self.out_queue.put({"data": data, "mime_type": "audio/pcm"})

    async def handle_tool_calls(self, tool_calls):
        """Handle tool calls and return function responses."""
        function_responses = []
        for fc in tool_calls.function_calls:
            # Execute the function using the provided executor
            result = self.function_executor(fc.name, fc.args)
            
            function_response = types.FunctionResponse(
                id=fc.id,
                name=fc.name,
                response=result
            )
            function_responses.append(function_response)
        
        # Send all function responses back to the model
        await self.session.send_tool_response(function_responses=function_responses)

    async def receive_text(self):
        """Background task to handle text responses and tool calls."""
        while True:
            turn = self.session.receive()
            async for response in turn:
                if text := response.text:
                    print(text, end="")
                
                # Handle tool calls
                if response.tool_call:
                    await self.handle_tool_calls(response.tool_call)

    async def receive_audio(self):
        """Background task to handle audio responses and tool calls."""
        while True:
            turn = self.session.receive()
            async for response in turn:
                if data := response.data:
                    self.audio_in_queue.put_nowait(data)
                    continue
                if text := response.text:
                    print(text, end="")
                
                # Handle tool calls
                if response.tool_call:
                    await self.handle_tool_calls(response.tool_call)

            # If you interrupt the model, it sends a turn_complete.
            # For interruptions to work, we need to stop playback.
            # So empty out the audio queue because it may have loaded
            # much more audio than has played yet.
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
                self.client.aio.live.connect(model=self.model, config=self.config) as session,
                asyncio.TaskGroup() as tg,
            ):
                self.session = session

                self.audio_in_queue = asyncio.Queue()
                self.out_queue = asyncio.Queue(maxsize=5)

                tg.create_task(self.send_realtime())
                tg.create_task(self.listen_audio())
                if self.video_mode == "camera":
                    tg.create_task(self.get_frames())
                elif self.video_mode == "screen":
                    tg.create_task(self.get_screen())

                # Choose the appropriate receive function based on response modality
                if "AUDIO" in self.config.response_modalities:
                    tg.create_task(self.receive_audio())
                    tg.create_task(self.play_audio())
                else:
                    tg.create_task(self.receive_text())

                if self.initial_message:
                    print(f"Sending initial message: {self.initial_message}")
                    await self.session.send(input=self.initial_message, end_of_turn=True)
                send_text_task = tg.create_task(self.send_text())

                await send_text_task
                raise asyncio.CancelledError("User requested exit")

        except asyncio.CancelledError:
            pass
        except ExceptionGroup as EG:
            if self.audio_stream:
                self.audio_stream.close()
            traceback.print_exception(EG) 