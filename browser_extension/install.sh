#!/bin/bash
# IdentityOS Live Browser Bridge - Installation Script

set -e

EXTENSION_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IDENTITYOS_ROOT="$(dirname "$EXTENSION_DIR")"

echo "Installing IdentityOS Live Browser Bridge..."

# Create native messaging manifest directory
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    MANIFEST_DIR="$HOME/.mozilla/native-messaging-hosts"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    MANIFEST_DIR="$HOME/Library/Application Support/Mozilla/NativeMessagingHosts"
elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    MANIFEST_DIR="$APPDATA/Mozilla/NativeMessagingHosts"
else
    echo "Unsupported OS: $OSTYPE"
    exit 1
fi

mkdir -p "$MANIFEST_DIR"

# Copy native host script
cp "$EXTENSION_DIR/native_host.py" "$MANIFEST_DIR/identityos_live_bridge.py"
chmod +x "$MANIFEST_DIR/identityos_live_bridge.py"

# Create native messaging manifest
MANIFEST_FILE="$MANIFEST_DIR/identityos_live_bridge.json"
cat > "$MANIFEST_FILE" << EOF
{
  "name": "identityos_live_bridge",
  "description": "IdentityOS Live Browser Bridge - Native Messaging Host",
  "path": "$MANIFEST_DIR/identityos_live_bridge.py",
  "type": "stdio",
  "allowed_extensions": ["live-browser-bridge@identityos"]
}
EOF

echo "Native messaging host installed to $MANIFEST_DIR"

# Build extension (zip for local loading)
cd "$EXTENSION_DIR"
ZIP_FILE="/tmp/identityos_live_bridge.zip"
rm -f "$ZIP_FILE"
zip -r "$ZIP_FILE" manifest.json background.js content.js popup.html popup.js

echo "Extension packaged at $ZIP_FILE"
echo ""
echo "To install in Firefox:"
echo "1. Open Firefox and go to about:debugging"
echo "2. Click 'This Firefox' -> 'Load Temporary Add-on...'"
echo "3. Select $ZIP_FILE"
echo ""
echo "Or install permanently from Firefox Add-ons once published."
echo ""
echo "After installation:"
echo "1. Click the IdentityOS extension icon in toolbar"
echo "2. Click 'Connect to IdentityOS'"
echo "3. The extension will connect to the native host"
echo ""
echo "To test live browser mode:"
echo "1. Open Firefox manually"
echo "2. Open several tabs"
echo "3. In IdentityOS chat: identity chat --id comet"
echo "4. Ask: 'what tabs do I have open right now?'"

echo ""
echo "Installation complete!"