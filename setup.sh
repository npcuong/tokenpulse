#!/usr/bin/env bash
# TokenPulse — Quick installer
# Usage: bash setup.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🔮 Installing TokenPulse..."

# ── 1. Check Python ──────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "❌ Python 3 not found. Install from https://python.org"
    exit 1
fi

PY_VERSION=$(python3 -c 'import sys; print(sys.version_info >= (3, 11))')
if [ "$PY_VERSION" != "True" ]; then
    echo "⚠️  Python 3.11+ recommended. Current: $(python3 --version)"
fi

# ── 2. Create virtualenv ─────────────────────────────────────────
if [ ! -d ".venv" ]; then
    echo "🐍 Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate

# ── 3. Install dependencies ─────────────────────────────────────
echo "📦 Installing dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install -e . -q

# ── 4. Create config ─────────────────────────────────────────────
CONFIG_DIR="$HOME/.config/tokenpulse"
mkdir -p "$CONFIG_DIR"

if [ ! -f "$CONFIG_DIR/config.yaml" ]; then
    cp config.example.yaml "$CONFIG_DIR/config.yaml"
    echo "✅ Config created at $CONFIG_DIR/config.yaml"
    echo "   → Open it and add your API keys + limits."
else
    echo "ℹ️  Config already exists at $CONFIG_DIR/config.yaml"
fi

echo ""
echo "✅ TokenPulse installed!"
echo ""
echo "Next steps:"
echo "  1. Edit your config:   open $CONFIG_DIR/config.yaml"
echo "  2. Run TokenPulse:     source .venv/bin/activate && tokenpulse"
echo "     Or:                 .venv/bin/tokenpulse"
echo ""
echo "To auto-start on login, run:  bash scripts/autostart.sh"
