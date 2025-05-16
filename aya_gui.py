import asyncio
import os
import sys
import tkinter as tk
import threading
import datetime
from tkinter import ttk, scrolledtext
from dotenv import load_dotenv
from PIL import Image, ImageTk
from ttkthemes import ThemedTk

from google import genai
from google.genai import types

# Local imports
from live_loop import LiveLoop
from function_registry import FunctionRegistry, get_declarations_for_functions
from utils import load_system_message, list_system_messages, create_gemini_config
from gemini_tools import print_to_console

# Load environment variables and API key
load_dotenv()
API_KEY_ENV_VAR = "GEMINI_API_KEY"
api_key = os.getenv(API_KEY_ENV_VAR)

# Default languages and voices
LANGUAGES = {
    "English (US)": "en-US",
    "English (UK)": "en-GB",
    "German (DE)": "de-DE",
    "French (FR)": "fr-FR",
    "Spanish (ES)": "es-ES",
    "Italian (IT)": "it-IT",
    "Japanese (JP)": "ja-JP",
    "Korean (KR)": "ko-KR",
    "Chinese (CN)": "cmn-CN",
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
    """
    A streamlined GUI for the Aya AI Assistant with unified UI design.
    """
    
    def __init__(self, root):
        self.root = root
        self.root.title("Aya AI Assistant")
        
        # Main state variables
        self.conversation_active = False
        self.settings_visible = False
        self.system_message_visible = False
        
        # Setup UI components
        self.setup_ui()
        
        # Now that all UI components are created, refresh the system prompts
        self.refresh_system_prompts()
        
        # Initialize tool configuration
        self.tool_config = {
            "search": False,
            "code_execution": False,
            "write_message_to_gui": False,
            "write_live_hints": False,
            "print_to_console": True
        }
        
        # Initialize LiveLoop components
        self.live_loop = None
        self.loop = asyncio.new_event_loop()
        
        # Inject GUI tool implementations
        self.inject_tool_functions()

    def setup_ui(self):
        """Setup the main UI components"""
        # Define theme colors
        self.bg_color = "#464646"  # Dark background
        self.fg_color = "white"    # Light text
        self.text_bg = "#2e2e2e"   # Text area background
        self.text_fg = "#ffffff"   # Text area foreground
        self.accent_color = "#1c1c1c"  # Darker accent
        
        # Define standard fonts
        self.standard_font = (None, 11)
        self.message_font = (None, 11)
        self.hint_font = (None, 11)
        
        # Configure styles
        self.style = ttk.Style()
        self.style.configure("TButton", padding=6, relief="flat")
        self.style.configure("TFrame", background=self.bg_color)
        self.style.configure("TLabel", background=self.bg_color, foreground=self.fg_color)
        self.style.configure("TLabelframe", background=self.bg_color, foreground=self.fg_color)
        self.style.configure("TLabelframe.Label", background=self.bg_color, foreground=self.fg_color)
        self.style.configure("TEntry", fieldbackground=self.text_bg, foreground=self.text_fg)
        self.style.configure("TScrollbar", borderwidth=0, arrowsize=14)
        
        # Initialize system prompts before creating UI components that use them
        self.system_prompts = {}
        self.categories = []
        self.current_category = None
        self.current_category_prompts = []
        self.selected_prompt_path = "system_prompts/default/aya_default_gui.txt"
        
        # Basic initialization of system prompts
        prompt_dict = list_system_messages()
        self.system_prompts = prompt_dict
        self.categories = sorted(prompt_dict.keys())
        if self.categories:
            self.current_category = self.categories[0]
        
        # Store content buffers
        self.message_content = ""
        self.hints_content = ""
        self.status_content = ""
        
        # Store configuration settings
        self.config = {
            "language": "English (US)",
            "voice": "Leda (Female)",
            "response_modality": "TEXT",
            "audio_source": "none",
            "video_mode": "none",
            "text_input": True,
            "tools_enabled": False
        }
        
        # Main frame
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Top control bar
        self.control_bar = ttk.Frame(self.main_frame)
        self.control_bar.pack(fill=tk.X, pady=5)
        
        # Start/Stop conversation button
        self.conversation_button = ttk.Button(
            self.control_bar, 
            text="Start Conversation",
            command=self.toggle_conversation
        )
        self.conversation_button.pack(side=tk.LEFT, padx=5)
        
        # Settings toggle button
        self.settings_button = ttk.Button(
            self.control_bar, 
            text="▼ Show Settings",
            command=self.toggle_settings
        )
        self.settings_button.pack(side=tk.RIGHT, padx=5)
        
        # Clear button
        self.clear_button = ttk.Button(
            self.control_bar,
            text="Clear",
            command=self.clear_display
        )
        self.clear_button.pack(side=tk.RIGHT, padx=5)
        
        # Status indicator
        self.status_var = tk.StringVar(value="Status: Disconnected")
        self.status_label = ttk.Label(self.control_bar, textvariable=self.status_var)
        self.status_label.pack(side=tk.RIGHT, padx=10)
        
        # Settings frame (initially hidden)
        self.setup_settings_frame()
        
        # Main content area
        self.content_frame = ttk.Frame(self.main_frame)
        self.content_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Output display area
        self.output_frame = ttk.LabelFrame(self.content_frame, text="Conversation")
        self.output_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.message_area = scrolledtext.ScrolledText(
            self.output_frame, 
            height=15, 
            wrap=tk.WORD, 
            font=self.message_font,
            bg=self.text_bg,
            fg=self.text_fg
        )
        self.message_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.message_area.config(state=tk.DISABLED)
        
        # Display selector
        self.display_var = tk.StringVar(value="Conversation")
        self.display_options = ["Conversation", "Hints", "Status"]
        self.display_selector = ttk.Combobox(
            self.output_frame,
            textvariable=self.display_var,
            values=self.display_options,
            state="readonly",
            font=self.standard_font,
            width=15
        )
        self.display_selector.pack(side=tk.LEFT, padx=5, pady=5)
        self.display_var.trace_add('write', self.on_display_change)
        
        # User input area (text chat)
        self.input_frame = ttk.Frame(self.main_frame)
        self.input_frame.pack(fill=tk.X, pady=5)
        
        self.user_input = ttk.Entry(self.input_frame, font=self.standard_font)
        self.user_input.pack(fill=tk.X, side=tk.LEFT, expand=True, padx=5)
        
        self.send_button = ttk.Button(
            self.input_frame,
            text="Send",
            command=self.send_message
        )
        self.send_button.pack(side=tk.RIGHT, padx=5)
        
        # Bind Enter key to send message
        self.user_input.bind("<Return>", lambda event: self.send_message())
        
    def setup_settings_frame(self):
        """Create the settings frame with all configuration options"""
        self.settings_frame = ttk.LabelFrame(self.main_frame, text="Settings")
        # Don't pack it yet - it will be shown/hidden with toggle_settings()
        
        # Create a grid layout for settings
        # Left column - Input settings
        ttk.Label(self.settings_frame, text="Inputs:", font=(None, 11, "bold")).grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=5)
        
        # Text chat option
        self.text_input_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            self.settings_frame, 
            text="Text chat", 
            variable=self.text_input_var,
            command=self.update_config_from_ui
        ).grid(row=1, column=0, sticky=tk.W, padx=20, pady=2)
        
        # Microphone option
        self.mic_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            self.settings_frame, 
            text="Microphone audio", 
            variable=self.mic_var,
            command=self.update_audio_source
        ).grid(row=2, column=0, sticky=tk.W, padx=20, pady=2)
        
        # Computer audio option
        self.computer_audio_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            self.settings_frame, 
            text="Computer audio", 
            variable=self.computer_audio_var,
            command=self.update_audio_source
        ).grid(row=3, column=0, sticky=tk.W, padx=20, pady=2)
        
        # Video mode - moved from Tools section to Input section
        ttk.Label(self.settings_frame, text="Video mode:").grid(
            row=4, column=0, sticky=tk.W, padx=20, pady=2)
        
        self.video_var = tk.StringVar(value="none")
        video_combo = ttk.Combobox(
            self.settings_frame, 
            textvariable=self.video_var, 
            values=VIDEO_MODES, 
            state="readonly", 
            width=10
        )
        video_combo.grid(row=4, column=0, sticky=tk.E, padx=5, pady=2)
        self.video_var.trace_add('write', lambda *args: self.update_config_from_ui())
        
        # Middle column - Output settings
        ttk.Label(self.settings_frame, text="Outputs:", font=(None, 11, "bold")).grid(
            row=0, column=1, sticky=tk.W, padx=10, pady=5)
        
        # Main output type
        ttk.Label(self.settings_frame, text="Main output:").grid(
            row=1, column=1, sticky=tk.W, padx=20, pady=2)
        
        self.output_var = tk.StringVar(value="TEXT")
        output_combo = ttk.Combobox(
            self.settings_frame, 
            textvariable=self.output_var, 
            values=MODALITIES, 
            state="readonly", 
            width=10
        )
        output_combo.grid(row=1, column=2, sticky=tk.W, padx=5, pady=2)
        self.output_var.trace_add('write', lambda *args: self.update_config_from_ui())
        
        # Language selection
        ttk.Label(self.settings_frame, text="Audio language:").grid(
            row=2, column=1, sticky=tk.W, padx=20, pady=2)
        
        self.language_var = tk.StringVar(value="English (US)")
        language_combo = ttk.Combobox(
            self.settings_frame, 
            textvariable=self.language_var, 
            values=list(LANGUAGES.keys()), 
            state="readonly", 
            width=15
        )
        language_combo.grid(row=2, column=2, sticky=tk.W, padx=5, pady=2)
        self.language_var.trace_add('write', lambda *args: self.update_config_from_ui())
        
        # Voice selection
        ttk.Label(self.settings_frame, text="Voice:").grid(
            row=3, column=1, sticky=tk.W, padx=20, pady=2)
        
        self.voice_var = tk.StringVar(value="Leda (Female)")
        voice_combo = ttk.Combobox(
            self.settings_frame, 
            textvariable=self.voice_var, 
            values=list(VOICES.keys()), 
            state="readonly", 
            width=15
        )
        voice_combo.grid(row=3, column=2, sticky=tk.W, padx=5, pady=2)
        self.voice_var.trace_add('write', lambda *args: self.update_config_from_ui())
        
        # Right column - Tools settings
        ttk.Label(self.settings_frame, text="Tools:", font=(None, 11, "bold")).grid(
            row=0, column=3, sticky=tk.W, padx=10, pady=5)
        
        # Enable tools checkbox
        self.tools_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            self.settings_frame, 
            text="Enable tools", 
            variable=self.tools_var,
            command=self.update_config_from_ui
        ).grid(row=1, column=3, sticky=tk.W, padx=20, pady=2)
        
        # Configure tools button (for future implementation)
        ttk.Button(
            self.settings_frame, 
            text="Configure tools", 
            command=self.configure_tools
        ).grid(row=2, column=3, sticky=tk.W, padx=20, pady=2)
        
        # System prompt section
        prompt_frame = ttk.Frame(self.settings_frame)
        prompt_frame.grid(row=5, column=0, columnspan=5, sticky=tk.EW, padx=10, pady=10)
        
        # Category dropdown
        ttk.Label(prompt_frame, text="Category:").grid(row=0, column=0, sticky=tk.W, padx=5)
        
        self.category_var = tk.StringVar()
        self.category_combo = ttk.Combobox(
            prompt_frame, 
            textvariable=self.category_var, 
            values=self.categories, 
            state="readonly", 
            width=15
        )
        self.category_combo.grid(row=0, column=1, sticky=tk.W, padx=5)
        
        # Prompt dropdown
        ttk.Label(prompt_frame, text="Prompt:").grid(row=0, column=2, sticky=tk.W, padx=5)
        
        self.prompt_var = tk.StringVar()
        self.prompt_combo = ttk.Combobox(
            prompt_frame, 
            textvariable=self.prompt_var, 
            values=self.current_category_prompts, 
            state="readonly", 
            width=30
        )
        self.prompt_combo.grid(row=0, column=3, sticky=tk.W, padx=5)
        
        # Refresh button
        ttk.Button(
            prompt_frame, 
            text="↻", 
            width=3, 
            command=self.refresh_system_prompts
        ).grid(row=0, column=4, sticky=tk.E, padx=5)
        
        # Show/Hide system message button
        self.system_message_button = ttk.Button(
            prompt_frame, 
            text="Show System Message", 
            command=self.toggle_system_message
        )
        self.system_message_button.grid(row=0, column=5, sticky=tk.E, padx=5)
        
        # System message text area (initially hidden)
        self.system_message_frame = ttk.Frame(self.settings_frame)
        self.system_message_frame.grid(row=6, column=0, columnspan=5, sticky=tk.EW, padx=10, pady=5)
        self.system_message_frame.grid_remove()  # Hide initially
        
        self.system_message = scrolledtext.ScrolledText(
            self.system_message_frame, 
            height=8, 
            width=80, 
            wrap=tk.WORD, 
            font=self.standard_font,
            bg=self.text_bg,
            fg=self.text_fg
        )
        self.system_message.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Bind selection change events
        self.category_var.trace_add('write', self.on_category_selected)
        self.prompt_var.trace_add('write', self.on_prompt_selected)
        
        # Set initial values if available
        if self.categories:
            self.category_var.set(self.categories[0])
            self.update_prompt_dropdown()
            
        # Configure grid
        for i in range(5):
            self.settings_frame.columnconfigure(i, weight=1)
        
        # Initially hide the settings frame
        # The frame will be shown when toggle_settings is called

    def inject_tool_functions(self):
        """Inject implementations for tool functions"""
        # Inject the actual implementation for write_message_to_gui
        def _write_message_impl(message):
            self.display_message("Aya", message)
            return {"result": f"Message displayed: {message}"}
        
        # Replace the function in the registry
        FunctionRegistry._functions["write_message_to_gui"]["implementation"] = _write_message_impl
        
        # Inject implementation for write_live_hints
        def _write_hints_impl(hint):
            self.display_hint(hint)
            return {"result": f"Hint displayed: {hint}"}
        
        # Replace the function in the registry
        FunctionRegistry._functions["write_live_hints"]["implementation"] = _write_hints_impl
    
    def toggle_conversation(self):
        """Toggle between starting and stopping the conversation"""
        if self.conversation_active:
            self.stop_conversation()
        else:
            self.start_conversation()
    
    def start_conversation(self):
        """Start a new conversation with Aya"""
        # Update UI state
        self.conversation_button.config(text="Stop Conversation")
        self.status_var.set("Status: Connecting...")
        self.conversation_active = True
        
        # Disable settings during conversation
        self._set_conversation_ui_state(disabled=True)
        
        # Create a new thread for the event loop
        threading_event_loop = asyncio.new_event_loop()
        self.loop = threading_event_loop
        
        # Create a thread to run the event loop
        def run_event_loop():
            asyncio.set_event_loop(threading_event_loop)
            threading_event_loop.run_forever()
        
        self.thread = threading.Thread(target=run_event_loop, daemon=True)
        self.thread.start()
        
        # Create and start LiveLoop in the event loop
        asyncio.run_coroutine_threadsafe(self.create_and_run_live_loop(), self.loop)
        
        # Log starting message
        self.log_status("Starting conversation...")
    
    def stop_conversation(self):
        """Stop the current conversation"""
        # Update UI state
        self.conversation_button.config(text="Start Conversation")
        self.status_var.set("Status: Disconnected")
        self.conversation_active = False
        
        # Enable settings after conversation ends
        self._set_conversation_ui_state(disabled=False)
        
        # Stop the event loop
        if self.loop:
            for task in asyncio.all_tasks(self.loop):
                task.cancel()
            
            # Schedule loop stop
            self.loop.call_soon_threadsafe(self.loop.stop)
        
        # Reset live_loop
        self.live_loop = None
        
        # Log message
        self.log_status("Conversation stopped.")
    
    def _set_conversation_ui_state(self, disabled):
        """Enable or disable UI elements during conversation"""
        # Disable settings widgets during conversation
        state = "disabled" if disabled else "normal"
        
        # Disable settings button during conversation
        self.settings_button.config(state=state)
        
        # If settings are visible, disable all settings widgets
        if self.settings_visible:
            for widget in self.settings_frame.winfo_children():
                if isinstance(widget, (ttk.Combobox, ttk.Entry, ttk.Button, ttk.Checkbutton)):
                    if widget != self.system_message_button:  # Allow toggling system message
                        widget.config(state=state)
    
    async def create_and_run_live_loop(self):
        """Create and run a LiveLoop instance"""
        try:
            # Initialize Gemini client
            client = genai.Client(http_options={"api_version": "v1beta"}, api_key=api_key)
            
            # Create config
            config = self.create_gemini_config()
            
            # Log configuration
            self.log_status(f"Using audio source: {self.config['audio_source']}")
            self.log_status(f"Using video mode: {self.config['video_mode']}")
            self.log_status(f"Response modality: {self.config['response_modality']}")
            
            # Log microphone initialization if mic is active
            if self.config['audio_source'] in ["microphone", "both"]:
                self.log_status("Initializing microphone...")
                
                # List available audio devices for debugging
                try:
                    import pyaudio
                    p = pyaudio.PyAudio()
                    mic_info = "Available audio devices:\n"
                    for i in range(p.get_device_count()):
                        dev_info = p.get_device_info_by_index(i)
                        mic_info += f"[{i}] {dev_info.get('name')}"
                        mic_info += f" (Input: {dev_info.get('maxInputChannels')}, Output: {dev_info.get('maxOutputChannels')})\n"
                    self.log_status(mic_info)
                    p.terminate()
                except Exception as e:
                    self.log_status(f"Error listing audio devices: {e}")
            
            # Create LiveLoop instance
            self.live_loop = LiveLoop(
                video_mode=self.config['video_mode'],
                client=client,
                model="models/gemini-2.0-flash-live-001",
                config=config,
                initial_message="[CALL_START]",
                audio_source=self.config['audio_source'],
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
            
            # Replace the output_text method to display in GUI instead of console
            accumulated_text = [""]  # Using a list for mutable state in the closure
            
            def custom_output_text(text):
                accumulated_text[0] += text
                
                # Check if we have a natural break or enough accumulated text
                if text.endswith(("\n")) or len(accumulated_text[0]) > 300:
                    # Display in UI
                    display_text = accumulated_text[0]
                    self.root.after(0, lambda t=display_text: self.display_message("Aya", t))
                    
                    # Reset accumulated text
                    accumulated_text[0] = ""
            
            # Replace the original output_text method
            self.live_loop.output_text = custom_output_text
            
            # Update connection status
            self.root.after(0, lambda: self.status_var.set("Status: Connected"))
            
            # Start the LiveLoop
            try:
                self.log_status("Connecting to Gemini...")
                await self.live_loop.run()
            except asyncio.CancelledError:
                self.log_status("Conversation stopped.")
                self.root.after(0, lambda: self.status_var.set("Status: Disconnected"))
                self.root.after(0, lambda: self.conversation_button.config(text="Start Conversation"))
                self.root.after(0, lambda: setattr(self, 'conversation_active', False))
                self.root.after(0, lambda: self._set_conversation_ui_state(disabled=False))
                self.live_loop = None
            except Exception as e:
                error_msg = f"Error in conversation: {e}"
                self.log_status(error_msg)
                self.root.after(0, lambda: self.status_var.set("Status: Error"))
                self.root.after(0, lambda: self.conversation_button.config(text="Start Conversation"))
                self.root.after(0, lambda: setattr(self, 'conversation_active', False))
                self.root.after(0, lambda: self._set_conversation_ui_state(disabled=False))
                self.live_loop = None
        except Exception as e:
            error_msg = f"Failed to start conversation: {e}"
            self.log_status(error_msg)
            self.root.after(0, lambda: self.status_var.set("Status: Error"))
            self.root.after(0, lambda: self.conversation_button.config(text="Start Conversation"))
            self.root.after(0, lambda: setattr(self, 'conversation_active', False))
            self.root.after(0, lambda: self._set_conversation_ui_state(disabled=False))
            self.live_loop = None
    
    def create_gemini_config(self):
        """Create a Gemini config using the current settings"""
        # Get language and voice settings
        language_code = LANGUAGES[self.config["language"]]
        voice_name = VOICES[self.config["voice"]]
        
        # Configure tools if enabled
        tools = []
        if self.config["tools_enabled"]:
            # Check if tool_config exists (otherwise use empty list)
            if hasattr(self, 'tool_config'):
                # Add search tool if enabled
                if self.tool_config.get("search", False):
                    search_tool = {'google_search': {}}
                    tools.append(search_tool)
                
                # Collect enabled functions
                enabled_functions = []
                for func_name, enabled in self.tool_config.items():
                    if enabled and func_name in FunctionRegistry._functions:
                        # Get the function from the registry
                        func_impl = FunctionRegistry._functions[func_name]["implementation"]
                        enabled_functions.append(func_impl)
                
                # Add function tools if any are enabled
                if enabled_functions:
                    function_tools = {
                        'function_declarations': get_declarations_for_functions(enabled_functions)
                    }
                    tools.append(function_tools)
        
        # Use the utility function to create the config
        return create_gemini_config(
            system_message_path=self.selected_prompt_path,
            language_code=language_code,
            voice_name=voice_name,
            response_modality=self.config["response_modality"],
            tools=tools
        )
    
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
        if self.conversation_active and self.live_loop and hasattr(self.live_loop, 'session'):
            asyncio.run_coroutine_threadsafe(self.send_to_live_loop(message), self.loop)
        else:
            self.log_status("Cannot send message: No active conversation")
    
    async def send_to_live_loop(self, message):
        """Send a message to the LiveLoop instance"""
        if self.live_loop and hasattr(self.live_loop, 'session'):
            try:
                await self.live_loop.session.send(input=message, end_of_turn=True)
            except Exception as e:
                self.log_status(f"Error sending message: {e}")
    
    def toggle_settings(self):
        """Toggle the visibility of settings panel"""
        self.settings_visible = not self.settings_visible
        
        if self.settings_visible:
            # Show settings
            self.settings_frame.pack(fill=tk.X, pady=5, after=self.control_bar)
            self.settings_button.config(text="▲ Hide Settings")
        else:
            # Hide settings
            self.settings_frame.pack_forget()
            self.settings_button.config(text="▼ Show Settings")
            
            # Also hide system message if it's visible
            if self.system_message_visible:
                self.toggle_system_message()
    
    def toggle_system_message(self):
        """Toggle the visibility of the system message"""
        self.system_message_visible = not self.system_message_visible
        
        if self.system_message_visible:
            # Show system message
            self.system_message_frame.grid()
            self.system_message_button.config(text="Hide System Message")
        else:
            # Hide system message
            self.system_message_frame.grid_remove()
            self.system_message_button.config(text="Show System Message")
    
    def update_audio_source(self):
        """Update audio source based on checkbox states"""
        mic = self.mic_var.get()
        computer = self.computer_audio_var.get()
        
        # Determine audio source based on checkboxes
        if mic and computer:
            self.config["audio_source"] = "both"
        elif mic:
            self.config["audio_source"] = "microphone"
        elif computer:
            self.config["audio_source"] = "computer"
        else:
            self.config["audio_source"] = "none"
        
        # Check for potential audio loop and warn user
        if self.config["audio_source"] in ["computer", "both"] and self.config["response_modality"] == "AUDIO":
            self.display_warning("Warning: Using computer audio with audio output may create feedback.")
    
    def update_config_from_ui(self):
        """Update configuration from UI selections"""
        # Only update if conversation is not active
        if self.conversation_active:
            self.display_warning("Cannot change settings during active conversation.")
            # Reset UI elements to match current config
            self.reset_ui_to_config()
            return
            
        # Update config from UI settings
        self.config["language"] = self.language_var.get()
        self.config["voice"] = self.voice_var.get()
        self.config["response_modality"] = self.output_var.get()
        self.config["text_input"] = self.text_input_var.get()
        self.config["tools_enabled"] = self.tools_var.get()
        self.config["video_mode"] = self.video_var.get()
        
        # Update audio source
        self.update_audio_source()
        
        # Enable/disable text input based on checkbox
        if self.config["text_input"]:
            self.input_frame.pack(fill=tk.X, pady=5)
        else:
            self.input_frame.pack_forget()
        
        # Disable/enable audio settings based on output modality
        audio_enabled = self.config["response_modality"] == "AUDIO"
        self._set_widget_state([self.language_var, self.voice_var], not audio_enabled)
    
    def reset_ui_to_config(self):
        """Reset UI elements to match current config"""
        # Reset dropdowns to match config
        self.language_var.set(self.config["language"])
        self.voice_var.set(self.config["voice"])
        self.output_var.set(self.config["response_modality"])
        self.video_var.set(self.config["video_mode"])
        
        # Reset checkboxes
        self.text_input_var.set(self.config["text_input"])
        self.tools_var.set(self.config["tools_enabled"])
        
        # Reset audio checkboxes
        audio_source = self.config["audio_source"]
        self.mic_var.set(audio_source in ["microphone", "both"])
        self.computer_audio_var.set(audio_source in ["computer", "both"])
    
    def _set_widget_state(self, widgets, disabled=True):
        """Helper to enable/disable widgets"""
        state = "disabled" if disabled else "readonly"
        for widget in widgets:
            if hasattr(widget, "config"):
                widget.config(state=state)
    
    def on_category_selected(self, *args):
        """Handle category selection change"""
        if not hasattr(self, 'category_var'):
            return
        
        selected = self.category_var.get()
        if selected in self.categories:
            self.current_category = selected
            self.update_prompt_dropdown()
    
    def on_prompt_selected(self, *args):
        """Handle prompt selection change"""
        if not all(hasattr(self, attr) for attr in ['prompt_var', 'system_message']):
            return
            
        if self.current_category and self.prompt_var.get():
            selected_filename = self.prompt_var.get()
            
            # Find full path by matching filename
            for path in self.system_prompts.get(self.current_category, []):
                if os.path.basename(path) == selected_filename:
                    # Update selected path
                    self.selected_prompt_path = path
                    
                    # Load and display system message
                    system_msg = load_system_message(path)
                    self.system_message.delete(1.0, tk.END)
                    self.system_message.insert(tk.END, system_msg)
                    break
    
    def refresh_system_prompts(self):
        """Refresh the list of available system prompts"""
        # Get available system prompts
        prompt_dict = list_system_messages()
        
        # Store the original dictionary
        self.system_prompts = prompt_dict
        
        # Get categories and sort them
        self.categories = sorted(prompt_dict.keys())
        
        # Remember current selections
        current_category = self.current_category
        current_prompt_path = self.selected_prompt_path
        
        # Reset current selections for update
        self.current_category = None
        self.current_category_prompts = []
        
        # Update category dropdown if it exists
        if hasattr(self, 'category_combo'):
            self.category_combo['values'] = self.categories
            
            # Try to maintain selection or set to first value
            if current_category in self.categories:
                self.category_var.set(current_category)
            elif self.categories:
                self.category_var.set(self.categories[0])
                current_category = self.categories[0]
            
            self.current_category = current_category
            self.update_prompt_dropdown()
            
            # Try to maintain the selected prompt if possible
            if current_prompt_path:
                for category, prompts in self.system_prompts.items():
                    if current_prompt_path in prompts:
                        # Select this category and prompt
                        self.category_var.set(category)
                        self.current_category = category
                        
                        # Update prompts dropdown
                        self.update_prompt_dropdown()
                        
                        # Select the prompt
                        prompt_name = os.path.basename(current_prompt_path)
                        if prompt_name in self.get_prompt_display_names():
                            self.prompt_var.set(prompt_name)
                        break
        # If UI hasn't been created yet, just set a default category
        elif self.categories:
            self.current_category = self.categories[0]
    
    def get_prompt_display_names(self):
        """Get display names for prompts in the current category"""
        if not self.current_category or self.current_category not in self.system_prompts:
            return []
        
        # Get file names without full paths
        return [os.path.basename(path) for path in self.system_prompts[self.current_category]]
    
    def update_prompt_dropdown(self):
        """Update the prompt dropdown based on selected category"""
        # Skip if UI components don't exist yet or no category is selected
        if not hasattr(self, 'prompt_combo') or not self.current_category:
            return
        
        if self.current_category in self.system_prompts:
            # Get file names for display
            display_names = self.get_prompt_display_names()
            self.current_category_prompts = display_names
            
            # Update dropdown
            self.prompt_combo['values'] = display_names
            
            # Select first item if list not empty
            if display_names and hasattr(self, 'prompt_var'):
                self.prompt_var.set(display_names[0])
                self.on_prompt_selected()
    
    def on_display_change(self, *args):
        """Handle display type selection change"""
        display_type = self.display_var.get()
        
        # Clear the message area
        self.message_area.config(state=tk.NORMAL)
        self.message_area.delete(1.0, tk.END)
        
        # Display the appropriate content
        if display_type == "Conversation":
            self.message_area.insert(tk.END, self.message_content)
        elif display_type == "Hints":
            self.message_area.insert(tk.END, self.hints_content)
        elif display_type == "Status":
            self.message_area.insert(tk.END, self.status_content)
        
        self.message_area.config(state=tk.DISABLED)
        self.message_area.see(tk.END)
    
    def clear_display(self):
        """Clear the current display content"""
        display_type = self.display_var.get()
        
        if display_type == "Conversation":
            self.message_content = ""
        elif display_type == "Hints":
            self.hints_content = ""
        elif display_type == "Status":
            self.status_content = ""
        
        # Update display
        self.message_area.config(state=tk.NORMAL)
        self.message_area.delete(1.0, tk.END)
        self.message_area.config(state=tk.DISABLED)
    
    def configure_tools(self):
        """Open a dialog to configure available tools"""
        # Create a popup window
        tools_window = tk.Toplevel(self.root)
        tools_window.title("Configure Tools")
        tools_window.geometry("500x400")
        tools_window.transient(self.root)  # Make window modal
        tools_window.grab_set()  # Make window modal
        
        # Set the window style
        tools_window.configure(bg=self.bg_color)
        
        # Add a title label
        title_label = ttk.Label(
            tools_window, 
            text="Select Tools to Enable", 
            font=(None, 12, "bold"),
            background=self.bg_color,
            foreground=self.fg_color
        )
        title_label.pack(pady=10)
        
        # Create a frame to hold the checkboxes
        checkbox_frame = ttk.Frame(tools_window)
        checkbox_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Add scrollbar for many tools
        checkbox_canvas = tk.Canvas(checkbox_frame, bg=self.bg_color, highlightthickness=0)
        scrollbar = ttk.Scrollbar(checkbox_frame, orient=tk.VERTICAL, command=checkbox_canvas.yview)
        scrollable_frame = ttk.Frame(checkbox_canvas)
        
        # Configure scrolling
        scrollable_frame.bind(
            "<Configure>",
            lambda e: checkbox_canvas.configure(scrollregion=checkbox_canvas.bbox("all"))
        )
        
        checkbox_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        checkbox_canvas.configure(yscrollcommand=scrollbar.set)
        
        # Pack the scrollbar and canvas
        checkbox_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Create variables to track selections
        tool_vars = {}
        
        # Section: Search Tool
        search_label = ttk.Label(
            scrollable_frame, 
            text="Search Tool", 
            font=(None, 11, "bold"),
            background=self.bg_color,
            foreground=self.fg_color
        )
        search_label.pack(anchor=tk.W, pady=(10, 5))
        
        search_var = tk.BooleanVar(value=False)
        search_check = ttk.Checkbutton(
            scrollable_frame, 
            text="Google Search", 
            variable=search_var
        )
        search_check.pack(anchor=tk.W, padx=20)
        tool_vars["search"] = search_var
        
        # Section: Code Execution
        code_label = ttk.Label(
            scrollable_frame, 
            text="Code Execution", 
            font=(None, 11, "bold"),
            background=self.bg_color,
            foreground=self.fg_color
        )
        code_label.pack(anchor=tk.W, pady=(10, 5))
        
        code_var = tk.BooleanVar(value=False)
        code_check = ttk.Checkbutton(
            scrollable_frame, 
            text="Python Code Execution", 
            variable=code_var
        )
        code_check.pack(anchor=tk.W, padx=20)
        tool_vars["code_execution"] = code_var
        
        # Section: Function Registry Tools
        func_label = ttk.Label(
            scrollable_frame, 
            text="Function Registry Tools", 
            font=(None, 11, "bold"),
            background=self.bg_color,
            foreground=self.fg_color
        )
        func_label.pack(anchor=tk.W, pady=(10, 5))
        
        # Get all registered functions
        for func_name, func_info in FunctionRegistry._functions.items():
            description = func_info.get("declaration", {}).description
            short_desc = description[:50] + "..." if description and len(description) > 50 else description
            
            func_var = tk.BooleanVar(value=False)
            func_check = ttk.Checkbutton(
                scrollable_frame, 
                text=f"{func_name} - {short_desc}", 
                variable=func_var
            )
            func_check.pack(anchor=tk.W, padx=20)
            tool_vars[func_name] = func_var
        
        # Button frame
        button_frame = ttk.Frame(tools_window)
        button_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Function to save selections
        def save_selections():
            # Create a new config dictionary
            selected_tools = {name: var.get() for name, var in tool_vars.items()}
            
            # Update tool config
            self.tool_config = selected_tools
            
            # Log the selections
            selected_names = [name for name, selected in selected_tools.items() if selected]
            self.log_status(f"Updated tool configuration. Enabled tools: {', '.join(selected_names) or 'None'}")
            
            # Close the window
            tools_window.destroy()
        
        # Save button
        save_button = ttk.Button(
            button_frame,
            text="Save",
            command=save_selections
        )
        save_button.pack(side=tk.RIGHT, padx=5)
        
        # Cancel button
        cancel_button = ttk.Button(
            button_frame,
            text="Cancel",
            command=tools_window.destroy
        )
        cancel_button.pack(side=tk.RIGHT, padx=5)
        
        # Set initial values if tool_config exists
        if hasattr(self, 'tool_config'):
            for name, var in tool_vars.items():
                if name in self.tool_config:
                    var.set(self.tool_config[name])
        else:
            # Initialize tool_config if it doesn't exist
            self.tool_config = {name: False for name in tool_vars.keys()}
    
    def display_message(self, sender, message):
        """Display a message in the conversation area"""
        if sender is None:
            text = message
        else:
            text = f"\n{sender}: {message}\n\n"
        
        # Add to message content buffer
        self.message_content += text
        
        # Update display if showing conversation
        if self.display_var.get() == "Conversation":
            self.message_area.config(state=tk.NORMAL)
            self.message_area.insert(tk.END, text)
            self.message_area.see(tk.END)
            self.message_area.config(state=tk.DISABLED)
    
    def display_hint(self, hint):
        """Display a hint in the hints area"""
        formatted_hint = f"{hint}\n\n"
        
        # Add to hints content buffer
        self.hints_content += formatted_hint
        
        # Update display if showing hints
        if self.display_var.get() == "Hints":
            self.message_area.config(state=tk.NORMAL)
            self.message_area.insert(tk.END, formatted_hint)
            self.message_area.see(tk.END)
            self.message_area.config(state=tk.DISABLED)
    
    def log_status(self, message):
        """Log a status message"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        formatted_status = f"[{timestamp}] {message}\n"
        
        # Add to status content buffer
        self.status_content += formatted_status
        
        # Update display if showing status
        if self.display_var.get() == "Status":
            self.message_area.config(state=tk.NORMAL)
            self.message_area.insert(tk.END, formatted_status)
            self.message_area.see(tk.END)
            self.message_area.config(state=tk.DISABLED)
        
        # Also print to console for debugging
        print(formatted_status.strip())
    
    def display_warning(self, message):
        """Display a warning message in status and show a popup"""
        self.log_status(f"WARNING: {message}")
        
        import tkinter.messagebox as messagebox
        messagebox.showwarning("Warning", message)

def main():
    # Create the Tkinter root with themed support
    root = ThemedTk(theme="equilux")
    
    # Create the app
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