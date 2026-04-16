#!/bin/bash

# Exit on any failure
set -e

echo "========================================"
echo " Starting Nagman Calibration Project    "
echo "========================================"
echo ""

# STEP 1: Check Python Installation
echo ">>> [1/4] Checking Python 3 installation..."
if command -v python3 >/dev/null 2>&1; then
    echo "✅ Python 3 is installed: $(python3 --version)"
else
    echo "❌ Python 3 was not found."
    echo "Please install Python 3. For example, on Ubuntu/Debian run: sudo apt-get update && sudo apt-get install python3"
    exit 1
fi

# STEP 2: Check PIP installation
echo ""
echo ">>> [2/4] Checking pip installation..."
if command -v pip3 >/dev/null 2>&1 || command -v pip >/dev/null 2>&1; then
    echo "✅ pip package manager is installed."
else
    echo "❌ pip was not found."
    echo "Please install pip. For example, on Ubuntu/Debian run: sudo apt-get install python3-pip"
    exit 1
fi

# STEP 3: Install Required Packages
echo ""
echo ">>> [3/4] Installing required packages from requirements.txt..."
echo "This might take a few moments depending on your internet connection..."
python3 -m pip install -r requirements.txt
echo "✅ All required packages are correctly installed."

# STEP 4: Run the Flask website
echo ""
echo ">>> [4/4] Starting the web application..."
echo "The website is being hosted locally at: http://127.0.0.1:5000"
echo "Press Ctrl+C to shut down the server when you are done."
echo "========================================"
echo ""

# Launch the app
python3 app.py
