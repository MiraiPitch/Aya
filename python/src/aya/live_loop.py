"""
Module containing the LiveLoop class for handling real-time audio/video communication
with the Gemini Live API.
"""

import asyncio
import base64
import io
import os
import traceback
import wave
import array
import struct
import datetime
import platform
import logging
import cv2
import pyaudio
import PIL.Image
import mss
from dotenv import load_dotenv

from google import genai
from google.genai import types

# Package imports
from aya.function_registry import execute_function

# Compatibility for Python < 3.11
import sys
if sys.version_info < (3, 11, 0):
    import taskgroup, exceptiongroup
    asyncio.TaskGroup = taskgroup.TaskGroup
    asyncio.ExceptionGroup = exceptiongroup.ExceptionGroup

# Suppress warnings about non-text parts in gemini responses
class _NoFunctionCallWarning(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if ("there are non-text parts in the response:" in message or
            "there are non-data parts in the response:" in message):
            return False
        else:
            return True

logging.getLogger("google_genai.types").addFilter(_NoFunctionCallWarning())

# Constants
FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024

DEFAULT_MODE = "none"  # screen, camera
DEFAULT_CONFIG = {"response_modalities": ["AUDIO"]}
DEFAULT_AUDIO_SOURCE = "microphone"  # microphone, computer, both
# Define a default system audio device index, set to None to auto-detect
DEFAULT_SYSTEM_AUDIO_DEVICE = None  # Set to a specific index to force using that device

# Initialize PyAudio
pya = pyaudio.PyAudio()

# Create conversation_logs directory if it doesn't exist
CONVERSATION_LOGS_DIR = "conversation_logs"
os.makedirs(CONVERSATION_LOGS_DIR, exist_ok=True)


class LiveLoop:
    def __init__(self, video_mode=DEFAULT_MODE, client=None, model=None, config=DEFAULT_CONFIG, 
                 initial_message=None, function_executor=None, audio_source=DEFAULT_AUDIO_SOURCE,
                 record_conversation=False, system_audio_device_index=DEFAULT_SYSTEM_AUDIO_DEVICE,
                 api_key=None):
        self.video_mode = video_mode
        self.model = model
        self.config = config
        self.initial_message = initial_message
        # Function executor is a callable that takes function_name and args
        # and returns a result. If None, the default execute_function from function_registry is used
        self.function_executor = function_executor or execute_function
        # Audio source can be 'microphone', 'computer', or 'both'
        self.audio_source = audio_source
        # If True, record the conversation to a wav file
        self.record_conversation = record_conversation
        # Optional manual override for system audio device index
        self.system_audio_device_index = system_audio_device_index
        # API key for Gemini API
        self.api_key = api_key
        
        # Initialize client if not provided
        self.client = client
        if self.client is None:
            self._initialize_client()

        print("--------------------------------")
        print(f"Audio source: {self.audio_source}")
        print(f"Video mode: {self.video_mode}")
        print(f"model: {self.model}")
        print(f"config: {self.config}")
        print("--------------------------------")

        # Verify audio_source is valid and handle audio loop prevention
        if self.audio_source not in ["none", "microphone", "computer", "both"]:
            raise ValueError("audio_source must be 'none', 'microphone', 'computer', or 'both'")
        
        # Check for potential audio loop if using computer audio and audio output
        if self.audio_source in ["computer", "both"] and "AUDIO" in self.config.response_modalities:
            raise ValueError("Cannot use computer audio as input when audio output is enabled. "
                             "This would create an audio feedback loop.")

        self.audio_in_queue = None
        self.out_queue = None
        self.recording_buffer = None

        self.session = None
        self.mic_stream = None
        self.system_stream = None
        self.recorder = None
        self.recording_file = None

        self.send_text_task = None
        self.receive_audio_task = None
        self.play_audio_task = None
        
    def _initialize_client(self):
        """Initialize the Gemini client with API key from parameters or environment"""
        # If API key wasn't provided, try to get it from environment
        if self.api_key is None:
            # Load environment variables if not already loaded
            load_dotenv()
            API_KEY_ENV_VAR = "GEMINI_API_KEY"
            self.api_key = os.getenv(API_KEY_ENV_VAR)
            
            if self.api_key is None:
                raise ValueError(f"API key not provided and {API_KEY_ENV_VAR} environment variable not set")
        
        # Initialize the client
        self.client = genai.Client(http_options={"api_version": "v1beta"}, api_key=self.api_key)

    def _initialize_recording(self):
        """Initialize audio recording if enabled"""
        if self.record_conversation:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            self.recording_file = os.path.join(CONVERSATION_LOGS_DIR, f"conversation_{timestamp}.wav")
            self.recording_buffer = []
            print(f"Recording conversation to {self.recording_file}")

    def _save_recording(self):
        """Save the recorded audio to a WAV file"""
        if self.record_conversation and self.recording_buffer:
            try:
                with wave.open(self.recording_file, 'wb') as wf:
                    wf.setnchannels(CHANNELS)
                    wf.setsampwidth(pya.get_sample_size(FORMAT))
                    wf.setframerate(SEND_SAMPLE_RATE)
                    wf.writeframes(b''.join(self.recording_buffer))
                print(f"Conversation saved to {self.recording_file}")
            except Exception as e:
                print(f"Error saving recording: {e}")

    async def send_text(self):
        while True:
            text = await asyncio.to_thread(
                input,
                "", # "message > "
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

    def _mix_audio(self, mic_data, system_data):
        """Mix microphone and system audio data"""
        if not mic_data or not system_data:
            return mic_data or system_data
        
        # Convert bytes to int16 arrays for mixing
        mic_array = array.array('h', mic_data)
        system_array = array.array('h', system_data)
        
        # Ensure both arrays are the same length
        length = min(len(mic_array), len(system_array))
        mic_array = mic_array[:length]
        system_array = system_array[:length]
        
        # Mix audio (simple averaging to prevent clipping)
        result = array.array('h', [0] * length)
        for i in range(length):
            # Mix with equal weighting, then scale to prevent clipping
            mixed_value = (mic_array[i] + system_array[i]) // 2
            result[i] = max(min(mixed_value, 32767), -32768)  # Clamp to int16 range
        
        return result.tobytes()

    def _get_system_audio_device(self):
        """Find an appropriate system audio capture device based on the platform"""
        # If a manual device index is specified, use it
        if self.system_audio_device_index is not None:
            try:
                dev_info = pya.get_device_info_by_index(self.system_audio_device_index)
                print(f"\nUsing manually specified system audio device: [{self.system_audio_device_index}] {dev_info.get('name')}")
                return self.system_audio_device_index
            except Exception as e:
                print(f"Error using specified system audio device index {self.system_audio_device_index}: {e}")
                print("Falling back to auto-detection")
                
        os_name = platform.system()
        
        # List all available audio devices for debugging
        print("\nAvailable audio devices:")
        for i in range(pya.get_device_count()):
            dev_info = pya.get_device_info_by_index(i)
            host_api = pya.get_host_api_info_by_index(dev_info.get('hostApi')).get('name', '')
            print(f"  [{i}] {dev_info.get('name')} - {host_api}")
            print(f"      Input channels: {dev_info.get('maxInputChannels')}, Output channels: {dev_info.get('maxOutputChannels')}")
        
        if os_name == "Windows":
            # First try WDM-KS Stereo Mix as it's often more reliable 
            for i in range(pya.get_device_count()):
                dev_info = pya.get_device_info_by_index(i)
                name = dev_info.get('name', '').lower()
                host_api = pya.get_host_api_info_by_index(dev_info.get('hostApi')).get('name', '')
                
                # Check for WDM-KS Stereo Mix (often most reliable)
                if (dev_info.get('maxInputChannels') > 0 and 
                    host_api == 'Windows WDM-KS' and
                    'stereo mix' in name):
                    print(f"\nSelected system audio device: [{i}] {dev_info.get('name')} - {host_api}")
                    return i
            
            # Then try regular Stereo Mix on any API
            for i in range(pya.get_device_count()):
                dev_info = pya.get_device_info_by_index(i)
                name = dev_info.get('name', '').lower()
                if dev_info.get('maxInputChannels') > 0 and 'stereo mix' in name:
                    print(f"\nSelected system audio device: [{i}] {dev_info.get('name')}")
                    return i
                    
            # Last try any WASAPI loopback device
            for i in range(pya.get_device_count()):
                dev_info = pya.get_device_info_by_index(i)
                name = dev_info.get('name', '').lower()
                host_api = pya.get_host_api_info_by_index(dev_info.get('hostApi')).get('name', '')
                
                # Check for WASAPI loopback device
                if (dev_info.get('maxInputChannels') > 0 and 
                    host_api == 'Windows WASAPI' and
                    ('loopback' in name or 'speaker' in name or 'output' in name)):
                    print(f"\nSelected system audio device: [{i}] {dev_info.get('name')} - {host_api}")
                    return i
            
            print("\nNo suitable system audio capture device found.")
            print("Please enable 'Stereo Mix' in Windows sound settings or install a loopback audio driver.")
            print("Instructions to enable Stereo Mix:")
            print("1. Right-click the sound icon in the system tray and select 'Sound settings'")
            print("2. Click 'Sound Control Panel'")
            print("3. Go to the 'Recording' tab")
            print("4. Right-click in the empty area and select 'Show Disabled Devices'")
            print("5. Right-click on 'Stereo Mix' and select 'Enable'")
            print("\nAlternatively, you can install a virtual audio cable software.")
            
            raise RuntimeError("No suitable system audio capture device found.")
        
        elif os_name == "Darwin":  # macOS
            print("\nSystem audio capture on macOS requires additional software.")
            print("Please install a virtual audio cable software like BlackHole or Loopback.")
            raise NotImplementedError("System audio capture on macOS requires additional software.")
        
        elif os_name == "Linux":
            print("\nSystem audio capture on Linux requires PulseAudio or JACK configuration.")
            print("You may need to install and configure tools like 'pactl' or 'pavucontrol'.")
            raise NotImplementedError("System audio capture on Linux requires additional configuration.")
        
        else:
            raise NotImplementedError(f"System audio capture on {os_name} is not supported.")

    async def listen_audio(self):
        """Capture audio based on the configured audio source"""
        if self.audio_source == "microphone":
            await self._listen_microphone()
        elif self.audio_source == "computer":
            await self._listen_system_audio()
        elif self.audio_source == "both":
            await self._listen_mixed_audio()

    async def _listen_microphone(self):
        """Capture audio from the microphone"""
        mic_info = pya.get_default_input_device_info()
        self.mic_stream = await asyncio.to_thread(
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
            data = await asyncio.to_thread(self.mic_stream.read, CHUNK_SIZE, **kwargs)
            
            # Save to recording buffer if enabled
            if self.record_conversation:
                self.recording_buffer.append(data)
                
            await self.out_queue.put({"data": data, "mime_type": "audio/pcm"})

    async def _listen_system_audio(self):
        """Capture audio from the system/computer"""
        try:
            system_device_index = self._get_system_audio_device()
            
            # Add extra debug information
            dev_info = pya.get_device_info_by_index(system_device_index)
            host_api = pya.get_host_api_info_by_index(dev_info.get('hostApi')).get('name', '')
            print(f"\nAttempting to open system audio device: [{system_device_index}] {dev_info.get('name')} - {host_api}")
            print(f"  Sample Rate: {SEND_SAMPLE_RATE}, Channels: {CHANNELS}, Format: {FORMAT}")
            
            # Get the device's default sample rate
            device_sample_rate = int(dev_info.get('defaultSampleRate', SEND_SAMPLE_RATE))
            print(f"  Device default sample rate: {device_sample_rate}")
            
            # Try different configurations in order of preference
            configs_to_try = [
                # First try with our desired settings
                {"rate": SEND_SAMPLE_RATE, "buffer": CHUNK_SIZE},
                # Then try with device's default sample rate
                {"rate": device_sample_rate, "buffer": CHUNK_SIZE},
                # Try larger buffer sizes
                {"rate": SEND_SAMPLE_RATE, "buffer": CHUNK_SIZE * 2},
                {"rate": device_sample_rate, "buffer": CHUNK_SIZE * 2},
                # Try even larger buffer as last resort
                {"rate": SEND_SAMPLE_RATE, "buffer": CHUNK_SIZE * 4},
                {"rate": device_sample_rate, "buffer": CHUNK_SIZE * 4},
            ]
            
            for i, config in enumerate(configs_to_try):
                try:
                    print(f"Trying configuration {i+1}/{len(configs_to_try)}: "
                          f"Sample rate: {config['rate']}, Buffer size: {config['buffer']}")
                    
                    self.system_stream = await asyncio.to_thread(
                        pya.open,
                        format=FORMAT,
                        channels=CHANNELS,
                        rate=config['rate'],
                        input=True,
                        input_device_index=system_device_index,
                        frames_per_buffer=config['buffer'],
                    )
                    
                    # If we get here, the stream opened successfully
                    print(f"Successfully opened system audio stream with configuration {i+1}!")
                    
                    # Store the actual rate used for resampling if needed
                    self.system_sample_rate = config['rate']
                    self.system_buffer_size = config['buffer']
                    break
                    
                except Exception as e:
                    print(f"Failed with configuration {i+1}: {e}")
                    if i == len(configs_to_try) - 1:
                        # Last attempt failed
                        raise RuntimeError(f"Could not open system audio device after trying {len(configs_to_try)} configurations")
            
            if __debug__:
                kwargs = {"exception_on_overflow": False}
            else:
                kwargs = {}
                
            while True:
                try:
                    data = await asyncio.to_thread(self.system_stream.read, self.system_buffer_size, **kwargs)
                    
                    # Resample if needed
                    if self.system_sample_rate != SEND_SAMPLE_RATE:
                        # This is a naive resampling implementation - in production you would want to use a proper 
                        # resampling library like librosa, scipy, etc. with better quality
                        print(f"Warning: Using naive resampling from {self.system_sample_rate} to {SEND_SAMPLE_RATE}")
                        # Just for initial testing, we'll use a very simple approach
                        data = self._simple_resample(data, self.system_sample_rate, SEND_SAMPLE_RATE)
                    
                    # Save to recording buffer if enabled
                    if self.record_conversation:
                        self.recording_buffer.append(data)
                        
                    await self.out_queue.put({"data": data, "mime_type": "audio/pcm"})
                except Exception as e:
                    print(f"Error reading from system audio stream: {e}")
                    break
                
        except RuntimeError as e:
            print(f"Error: {e}")
            print("Falling back to microphone audio")
            await self._listen_microphone()
        except Exception as e:
            print(f"Error capturing system audio: {e}")
            print("Falling back to microphone audio")
            await self._listen_microphone()
            
    def _simple_resample(self, audio_data, from_rate, to_rate):
        """Very simple audio resampling for testing purposes only.
        This is not high quality and should be replaced with a proper resampling library."""
        # Convert bytes to int16 samples
        samples = array.array('h', audio_data)
        
        if from_rate == to_rate:
            return audio_data
            
        # Simple ratio-based resampling
        ratio = from_rate / to_rate
        
        if ratio == 2.0:  # Simple case: downsample by 2
            # Take every other sample
            resampled = array.array('h', samples[::2])
            return resampled.tobytes()
        elif ratio == 0.5:  # Simple case: upsample by 2
            # Duplicate each sample
            resampled = array.array('h')
            for sample in samples:
                resampled.append(sample)
                resampled.append(sample)
            return resampled.tobytes()
        else:
            # For other ratios, use linear interpolation (still not great quality)
            output_length = int(len(samples) / ratio)
            resampled = array.array('h', [0] * output_length)
            
            for i in range(output_length):
                src_idx = i * ratio
                src_idx_int = int(src_idx)
                fraction = src_idx - src_idx_int
                
                if src_idx_int < len(samples) - 1:
                    # Linear interpolation between two adjacent samples
                    sample1 = samples[src_idx_int]
                    sample2 = samples[src_idx_int + 1]
                    resampled[i] = int(sample1 * (1 - fraction) + sample2 * fraction)
                else:
                    # Edge case at the end
                    resampled[i] = samples[-1]
                    
            return resampled.tobytes()

    async def _listen_mixed_audio(self):
        """Capture and mix audio from both microphone and system"""
        try:
            # Set up microphone stream
            mic_info = pya.get_default_input_device_info()
            self.mic_stream = await asyncio.to_thread(
                pya.open,
                format=FORMAT,
                channels=CHANNELS,
                rate=SEND_SAMPLE_RATE,
                input=True,
                input_device_index=mic_info["index"],
                frames_per_buffer=CHUNK_SIZE,
            )
            
            # Set up system audio stream with better error handling
            system_device_index = self._get_system_audio_device()
            
            # Add extra debug information
            dev_info = pya.get_device_info_by_index(system_device_index)
            host_api = pya.get_host_api_info_by_index(dev_info.get('hostApi')).get('name', '')
            print(f"\nAttempting to open system audio device for mixed mode: [{system_device_index}] {dev_info.get('name')} - {host_api}")
            print(f"  Sample Rate: {SEND_SAMPLE_RATE}, Channels: {CHANNELS}, Format: {FORMAT}")
            
            # Get the device's default sample rate
            device_sample_rate = int(dev_info.get('defaultSampleRate', SEND_SAMPLE_RATE))
            print(f"  Device default sample rate: {device_sample_rate}")
            
            # Try different configurations in order of preference
            configs_to_try = [
                # First try with our desired settings
                {"rate": SEND_SAMPLE_RATE, "buffer": CHUNK_SIZE},
                # Then try with device's default sample rate
                {"rate": device_sample_rate, "buffer": CHUNK_SIZE},
                # Try larger buffer sizes
                {"rate": SEND_SAMPLE_RATE, "buffer": CHUNK_SIZE * 2},
                {"rate": device_sample_rate, "buffer": CHUNK_SIZE * 2},
                # Try even larger buffer as last resort
                {"rate": SEND_SAMPLE_RATE, "buffer": CHUNK_SIZE * 4},
                {"rate": device_sample_rate, "buffer": CHUNK_SIZE * 4},
            ]
            
            for i, config in enumerate(configs_to_try):
                try:
                    print(f"Trying configuration {i+1}/{len(configs_to_try)}: "
                          f"Sample rate: {config['rate']}, Buffer size: {config['buffer']}")
                    
                    self.system_stream = await asyncio.to_thread(
                        pya.open,
                        format=FORMAT,
                        channels=CHANNELS,
                        rate=config['rate'],
                        input=True,
                        input_device_index=system_device_index,
                        frames_per_buffer=config['buffer'],
                    )
                    
                    # If we get here, the stream opened successfully
                    print(f"Successfully opened system audio stream with configuration {i+1}!")
                    
                    # Store the actual rate used for resampling if needed
                    self.system_sample_rate = config['rate']
                    self.system_buffer_size = config['buffer']
                    break
                    
                except Exception as e:
                    print(f"Failed with configuration {i+1}: {e}")
                    if i == len(configs_to_try) - 1:
                        # Last attempt failed
                        raise RuntimeError(f"Could not open system audio device after trying {len(configs_to_try)} configurations")
            
            print("Successfully opened mixed audio streams!")
            
            if __debug__:
                kwargs = {"exception_on_overflow": False}
            else:
                kwargs = {}
                
            while True:
                try:
                    mic_data = await asyncio.to_thread(self.mic_stream.read, CHUNK_SIZE, **kwargs)
                    system_data = await asyncio.to_thread(self.system_stream.read, self.system_buffer_size, **kwargs)
                    
                    # Resample system audio if needed
                    if self.system_sample_rate != SEND_SAMPLE_RATE:
                        system_data = self._simple_resample(system_data, self.system_sample_rate, SEND_SAMPLE_RATE)
                    
                    # Mix the audio
                    mixed_data = self._mix_audio(mic_data, system_data)
                    
                    # Save to recording buffer if enabled
                    if self.record_conversation:
                        self.recording_buffer.append(mixed_data)
                        
                    await self.out_queue.put({"data": mixed_data, "mime_type": "audio/pcm"})
                except Exception as e:
                    print(f"Error reading or mixing audio streams: {e}")
                    break
                
        except Exception as e:
            print(f"Error capturing mixed audio: {e}")
            # Fall back to microphone if mixing fails
            print("Falling back to microphone audio")
            await self._listen_microphone()

    async def handle_tool_calls(self, tool_calls):
        """Handle tool calls from the Gemini API"""
        function_responses = []

        print(f"[Tool Call]")
        
        for tool_call in tool_calls:
            if hasattr(tool_call, 'function_call'):
                fc = tool_call.function_call
                function_name = fc.name
                args = {}
                if hasattr(fc, 'args') and fc.args:
                    args = fc.args
                
                try:
                    # If a custom function executor was provided, use it
                    if self.function_executor:
                        result = self.function_executor(function_name, args)
                    # Otherwise use the FunctionRegistry
                    else:
                        result = execute_function(function_name, args)
                    
                    self.output_text(f"[Function {function_name}] Result: {result}")
                    
                    # Create function response
                    function_response = types.FunctionResponse(
                        id=fc.id,
                        name=function_name,
                        response=result
                    )
                    function_responses.append(function_response)
                    
                except Exception as e:
                    error_result = {"error": f"Error executing {function_name}: {repr(e)}"}
                    self.output_text(f"[Function Error] {error_result}")
                    
                    # Create error response
                    function_response = types.FunctionResponse(
                        id=fc.id,
                        name=function_name,
                        response=error_result
                    )
                    function_responses.append(function_response)
        
        # Send all function responses back to the model
        if function_responses:
            await self.session.send_tool_response(function_responses=function_responses)

    def output_text(self, text):
        # Can be overridden to output text elsewhere, e.g. to a GUI
        print(text, end="")

    async def receive_text(self):
        """Background task to handle text responses and tool calls."""
        while True:
            turn = self.session.receive()
            async for chunk in turn:
                if chunk.server_content:
                    if chunk.text is not None:
                        self.output_text(chunk.text)

                    model_turn = chunk.server_content.model_turn
                    if model_turn:
                        for part in model_turn.parts:
                            if part.executable_code is not None:
                                print(f"Executing code: \n```\n{part.executable_code.code}\n```")

                            if part.code_execution_result is not None:
                                print(f"Code execution result: \n```\n{part.code_execution_result.output}\n```")
                
                # Handle tool calls
                elif chunk.tool_call:
                    await self.handle_tool_calls(chunk.tool_call)

    async def receive_audio(self):
        """Background task to handle audio responses and tool calls."""
        while True:
            turn = self.session.receive()
            async for chunk in turn:
                if chunk.server_content:
                    if chunk.text is not None:
                        self.output_text(chunk.text)
                    
                    if chunk.data is not None:
                        self.audio_in_queue.put_nowait(chunk.data)

                    model_turn = chunk.server_content.model_turn
                    if model_turn:
                        for part in model_turn.parts:
                            if part.executable_code is not None:
                                print(f"Executing code: \n```\n{part.executable_code.code}\n```")

                            if part.code_execution_result is not None:
                                print(f"Code execution result: \n```\n{part.code_execution_result.output}\n```")
                
                # Handle tool calls
                elif chunk.tool_call:
                    await self.handle_tool_calls(chunk.tool_call)

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
            
            # Append model's audio to recording if enabled
            if self.record_conversation:
                # Need to resample from RECEIVE_SAMPLE_RATE to SEND_SAMPLE_RATE for consistent recording
                if RECEIVE_SAMPLE_RATE != SEND_SAMPLE_RATE:
                    # Simple resampling: just take every other sample if downsampling by half
                    if RECEIVE_SAMPLE_RATE == 2 * SEND_SAMPLE_RATE:
                        # Convert bytes to samples, take every other sample, convert back to bytes
                        samples = struct.unpack(f"{len(bytestream)//2}h", bytestream)
                        resampled = struct.pack(f"{len(samples)//2}h", *samples[::2])
                        self.recording_buffer.append(resampled)
                    else:
                        # For other rates, just append as-is (this will cause speed/pitch issues)
                        self.recording_buffer.append(bytestream)
                else:
                    self.recording_buffer.append(bytestream)

    async def run(self):
        try:
            # Initialize recording if enabled
            if self.record_conversation:
                self._initialize_recording()
                
            async with (
                self.client.aio.live.connect(model=self.model, config=self.config) as session,
                asyncio.TaskGroup() as tg,
            ):
                self.session = session

                self.audio_in_queue = asyncio.Queue()
                self.out_queue = asyncio.Queue(maxsize=5)

                tg.create_task(self.send_realtime())

                # MODEL AUDIO INPUT
                if self.audio_source != "none":
                    tg.create_task(self.listen_audio())

                # MODEL VIDEO INPUT
                if self.video_mode == "camera":
                    tg.create_task(self.get_frames())
                elif self.video_mode == "screen":
                    tg.create_task(self.get_screen())

                # MODEL OUTPUT
                if "AUDIO" in self.config.response_modalities:
                    tg.create_task(self.receive_audio())
                    tg.create_task(self.play_audio())
                elif "TEXT" in self.config.response_modalities:
                    tg.create_task(self.receive_text())
                else:
                    raise ValueError("Invalid response modality")

                if self.initial_message:
                    print(f"Sending initial message: {self.initial_message}")
                    await self.session.send(input=self.initial_message, end_of_turn=True)
                send_text_task = tg.create_task(self.send_text())

                await send_text_task
                raise asyncio.CancelledError("User requested exit")

        except asyncio.CancelledError:
            pass
        except ExceptionGroup as EG:
            traceback.print_exception(EG)
        finally:
            # Clean up audio streams
            if self.mic_stream:
                self.mic_stream.close()
            if self.system_stream:
                self.system_stream.close()
                
            # Save recording if enabled
            if self.record_conversation:
                self._save_recording() 