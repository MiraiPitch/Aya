#!/bin/bash
# Shell script to package the Aya Voice Assistant Tauri app with Python

# Set colors for output
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Create a virtual environment for the Python package
echo -e "${GREEN}Creating Python virtual environment...${NC}"
python3 -m venv .venv

# Activate the virtual environment
echo -e "${GREEN}Activating virtual environment...${NC}"
source .venv/bin/activate

# Install the Aya package and its dependencies
echo -e "${GREEN}Installing Aya package and dependencies...${NC}"
pip install -e ../python
pip install pyinstaller websockets

# Create a standalone Python executable
echo -e "${GREEN}Creating standalone Python executable...${NC}"
pyinstaller --onefile ../python/src/aya/tauri_bridge.py --name aya_bridge --hidden-import=websockets

# Copy the executable to the Tauri resources directory
echo -e "${GREEN}Copying executable to Tauri resources...${NC}"
mkdir -p ./src-tauri/resources
cp ./dist/aya_bridge ./src-tauri/resources/

# Update Tauri config to use the bundled executable
echo -e "${GREEN}Updating Tauri configuration...${NC}"
# Using node to modify JSON since it's easier than with bash
node -e "
const fs = require('fs');
const config = JSON.parse(fs.readFileSync('./src-tauri/tauri.conf.json', 'utf8'));
config.tauri.bundle.externalBin = ['resources/aya_bridge'];
fs.writeFileSync('./src-tauri/tauri.conf.json', JSON.stringify(config, null, 2));
"

# Build the Tauri application
echo -e "${GREEN}Building Tauri application...${NC}"
npm run build
npm run tauri build

echo -e "${GREEN}Packaging complete!${NC}"
echo -e "${CYAN}The packaged application can be found in: ./src-tauri/target/release/bundle${NC}" 