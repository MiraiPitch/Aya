#!/usr/bin/env python
"""
Tauri Bridge for Aya AI Assistant
This module serves as the entry point for the Tauri desktop application.
It starts the WebSocket server that provides the interface between the Tauri frontend and Python backend.
"""

import asyncio
import logging
import signal
import sys
from aya.websocket_server import AyaWebSocketServer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Global server instance
server = None

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info(f"Received signal {signum}, shutting down...")
    if server:
        # Create a new event loop if we're not in one
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Stop the server
        loop.run_until_complete(server.stop_server())
    
    sys.exit(0)

async def main():
    """Main function to start the Tauri bridge"""
    global server
    
    print("=== TAURI BRIDGE STARTING ===")
    logger.info("Starting Aya Tauri Bridge...")
    
    # Check if port is already in use
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 8765))
        sock.close()
        print("=== PORT 8765 IS AVAILABLE ===")
    except OSError as e:
        print(f"=== PORT 8765 IS IN USE: {e} ===")
        logger.error(f"Port 8765 is already in use: {e}")
        # Try to continue anyway, might be from a previous run
    
    # Create WebSocket server instance with debug enabled
    server = AyaWebSocketServer(
        host="127.0.0.1",
        port=8765,
        debug=True  # Enable debug logging
    )
    print(f"=== WebSocket server instance created at 127.0.0.1:8765 ===")
    
    # Set up custom callbacks for start/stop commands
    async def on_start(config):
        """Callback when start command is received"""
        logger.info(f"Starting LiveLoop with config: {config}")
        if server.live_loop:
            server.live_loop_task = asyncio.create_task(server.live_loop.run())
            server.live_loop_task.add_done_callback(server._live_loop_done_callback)
    
    async def on_stop():
        """Callback when stop command is received"""
        logger.info("Stopping LiveLoop")
        if server.live_loop:
            try:
                if hasattr(server.live_loop, 'stop') and callable(server.live_loop.stop):
                    await server.live_loop.stop()
                
                if server.live_loop_task and not server.live_loop_task.done():
                    server.live_loop_task.cancel()
                    try:
                        await asyncio.wait_for(server.live_loop_task, timeout=5.0)
                    except (asyncio.CancelledError, asyncio.TimeoutError):
                        logger.warning("LiveLoop task cancellation timed out")
            except Exception as e:
                logger.error(f"Error stopping LiveLoop: {e}")
            finally:
                server.live_loop = None
                server.live_loop_task = None
    
    # Set callbacks
    server.set_callbacks(on_start=on_start, on_stop=on_stop)
    
    try:
        # Start the WebSocket server
        print("=== ATTEMPTING TO START WEBSOCKET SERVER ===")
        await server.start_server()
        print("=== WEBSOCKET SERVER STARTED SUCCESSFULLY ===")
        logger.info("Tauri Bridge started successfully - WebSocket server listening on ws://127.0.0.1:8765")
        
        # Keep the server running
        while True:
            await asyncio.sleep(1)
            
    except asyncio.CancelledError:
        logger.info("Bridge cancelled")
    except Exception as e:
        logger.error(f"Error in Tauri Bridge: {e}")
        raise
    finally:
        logger.info("Stopping Tauri Bridge...")
        if server:
            await server.stop_server()

if __name__ == "__main__":
    print("=== TAURI BRIDGE ENTRY POINT ===")
    print(f"Python version: {sys.version}")
    print(f"Command line args: {sys.argv}")
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Run the bridge
        print("=== STARTING ASYNCIO EVENT LOOP ===")
        asyncio.run(main())
    except KeyboardInterrupt:
        print("=== BRIDGE STOPPED BY USER ===")
        logger.info("Bridge stopped by user")
    except Exception as e:
        print(f"=== UNHANDLED ERROR: {e} ===")
        logger.error(f"Unhandled error in Tauri Bridge: {e}")
        sys.exit(1) 