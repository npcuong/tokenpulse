#!/usr/bin/env bash
# Register TokenPulse as a Login Item via launchd.
# Usage: bash scripts/autostart.sh

set -e

PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST_FILE="$PLIST_DIR/com.tokenpulse.app.plist"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Prefer venv binary
if [ -f "$SCRIPT_DIR/.venv/bin/tokenpulse" ]; then
    TP_BIN="$SCRIPT_DIR/.venv/bin/tokenpulse"
elif command -v tokenpulse &>/dev/null; then
    TP_BIN="$(command -v tokenpulse)"
else
    echo "❌ tokenpulse not found. Run setup.sh first."
    exit 1
fi

mkdir -p "$PLIST_DIR"

cat > "$PLIST_FILE" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.tokenpulse.app</string>
    <key>ProgramArguments</key>
    <array>
        <string>$TP_BIN</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>$HOME/.config/tokenpulse/tokenpulse.log</string>
    <key>StandardErrorPath</key>
    <string>$HOME/.config/tokenpulse/tokenpulse.log</string>
</dict>
</plist>
EOF

launchctl load "$PLIST_FILE"

echo "✅ TokenPulse will now start automatically on login."
echo "   Plist: $PLIST_FILE"
echo ""
echo "To disable auto-start:"
echo "  launchctl unload $PLIST_FILE"
