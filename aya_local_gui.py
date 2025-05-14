import asyncio
import os
import sys
import tkinter as tk
from tkinter import ttk, scrolledtext
from dotenv import load_dotenv
from PIL import Image, ImageTk  # Added for logo handling
from ttkthemes import ThemedTk

from google import genai
from google.genai import types

# Local imports
from live_loop import LiveLoop
from function_registry import FunctionRegistry, get_declarations_for_functions
from utils import load_system_message, list_system_messages

# Import tool functions for the GUI
from gemini_tools import print_to_console

# Load environment variables and API key
load_dotenv()
API_KEY_ENV_VAR = "GEMINI_API_KEY"
api_key = os.getenv(API_KEY_ENV_VAR)


# Default languages and voices
LANGUAGES = {
    "English (US)": "en-US",
    "German (DE)": "de-DE",
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
AUDIO_SOURCES = ["none", "microphone", "computer", "both"]

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
    Use this to provide real-time feedback to the user regarding their communication style.
    
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
        
        # Debug mode flag and window size memory
        self.debug_mode = False
        self.minimalist_window_size = "400x300"  # Default minimalist size
        self.root.geometry(self.minimalist_window_size)
        
        # Storage for text content to preserve between UI modes
        self.message_content = ""
        self.hints_content = ""
        
        # System prompts storage
        self.system_prompts = {}  # Will be populated by refresh_system_prompts
        self.selected_prompt_path = "system_prompts/default/aya_default_gui.txt"  # Default prompt path
        
        # Set dark theme colors
        self.bg_color = "#464646"  # Dark background
        self.fg_color = "white"    # Light text
        self.text_bg = "#2e2e2e"   # Text area background
        self.text_fg = "#ffffff"   # Text area foreground
        self.accent_color = "#1c1c1c"  # Darker accent
        
        # Define standard fonts
        self.config_font = (None, 11)
        self.message_font = (None, 11)
        self.hint_font_debug = (None, 11)
        self.hint_font_mini = (None, 18)
        
        # Load system prompts
        self.refresh_system_prompts()
        
        # Load and set the logo
        logo_path = "MP-logo.png"
        try:
            logo_img = Image.open(logo_path)
            # Resize the logo image to a reasonable size if needed
            logo_img = logo_img.resize((150, 150), Image.LANCZOS)
            logo_photo = ImageTk.PhotoImage(logo_img)
            self.root.iconphoto(True, logo_photo)
            # Keep a reference to prevent garbage collection
            self.logo_photo = logo_photo
        except Exception as e:
            print(f"Failed to load logo: {e}")
        
        # Set style
        self.style = ttk.Style()
        self.style.configure("TButton", padding=6, relief="flat")
        self.style.configure("TFrame", background=self.bg_color)
        self.style.configure("TLabel", background=self.bg_color, foreground=self.fg_color)
        self.style.configure("TLabelframe", background=self.bg_color, foreground=self.fg_color)
        self.style.configure("TLabelframe.Label", background=self.bg_color, foreground=self.fg_color)
        self.style.configure("TEntry", fieldbackground=self.text_bg, foreground=self.text_fg)
        
        # Configure main frame with minimal borders
        self.main_frame = ttk.Frame(root, borderwidth=0, relief="flat")
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        
        # Remove scrollbar borders
        self.style.configure("TScrollbar", borderwidth=0, arrowsize=14)
        
        # Live loop instance and task
        self.live_loop = None
        self.conversation_task = None
        self.loop = asyncio.new_event_loop()
        
        # Setup UI components based on mode
        self.setup_minimalist_ui()
        
        # Inject the GUI message function implementation
        self.inject_write_message_function()
        
    def configure_tags(self, text_widget, tag_name, font):
        """Configure tags for text widgets"""
        try:
            text_widget.tag_configure(tag_name, font=font)
        except Exception:
            pass  # Ignore if tag configuration fails
        
    def setup_config_section(self):
        # Configuration section frame
        config_frame = ttk.LabelFrame(self.main_frame, text="Configuration")
        config_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # System prompt selection
        prompt_frame = ttk.Frame(config_frame)
        prompt_frame.grid(row=0, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=5)
        
        ttk.Label(prompt_frame, text="System Prompt:").pack(side=tk.LEFT, padx=5)
        
        # Prompt selection dropdown
        self.prompt_var = tk.StringVar()
        self.prompt_combo = ttk.Combobox(prompt_frame, textvariable=self.prompt_var, values=self.system_prompts, state="readonly", font=self.config_font, width=40)
        self.prompt_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Set initial value if available
        if self.system_prompts:
            # Find current prompt in the list
            current_prompt = None
            for display_name, path in self.prompt_paths.items():
                if path == self.selected_prompt_path:
                    current_prompt = display_name
                    break
            
            if current_prompt and current_prompt in self.system_prompts:
                self.prompt_var.set(current_prompt)
            else:
                self.prompt_var.set(self.system_prompts[0])
        
        # Bind selection change event
        self.prompt_var.trace('w', self.on_prompt_selected)
        
        # Refresh button
        refresh_button = ttk.Button(prompt_frame, text="↻", width=3, command=self.refresh_system_prompts)
        refresh_button.pack(side=tk.RIGHT, padx=5)
        
        # System message text area - remove label and make textarea span full width
        self.system_message = scrolledtext.ScrolledText(config_frame, height=4, width=70, wrap=tk.WORD, font=self.config_font)
        self.system_message.grid(row=1, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=5)
        
        # Load selected system message
        system_msg = load_system_message(self.selected_prompt_path)
        self.system_message.insert(tk.END, system_msg)
        self.system_message.config(bg=self.text_bg, fg=self.text_fg)  # Apply dark theme to system message
        
        # Language selection
        ttk.Label(config_frame, text="Language:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.language_var = tk.StringVar(value=list(LANGUAGES.keys())[0])
        language_combo = ttk.Combobox(config_frame, textvariable=self.language_var, values=list(LANGUAGES.keys()), state="readonly", font=self.config_font)
        language_combo.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Voice selection
        ttk.Label(config_frame, text="Voice:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.voice_var = tk.StringVar(value=list(VOICES.keys())[0])
        voice_combo = ttk.Combobox(config_frame, textvariable=self.voice_var, values=list(VOICES.keys()), state="readonly", font=self.config_font)
        voice_combo.grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Response modality
        ttk.Label(config_frame, text="Response Type:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        self.modality_var = tk.StringVar(value=MODALITIES[0])  # Default to TEXT
        modality_combo = ttk.Combobox(config_frame, textvariable=self.modality_var, values=MODALITIES, state="readonly", font=self.config_font)
        modality_combo.grid(row=4, column=1, sticky=tk.W, padx=5, pady=5)

        # Audio source selection
        ttk.Label(config_frame, text="Audio Source:").grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        self.audio_source_var = tk.StringVar(value=AUDIO_SOURCES[1])  # Default to microphone
        audio_source_combo = ttk.Combobox(config_frame, textvariable=self.audio_source_var, values=AUDIO_SOURCES, state="readonly", font=self.config_font)
        audio_source_combo.grid(row=5, column=1, sticky=tk.W, padx=5, pady=5)

        # Video mode selection
        ttk.Label(config_frame, text="Video Mode:").grid(row=6, column=0, sticky=tk.W, padx=5, pady=5)
        self.video_mode_var = tk.StringVar(value=VIDEO_MODES[0])  # Default to none
        video_mode_combo = ttk.Combobox(config_frame, textvariable=self.video_mode_var, values=VIDEO_MODES, state="readonly", font=self.config_font)
        video_mode_combo.grid(row=6, column=1, sticky=tk.W, padx=5, pady=5)
        
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
        
        self.message_area = scrolledtext.ScrolledText(msg_frame, height=10, width=40, wrap=tk.WORD, font=self.message_font)
        self.message_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.message_area.config(state=tk.DISABLED, bg=self.text_bg, fg=self.text_fg)
        
        self.configure_tags(self.message_area, "message", self.message_font)
        
        # Fill the message area with stored content
        if self.message_content:
            self.message_area.config(state=tk.NORMAL)
            self.message_area.insert(tk.END, self.message_content)
            self.message_area.see(tk.END)
            self.message_area.config(state=tk.DISABLED)
        
        # Right side - Hints display area
        hint_frame = ttk.LabelFrame(split_frame, text="Communication Hints")
        hint_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.hints_area = scrolledtext.ScrolledText(hint_frame, height=10, width=30, wrap=tk.WORD, font=self.hint_font_debug)
        self.hints_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.hints_area.config(state=tk.DISABLED, bg=self.text_bg, fg=self.text_fg)
        self.configure_tags(self.hints_area, "hint", self.hint_font_debug)
        
        # Fill the hints area with stored content
        if self.hints_content:
            self.hints_area.config(state=tk.NORMAL)
            self.hints_area.insert(tk.END, self.hints_content, "hint")
            self.hints_area.see(tk.END)
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
        self.user_input = ttk.Entry(input_frame, width=50, font=self.message_font)
        self.user_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        send_button = ttk.Button(input_frame, text="Send", command=self.send_message)
        send_button.pack(side=tk.RIGHT, padx=5)
        
        # Bind Enter key to send message
        self.user_input.bind("<Return>", lambda event: self.send_message())
        
    def setup_control_section(self):
        # Control buttons frame
        control_frame = ttk.Frame(self.main_frame)
        control_frame.pack(fill=tk.X, padx=5, pady=10)
        
        # Start/Stop toggle button
        button_text = "Stop Conversation" if self.live_loop else "Start Conversation"
        self.start_stop_button = ttk.Button(
            control_frame, 
            text=button_text, 
            command=self.toggle_conversation
        )
        self.start_stop_button.pack(side=tk.LEFT, padx=5)
        
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
            print(f"Message tool called with: '{message}'")
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
        """Display a message in the message area with the sender name if it exists"""
        if sender is None:
            text = message
        else:
            text = f"\n{sender}: {message}\n\n"
        
        # Always store content for preservation between mode switches
        self.message_content += text
        
        # Only update UI in the mode that has a message area
        if hasattr(self, 'message_area'):
            self._update_message_area(text)
        else:
            # In minimalist mode, just print to console
            print(f"{sender if sender else ''}: {message}")
    
    def display_hint(self, hint):
        """Display a hint in the hints area"""
        # Store hint content for preservation between mode switches
        formatted_hint = f"{hint}\n\n"
        self.hints_content += formatted_hint
        
        if hasattr(self, 'hints_area'):
            self.hints_area.config(state=tk.NORMAL)
            # Insert with tag for custom formatting
            self.hints_area.insert(tk.END, formatted_hint, "hint")
            self.hints_area.see(tk.END)  # Scroll to the bottom
            self.hints_area.config(state=tk.DISABLED)
    
    def clear_messages(self):
        """Clear all messages from the message area"""
        # Clear stored message content
        self.message_content = ""
        
        if hasattr(self, 'message_area'):
            self.message_area.config(state=tk.NORMAL)
            self.message_area.delete(1.0, tk.END)
            self.message_area.config(state=tk.DISABLED)
    
    def clear_hints(self):
        """Clear all hints from the hints area"""
        # Clear stored hints content
        self.hints_content = ""
        
        if hasattr(self, 'hints_area'):
            self.hints_area.config(state=tk.NORMAL)
            self.hints_area.delete(1.0, tk.END)
            self.hints_area.config(state=tk.DISABLED)
        
    def clear_all(self):
        """Clear both message and hints areas"""
        self.clear_messages()
        self.clear_hints()
    
    def send_message(self):
        """Send the user message to the AI"""
        # In minimalist mode, we don't have a user_input field
        if not hasattr(self, 'user_input'):
            return
        
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
        # If in debug mode, use the values from the UI
        if self.debug_mode and hasattr(self, 'system_message'):
            system_message = self.system_message.get("1.0", tk.END).strip()
            language_code = LANGUAGES[self.language_var.get()]
            voice_name = VOICES[self.voice_var.get()]
            response_modalities = [self.modality_var.get()]
            audio_source = self.audio_source_var.get()
            video_mode = self.video_mode_var.get()
        else:
            # In minimalist mode, use selected prompt but default values for other settings
            system_message = load_system_message(self.selected_prompt_path)
            language_code = LANGUAGES[list(LANGUAGES.keys())[0]]  # First language
            voice_name = VOICES[list(VOICES.keys())[0]]  # First voice
            response_modalities = ["TEXT"]
            audio_source = AUDIO_SOURCES[1]  # Default to microphone
            video_mode = VIDEO_MODES[0]  # Default to none
        
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
            temperature=0.05,
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
        
        return config, audio_source, video_mode
    
    def start_conversation(self):
        """Start a new conversation with Aya"""
        # Update button state and text
        if hasattr(self, 'start_stop_button'):
            self.start_stop_button.config(text="Stop Conversation")
        
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
        
        # Log starting message (will be stored regardless of UI mode)
        self.log_message("Starting conversation...")
        
        # Update status text
        if hasattr(self, 'connection_status_var'):
            self.connection_status_var.set("Status: Connecting...")
    
    def log_message(self, message):
        """Add a system log message to the message area if it exists"""
        # Always store the message in message_content regardless of UI mode
        text = f"\nSystem: {message}\n\n"
        self.message_content += text
        
        # Only display in the message area in debug mode
        if hasattr(self, 'message_area'):
            self.message_area.config(state=tk.NORMAL)
            self.message_area.insert(tk.END, text)
            self.message_area.see(tk.END)
            self.message_area.config(state=tk.DISABLED)
        else:
            # Print to console in minimalist mode
            print(f"System: {message}")
    
    def update_mic_status(self, is_active):
        """Update the microphone status indicator"""
        if hasattr(self, 'mic_status_var'):
            self.mic_status_var.set(f"Microphone: {'Active' if is_active else 'Inactive'}")
        
    def update_connection_status(self, is_connected):
        """Update the connection status indicator"""
        if hasattr(self, 'mic_status_var'):
            self.connection_status_var.set(f"Connection: {'Connected' if is_connected else 'Disconnected'}")
        else:
            # In minimalist mode, we have a simpler status display
            self.connection_status_var.set(f"Status: {'Active' if is_connected else 'Disconnected'}")
        
    async def create_and_run_live_loop(self):
        """Create and run a LiveLoop instance"""
        try:
            # Initialize Gemini client
            client = genai.Client(http_options={"api_version": "v1beta"}, api_key=api_key)
            
            # Create config - now returns audio/video settings too
            config, audio_source, video_mode = self.create_config()
            
            # Update mic status indicator based on audio source
            is_mic_active = audio_source != "none"
            if hasattr(self, 'mic_status_var'):
                self.root.after(0, lambda: self.update_mic_status(is_mic_active))
            
            # Log microphone initialization if mic is active
            if is_mic_active:
                self.log_message("Initializing microphone...")
                
                # List available audio devices for debugging
                try:
                    import pyaudio
                    p = pyaudio.PyAudio()
                    mic_info = "Available audio devices:\n"
                    for i in range(p.get_device_count()):
                        dev_info = p.get_device_info_by_index(i)
                        mic_info += f"[{i}] {dev_info.get('name')}"
                        mic_info += f" (Input: {dev_info.get('maxInputChannels')}, Output: {dev_info.get('maxOutputChannels')})\n"
                    self.log_message(mic_info)  # Log to both UIs
                    p.terminate()
                except Exception as e:
                    self.log_message(f"Error listing audio devices: {e}")
            else:
                self.log_message("Audio input disabled.")
                
            # Create LiveLoop instance with selected video mode and audio source
            self.live_loop = LiveLoop(
                video_mode=video_mode,  # Use selected video mode
                client=client,
                model="models/gemini-2.0-flash-live-001",
                config=config,
                initial_message="[CALL_START]",  # Initial greeting
                audio_source=audio_source,  # Use selected audio source
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
            
            # Replace the output_text method in LiveLoop to display in GUI instead of console
            # We need to maintain text accumulation to display in sensible chunks
            accumulated_text = [""]  # Using a list for mutable state in the closure
            
            def custom_output_text(text):
                accumulated_text[0] += text
                
                # Check if we have a natural break or enough accumulated text
                if text.endswith(("\n", ".", "!", "?")) or len(accumulated_text[0]) > 100:
                    # Store text in message_content regardless of UI mode
                    display_text = accumulated_text[0]
                    self.message_content += display_text
                    
                    # Display in UI if in debug mode
                    if hasattr(self, 'message_area') and self.debug_mode:
                        # Display accumulated text via the main thread
                        self.root.after(0, lambda t=display_text: self._update_message_area(t))
                    
                    # Reset accumulated text
                    accumulated_text[0] = ""
            
            # Replace the original output_text method
            self.live_loop.output_text = custom_output_text
            
            # Update connection status
            self.root.after(0, lambda: self.update_connection_status(True))
            
            # Start the LiveLoop
            try:
                # Log connecting message
                self.log_message("Connecting to Gemini...")
                await self.live_loop.run()
            except asyncio.CancelledError:
                # Log cancellation
                self.log_message("Conversation stopped.")
                
                # Update status indicators
                self.root.after(0, lambda: self.update_connection_status(False))
                if hasattr(self, 'mic_status_var'):
                    self.root.after(0, lambda: self.update_mic_status(False))
                
                # Reset button text
                if hasattr(self, 'start_stop_button'):
                    self.root.after(0, lambda: self.start_stop_button.config(text="Start Conversation"))
                
                # Reset live_loop
                self.live_loop = None
            except Exception as e:
                # Log error
                error_msg = f"Error in conversation: {e}"
                self.log_message(error_msg)
                
                # Update status indicators
                self.root.after(0, lambda: self.update_connection_status(False))
                if hasattr(self, 'mic_status_var'):
                    self.root.after(0, lambda: self.update_mic_status(False))
                
                # Reset button text
                if hasattr(self, 'start_stop_button'):
                    self.root.after(0, lambda: self.start_stop_button.config(text="Start Conversation"))
                
                # Reset live_loop
                self.live_loop = None
        except Exception as e:
            # Log startup error
            error_msg = f"Failed to start conversation: {e}"
            self.log_message(error_msg)
            
            # Update status indicators
            self.root.after(0, lambda: self.update_connection_status(False))
            if hasattr(self, 'mic_status_var'):
                self.root.after(0, lambda: self.update_mic_status(False))
            
            # Reset button state
            if hasattr(self, 'start_stop_button'):
                self.root.after(0, lambda: self.start_stop_button.config(text="Start Conversation"))
            
            # Reset live_loop to None to indicate we're not connected
            self.live_loop = None
    
    def stop_conversation(self):
        """Stop the current conversation"""
        # Update button text
        if hasattr(self, 'start_stop_button'):
            self.start_stop_button.config(text="Start Conversation")
        
        # Update status indicators
        if hasattr(self, 'connection_status_var'):
            self.update_connection_status(False)
        if hasattr(self, 'mic_status_var'):
            self.update_mic_status(False)
        
        # Stop the event loop
        if self.loop:
            for task in asyncio.all_tasks(self.loop):
                task.cancel()
            
            # Schedule loop stop
            self.loop.call_soon_threadsafe(self.loop.stop)
        
        # Reset live_loop to None
        self.live_loop = None
        
        # Log message about stopping conversation
        self.log_message("Conversation stopped.")
    
    def setup_minimalist_ui(self):
        """Setup the minimalist UI with just hints and control buttons"""
        # Clear existing UI elements if any
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        
        # Control buttons frame at the top
        control_frame = ttk.Frame(self.main_frame, borderwidth=0)
        control_frame.pack(fill=tk.X, padx=2, pady=2)
        
        # Start/Stop button
        button_text = "Stop Conversation" if self.live_loop else "Start Conversation"
        self.start_stop_button = ttk.Button(
            control_frame, 
            text=button_text,
            command=self.toggle_conversation
        )
        self.start_stop_button.pack(side=tk.LEFT, padx=2, pady=2)
        
        # Debug button
        debug_button = ttk.Button(
            control_frame, 
            text="Settings", 
            command=self.toggle_debug_mode
        )
        debug_button.pack(side=tk.RIGHT, padx=2, pady=2)
        
        # Add system prompt selection in minimal UI
        prompt_frame = ttk.Frame(self.main_frame, borderwidth=0)
        prompt_frame.pack(fill=tk.X, padx=2, pady=2)
        
        ttk.Label(prompt_frame, text="Prompt:").pack(side=tk.LEFT, padx=2)
        
        # Prompt selection dropdown
        self.mini_prompt_var = tk.StringVar()
        self.mini_prompt_combo = ttk.Combobox(prompt_frame, textvariable=self.mini_prompt_var, values=self.system_prompts, state="readonly", font=self.config_font, width=30)
        self.mini_prompt_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        # Set initial value if available
        if self.system_prompts:
            # Find current prompt in the list
            current_prompt = None
            for display_name, path in self.prompt_paths.items():
                if path == self.selected_prompt_path:
                    current_prompt = display_name
                    break
            
            if current_prompt and current_prompt in self.system_prompts:
                self.mini_prompt_var.set(current_prompt)
            else:
                self.mini_prompt_var.set(self.system_prompts[0])
        
        # Bind selection change event
        self.mini_prompt_var.trace('w', self.on_mini_prompt_selected)
        
        # Refresh button
        refresh_button = ttk.Button(prompt_frame, text="↻", width=3, command=self.refresh_system_prompts)
        refresh_button.pack(side=tk.RIGHT, padx=2)
        
        # Hints display area (main content in minimalist mode)
        hint_frame = ttk.LabelFrame(self.main_frame, text="Communication Hints", borderwidth=1)
        hint_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        
        self.hints_area = scrolledtext.ScrolledText(hint_frame, height=10, wrap=tk.WORD, borderwidth=0, font=self.hint_font_mini)
        self.hints_area.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self.hints_area.config(state=tk.DISABLED, bg=self.text_bg, fg=self.text_fg)
        self.configure_tags(self.hints_area, "hint", self.hint_font_mini)
        
        # Fill the hints area with stored content
        if self.hints_content:
            self.hints_area.config(state=tk.NORMAL)
            self.hints_area.insert(tk.END, self.hints_content, "hint")
            self.hints_area.see(tk.END)
            self.hints_area.config(state=tk.DISABLED)
        
        # Status indicator at the bottom
        status_frame = ttk.Frame(self.main_frame, borderwidth=0)
        status_frame.pack(fill=tk.X, padx=2, pady=1)
        
        # Connection status
        status_text = "Status: Connected" if self.live_loop else "Status: Disconnected"
        self.connection_status_var = tk.StringVar(value=status_text)
        ttk.Label(status_frame, textvariable=self.connection_status_var).pack(side=tk.LEFT, padx=2)
    
    def setup_debug_ui(self):
        """Setup the detailed debug UI with all configuration options"""
        # Clear existing UI elements
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        
        # Add close debug button at the top
        control_frame = ttk.Frame(self.main_frame)
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        close_debug_button = ttk.Button(
            control_frame, 
            text="Close Settings", 
            command=self.toggle_debug_mode
        )
        close_debug_button.pack(side=tk.RIGHT, padx=5, pady=5)
        
        # Setup the standard UI components
        self.setup_config_section()
        self.setup_message_section()
        self.setup_control_section()
        
        # Resize window for debug mode - always use the same debug size
        self.root.geometry("800x900")
    
    def toggle_debug_mode(self):
        """Toggle between minimalist and debug UI modes"""
        # Remember the current conversation state before changing UI
        is_conversation_active = self.live_loop is not None
        
        if not self.debug_mode:
            # When switching from minimalist to debug mode
            # Save current window size for later restoration
            self.minimalist_window_size = self.root.geometry().split('+')[0]  # Get just the WxH part
            
            # Enable debug mode
            self.debug_mode = True
            
            # Setup debug UI
            self.setup_debug_ui()
        else:
            # When switching from debug to minimalist mode
            # Disable debug mode
            self.debug_mode = False
            
            # Setup minimalist UI
            self.setup_minimalist_ui()
            
            # Restore the minimalist window size
            self.root.geometry(self.minimalist_window_size)
        
        # Ensure button text reflects current state in both modes
        if hasattr(self, 'start_stop_button'):
            self.start_stop_button.config(
                text="Stop Conversation" if is_conversation_active else "Start Conversation"
            )
    
    def toggle_conversation(self):
        """Toggle between starting and stopping the conversation"""
        if self.live_loop:
            # Stop the conversation
            self.stop_conversation()
        else:
            # Start the conversation
            self.start_conversation()

    def _update_message_area(self, text):
        """Update the message area directly without adding to message_content"""
        if hasattr(self, 'message_area'):
            self.message_area.config(state=tk.NORMAL)
            self.message_area.insert(tk.END, text)
            self.message_area.see(tk.END)
            self.message_area.config(state=tk.DISABLED)

    # New method to refresh system prompts
    def refresh_system_prompts(self):
        """Refresh the list of available system prompts"""
        # Get available system prompts
        prompt_dict = list_system_messages()
        
        # Clear existing system prompts
        self.system_prompts = {}
        
        # Process prompts for the dropdown
        formatted_prompts = []
        prompt_paths = {}
        
        for category, prompts in prompt_dict.items():
            for prompt_path in prompts:
                # Get filename without extension
                filename = os.path.basename(prompt_path)
                name, _ = os.path.splitext(filename)
                
                # Format display name
                display_name = f"{name} ({category})"
                
                # Add to formatted prompts list
                formatted_prompts.append(display_name)
                
                # Store path mapping
                prompt_paths[display_name] = prompt_path
        
        # Sort prompts alphabetically
        formatted_prompts.sort()
        
        # Store in instance variables
        self.system_prompts = formatted_prompts
        self.prompt_paths = prompt_paths
        
        # Update dropdown in both UIs if they exist
        if hasattr(self, 'prompt_var') and hasattr(self, 'prompt_combo'):
            current_val = self.prompt_var.get()
            self.prompt_combo['values'] = self.system_prompts
            
            # Try to maintain selection or set to first value
            if current_val in self.system_prompts:
                self.prompt_var.set(current_val)
            elif self.system_prompts:
                self.prompt_var.set(self.system_prompts[0])
        
        if hasattr(self, 'mini_prompt_var') and hasattr(self, 'mini_prompt_combo'):
            current_val = self.mini_prompt_var.get()
            self.mini_prompt_combo['values'] = self.system_prompts
            
            # Try to maintain selection or set to first value
            if current_val in self.system_prompts:
                self.mini_prompt_var.set(current_val)
            elif self.system_prompts:
                self.mini_prompt_var.set(self.system_prompts[0])
    
    # Method to handle prompt selection change
    def on_prompt_selected(self, *args):
        """Handle prompt selection change in debug mode"""
        if hasattr(self, 'prompt_var'):
            selected = self.prompt_var.get()
            if selected in self.prompt_paths:
                # Get path
                path = self.prompt_paths[selected]
                self.selected_prompt_path = path
                
                # Load and display system message
                system_msg = load_system_message(path)
                
                # Update message text if text area exists
                if hasattr(self, 'system_message'):
                    self.system_message.delete(1.0, tk.END)
                    self.system_message.insert(tk.END, system_msg)
    
    # Method to handle prompt selection change in minimalist mode
    def on_mini_prompt_selected(self, *args):
        """Handle prompt selection change in minimalist mode"""
        if hasattr(self, 'mini_prompt_var'):
            selected = self.mini_prompt_var.get()
            if selected in self.prompt_paths:
                # Get path and store
                path = self.prompt_paths[selected]
                self.selected_prompt_path = path

def main():
    # Create the Tkinter root with themed support
    root = ThemedTk(theme="equilux")
    # Remove window borders
    root.overrideredirect(False)  # Keep standard titlebar
    if sys.platform.startswith('win'):
        # For Windows, reduce border thickness
        root.attributes('-alpha', 0.9999)  # Trick to force window to redraw
        # Remove padding around the window
        root.config(borderwidth=0, highlightthickness=0, padx=0, pady=0)
        # Set window style to remove borders using Windows API
        try:
            import ctypes
            HWND = ctypes.windll.user32.GetParent(root.winfo_id())
            style = ctypes.windll.user32.GetWindowLongPtrW(HWND, -16)  # GWL_STYLE
            style = style & ~0x00C00000  # WS_CAPTION
            style = style & ~0x00800000  # WS_BORDER
            ctypes.windll.user32.SetWindowLongPtrW(HWND, -16, style)  # GWL_STYLE
            root.update_idletasks()
            root.attributes('-alpha', 1.0)  # Restore transparency
        except:
            pass  # Fallback if Windows API access fails
    
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