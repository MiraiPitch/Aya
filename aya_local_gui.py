import asyncio
import os
import sys
import tkinter as tk
from tkinter import ttk, scrolledtext
from dotenv import load_dotenv

from google import genai
from google.genai import types

# Local imports
from live_loop import LiveLoop
from function_registry import FunctionRegistry, get_declarations_for_functions

# Import tool functions for the GUI
from gemini_tools import print_to_console

# Load environment variables and API key
load_dotenv()
API_KEY_ENV_VAR = "GEMINI_API_KEY"
api_key = os.getenv(API_KEY_ENV_VAR)

# Default system message
DEFAULT_SYSTEM_MESSAGE = """
You are Aya, an AI assistant with a friendly and helpful personality. 
You should be concise, clear, and engaging in your responses. 
When appropriate, you can use humor and show personality while maintaining professionalism.
Always aim to be helpful while respecting user privacy and safety.

IMPORTANT: While you respond normally to the user in the main conversation, you should also provide helpful hints about how the user could speak more naturally and effectively. 
provide these hints only if the user has said something clearly unnatural or unacceptably.
Send these hints using the write_live_hints function. 
These hints should be very concise tips to improve communication style, clarity, or naturalness of speech.
Prepend the hints with "-----\n"

If the call starts with "[CALL_START]", you should greet the user.
"""

# DEFAULT_SYSTEM_MESSAGE = """
# You are a sales assistant AI participating in a live call. 
# Your role is to listen and provide short, impactful keyword-based advice to help the speaker improve their sales technique.
# Write this advice directly to the console—do not speak or interrupt the call.
# Keep your messages concise, action-oriented, and professional. Use keywords or short phrases (e.g., "Build rapport", "Ask open-ended question", "Handle objection").
# Do not provide full sentences unless necessary for clarity.
# If the call starts with "[CALL_START]", begin monitoring silently.
# Always aim to support better performance without disrupting the conversation.
# """

# Default languages and voices
LANGUAGES = {
    "English (US)": "en-US",
    "German": "de-DE",
    # Add more languages as needed
}

# Voice options
VOICES = {
    "Leda (Female)": "Leda",
    "Kore (Female)": "Kore", 
    "Zephyr (Female)": "Zephyr",
    "Puck (Male)": "Puck",
    "Charon (Male)": "Charon",
    "Fenrir (Male)": "Fenrir",
    "Orus (Male)": "Orus"
}

# Audio source options
AUDIO_SOURCES = ["microphone", "computer", "both"]

# Video mode options
VIDEO_MODES = ["none", "camera", "screen"]

# Output modalities
MODALITIES = ["TEXT", "AUDIO"]

# Define the GUI message tool
@FunctionRegistry.register()
def write_message_to_gui(message: str) -> dict:
    """
    Writes a message to the GUI message area.
    
    :param message: The message to display in the GUI
    :return: Result confirmation
    """
    # This will be populated with the actual function in the AyaGUI class
    # Implementation injected at runtime
    return {"result": f"Message displayed: {message}"}

# Define the live hints tool
@FunctionRegistry.register()
def write_live_hints(hint: str) -> dict:
    """
    Writes a communication hint to the hints area of the GUI.
    Use this to provide real-time feedback on how the user could improve their communication style.
    
    :param hint: A concise tip or hint about how to speak more naturally or effectively
    :return: Result confirmation
    """
    # This will be populated with the actual function in the AyaGUI class
    # Implementation injected at runtime
    return {"result": f"Hint displayed: {hint}"}

class AyaGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Aya AI Assistant")
        self.root.geometry("800x800")
        self.root.state('zoomed')  # Start in full screen mode
        
        # Set style
        self.style = ttk.Style()
        self.style.configure("TButton", padding=6, relief="flat")
        self.style.configure("TFrame", background="#f0f0f0")
        
        # Configure main frame
        self.main_frame = ttk.Frame(root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Live loop instance and task
        self.live_loop = None
        self.conversation_task = None
        self.loop = asyncio.new_event_loop()
        
        # Setup UI components
        self.setup_config_section()
        self.setup_message_section()
        self.setup_control_section()
        
        # Inject the GUI message function implementation
        self.inject_write_message_function()
        
    def setup_config_section(self):
        # Configuration section frame
        config_frame = ttk.LabelFrame(self.main_frame, text="Configuration")
        config_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # System message
        ttk.Label(config_frame, text="System Message:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.system_message = scrolledtext.ScrolledText(config_frame, height=4, width=70, wrap=tk.WORD)
        self.system_message.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=5)
        self.system_message.insert(tk.END, DEFAULT_SYSTEM_MESSAGE)
        
        # Language selection
        ttk.Label(config_frame, text="Language:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.language_var = tk.StringVar(value=list(LANGUAGES.keys())[0])
        language_combo = ttk.Combobox(config_frame, textvariable=self.language_var, values=list(LANGUAGES.keys()), state="readonly")
        language_combo.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Voice selection
        ttk.Label(config_frame, text="Voice:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.voice_var = tk.StringVar(value=list(VOICES.keys())[0])
        voice_combo = ttk.Combobox(config_frame, textvariable=self.voice_var, values=list(VOICES.keys()), state="readonly")
        voice_combo.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Response modality
        ttk.Label(config_frame, text="Response Type:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.modality_var = tk.StringVar(value=MODALITIES[0])  # Default to TEXT
        modality_combo = ttk.Combobox(config_frame, textvariable=self.modality_var, values=MODALITIES, state="readonly")
        modality_combo.grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)

        # Audio source selection
        ttk.Label(config_frame, text="Audio Source:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        self.audio_source_var = tk.StringVar(value=AUDIO_SOURCES[0])  # Default to microphone
        audio_source_combo = ttk.Combobox(config_frame, textvariable=self.audio_source_var, values=AUDIO_SOURCES, state="readonly")
        audio_source_combo.grid(row=4, column=1, sticky=tk.W, padx=5, pady=5)

        # Video mode selection
        ttk.Label(config_frame, text="Video Mode:").grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        self.video_mode_var = tk.StringVar(value=VIDEO_MODES[0])  # Default to none
        video_mode_combo = ttk.Combobox(config_frame, textvariable=self.video_mode_var, values=VIDEO_MODES, state="readonly")
        video_mode_combo.grid(row=5, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Audio input section
        audio_frame = ttk.LabelFrame(config_frame, text="Audio Input")
        audio_frame.grid(row=6, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=5)
        
        # Audio input checkbox 
        self.use_mic_var = tk.BooleanVar(value=True)
        mic_checkbox = ttk.Checkbutton(audio_frame, text="Process Microphone Input", variable=self.use_mic_var)
        mic_checkbox.pack(side=tk.LEFT, padx=5, pady=5)
        
        # Help text for microphone
        ttk.Label(audio_frame, 
                 text="Enable this to process your microphone audio in the conversation. When disabled, audio will still be captured but not processed.", 
                 wraplength=400).pack(side=tk.LEFT, padx=10, pady=5)
        
        # Configure grid columns
        config_frame.columnconfigure(1, weight=1)
        
    def setup_message_section(self):
        # Message section frame
        message_frame = ttk.LabelFrame(self.main_frame, text="Messages")
        message_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Split frame for messages and hints
        split_frame = ttk.Frame(message_frame)
        split_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Left side - Message display area
        msg_frame = ttk.LabelFrame(split_frame, text="Conversation")
        msg_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.message_area = scrolledtext.ScrolledText(msg_frame, height=10, width=40, wrap=tk.WORD)
        self.message_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.message_area.config(state=tk.DISABLED)
        
        # Right side - Hints display area
        hint_frame = ttk.LabelFrame(split_frame, text="Communication Hints")
        hint_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.hints_area = scrolledtext.ScrolledText(hint_frame, height=10, width=30, wrap=tk.WORD)
        self.hints_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.hints_area.config(state=tk.DISABLED)
        
        # Status indicators
        status_frame = ttk.Frame(message_frame)
        status_frame.pack(fill=tk.X, padx=5, pady=2)
        
        # Mic status
        self.mic_status_var = tk.StringVar(value="Microphone: Inactive")
        ttk.Label(status_frame, textvariable=self.mic_status_var).pack(side=tk.LEFT, padx=5)
        
        # Connection status
        self.connection_status_var = tk.StringVar(value="Connection: Disconnected")
        ttk.Label(status_frame, textvariable=self.connection_status_var).pack(side=tk.LEFT, padx=5)
        
        # User message input area
        input_frame = ttk.Frame(message_frame)
        input_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(input_frame, text="Message:").pack(side=tk.LEFT, padx=5)
        self.user_input = ttk.Entry(input_frame, width=50)
        self.user_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        send_button = ttk.Button(input_frame, text="Send", command=self.send_message)
        send_button.pack(side=tk.RIGHT, padx=5)
        
        # Bind Enter key to send message
        self.user_input.bind("<Return>", lambda event: self.send_message())
        
    def setup_control_section(self):
        # Control buttons frame
        control_frame = ttk.Frame(self.main_frame)
        control_frame.pack(fill=tk.X, padx=5, pady=10)
        
        # Start/Stop buttons
        self.start_button = ttk.Button(control_frame, text="Start Conversation", command=self.start_conversation)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(control_frame, text="Stop Conversation", command=self.stop_conversation, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        # Clear buttons
        clear_all_button = ttk.Button(control_frame, text="Clear All", command=self.clear_all)
        clear_all_button.pack(side=tk.RIGHT, padx=5)
        
        clear_messages_button = ttk.Button(control_frame, text="Clear Messages", command=self.clear_messages)
        clear_messages_button.pack(side=tk.RIGHT, padx=5)
        
        clear_hints_button = ttk.Button(control_frame, text="Clear Hints", command=self.clear_hints)
        clear_hints_button.pack(side=tk.RIGHT, padx=5)
    
    def inject_write_message_function(self):
        """Inject the actual implementation for the write_message_to_gui function"""
        def _write_message_impl(message):
            self.display_message("Aya", message)
            return {"result": f"Message displayed: {message}"}
        
        # Replace the function in the registry with our implementation
        FunctionRegistry._functions["write_message_to_gui"]["implementation"] = _write_message_impl
        
        # Also inject implementation for the write_live_hints function
        def _write_hints_impl(hint):
            self.display_hint(hint)
            return {"result": f"Hint displayed: {hint}"}
        
        # Replace the function in the registry with our implementation
        FunctionRegistry._functions["write_live_hints"]["implementation"] = _write_hints_impl
    
    def display_message(self, sender, message):
        """Display a message in the message area with the sender name"""
        self.message_area.config(state=tk.NORMAL)
        self.message_area.insert(tk.END, f"{sender}: {message}\n\n")
        self.message_area.see(tk.END)  # Scroll to the bottom
        self.message_area.config(state=tk.DISABLED)
    
    def display_hint(self, hint):
        """Display a hint in the hints area"""
        self.hints_area.config(state=tk.NORMAL)
        self.hints_area.insert(tk.END, f"{hint}\n\n")
        self.hints_area.see(tk.END)  # Scroll to the bottom
        self.hints_area.config(state=tk.DISABLED)
    
    def clear_messages(self):
        """Clear all messages from the message area"""
        self.message_area.config(state=tk.NORMAL)
        self.message_area.delete(1.0, tk.END)
        self.message_area.config(state=tk.DISABLED)
        
    def clear_hints(self):
        """Clear all hints from the hints area"""
        self.hints_area.config(state=tk.NORMAL)
        self.hints_area.delete(1.0, tk.END)
        self.hints_area.config(state=tk.DISABLED)
        
    def clear_all(self):
        """Clear both message and hints areas"""
        self.clear_messages()
        self.clear_hints()
    
    def send_message(self):
        """Send the user message to the AI"""
        message = self.user_input.get().strip()
        if not message:
            return
        
        # Display user message
        self.display_message("You", message)
        
        # Clear input field
        self.user_input.delete(0, tk.END)
        
        # Send to AI if conversation is active
        if self.live_loop and self.live_loop.session:
            asyncio.run_coroutine_threadsafe(self.send_to_live_loop(message), self.loop)
    
    async def send_to_live_loop(self, message):
        """Send a message to the LiveLoop instance"""
        if self.live_loop and self.live_loop.session:
            try:
                await self.live_loop.session.send(input=message, end_of_turn=True)
            except Exception as e:
                self.display_message("System", f"Error sending message: {e}")
    
    def create_config(self):
        """Create a Gemini config using the current settings"""
        # Get selected values
        system_message = self.system_message.get("1.0", tk.END).strip()
        language_code = LANGUAGES[self.language_var.get()]
        voice_name = VOICES[self.voice_var.get()]
        response_modalities = [self.modality_var.get()]
        
        # Configure tools
        search_tool = {'google_search': {}}
        function_tools = {
            'function_declarations': get_declarations_for_functions([
                print_to_console,
                write_message_to_gui,
                write_live_hints,
                # Add other functions here as needed
            ])
        }
        tools = [search_tool, function_tools]
        
        # Create the config
        config = types.LiveConnectConfig(
            response_modalities=response_modalities,
            tools=tools,
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
    
    def start_conversation(self):
        """Start a new conversation with Aya"""
        # Disable start button, enable stop button
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        # Create a new thread for the event loop
        threading_event_loop = asyncio.new_event_loop()
        self.loop = threading_event_loop
        
        # Create a thread to run the event loop
        def run_event_loop():
            asyncio.set_event_loop(threading_event_loop)
            threading_event_loop.run_forever()
        
        import threading
        self.thread = threading.Thread(target=run_event_loop, daemon=True)
        self.thread.start()
        
        # Create and start LiveLoop in the event loop
        asyncio.run_coroutine_threadsafe(self.create_and_run_live_loop(), self.loop)
        
        # Display a message
        self.display_message("System", "Starting conversation...")
    
    def log_message(self, message):
        """Add a system log message to the message area"""
        self.display_message("System", message)
    
    def update_mic_status(self, is_active):
        """Update the microphone status indicator"""
        self.mic_status_var.set(f"Microphone: {'Active' if is_active else 'Inactive'}")
        
    def update_connection_status(self, is_connected):
        """Update the connection status indicator"""
        self.connection_status_var.set(f"Connection: {'Connected' if is_connected else 'Disconnected'}")
        
    async def create_and_run_live_loop(self):
        """Create and run a LiveLoop instance"""
        try:
            # Initialize Gemini client
            client = genai.Client(http_options={"api_version": "v1beta"}, api_key=api_key)
            
            # Create config
            config = self.create_config()
            
            # Check if we should process microphone input
            process_mic = self.use_mic_var.get()
            self.root.after(0, lambda: self.update_mic_status(process_mic))
            
            # Always initialize microphone, but let user know if we're processing it
            self.log_message("Initializing microphone...")
            if process_mic:
                self.log_message("Microphone audio will be processed in the conversation.")
            else:
                self.log_message("Microphone is enabled but audio will not be processed in the conversation.")
                
            # List available audio devices for debugging
            import pyaudio
            p = pyaudio.PyAudio()
            mic_info = "Available audio devices:\n"
            for i in range(p.get_device_count()):
                dev_info = p.get_device_info_by_index(i)
                mic_info += f"[{i}] {dev_info.get('name')}"
                mic_info += f" (Input: {dev_info.get('maxInputChannels')}, Output: {dev_info.get('maxOutputChannels')})\n"
            self.log_message(mic_info)
            p.terminate()
            
            # Create LiveLoop instance with selected video mode and audio source
            self.live_loop = LiveLoop(
                video_mode=self.video_mode_var.get(),  # Use selected video mode
                client=client,
                model="models/gemini-2.0-flash-live-001",
                config=config,
                initial_message="[CALL_START]",  # Initial greeting
                audio_source=self.audio_source_var.get(),  # Use selected audio source
                record_conversation=False
            )
            
            # Replace the send_text method with our custom implementation
            original_send_text = self.live_loop.send_text
            
            # Create a dummy method that never exits (no 'q' checking)
            async def custom_send_text():
                # Just wait indefinitely - sending will be done through our GUI
                future = asyncio.Future()
                await future
            
            # Replace the send_text method
            self.live_loop.send_text = custom_send_text
            
            # Also intercept the microphone streaming if needed
            if not process_mic:
                # Store the original listen_audio method
                original_listen_audio = self.live_loop.listen_audio
                
                # Create a dummy method that captures audio but doesn't send it
                async def custom_listen_audio():
                    """Modified listen_audio that captures but doesn't process audio if disabled"""
                    # We'll still initialize the audio streams to keep the LiveLoop working
                    # but we won't send the audio data to the model
                    try:
                        import pyaudio
                        import array
                        import struct
                        
                        # Constants from LiveLoop
                        FORMAT = pyaudio.paInt16
                        CHANNELS = 1
                        CHUNK_SIZE = 1024
                        SAMPLE_RATE = 16000
                        
                        # Initialize PyAudio
                        p = pyaudio.PyAudio()
                        
                        # Open microphone stream
                        stream = p.open(
                            format=FORMAT,
                            channels=CHANNELS,
                            rate=SAMPLE_RATE,
                            input=True,
                            frames_per_buffer=CHUNK_SIZE
                        )
                        
                        # Just read from the mic but don't send data
                        while True:
                            # Read data but don't do anything with it
                            data = await asyncio.to_thread(stream.read, CHUNK_SIZE, exception_on_overflow=False)
                            # Small delay to not hog CPU
                            await asyncio.sleep(0.1)
                    except Exception as e:
                        self.log_message(f"Error in audio capture: {e}")
                
                # Replace the listen_audio method when mic processing is disabled
                self.live_loop.listen_audio = custom_listen_audio
            
            # Also replace the receive_text method to output to our GUI
            original_receive_text = self.live_loop.receive_text
            
            async def custom_receive_text():
                """Modified receive_text to display in GUI instead of console"""
                # Update connection status
                self.root.after(0, lambda: self.update_connection_status(True))
                
                while True:
                    turn = self.live_loop.session.receive()
                    accumulated_text = ""
                    
                    async for response in turn:
                        if text := response.text:
                            # Accumulate text - we'll display it in chunks
                            accumulated_text += text
                            if text.endswith(("\n", ".", "!", "?")) or len(accumulated_text) > 100:
                                # Display accumulated text and reset
                                self.root.after(0, lambda t=accumulated_text: 
                                               self.display_message("Aya", t))
                                accumulated_text = ""
                        
                        # Handle tool calls
                        if response.tool_call:
                            await self.live_loop.handle_tool_calls(response.tool_call)
                    
                    # Display any remaining text
                    if accumulated_text:
                        self.root.after(0, lambda t=accumulated_text: 
                                       self.display_message("Aya", t))
            
            # Replace the receive_text method
            self.live_loop.receive_text = custom_receive_text
            
            # Start the LiveLoop
            try:
                self.log_message("Connecting to Gemini...")
                await self.live_loop.run()
            except asyncio.CancelledError:
                self.log_message("Conversation stopped.")
                self.root.after(0, lambda: self.update_connection_status(False))
                self.root.after(0, lambda: self.update_mic_status(False))
            except Exception as e:
                self.log_message(f"Error in conversation: {e}")
                self.root.after(0, lambda: self.update_connection_status(False))
                self.root.after(0, lambda: self.update_mic_status(False))
        except Exception as e:
            error_msg = f"Failed to start conversation: {e}"
            self.log_message(error_msg)
            self.root.after(0, lambda: self.update_connection_status(False))
            self.root.after(0, lambda: self.update_mic_status(False))
            # Re-enable start button, disable stop button
            self.root.after(0, lambda: self.start_button.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.stop_button.config(state=tk.DISABLED))
    
    def stop_conversation(self):
        """Stop the current conversation"""
        # Disable stop button, enable start button
        self.stop_button.config(state=tk.DISABLED)
        self.start_button.config(state=tk.NORMAL)
        
        # Update status indicators
        self.update_connection_status(False)
        self.update_mic_status(False)
        
        # Stop the event loop
        if self.loop:
            for task in asyncio.all_tasks(self.loop):
                task.cancel()
            
            # Schedule loop stop
            self.loop.call_soon_threadsafe(self.loop.stop)
            self.live_loop = None
        
        # Display a message
        self.log_message("Conversation stopped.")

def main():
    # Create the Tkinter root
    root = tk.Tk()
    app = AyaGUI(root)
    
    # Handle window close
    def on_closing():
        if app.loop:
            try:
                for task in asyncio.all_tasks(app.loop):
                    task.cancel()
                app.loop.call_soon_threadsafe(app.loop.stop)
            except:
                pass
        root.destroy()
        sys.exit(0)
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    # Start the main loop
    root.mainloop()

if __name__ == "__main__":
    main() 