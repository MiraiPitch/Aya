# Aya Voice Assistant - Tauri Edition

A cross-platform desktop application for the Aya Voice Assistant, built with Tauri, React, and Python.

## Features

- 🤖 Desktop version of the Aya AI voice assistant
- 🗣️ Natural voice interaction
- 🚀 Low-latency processing of voice and video inputs
- 💻 System tray integration for background operation
- 🔧 Configurable settings for input/output modalities

## Input/Output Capabilities

- **Input:** Live webcam video, screen capture, microphone input, computer audio
- **Output:** Voice responses, text responses

## Development

### Prerequisites

- [Node.js](https://nodejs.org/) (v16+)
- [Rust](https://www.rust-lang.org/tools/install)
- [Python](https://www.python.org/downloads/) (v3.12+)
- [Tauri CLI](https://tauri.app/v1/guides/getting-started/prerequisites)

### Setup

1. Install dependencies:

```bash
# Install Node.js dependencies
npm install

# Install Python dependencies
pip install -e ../python
pip install websockets
```

2. Run in development mode:

```bash
npm run dev
```

### Building

To build a production version:

```bash
# Windows
.\scripts\package.ps1

# Linux/macOS
bash ./scripts/package.sh
```

The packaged application will be available in `src-tauri/target/release/bundle`.

## Configuration

The application uses a WebSocket connection to communicate with the Python backend. The default WebSocket server address is `ws://localhost:8765`.

## Architecture

### Frontend

- React.js for the user interface
- Tauri API for native system integration
- WebSocket for real-time communication with the Python backend

### Backend

- Python bridge using the Aya package
- WebSocket server for bidirectional communication
- Python packaged as a standalone executable for distribution

## Project Structure

```txt
tauri/
├── public/             # Static assets
│   └── index.html      # HTML entry point
├── scripts/            # Build scripts
│   ├── package.ps1     # Windows packaging script
│   └── package.sh      # Unix packaging script
├── src/                # React frontend
│   ├── components/     # UI components
│   │   ├── SettingsPanel.tsx   # Settings configuration UI
│   │   ├── StatusDisplay.tsx   # Voice agent status indicator
│   │   └── VoiceControls.tsx   # Start/stop controls
│   ├── hooks/          # React hooks
│   │   ├── useVoiceAgent.ts    # Voice agent control hook
│   │   └── useWebSocket.ts     # WebSocket communication hook
│   ├── styles/         # CSS styles
│   │   └── App.css             # Main application styles
│   ├── App.ts          # Application types and interfaces
│   ├── App.tsx         # Main React component
│   ├── index.tsx       # React entry point
│   └── types.ts        # TypeScript type definitions
├── src-tauri/          # Tauri backend
│   ├── icons/          # Application icons
│   │   ├── icon.ico    # Icon ICO
│   │   └── icon.png    # Icon PNG
│   ├── src/            # Rust code
│   │   └── main.rs     # Main application entry point
│   ├── build.rs        # Build script
│   ├── Cargo.toml      # Rust dependencies
│   ├── Cargo.lock      # Locked Rust dependencies
│   └── tauri.conf.json # Tauri configuration
├── package.json        # Node.js package configuration
├── README.md           # This documentation file
└── tsconfig.json       # TypeScript configuration
```

Python bridge code is in the `../python/src/aya/` directory.

```txt
../python/src/aya/       # Python bridge code
├── websocket_server.py  # WebSocket server implementation
└── tauri_bridge.py      # Bridge between Tauri and Python
```

## License

This project is licensed under the MIT License - see the LICENSE file for details. 
