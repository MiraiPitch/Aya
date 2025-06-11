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
import traceback

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
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    if server:
        # Create a new event loop if we're not in one
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError("Event loop is closed")
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Stop the server gracefully
        try:
            logger.info("Stopping WebSocket server...")
            loop.run_until_complete(server.stop_server())
            logger.info("WebSocket server stopped")
        except Exception as e:
            logger.error(f"Error stopping server: {e}")
    
    logger.info("Graceful shutdown completed")
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
        logger.info("Tauri bridge stop callback - performing any bridge-specific cleanup")
        # The WebSocket server will handle calling LiveLoop.stop() 
        # This callback is just for any bridge-specific operations
        # No LiveLoop cleanup needed here since LiveLoop handles its own cleanup
    
    # Set callbacks
    server.set_callbacks(on_start=on_start, on_stop=on_stop)
    
    try:
        # Start the WebSocket server
        print("=== ATTEMPTING TO START WEBSOCKET SERVER ===")
        await server.start_server()
        print("=== WEBSOCKET SERVER STARTED SUCCESSFULLY ===")
        logger.info("Tauri Bridge started successfully - WebSocket server listening on ws://127.0.0.1:8765")
        
        # Keep the server running with periodic status checks
        loop_count = 0
        while True:
            try:
                await asyncio.sleep(5)  # Check every 5 seconds
                loop_count += 1
                if loop_count % 12 == 0:  # Log every minute
                    print(f"=== BRIDGE ALIVE - Loop #{loop_count}, Clients: {len(server.clients) if server else 0} ===")
                    logger.info(f"Bridge status check - Loop #{loop_count}, Clients: {len(server.clients)}")
            except Exception as loop_error:
                logger.error(f"Error in bridge main loop: {loop_error}")
                logger.error(traceback.format_exc())
                # Don't exit on loop errors, just continue
                continue
            
    except asyncio.CancelledError:
        logger.info("Bridge cancelled")
    except Exception as e:
        logger.error(f"Error in Tauri Bridge: {e}")
        logger.error(traceback.format_exc())
        # Don't raise the exception - just log it and try to continue gracefully
        logger.info("Bridge encountered an error but will attempt graceful shutdown")
    finally:
        logger.info("Stopping Tauri Bridge...")
        if server:
            try:
                await server.stop_server()
                logger.info("WebSocket server stopped successfully")
            except Exception as stop_error:
                logger.error(f"Error stopping WebSocket server: {stop_error}")
                logger.error(traceback.format_exc())

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
        logger.error(traceback.format_exc())
        print("=== BRIDGE WILL EXIT DUE TO UNHANDLED ERROR ===")
        sys.exit(1) 