"""
Tauri Bridge for Aya AI Assistant
Connects the Tauri frontend with the Aya AI Assistant through WebSocket
"""

import asyncio
import logging
import argparse
import signal
import sys
from typing import Dict, Any, Optional

from aya.live_loop import LiveLoop
from aya.websocket_server import AyaWebSocketServer
from aya.function_registry import get_declarations_for_functions
from aya.utils import create_gemini_config
from aya.gemini_tools import print_to_console, get_current_date_and_time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

class AyaTauriBridge:
    """Bridge between Tauri frontend and Aya AI Assistant"""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        """Initialize the bridge"""
        self.host = host
        self.port = port
        self.websocket_server = AyaWebSocketServer(host, port)
        self.live_loop: Optional[LiveLoop] = None
        
        # Set up callbacks
        self.websocket_server.set_callbacks(
            on_start=self.handle_start,
            on_stop=self.handle_stop
        )
        
        # Handle signals for graceful shutdown
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, self.handle_signal)

    def handle_signal(self, sig, frame):
        """Handle termination signals"""
        logger.info(f"Received signal {sig}, shutting down...")
        asyncio.create_task(self.shutdown())

    async def handle_start(self, config: Dict[str, Any]):
        """Handle start command from WebSocket client"""
        logger.info(f"Starting voice agent with config: {config}")
        
        # Configure tools
        search_tool = {'google_search': {}}
        code_execution_tool = {'code_execution': {}}
        function_tools = {
            'function_declarations': get_declarations_for_functions([
                print_to_console,
                get_current_date_and_time
                # Add other functions here as needed
            ])
        }
        tools = [search_tool, code_execution_tool, function_tools]
        
        # Extract configuration from request
        video_mode = config.get("videoMode", "none")
        audio_source = config.get("audioSource", "microphone")
        system_prompt = config.get("systemPrompt", "system_prompts/default/aya_default_tools.txt")
        language = config.get("language", "en-US")
        voice = config.get("voice", "Leda")
        response_modality = config.get("responseModality", "AUDIO")
        initial_message = config.get("initialMessage", "[CALL_START]")
        model = config.get("model", "models/gemini-2.0-flash-live-001")
        
        # Create Gemini configuration
        gemini_config = create_gemini_config(
            system_message_path=system_prompt,
            language_code=language,
            voice_name=voice,
            response_modality=response_modality,
            tools=tools,
            temperature=0.05
        )
        
        # Create and start LiveLoop
        self.live_loop = LiveLoop(
            video_mode=video_mode,
            model=model,
            config=gemini_config,
            initial_message=initial_message,
            audio_source=audio_source,
            record_conversation=False
        )
        
        # Connect LiveLoop status updates to WebSocket
        self.live_loop.on_status_change = self.handle_status_change
        
        # Start LiveLoop
        asyncio.create_task(self.live_loop.run())
        
        await self.websocket_server.update_status("listening")
        return True

    async def handle_stop(self):
        """Handle stop command from WebSocket client"""
        logger.info("Stopping voice agent")
        
        if self.live_loop:
            await self.live_loop.stop()
            self.live_loop = None
            
        await self.websocket_server.update_status("idle")
        return True

    async def handle_status_change(self, status: str, data: Dict[str, Any] = None):
        """Handle status change from LiveLoop"""
        await self.websocket_server.update_status(status, data)

    async def run(self):
        """Run the bridge"""
        await self.websocket_server.start_server()
        
        # Keep the server running
        while True:
            await asyncio.sleep(1)

    async def shutdown(self):
        """Shutdown the bridge"""
        if self.live_loop:
            await self.live_loop.stop()
            
        await self.websocket_server.stop_server()
        asyncio.get_event_loop().stop()

def main():
    """Main entry point for the Tauri bridge"""
    parser = argparse.ArgumentParser(description="Aya AI Assistant Tauri Bridge")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="WebSocket server host")
    parser.add_argument("--port", type=int, default=8765, help="WebSocket server port")
    args = parser.parse_args()
    
    bridge = AyaTauriBridge(args.host, args.port)
    
    try:
        asyncio.run(bridge.run())
    except KeyboardInterrupt:
        logger.info("Interrupted by user, shutting down...")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Error in bridge: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 