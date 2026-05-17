#!/usr/bin/env bash
# IndieGala Auto-Spin Bot Runner (Linux + Windows/Git Bash)
set -e
export PYTHONUTF8=1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Auto-bootstrap venv if it doesn't exist
if [ ! -f "$SCRIPT_DIR/venv/Scripts/activate" ] && [ ! -f "$SCRIPT_DIR/venv/bin/activate" ]; then
    echo "Setting up virtual environment..."
    python3 -m venv "$SCRIPT_DIR/venv" 2>/dev/null || python -m venv "$SCRIPT_DIR/venv"
fi

# Activate venv — path differs between Linux and Windows/Git Bash
if [ -f "$SCRIPT_DIR/venv/Scripts/activate" ]; then
    source "$SCRIPT_DIR/venv/Scripts/activate"   # Windows Git Bash
elif [ -f "$SCRIPT_DIR/venv/bin/activate" ]; then
    source "$SCRIPT_DIR/venv/bin/activate"        # Linux/macOS
fi

# Install dependencies if any are missing
if ! python -c "import undetected_chromedriver" 2>/dev/null; then
    echo "Installing dependencies..."
    pip install -r "$SCRIPT_DIR/requirements.txt" -q
fi

python spin_wheel.py "$@"
