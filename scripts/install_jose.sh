#!/bin/zsh
# Fix for zsh pip installation issue with python-jose[cryptography]
# This script bypasses the custom pip function

set -e

echo "🔧 Installing python-jose[cryptography] (zsh-safe method)"
echo ""

# Navigate to project directory
cd "$(dirname "$0")"

# Create venv if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate venv
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Install using python -m pip (bypasses custom pip function)
echo "⬇️  Installing python-jose[cryptography]..."
python -m pip install 'python-jose[cryptography]'

# Verify installation
echo ""
echo "✅ Verifying installation..."
python -c "from jose import jwt; print('✅ python-jose installed successfully!')"

echo ""
echo "🎉 Done! You can now use generate_token.py"
echo ""
echo "Next steps:"
echo "  1. Get your SECRET_KEY from your environment"
echo "  2. Run: export SECRET_KEY='your-secret-key'"
echo "  3. Run: python3 generate_token.py 'user-123' 'account-456'"
