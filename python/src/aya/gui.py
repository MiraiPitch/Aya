import asyncio
import os
import sys
import tkinter as tk
import threading
import datetime
from tkinter import ttk, scrolledtext
from PIL import Image, ImageTk
from ttkthemes import ThemedTk

# Package imports
from aya.live_loop import LiveLoop
from aya.function_registry import FunctionRegistry, get_declarations_for_functions
from aya.utils import (
    load_system_message, 
    list_system_messages, 
    create_gemini_config,
    get_package_resource_path,
    LANGUAGES,
    VOICES,
    AUDIO_SOURCES,
    VIDEO_MODES,
    MODALITIES
)

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

        self._init_complete = False
        self.refresh_system_prompts()
        self._init_complete = True
        
        # Ensure the default prompt is loaded into the system message area if visible
        if hasattr(self, 'system_message') and self.selected_prompt_path:
            try:
                system_msg = load_system_message(self.selected_prompt_path)
                self.system_message.delete(1.0, tk.END)
                self.system_message.insert(tk.END, system_msg)
                print(f"Initialized with system prompt: {self.selected_prompt_path}")
            except Exception as e:
                print(f"Error loading system prompt: {e}")
                # Try fallback to default
                if hasattr(self, 'default_prompt_path'):
                    try:
                        system_msg = load_system_message(self.default_prompt_path)
                        self.system_message.delete(1.0, tk.END)
                        self.system_message.insert(tk.END, system_msg)
                        print(f"Initialized with default prompt: {self.default_prompt_path}")
                        # Update selected prompt to default
                        self.selected_prompt_path = self.default_prompt_path
                    except:
                        print("Could not load default prompt either")
        
        # Initialize tool configuration
        self.tool_config = {
            "search": True,
            "code_execution": True,
            "write_message_to_gui": True,
            "write_live_hints": True,
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
        
        # Load the Aya logo
        try:
            logo_path = get_package_resource_path("images/aya-logo.png")
            self.logo_img = Image.open(logo_path)
            # Smaller logo for header
            self.header_logo_img = self.logo_img.resize((40, 40), Image.Resampling.LANCZOS)
            self.header_logo_photo = ImageTk.PhotoImage(self.header_logo_img)
            
            # Use the ICO file for window icon
            ico_path = get_package_resource_path("images/aya-logo.ico")
            if os.path.exists(ico_path):
                self.root.iconbitmap(ico_path)
            else:
                # Fallback to PNG if ICO not found
                window_icon_img = self.logo_img.resize((100, 100), Image.Resampling.LANCZOS)
                window_icon_photo = ImageTk.PhotoImage(window_icon_img)
                self.root.iconphoto(True, window_icon_photo)
        except Exception as e:
            print(f"Error loading logo: {e}")
            self.header_logo_photo = None
        
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
        self.default_prompt_path = "system_prompts/default/aya_default_tools.txt"
        self.selected_prompt_path = self.default_prompt_path
        
        # Basic initialization of system prompts
        prompt_dict = list_system_messages()
        self.system_prompts = prompt_dict
        self.categories = sorted(prompt_dict.keys())
        if self.categories:
            self.current_category = self.categories[0]
            # Try to find the default prompt in the system prompts
            default_found = False
            for category, prompts in self.system_prompts.items():
                for path in prompts:
                    if "aya_default_tools.txt" in path:
                        self.selected_prompt_path = path
                        self.current_category = category
                        default_found = True
                        print(f"Found default prompt at: {path}")
                        break
                if default_found:
                    break
        
        # Store content buffers
        self.message_content = ""
        self.hints_content = ""
        self.status_content = ""
        
        # Store configuration settings
        self.config = {
            "language": "English (US)",
            "voice": "Leda (Female)",
            "response_modality": "AUDIO",
            "audio_source": "microphone",
            "video_mode": "none",
            "text_input": True,
            "tools_enabled": True
        }
        
        # Main frame
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Header frame with logo and controls
        self.header_frame = ttk.Frame(self.main_frame)
        self.header_frame.pack(fill=tk.X, pady=5)
        
        # Left side: Logo and title
        left_frame = ttk.Frame(self.header_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.Y)
        
        # Display logo if loaded
        if hasattr(self, 'header_logo_photo') and self.header_logo_photo:
            logo_label = ttk.Label(left_frame, image=self.header_logo_photo, background=self.bg_color)
            logo_label.pack(side=tk.LEFT, padx=10)
            
            # App title
            title_label = ttk.Label(
                left_frame, 
                text="Aya", 
                font=(None, 16, "bold"),
                background=self.bg_color,
                foreground=self.fg_color
            )
            title_label.pack(side=tk.LEFT, padx=10)
        
        # Right side: Control buttons
        right_frame = ttk.Frame(self.header_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Start/Stop conversation button
        self.conversation_button = ttk.Button(
            right_frame, 
            text="▶ Start Conversation",
            command=self.toggle_conversation
        )
        self.conversation_button.pack(side=tk.LEFT, padx=5)
        
        # Settings toggle button
        self.settings_button = ttk.Button(
            right_frame, 
            text="▼ Show Settings",
            command=self.toggle_settings
        )
        self.settings_button.pack(side=tk.LEFT, padx=5)
        
        # Clear button
        self.clear_button = ttk.Button(
            right_frame,
            text="Clear Conversation",
            command=self.clear_display
        )
        self.clear_button.pack(side=tk.LEFT, padx=5)
        
        # Status indicator
        self.status_var = tk.StringVar(value="Status: Disconnected")
        self.status_label = ttk.Label(right_frame, textvariable=self.status_var)
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        # Add a separator for visual clarity
        separator = ttk.Separator(self.main_frame, orient=tk.HORIZONTAL)
        separator.pack(fill=tk.X, pady=5)
        
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
        self.text_input_check = ttk.Checkbutton(
            self.settings_frame, 
            text="Text chat", 
            variable=self.text_input_var,
            command=self.update_config_from_ui
        )
        self.text_input_check.grid(row=1, column=0, sticky=tk.W, padx=20, pady=2)
        
        # Microphone option
        self.mic_var = tk.BooleanVar(value=True)
        self.mic_check = ttk.Checkbutton(
            self.settings_frame, 
            text="Microphone audio", 
            variable=self.mic_var,
            command=self.update_audio_source
        )
        self.mic_check.grid(row=2, column=0, sticky=tk.W, padx=20, pady=2)
        
        # Computer audio option
        self.computer_audio_var = tk.BooleanVar(value=False)
        self.computer_audio_check = ttk.Checkbutton(
            self.settings_frame, 
            text="Computer audio", 
            variable=self.computer_audio_var,
            command=self.update_audio_source
        )
        self.computer_audio_check.grid(row=3, column=0, sticky=tk.W, padx=20, pady=2)
        
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
        
        self.output_var = tk.StringVar(value="AUDIO")
        output_frame = ttk.Frame(self.settings_frame)
        output_frame.grid(row=1, column=2, sticky=tk.W, padx=5, pady=2)
        
        self.text_radio = ttk.Radiobutton(
            output_frame,
            text="Text",
            variable=self.output_var,
            value="TEXT",
            command=lambda: self.update_config_from_ui()
        )
        self.text_radio.pack(side=tk.LEFT, padx=5)
        
        self.audio_radio = ttk.Radiobutton(
            output_frame,
            text="Voice",
            variable=self.output_var,
            value="AUDIO",
            command=lambda: self.update_config_from_ui()
        )
        self.audio_radio.pack(side=tk.LEFT, padx=5)
        
        # Language selection
        ttk.Label(self.settings_frame, text="Voice language:").grid(
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
        self.tools_var = tk.BooleanVar(value=True)
        self.tools_check = ttk.Checkbutton(
            self.settings_frame, 
            text="Enable tools", 
            variable=self.tools_var,
            command=self.update_config_from_ui
        )
        self.tools_check.grid(row=1, column=3, sticky=tk.W, padx=20, pady=2)
        
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
        self.conversation_button.config(text="■ Stop Conversation")
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
        self.conversation_button.config(text="▶ Start Conversation")
        self.status_var.set("Status: Disconnected")
        self.conversation_active = False
        self.display_message(None, "\n---------------------------------\n")
        
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
        # If settings are visible, disable all settings widgets
        if self.settings_visible:
            for widget in self.settings_frame.winfo_children():
                if isinstance(widget, ttk.Combobox):
                    widget.config(state="disabled" if disabled else "readonly")
                elif isinstance(widget, (ttk.Entry, ttk.Button)):
                    if widget != self.system_message_button:  # Allow toggling system message
                        widget.config(state="disabled" if disabled else "normal")
                elif widget.winfo_class() == "TCheckbutton":
                    # For checkbuttons, use 'alternate' state to maintain visual state when disabled
                    if disabled:
                        widget.state(['disabled', '!alternate'])
                        # Ensure the checkbutton displays correctly in disabled state
                        # The checkbutton will display as checked/unchecked based on variable value
                    else:
                        widget.state(['!disabled'])
                elif widget.winfo_class() == "TRadiobutton":
                    # Handle radiobutton state
                    if disabled:
                        widget.state(['disabled'])
                    else:
                        widget.state(['!disabled'])
                
                # Recurse into any frames
                if widget.winfo_class() in ("TFrame", "TLabelframe"):
                    for child in widget.winfo_children():
                        if isinstance(child, ttk.Combobox):
                            child.config(state="disabled" if disabled else "readonly")
                        elif isinstance(child, (ttk.Entry, ttk.Button)):
                            child.config(state="disabled" if disabled else "normal")
                        elif child.winfo_class() == "TCheckbutton":
                            if disabled:
                                child.state(['disabled', '!alternate'])
                            else:
                                child.state(['!disabled'])
                        elif child.winfo_class() == "TRadiobutton":
                            if disabled:
                                child.state(['disabled'])
                            else:
                                child.state(['!disabled'])
    
    async def create_and_run_live_loop(self):
        """Create and run a LiveLoop instance"""
        try:
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
                self.root.after(0, lambda: self.conversation_button.config(text="▶ Start Conversation"))
                self.root.after(0, lambda: setattr(self, 'conversation_active', False))
                self.root.after(0, lambda: self._set_conversation_ui_state(disabled=False))
                self.live_loop = None
            except Exception as e:
                error_msg = f"Error in conversation: {e}"
                self.log_status(error_msg)
                self.root.after(0, lambda: self.status_var.set("Status: Error"))
                self.root.after(0, lambda: self.conversation_button.config(text="▶ Start Conversation"))
                self.root.after(0, lambda: setattr(self, 'conversation_active', False))
                self.root.after(0, lambda: self._set_conversation_ui_state(disabled=False))
                self.live_loop = None
        except Exception as e:
            error_msg = f"Failed to start conversation: {e}"
            self.log_status(error_msg)
            self.root.after(0, lambda: self.status_var.set("Status: Error"))
            self.root.after(0, lambda: self.conversation_button.config(text="▶ Start Conversation"))
            self.root.after(0, lambda: setattr(self, 'conversation_active', False))
            self.root.after(0, lambda: self._set_conversation_ui_state(disabled=False))
            self.live_loop = None
    
    def create_gemini_config(self):
        """Create a Gemini config using the current settings"""
        # Verify if the selected prompt path exists
        system_prompt_path = self.selected_prompt_path
        if not os.path.exists(system_prompt_path) and hasattr(self, 'default_prompt_path'):
            # Try to use the default path as a fallback
            if os.path.exists(self.default_prompt_path):
                system_prompt_path = self.default_prompt_path
                print(f"Selected prompt not found, using default: {system_prompt_path}")
            else:
                print(f"Warning: Neither selected prompt nor default prompt found.")
        
        # Configure tools if enabled
        tools = []
        if self.config["tools_enabled"]:
            # Check if tool_config exists (otherwise use empty list)
            if hasattr(self, 'tool_config'):
                # Add search tool if enabled
                if self.tool_config.get("search", False):
                    search_tool = {'google_search': {}}
                    tools.append(search_tool)

                if self.tool_config.get("code_execution", False):
                    code_execution_tool = {'code_execution': {}}
                    tools.append(code_execution_tool)
                
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
        
        # Use the utility function to create the config with all parameters
        return create_gemini_config(
            system_message_path=system_prompt_path,
            language_code=self.config["language"],  # Pass display name, util function will handle conversion
            voice_name=self.config["voice"],        # Pass display name, util function will handle conversion
            response_modality=self.config["response_modality"],
            tools=tools,
            temperature=0.05                       # Fixed temperature value
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
            self.settings_frame.pack(fill=tk.X, pady=5, after=self.header_frame)
            self.settings_button.config(text="▲ Hide Settings")
            
            # If conversation is active, ensure settings are disabled
            if self.conversation_active:
                self._set_conversation_ui_state(disabled=True)
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
        
        # Only show the warning if this is a user-initiated change (not during reset)
        # and only warn if we're in a configuration that could cause feedback
        if not hasattr(self, '_updating_ui') and self.config["audio_source"] in ["computer", "both"] and self.config["response_modality"] == "AUDIO":
            # Log the warning instead of displaying a popup to avoid potential endless loops
            self.log_status("Warning: Using computer audio with audio output may create feedback.")
            
    def update_config_from_ui(self):
        """Update configuration from UI selections"""
        # Only update if conversation is not active
        if self.conversation_active:
            # Don't display warnings if we're already in the process of resetting UI
            if not hasattr(self, '_updating_ui') or not self._updating_ui:
                self.display_warning("Cannot change settings during active conversation.")
                # Set a flag to prevent multiple warning popups
                self._updating_ui = True
                try:
                    # Reset UI elements to match current config
                    self.reset_ui_to_config()
                finally:
                    self._updating_ui = False
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
        # Set a flag to prevent warning popups during reset
        self._updating_ui = True
        
        try:
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
            
            # If conversation is active, make sure settings are properly disabled
            if self.conversation_active and self.settings_visible:
                self._set_conversation_ui_state(disabled=True)
        finally:
            # Remove the updating flag when done
            self._updating_ui = False
    
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
                    # Only update if the path has changed
                    if self.selected_prompt_path != path:
                        # Update selected path
                        self.selected_prompt_path = path
                        
                        # Load and display system message
                        system_msg = load_system_message(path)
                        self.system_message.delete(1.0, tk.END)
                        self.system_message.insert(tk.END, system_msg)
                        
                        # Only log when not initializing and path actually changed
                        if hasattr(self, '_init_complete') and self._init_complete:
                            print(f"Selected system prompt: {path}")
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
            
            # Flag to track if we've found our preferred prompt
            found_preferred_prompt = False
            
            # First, try to find the exact path that was selected
            if current_prompt_path:
                for category, prompts in self.system_prompts.items():
                    for path in prompts:
                        if os.path.normpath(current_prompt_path) == os.path.normpath(path):
                            # We found the exact path
                            self.category_var.set(category)
                            self.current_category = category
                            self.selected_prompt_path = path
                            found_preferred_prompt = True
                            if not hasattr(self, '_init_complete'):
                                print(f"Maintained selected prompt: {path}")
                            break
                    if found_preferred_prompt:
                        break
            
            # If we didn't find the exact path but have a default_prompt_path, try to find that
            if not found_preferred_prompt and hasattr(self, 'default_prompt_path'):
                default_basename = os.path.basename(self.default_prompt_path)
                for category, prompts in self.system_prompts.items():
                    for path in prompts:
                        if os.path.basename(path) == default_basename:
                            # We found the default prompt
                            self.category_var.set(category)
                            self.current_category = category
                            self.selected_prompt_path = path
                            found_preferred_prompt = True
                            if not hasattr(self, '_init_complete'):
                                print(f"Using default prompt: {path}")
                            break
                    if found_preferred_prompt:
                        break
            
            # If we still haven't found a prompt, use the first available
            if not found_preferred_prompt:
                # Try to maintain the category if it exists
                if current_category in self.categories:
                    self.category_var.set(current_category)
                    self.current_category = current_category
                # Otherwise use the first category
                elif self.categories:
                    self.category_var.set(self.categories[0])
                    self.current_category = self.categories[0]
                
                # Update the prompt dropdown based on the selected category
                self.update_prompt_dropdown()
                
                # Note: update_prompt_dropdown will select first prompt in the category
            else:
                # We found our preferred prompt, so update the dropdown for that category
                self.update_prompt_dropdown()
                
                # Make sure the correct prompt is selected in the dropdown
                if self.current_category:
                    selected_basename = os.path.basename(self.selected_prompt_path)
                    if selected_basename in self.get_prompt_display_names():
                        self.prompt_var.set(selected_basename)
                        # Call on_prompt_selected to update the system message
                        self.on_prompt_selected()
                    
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
            
            # Try to find the current selected_prompt_path in this category
            current_prompt_basename = os.path.basename(self.selected_prompt_path)
            found_in_category = False
            
            if current_prompt_basename in display_names:
                self.prompt_var.set(current_prompt_basename)
                found_in_category = True
            
            # Only select first item if we don't have a match and the list is not empty
            if not found_in_category and display_names and hasattr(self, 'prompt_var'):
                # Store the previous path before changing it
                previous_path = self.selected_prompt_path
                
                # Set to first item
                self.prompt_var.set(display_names[0])
                
                # Log the change only when not initializing
                if hasattr(self, '_init_complete') and self._init_complete:
                    print(f"Changed prompt from {previous_path} to {self.system_prompts[self.current_category][0]}")
                
            # We need to call on_prompt_selected to update the system message
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
            text = f"\n{sender}: {message.strip()}"
        
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
        
        # Only show popup if we don't already have an active warning dialog 
        # and we're not rapidly showing multiple warnings
        if not hasattr(self, '_warning_active') or not self._warning_active:
            try:
                # Set flag to prevent recursive warnings
                self._warning_active = True
                
                # Check if this is a repeated warning in a short timeframe
                current_time = datetime.datetime.now()
                if (hasattr(self, '_last_warning_time') and 
                    hasattr(self, '_last_warning_message') and
                    self._last_warning_message == message and
                    (current_time - self._last_warning_time).total_seconds() < 2):
                    # Skip showing another dialog for the same warning within 2 seconds
                    pass
                else:
                    import tkinter.messagebox as messagebox
                    messagebox.showwarning("Warning", message)
                    # Store this warning to prevent repetition
                    self._last_warning_time = current_time
                    self._last_warning_message = message
            finally:
                # Always reset the flag when done
                self._warning_active = False

def main():
    # Create the Tkinter root with themed support
    root = ThemedTk(theme="equilux")
    
    # Create the app
    app = AyaGUI(root)
    
    # Set up window close handler
    def on_closing():
        if app.conversation_active:
            app.stop_conversation()
        root.destroy()
        
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    # Start the Tkinter main loop
    root.mainloop()

if __name__ == "__main__":
    main() 