"""
WebSocket server for Aya AI Assistant
Provides real-time status updates and control interface for Tauri frontend
"""

import asyncio
import json
import logging
import time
import websockets
import traceback
from typing import Dict, Any, Set, Optional, Callable
from aya.utils import list_system_messages, LANGUAGES, VOICES, AUDIO_SOURCES, VIDEO_MODES, MODALITIES, GEMINI_LIVE_MODELS, create_gemini_config
from aya.live_loop import LiveLoop
from aya.function_registry import FunctionRegistry, get_declarations_for_functions
from aya.gemini_tools import get_current_date_and_time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Default model for Gemini Live API
DEFAULT_MODEL = "models/gemini-2.0-flash-live-001"


class AyaWebSocketServer:
    """WebSocket server for Aya AI Assistant"""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 8765, debug: bool = False):
        """Initialize the WebSocket server"""
        self.host = host
        self.port = port
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.status = "idle"
        self.is_running = False
        self.server = None
        self.on_start_callback: Optional[Callable] = None
        self.on_stop_callback: Optional[Callable] = None
        self.live_loop: Optional[LiveLoop] = None
        self.live_loop_task = None
        
        # Dynamic channel management
        self.available_channels = ["conversation", "logs", "status"]  # Initial channels
        self.protected_channels = {"logs", "status"}  # Protected channels
        
        # Enable debug logging if requested
        if debug:
            logger.setLevel(logging.DEBUG)
            logger.info("Debug logging enabled")
        else:
            logger.setLevel(logging.INFO)
        
        self._pending_messages = []
            
        # Set up custom log handler to send logs to the logs channel
        self._setup_log_handler()
        
        # Register the channel function once during initialization
        self._register_channel_function()

    def _get_timestamp(self) -> float:
        """Get current timestamp in milliseconds (JavaScript format)"""
        return time.time() * 1000

    def _register_channel_function(self):
        """Register the send_message_to_channel function once during initialization"""
        @FunctionRegistry.register()
        def send_message_to_channel(message: str, channel: str = "conversation") -> dict:
            """
            Send a message to any channel in the chat interface.
            Creates new channels dynamically if they don't exist.
            
            :param message: The message to send to the channel
            :param channel: The channel to send the message to (any string)
            :return: Result confirmation
            """
            try:
                if channel in self.protected_channels:
                    return {"error": f"Cannot send message to protected channel: {channel}"}

                # Add new channel if it doesn't exist
                if channel not in self.available_channels:
                    self.available_channels.append(channel)
                    logger.info(f"Added new channel: {channel}")
                    self._pending_messages.append({
                        'type': 'channel_added',
                        'channel': channel,
                        'timestamp': self._get_timestamp()
                    })
                
                # Store the message in a queue for later processing
                # This avoids any async operations during tool execution
                self._pending_messages.append({
                    'type': 'message',
                    'sender': 'tool',
                    'message': message, 
                    'channel': channel,
                    'timestamp': self._get_timestamp()
                })
                    
                
                # Schedule processing of pending messages
                try:
                    import asyncio
                    asyncio.create_task(self._process_pending_messages())
                except Exception:
                    # If we can't schedule, just print to console
                    print("Error scheduling pending messages")
                    print(f"[{channel.upper()}] tool: {message}")
                
                return {"result": f"Message sent to {channel} channel"}
                    
            except Exception as e:
                # Fallback to console
                print(f"[{channel.upper()}] tool: {message}")
                return {"error": f"Failed to send via WebSocket: {str(e)}"}
        
        # Store the function reference as a class variable
        self.send_message_to_channel_func = send_message_to_channel

    async def _process_pending_messages(self):
        """Process any pending messages from tool calls"""
        if not hasattr(self, '_pending_messages') or not self._pending_messages:
            return
            
        # Process all pending messages
        messages_to_process = self._pending_messages.copy()
        self._pending_messages.clear()
        
        for item in messages_to_process:
            try:
                if item['type'] == 'message':
                    await self.send_chat_message(item['sender'], item['message'], item['channel'])
                    logger.debug(f"Processed pending tool message: {item['message'][:50]}...")
                elif item['type'] == 'channel_added':
                    # Send channel_added notification
                    await self.send_to_all({
                        "type": "channel_added",
                        "channel": item['channel'],
                        "timestamp": item['timestamp']
                    })
                    logger.debug(f"Processed pending channel notification: {item['channel']}")
            except Exception as e:
                logger.error(f"Error processing pending item: {e}")
                # Fallback to console for messages
                if item['type'] == 'message':
                    print(f"[{item['channel'].upper()}] {item['sender']}: {item['message']}")

    def get_tools(self):
        """Get the complete tools configuration"""
        # Base tools configuration
        search_tool = {'google_search': {}}
        code_execution_tool = {'code_execution': {}}

        function_tools = {
            'function_declarations': get_declarations_for_functions([
                get_current_date_and_time,
                self.send_message_to_channel_func
            ])
        }
        return [search_tool, code_execution_tool, function_tools]

    def _setup_log_handler(self):
        """Set up a custom log handler that sends logs to the logs channel"""
        class WebSocketLogHandler(logging.Handler):
            def __init__(self, server):
                super().__init__()
                self.server = server
                
            def emit(self, record):
                if self.server and self.server.clients:
                    try:
                        # Format the log message
                        msg = self.format(record)
                        # Send to logs channel asynchronously
                        asyncio.create_task(
                            self.server.send_chat_message("system", msg, "logs")
                        )
                    except Exception:
                        # Don't let logging errors crash anything
                        pass
        
        # Create and configure the handler
        ws_handler = WebSocketLogHandler(self)
        ws_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(levelname)s - %(name)s - %(message)s')
        ws_handler.setFormatter(formatter)
        
        # Add to the main logger
        logging.getLogger().addHandler(ws_handler)

    async def register(self, websocket: websockets.WebSocketServerProtocol):
        """Register a new client"""
        self.clients.add(websocket)
        logger.info(f"Client connected. Total clients: {len(self.clients)}")
        
        # Send initial status
        await self.send_status_to_client(websocket)

    async def unregister(self, websocket: websockets.WebSocketServerProtocol):
        """Unregister a client"""
        try:
            self.clients.remove(websocket)
            logger.info(f"Client disconnected from {websocket.remote_address}. Total clients: {len(self.clients)}")
            # Log WebSocket state with version compatibility
            try:
                if hasattr(websocket, 'open'):
                    open_state = websocket.open
                else:
                    open_state = "unknown"
                
                if hasattr(websocket, 'closed'):
                    closed_state = websocket.closed
                else:
                    closed_state = "unknown"
                    
                logger.info(f"WebSocket state: open={open_state}, closed={closed_state}")
            except Exception as state_error:
                logger.debug(f"Could not check WebSocket state: {state_error}")
        except KeyError:
            logger.warning(f"Attempted to remove a client that wasn't registered")

    async def send_to_all(self, message: Dict[str, Any]):
        """Send a message to all connected clients"""
        if not self.clients:
            return
        
        message_str = json.dumps(message)
        await asyncio.gather(
            *[client.send(message_str) for client in self.clients],
            return_exceptions=True
        )

    async def send_status_to_client(self, websocket: websockets.WebSocketServerProtocol):
        """Send current status to a specific client"""
        status_message = {
            "type": "status",
            "status": self.status,
            "isRunning": self.is_running,
            "timestamp": self._get_timestamp()
        }
        await websocket.send(json.dumps(status_message))

    async def send_error(self, error: str, stack_trace: str = None):
        """Send error message to all clients"""
        error_message = {
            "type": "error",
            "error": error,
            "stackTrace": stack_trace,
            "timestamp": self._get_timestamp()
        }
        await self.send_to_all(error_message)

    async def send_chat_message(self, sender: str, message: str, channel: str = "conversation"):
        """Send a chat message to all clients"""
        chat_message = {
            "type": "chat_message",
            "sender": sender,
            "message": message,
            "channel": channel,
            "timestamp": self._get_timestamp()
        }
        await self.send_to_all(chat_message)

    async def send_log_message(self, level: str, message: str):
        """Send a log message to all clients"""
        log_message = {
            "type": "log_message",
            "level": level,
            "message": message,
            "timestamp": self._get_timestamp()
        }
        await self.send_to_all(log_message)

    async def send_tool_message(self, message: str, channel: str = "logs", sender: str = "tool"):
        """Send a message from a tool to a specific channel"""
        try:
            # Add new channel if it doesn't exist
            if channel not in self.available_channels:
                self.available_channels.append(channel)
                logger.info(f"Added new channel: {channel}")
                # Notify clients about new channel
                await self.send_to_all({
                    "type": "channel_added",
                    "channel": channel,
                    "timestamp": self._get_timestamp()
                })
            
            await self.send_chat_message(sender, message, channel)
            logger.debug(f"Tool message sent to {channel} channel: {message[:50]}...")
        except Exception as e:
            logger.error(f"Error sending tool message: {e}")
            # Fallback to console if WebSocket fails
            print(f"[{channel.upper()}] {sender}: {message}")

    async def update_status(self, status: str, data: Dict[str, Any] = None):
        """Update and broadcast status to all clients"""
        self.status = status
        status_message = {
            "type": "status",
            "status": status,
            "isRunning": self.is_running,
            "timestamp": self._get_timestamp()
        }
        
        if data:
            status_message["data"] = data
            
        await self.send_to_all(status_message)

    async def handle_message(self, websocket: websockets.WebSocketServerProtocol):
        """Handle incoming messages from clients"""
        try:
            async for message_str in websocket:
                try:
                    message = json.loads(message_str)
                    command = message.get("command")
                    
                    logger.info(f"Received command: {command}")
                    
                    if command == "start":
                        config = message.get("config", {})
                        await self.handle_start_command(config)
                    
                    elif command == "stop":
                        try:
                            await self.handle_stop_command()
                        except Exception as stop_error:
                            logger.error(f"Error in stop command: {stop_error}")
                            logger.error(traceback.format_exc())
                            # Send error but don't crash the connection
                            await websocket.send(json.dumps({
                                "type": "error",
                                "error": f"Stop command failed: {str(stop_error)}",
                                "timestamp": self._get_timestamp()
                            }))
                    
                    elif command == "get_resources":
                        # Ensure this command is handled immediately
                        await self.handle_get_resources(websocket)
                        continue  # Skip sending status update
                    
                    elif command == "send_message":
                        message_text = message.get("message", "")
                        await self.handle_send_message(message_text)
                        continue  # Skip sending status update
                    
                    elif command == "clear_channel":
                        channel = message.get("channel", "conversation")
                        await self.handle_clear_channel(channel)
                        continue  # Skip sending status update
                    
                    else:
                        logger.warning(f"Unknown command received: {command}")
                        await websocket.send(json.dumps({
                            "type": "error",
                            "error": f"Unknown command: {command}",
                            "timestamp": self._get_timestamp()
                        }))
                        continue  # Skip sending status update
                    
                    # Send status update after handling other commands
                    try:
                        await self.send_status_to_client(websocket)
                    except Exception as status_error:
                        logger.error(f"Error sending status update: {status_error}")
                        # Don't re-raise - just log the error
                    
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON received: {message_str}")
                    await websocket.send(json.dumps({
                        "type": "error",
                        "error": "Invalid JSON format",
                        "timestamp": self._get_timestamp()
                    }))
        
        except websockets.exceptions.ConnectionClosed as e:
            logger.info(f"Connection closed: code={e.code}, reason={e.reason}")
            # Map close codes for debugging
            close_code_meanings = {
                1000: "Normal closure",
                1001: "Going away", 
                1002: "Protocol error",
                1003: "Unsupported data",
                1005: "No status received",
                1006: "Abnormal closure",
                1007: "Invalid frame payload data",
                1008: "Policy violation",
                1009: "Message too big",
                1010: "Mandatory extension",
                1011: "Internal server error",
                1015: "TLS handshake"
            }
            meaning = close_code_meanings.get(e.code, f"Unknown code: {e.code}")
            logger.info(f"Close code meaning: {meaning}")
        except Exception as e:
            logger.error(f"Error in handle_message: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(traceback.format_exc())
            
            # Try to send error to client if connection is still open
            try:
                # Check if connection is still open (websockets library version compatibility)
                connection_open = True
                if hasattr(websocket, 'closed'):
                    connection_open = not websocket.closed
                elif hasattr(websocket, 'open'):
                    connection_open = websocket.open
                
                if connection_open:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "error": f"Server error: {str(e)}",
                        "timestamp": self._get_timestamp()
                    }))
            except Exception as send_error:
                logger.error(f"Failed to send error to client: {send_error}")
        finally:
            await self.unregister(websocket)

    async def handle_send_message(self, message: str):
        """Handle send_message command from client"""
        try:
            if not self.is_running or not self.live_loop:
                await self.send_log_message("warning", "Cannot send message: voice agent is not running")
                return
            
            # Send message to the LiveLoop
            if hasattr(self.live_loop, 'session') and self.live_loop.session:
                await self.live_loop.session.send(input=message, end_of_turn=True)
                await self.send_log_message("info", f"Message sent to voice agent: {message}")
            else:
                await self.send_log_message("error", "Voice agent session not available")
                
        except Exception as e:
            logger.error(f"Error sending message to voice agent: {e}")
            await self.send_log_message("error", f"Failed to send message: {str(e)}")

    async def handle_clear_channel(self, channel: str):
        """Handle clear_channel command from client"""
        try:
            # Log the channel clear action
            await self.send_log_message("info", f"Cleared {channel} channel")
        except Exception as e:
            logger.error(f"Error handling clear channel: {e}")
            await self.send_log_message("error", f"Failed to clear channel: {str(e)}")

    async def handle_start_command(self, config: Dict[str, Any]):
        """Handle start command from client"""
        try:
            if self.is_running:
                await self.send_to_all({
                    "type": "error",
                    "error": "Voice agent is already running",
                    "timestamp": self._get_timestamp()
                })
                return
                
            self.is_running = True
            await self.update_status("starting")
            
            # Extract configuration parameters from the client's config
            video_mode = config.get("videoMode", "none")
            language_display = config.get("language", "English (US)")  # Display name from frontend
            voice_display = config.get("voice", "Leda (Female)")  # Display name from frontend
            model_display = config.get("model", "Gemini 2.0 Flash Live")  # Display name from frontend
            response_modality = config.get("responseModality", "AUDIO")
            audio_source = config.get("audioSource", "microphone")
            system_prompt_path = config.get("systemPrompt", "system_prompts/default/aya_default_tools_cli.txt")
            initial_message = config.get("initialMessage", "[CALL_START]")
            
            # Convert display names to actual values
            language_code = LANGUAGES.get(language_display, "en-US")  # Convert display name to language code
            voice_name = VOICES.get(voice_display, "Leda")  # Convert display name to voice name
            model_name = GEMINI_LIVE_MODELS.get(model_display, DEFAULT_MODEL)  # Convert display name to model name
            
            logger.info(f"Language: {language_display} -> {language_code}")
            logger.info(f"Voice: {voice_display} -> {voice_name}")
            logger.info(f"Model: {model_display} -> {model_name}")
            
            # Create Gemini configuration
            gemini_config = create_gemini_config(
                system_message_path=system_prompt_path,
                language_code=language_code,
                voice_name=voice_name,
                response_modality=response_modality,
                tools=self.get_tools(),
                temperature=0.05
            )
            
            # Create LiveLoop instance with
            self.live_loop = LiveLoop(
                video_mode=video_mode,
                model=model_name,
                config=gemini_config,
                initial_message=initial_message,
                audio_source=audio_source,
                record_conversation=False
            )
            
            # Set status change callback
            self.live_loop.on_status_change = self.update_status
            
            # Override the output_text method to send messages to frontend
            original_output_text = self.live_loop.output_text
            accumulated_text = [""]  # Using a list for mutable state in the closure
            
            def custom_output_text(text):
                accumulated_text[0] += text
                
                # Check if we have a natural break or enough accumulated text
                if text.endswith(("\n", ".", "!", "?")) or len(accumulated_text[0]) > 800:
                    # Send to frontend
                    display_text = accumulated_text[0].strip()
                    if display_text:
                        asyncio.create_task(self.send_chat_message("assistant", display_text, "conversation"))
                    
                    # Reset accumulated text
                    accumulated_text[0] = ""
            
            # Replace the original output_text method
            self.live_loop.output_text = custom_output_text
            
            # Run the LiveLoop
            if self.on_start_callback:
                await self.on_start_callback(config)
            else:
                # Run directly if no callback is set
                self.live_loop_task = asyncio.create_task(self.live_loop.run())
                self.live_loop_task.add_done_callback(self._live_loop_done_callback)
        
        except Exception as e:
            logger.exception("Error starting voice agent")
            self.is_running = False
            await self.send_error(str(e), traceback.format_exc())
            await self.update_status("error")

    def _live_loop_done_callback(self, future):
        """Callback when LiveLoop task completes"""
        logger.info("=== LIVE_LOOP_DONE_CALLBACK STARTED ===")
        try:
            # Check for exceptions
            try:
                result = future.result()
                logger.info("LiveLoop task completed successfully")
                logger.info(f"LiveLoop result: {result}")
            except asyncio.CancelledError:
                logger.info("LiveLoop task was cancelled")
            except Exception as e:
                logger.error(f"LiveLoop task failed with error: {e}")
                logger.error(traceback.format_exc())
                # Send error to clients but don't crash the server
                try:
                    logger.info("Attempting to send error to clients...")
                    asyncio.create_task(self.send_error(f"LiveLoop error: {str(e)}", traceback.format_exc()))
                    logger.info("Error sent to clients successfully")
                except Exception as send_error:
                    logger.error(f"Failed to send LiveLoop error to clients: {send_error}")
                    logger.error(traceback.format_exc())
        except Exception as callback_error:
            logger.error(f"Error in _live_loop_done_callback exception handling: {callback_error}")
            logger.error(traceback.format_exc())
        
        try:
            logger.info("=== RESETTING WEBSOCKET SERVER STATE ===")
            # Reset state if not already done
            if self.is_running:
                logger.info("Setting is_running to False")
                self.is_running = False
                # Use create_task to run the coroutine
                try:
                    logger.info("Creating task to update status to idle")
                    asyncio.create_task(self.update_status("idle"))
                    logger.info("Status update task created")
                except Exception as status_error:
                    logger.error(f"Failed to create status update task: {status_error}")
                    logger.error(traceback.format_exc())
            else:
                logger.info("is_running was already False")
            
            # Clear references
            logger.info("Clearing LiveLoop references")
            self.live_loop = None
            self.live_loop_task = None
            logger.info("LiveLoop references cleared")
            
        except Exception as cleanup_error:
            logger.error(f"Error in _live_loop_done_callback cleanup: {cleanup_error}")
            logger.error(traceback.format_exc())
        
        logger.info("=== LIVE_LOOP_DONE_CALLBACK COMPLETED ===")

    async def handle_stop_command(self):
        """Handle stop command from client"""
        logger.info("=== HANDLE_STOP_COMMAND STARTED ===")
        try:
            if not self.is_running:
                logger.info("Voice agent is not running - sending error response")
                await self.send_to_all({
                    "type": "error",
                    "error": "Voice agent is not running",
                    "timestamp": self._get_timestamp()
                })
                return
                
            logger.info("Stopping voice agent...")
            await self.update_status("stopping")
            
            # Set running to false first to prevent other operations
            logger.info("Setting is_running to False")
            self.is_running = False
            
            # Use the callback if available for any special handling
            try:
                if self.on_stop_callback:
                    logger.info("Calling stop callback")
                    await self.on_stop_callback()
                    logger.info("Stop callback completed")
                else:
                    logger.info("No stop callback defined")
            except Exception as e:
                logger.error(f"Error in stop callback: {e}")
                logger.error(traceback.format_exc())
                # Don't let callback errors stop the stop process
            
            # Let the LiveLoop handle its own cleanup
            try:
                if self.live_loop:
                    logger.info("Stopping LiveLoop...")
                    await self.live_loop.stop()
                    logger.info("LiveLoop stop() completed")
                else:
                    logger.info("No LiveLoop to stop")
            except Exception as e:
                logger.error(f"Error stopping LiveLoop: {e}")
                logger.error(traceback.format_exc())
                # Continue with cleanup even if LiveLoop stop fails
            
            # Clear references
            try:
                logger.info("Clearing LiveLoop references")
                self.live_loop = None
                if self.live_loop_task and not self.live_loop_task.done():
                    logger.info("Cancelling LiveLoop task")
                    self.live_loop_task.cancel()
                    try:
                        await asyncio.wait_for(self.live_loop_task, timeout=2.0)
                        logger.info("LiveLoop task cancelled successfully")
                    except (asyncio.CancelledError, asyncio.TimeoutError):
                        logger.warning("LiveLoop task cancellation timed out")
                    except Exception as cancel_error:
                        logger.error(f"Error cancelling LiveLoop task: {cancel_error}")
                        logger.error(traceback.format_exc())
                self.live_loop_task = None
                logger.info("LiveLoop references cleared")
            except Exception as cleanup_error:
                logger.error(f"Error clearing LiveLoop references: {cleanup_error}")
                logger.error(traceback.format_exc())
            
            logger.info("Voice agent stopped successfully")
            try:
                await self.update_status("idle")
                logger.info("Status updated to idle")
            except Exception as status_error:
                logger.error(f"Error updating status to idle: {status_error}")
                logger.error(traceback.format_exc())
        
        except Exception as e:
            logger.error(f"Error in handle_stop_command: {e}")
            logger.error(traceback.format_exc())
            
            # Always reset state even if there was an error
            try:
                logger.info("Resetting state due to error in stop command")
                self.is_running = False
                self.live_loop = None
                self.live_loop_task = None
                logger.info("State reset completed")
            except Exception as reset_error:
                logger.error(f"Error resetting state: {reset_error}")
                logger.error(traceback.format_exc())
            
            # Send error to clients but don't let it crash the connection
            try:
                await self.send_error(f"Error stopping voice agent: {str(e)}", traceback.format_exc())
                logger.info("Error message sent to clients")
            except Exception as send_error:
                logger.error(f"Failed to send error message: {send_error}")
                logger.error(traceback.format_exc())
            
            # Still try to update status
            try:
                await self.update_status("idle")
                logger.info("Status updated to idle after error")
            except Exception as status_error:
                logger.error(f"Failed to update status after error: {status_error}")
                logger.error(traceback.format_exc())
        
        logger.info("=== HANDLE_STOP_COMMAND COMPLETED ===")
        logger.info("WebSocket server should remain running and ready for new connections")

    async def handle_get_resources(self, websocket: websockets.WebSocketServerProtocol):
        """Handle request for available resources"""
        try:
            logger.info("Processing get_resources request")
            
            # Get all available resources with individual error handling
            try:
                system_prompts = list_system_messages()
                logger.debug(f"System prompts loaded: {len(system_prompts)} categories")
            except Exception as e:
                logger.error(f"Error loading system prompts: {e}")
                system_prompts = {}
            
            try:
                # Convert dictionaries to lists for frontend consumption
                # Frontend will display these names and send them back in start commands
                languages_list = list(LANGUAGES.keys())  # Display names like "English (US)"
                voices_list = list(VOICES.keys())  # Display names like "Leda (Female)"
                models_list = list(GEMINI_LIVE_MODELS.keys())  # Display names like "Gemini 2.0 Flash Live"
                logger.debug(f"Languages: {len(languages_list)}, Voices: {len(voices_list)}, Models: {len(models_list)}")
            except Exception as e:
                logger.error(f"Error loading languages/voices/models: {e}")
                languages_list = ["English (US)"]
                voices_list = ["Leda (Female)"]
                models_list = ["Gemini 2.0 Flash Live"]
            
            # Create the response with explicit type field
            resources = {
                "type": "resources",  # Ensure this is set to "resources"
                "resources": {
                    "systemPrompts": system_prompts,
                    "languages": languages_list,  # Now a list of display names
                    "voices": voices_list,  # Now a list of display names
                    "audioSources": AUDIO_SOURCES,
                    "videoModes": VIDEO_MODES,
                    "responseModalities": MODALITIES,
                    "models": models_list,  # Now a list of display names
                    "availableChannels": self.available_channels  # dynamic channels
                },
                "timestamp": self._get_timestamp()
            }
            
            logger.info(f"Sending resources with {len(resources['resources'])} categories")
            logger.debug(f"Resource structure: {list(resources['resources'].keys())}")
            
            # Convert to JSON string and send
            try:
                resources_json = json.dumps(resources)
                logger.debug(f"Resources JSON: {resources_json[:200]}...")  # Log first 200 chars
                await websocket.send(resources_json)
                logger.info("Resources sent successfully")
                
                # Wait a moment and verify connection is still open
                await asyncio.sleep(0.1)  # Small delay to let any immediate close events happen
                
                try:
                    # Check if connection is still open (websockets library version compatibility)
                    if hasattr(websocket, 'closed'):
                        is_closed = websocket.closed
                    elif hasattr(websocket, 'open'):
                        is_closed = not websocket.open
                    else:
                        # Can't determine state, assume it's open
                        is_closed = False
                        
                    if is_closed:
                        logger.warning("WebSocket was closed after sending resources")
                    else:
                        logger.debug("WebSocket connection still open after sending resources")
                        
                        # Try to ping the connection to ensure it's truly alive
                        try:
                            await websocket.ping()
                            logger.debug("WebSocket ping successful")
                        except Exception as ping_error:
                            logger.warning(f"WebSocket ping failed: {ping_error}")
                            
                except Exception as check_error:
                    logger.debug(f"Could not check WebSocket state: {check_error}")
                    
            except Exception as send_error:
                logger.error(f"Error sending resources: {send_error}")
                logger.error(f"Send error type: {type(send_error).__name__}")
                logger.error(traceback.format_exc())
                raise
            
        except Exception as e:
            logger.error(f"Error processing get_resources request: {e}")
            logger.error(traceback.format_exc())
            error_response = {
                "type": "error",
                "error": f"Failed to get resources: {str(e)}",
                "timestamp": self._get_timestamp()
            }
            await websocket.send(json.dumps(error_response))

    async def handler(self, websocket: websockets.WebSocketServerProtocol, path: str = None):
        """WebSocket connection handler"""
        logger.info(f"New WebSocket connection from {websocket.remote_address}")
        await self.register(websocket)
        try:
            await self.handle_message(websocket)
        except websockets.exceptions.ConnectionClosed as e:
            logger.info(f"WebSocket connection closed normally: {e}")
        except Exception as e:
            logger.error(f"Error in handler: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(traceback.format_exc())
            
            # Send error to client if connection is still open
            try:
                if websocket.open:
                    await self.send_error(f"Server error: {str(e)}", traceback.format_exc())
            except Exception as send_error:
                logger.error(f"Failed to send error to client: {send_error}")
        finally:
            await self.unregister(websocket)

    async def start_server(self):
        """Start the WebSocket server"""
        try:
            # Modern websockets library API (version 10+)
            self.server = await websockets.serve(
                self.handler,
                self.host,
                self.port
            )
            logger.info(f"WebSocket server started at ws://{self.host}:{self.port}")
            return self.server
        except TypeError as e:
            # For older websockets versions that might require different parameters
            logger.error(f"Error starting WebSocket server with modern API: {e}")
            logger.info("Trying legacy websockets API...")
            
            # Legacy websockets API
            self.server = await websockets.server.serve(
                self.handler,
                self.host, 
                self.port
            )
            logger.info(f"WebSocket server started at ws://{self.host}:{self.port}")
            return self.server

    def set_callbacks(self, on_start=None, on_stop=None):
        """Set callbacks for start and stop commands"""
        self.on_start_callback = on_start
        self.on_stop_callback = on_stop

    async def stop_server(self):
        """Stop the WebSocket server"""
        # Make sure to stop any running LiveLoop first
        if self.is_running and self.live_loop:
            await self.handle_stop_command()
            
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("WebSocket server stopped")

# Add main function to run the server directly
if __name__ == "__main__":
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Aya WebSocket Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind the server to")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind the server to")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()
    
    # Create server instance
    server = AyaWebSocketServer(host=args.host, port=args.port, debug=args.debug)
    
    # Setup callbacks
    async def on_start(config):
        logger.info(f"Starting LiveLoop with config: {config}")
        if server.live_loop:
            server.live_loop_task = asyncio.create_task(server.live_loop.run())
            server.live_loop_task.add_done_callback(server._live_loop_done_callback)
    
    async def on_stop():
        logger.info("Stopping LiveLoop")
        if server.live_loop:
            await server.live_loop.stop()
            if server.live_loop_task and not server.live_loop_task.done():
                server.live_loop_task.cancel()
            server.live_loop = None
            server.live_loop_task = None
    
    server.set_callbacks(on_start=on_start, on_stop=on_stop)
    
    # Run server
    async def main():
        await server.start_server()
        # Keep the server running until interrupted
        try:
            while True:
                await asyncio.sleep(3600)  # Sleep for an hour
        except asyncio.CancelledError:
            logger.info(f"Server cancelled: {asyncio.get_event_loop()._exception()}")
        finally:
            logger.info("Stopping server")
            await server.stop_server()
    
    # Start the server
    asyncio.run(main())