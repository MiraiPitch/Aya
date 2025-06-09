"""
WebSocket server for Aya AI Assistant
Provides real-time status updates and control interface for Tauri frontend
"""

import asyncio
import json
import logging
import websockets
import traceback
from typing import Dict, Any, Set, Optional, Callable
from aya.utils import list_system_messages, LANGUAGES, VOICES, AUDIO_SOURCES, VIDEO_MODES, MODALITIES, create_gemini_config
from aya.live_loop import LiveLoop
from aya.function_registry import get_declarations_for_functions
from aya.gemini_tools import print_to_console, get_current_date_and_time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Default model for Gemini Live API
DEFAULT_MODEL = "models/gemini-2.0-flash-live-001"

# Configure tools
search_tool = {'google_search': {}}
code_execution_tool = {'code_execution': {}}
function_tools = {
    'function_declarations': get_declarations_for_functions([
        print_to_console,
        get_current_date_and_time
    ])
}
tools = [search_tool, code_execution_tool, function_tools]

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
        
        # Enable debug logging if requested
        if debug:
            logger.setLevel(logging.DEBUG)
            logger.info("Debug logging enabled")
        else:
            logger.setLevel(logging.INFO)

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
            logger.info(f"Client disconnected. Total clients: {len(self.clients)}")
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
            "timestamp": asyncio.get_event_loop().time()
        }
        await websocket.send(json.dumps(status_message))

    async def send_error(self, error: str, stack_trace: str = None):
        """Send error message to all clients"""
        error_message = {
            "type": "error",
            "error": error,
            "stackTrace": stack_trace,
            "timestamp": asyncio.get_event_loop().time()
        }
        await self.send_to_all(error_message)

    async def update_status(self, status: str, data: Dict[str, Any] = None):
        """Update and broadcast status to all clients"""
        self.status = status
        status_message = {
            "type": "status",
            "status": status,
            "timestamp": asyncio.get_event_loop().time()
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
                        await self.handle_stop_command()
                    
                    elif command == "get_resources":
                        # Ensure this command is handled immediately
                        await self.handle_get_resources(websocket)
                        continue  # Skip sending status update
                    
                    else:
                        logger.warning(f"Unknown command received: {command}")
                        await websocket.send(json.dumps({
                            "type": "error",
                            "error": f"Unknown command: {command}",
                            "timestamp": asyncio.get_event_loop().time()
                        }))
                        continue  # Skip sending status update
                    
                    # Send status update after handling other commands
                    await self.send_status_to_client(websocket)
                    
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON received: {message_str}")
                    await websocket.send(json.dumps({
                        "type": "error",
                        "error": "Invalid JSON format",
                        "timestamp": asyncio.get_event_loop().time()
                    }))
        
        except websockets.exceptions.ConnectionClosed:
            logger.info("Connection closed")
        except Exception as e:
            logger.error(f"Error in handle_message: {e}")
            logger.error(traceback.format_exc())
        finally:
            await self.unregister(websocket)

    async def handle_start_command(self, config: Dict[str, Any]):
        """Handle start command from client"""
        try:
            if self.is_running:
                await self.send_to_all({
                    "type": "error",
                    "error": "Voice agent is already running",
                    "timestamp": asyncio.get_event_loop().time()
                })
                return
                
            self.is_running = True
            await self.update_status("starting")
            
            # Extract configuration parameters from the client's config
            video_mode = config.get("videoMode", "none")
            language_display = config.get("language", "English (US)")  # Display name from frontend
            voice_display = config.get("voice", "Leda (Female)")  # Display name from frontend
            response_modality = config.get("responseModality", "AUDIO")
            audio_source = config.get("audioSource", "microphone")
            system_prompt_path = config.get("systemPrompt", "system_prompts/default/aya_default_tools_cli.txt")
            initial_message = config.get("initialMessage", "[CALL_START]")
            
            # Convert display names to actual values
            language_code = LANGUAGES.get(language_display, "en-US")  # Convert display name to language code
            voice_name = VOICES.get(voice_display, "Leda")  # Convert display name to voice name
            
            logger.info(f"Language: {language_display} -> {language_code}")
            logger.info(f"Voice: {voice_display} -> {voice_name}")
            
            # Create Gemini configuration
            gemini_config = create_gemini_config(
                system_message_path=system_prompt_path,
                language_code=language_code,
                voice_name=voice_name,
                response_modality=response_modality,
                tools=tools,
                temperature=0.05
            )
            
            # Create LiveLoop instance
            self.live_loop = LiveLoop(
                video_mode=video_mode,
                model=DEFAULT_MODEL,
                config=gemini_config,
                initial_message=initial_message,
                audio_source=audio_source,
                record_conversation=False
            )
            
            # Set status change callback
            self.live_loop.on_status_change = self.update_status
            
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
        try:
            # Check for exceptions
            future.result()
        except asyncio.CancelledError:
            logger.info("LiveLoop task was cancelled")
        except Exception as e:
            logger.error(f"LiveLoop task failed with error: {e}")
            logger.error(traceback.format_exc())
        finally:
            # Reset state if not already done
            if self.is_running:
                self.is_running = False
                # Use create_task to run the coroutine
                asyncio.create_task(self.update_status("idle"))

    async def handle_stop_command(self):
        """Handle stop command from client"""
        try:
            if not self.is_running:
                await self.send_to_all({
                    "type": "error",
                    "error": "Voice agent is not running",
                    "timestamp": asyncio.get_event_loop().time()
                })
                return
                
            await self.update_status("stopping")
            
            if self.on_stop_callback:
                await self.on_stop_callback()
            elif self.live_loop:
                # Properly clean up the LiveLoop
                try:
                    # First stop the LiveLoop
                    if hasattr(self.live_loop, 'stop') and callable(self.live_loop.stop):
                        await self.live_loop.stop()
                    
                    # Then cancel the task if it exists and is still running
                    if self.live_loop_task and not self.live_loop_task.done():
                        self.live_loop_task.cancel()
                        try:
                            await asyncio.wait_for(self.live_loop_task, timeout=5.0)
                        except (asyncio.CancelledError, asyncio.TimeoutError):
                            logger.warning("LiveLoop task cancellation timed out or was cancelled")
                except Exception as e:
                    logger.error(f"Error stopping LiveLoop: {e}")
                    logger.error(traceback.format_exc())
                
                # Clear the references
                self.live_loop = None
                self.live_loop_task = None
                
            self.is_running = False
            await self.update_status("idle")
        
        except Exception as e:
            logger.exception("Error stopping voice agent")
            await self.send_error(str(e), traceback.format_exc())
            # Try to clean up anyway
            self.live_loop = None
            self.live_loop_task = None
            self.is_running = False
            await self.update_status("idle")

    async def handle_get_resources(self, websocket: websockets.WebSocketServerProtocol):
        """Handle request for available resources"""
        try:
            logger.info("Processing get_resources request")
            
            # Get all available resources
            system_prompts = list_system_messages()
            
            # Convert dictionaries to lists for frontend consumption
            # Frontend will display these names and send them back in start commands
            languages_list = list(LANGUAGES.keys())  # Display names like "English (US)"
            voices_list = list(VOICES.keys())  # Display names like "Leda (Female)"
            
            # Create the response with explicit type field
            resources = {
                "type": "resources",  # Ensure this is set to "resources"
                "resources": {
                    "systemPrompts": system_prompts,
                    "languages": languages_list,  # Now a list of display names
                    "voices": voices_list,  # Now a list of display names
                    "audioSources": AUDIO_SOURCES,
                    "videoModes": VIDEO_MODES,
                    "responseModalities": MODALITIES
                },
                "timestamp": asyncio.get_event_loop().time()
            }
            
            logger.info(f"Sending resources with {len(resources['resources'])} categories")
            # Convert to JSON string and send
            resources_json = json.dumps(resources)
            logger.debug(f"Resources JSON: {resources_json[:100]}...")  # Log first 100 chars
            await websocket.send(resources_json)
            logger.info("Resources sent successfully")
            
        except Exception as e:
            logger.error(f"Error processing get_resources request: {e}")
            logger.error(traceback.format_exc())
            error_response = {
                "type": "error",
                "error": f"Failed to get resources: {str(e)}",
                "timestamp": asyncio.get_event_loop().time()
            }
            await websocket.send(json.dumps(error_response))

    async def handler(self, websocket: websockets.WebSocketServerProtocol, path: str = None):
        """WebSocket connection handler"""
        await self.register(websocket)
        try:
            await self.handle_message(websocket)
        except Exception as e:
            logger.error(f"Error in handler: {e}")
            logger.error(traceback.format_exc())
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