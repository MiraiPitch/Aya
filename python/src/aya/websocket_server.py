"""
WebSocket server for Aya AI Assistant
Provides real-time status updates and control interface for Tauri frontend
"""

import asyncio
import json
import logging
import websockets
from typing import Dict, Any, Set, Optional, Callable
from aya.utils import list_system_messages, LANGUAGES, VOICES, AUDIO_SOURCES, VIDEO_MODES, MODALITIES

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

class AyaWebSocketServer:
    """WebSocket server for Aya AI Assistant"""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        """Initialize the WebSocket server"""
        self.host = host
        self.port = port
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.status = "idle"
        self.is_running = False
        self.server = None
        self.on_start_callback: Optional[Callable] = None
        self.on_stop_callback: Optional[Callable] = None

    async def register(self, websocket: websockets.WebSocketServerProtocol):
        """Register a new client"""
        self.clients.add(websocket)
        logger.info(f"Client connected. Total clients: {len(self.clients)}")
        
        # Send initial status
        await self.send_status_to_client(websocket)

    async def unregister(self, websocket: websockets.WebSocketServerProtocol):
        """Unregister a client"""
        self.clients.remove(websocket)
        logger.info(f"Client disconnected. Total clients: {len(self.clients)}")

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
                    
                    if command == "start":
                        if self.on_start_callback:
                            config = message.get("config", {})
                            await self.handle_start_command(config)
                    
                    elif command == "stop":
                        if self.on_stop_callback:
                            await self.handle_stop_command()
                    
                    elif command == "get_resources":
                        await self.handle_get_resources(websocket)
                    
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON received: {message_str}")
                    await websocket.send(json.dumps({
                        "type": "error",
                        "error": "Invalid JSON format",
                        "timestamp": asyncio.get_event_loop().time()
                    }))
        
        except websockets.exceptions.ConnectionClosed:
            pass
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
            
            if self.on_start_callback:
                # Call the start callback with the provided configuration
                await self.on_start_callback(config)
        
        except Exception as e:
            logger.exception("Error starting voice agent")
            self.is_running = False
            await self.send_error(str(e))
            await self.update_status("error")

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
                
            if self.on_stop_callback:
                await self.on_stop_callback()
                
            self.is_running = False
            await self.update_status("idle")
        
        except Exception as e:
            logger.exception("Error stopping voice agent")
            await self.send_error(str(e))

    async def handle_get_resources(self, websocket: websockets.WebSocketServerProtocol):
        """Handle request for available resources"""
        resources = {
            "type": "resources",
            "resources": {
                "systemPrompts": list_system_messages(),
                "languages": LANGUAGES,
                "voices": VOICES,
                "audioSources": AUDIO_SOURCES,
                "videoModes": VIDEO_MODES,
                "responseModalities": MODALITIES
            },
            "timestamp": asyncio.get_event_loop().time()
        }
        await websocket.send(json.dumps(resources))

    async def handler(self, websocket: websockets.WebSocketServerProtocol, path: str):
        """WebSocket connection handler"""
        await self.register(websocket)
        try:
            await self.handle_message(websocket)
        finally:
            await self.unregister(websocket)

    async def start_server(self):
        """Start the WebSocket server"""
        self.server = await websockets.serve(self.handler, self.host, self.port)
        logger.info(f"WebSocket server started at ws://{self.host}:{self.port}")
        return self.server

    def set_callbacks(self, on_start=None, on_stop=None):
        """Set callbacks for start and stop commands"""
        self.on_start_callback = on_start
        self.on_stop_callback = on_stop

    async def stop_server(self):
        """Stop the WebSocket server"""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("WebSocket server stopped") 