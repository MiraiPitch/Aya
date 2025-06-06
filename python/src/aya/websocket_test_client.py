#!/usr/bin/env python
"""
Simple WebSocket client test script for Aya AI Assistant.
This script connects to the WebSocket server, requests resources,
waits 5 seconds, then sends a start command.
"""

import asyncio
import json
import websockets
import time

# Server connection details
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8765
SERVER_URL = f"ws://{SERVER_HOST}:{SERVER_PORT}"

# Default configuration for the start command
DEFAULT_CONFIG = {
    "videoMode": "none",
    "language": "en-US",
    "voice": "Leda",
    "responseModality": "AUDIO",
    "audioSource": "microphone",
    "systemPrompt": "system_prompts/default/aya_default_tools_cli.txt",
    "initialMessage": "[CALL_START]"
}

async def test_client():
    """Main client function that connects to the server and sends test commands"""
    print(f"Connecting to WebSocket server at {SERVER_URL}...")
    
    async with websockets.connect(SERVER_URL) as websocket:
        print("Connected to server!")
        
        # Handle incoming messages in the background
        async def receive_messages():
            while True:
                try:
                    message = await websocket.recv()
                    message_json = json.loads(message)
                    message_type = message_json.get("type", "unknown")
                    
                    if message_type == "resources":
                        print("\nReceived resources:")
                        resources = message_json.get("resources", {})
                        for category, items in resources.items():
                            print(f"  {category}: {len(items) if isinstance(items, list) or isinstance(items, dict) else items}")
                    
                    elif message_type == "status":
                        status = message_json.get("status", "unknown")
                        print(f"\nStatus update: {status}")
                    
                    elif message_type == "error":
                        error = message_json.get("error", "Unknown error")
                        print(f"\nError: {error}")
                    
                    else:
                        print(f"\nReceived message: {message}")
                
                except websockets.exceptions.ConnectionClosed:
                    print("Connection closed")
                    break
                except Exception as e:
                    print(f"Error processing message: {e}")
        
        # Start the message receiver task
        receiver_task = asyncio.create_task(receive_messages())
        
        try:
            # Step 1: Request resources
            print("\nRequesting resources...")
            await websocket.send(json.dumps({
                "command": "get_resources"
            }))
            
            # Step 2: Wait 5 seconds
            print("\nWaiting 5 seconds before starting call...")
            await asyncio.sleep(5)
            
            # Step 3: Send start command with configuration
            print("\nSending start command...")
            await websocket.send(json.dumps({
                "command": "start",
                "config": DEFAULT_CONFIG
            }))
            
            # Keep the connection open to receive messages
            print("\nKeeping connection open for 10 seconds...")
            await asyncio.sleep(10)
            
            # Step 4: Send stop command
            print("\nSending stop command...")
            await websocket.send(json.dumps({
                "command": "stop"
            }))
            
            # Wait a bit more to see the results
            await asyncio.sleep(5)
            
        except Exception as e:
            print(f"Error during test: {e}")
        finally:
            # Cancel the receiver task
            receiver_task.cancel()
            try:
                await receiver_task
            except asyncio.CancelledError:
                pass

if __name__ == "__main__":
    # Run the test client
    asyncio.run(test_client()) 