#!/bin/bash
# Setup script for CommunicationMod integration (macOS + Linux)

BRIDGE_SCRIPT="$(cd "$(dirname "$0")" && pwd)/harness/communication_bridge.py"
STATE_DIR="/tmp/sts_bridge"

case "$(uname -s)" in
    Darwin)
        CONFIG_DIR="$HOME/Library/Preferences/ModTheSpire/CommunicationMod"
        ;;
    Linux)
        CONFIG_DIR="$HOME/.config/ModTheSpire/CommunicationMod"
        ;;
    *)
        echo "Unsupported OS: $(uname -s)"
        exit 1
        ;;
esac

CONFIG_FILE="$CONFIG_DIR/config.properties"

echo "=== CommunicationMod Setup for sts_lightspeed Testing ==="
echo "Detected OS: $(uname -s)"
echo "Config dir:  $CONFIG_DIR"
echo ""

# Create config dir if missing
mkdir -p "$CONFIG_DIR"

# If a previous config exists, back it up
if [ -f "$CONFIG_FILE" ]; then
    echo "Existing config:"
    cat "$CONFIG_FILE"
    echo ""
    cp "$CONFIG_FILE" "$CONFIG_FILE.backup"
    echo "Backup created at: $CONFIG_FILE.backup"
fi

# Find python in current $PATH; harness needs pyyaml installed there.
PYTHON_BIN="$(command -v python3 || command -v python)"
if [ -z "$PYTHON_BIN" ]; then
    echo "Error: no python on PATH; cannot write CommunicationMod command."
    exit 1
fi

# Write new config
{
    echo "command=$PYTHON_BIN $BRIDGE_SCRIPT --state-dir $STATE_DIR"
    echo "runAtGameStart=true"
} > "$CONFIG_FILE"

echo ""
echo "New config:"
cat "$CONFIG_FILE"
echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Launch Slay the Spire through ModTheSpire (see integration/STEAM_SETUP.md)"
echo "2. Enable CommunicationMod in the ModTheSpire UI"
echo "3. Click Play; the bridge will start automatically"
echo "4. In another terminal: python integration/run_tests.py --quick --seed 12345"
echo ""
echo "To restore original config: cp $CONFIG_FILE.backup $CONFIG_FILE"
