#!/bin/zsh
# Quick setup script for DigitalOcean App Platform deployment
# This script helps you get started with your Siloq deployment

set -e

echo "🚀 Siloq DigitalOcean App Platform Setup"
echo "========================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if we're in the right directory
if [ ! -f "generate_token.py" ]; then
    echo "❌ Error: Please run this script from the Siloq project directory"
    exit 1
fi

echo "📋 Prerequisites Checklist:"
echo "  1. DigitalOcean App Platform app created"
echo "  2. App URL: https://siloq-app-edwlr.ondigitalocean.app"
echo "  3. Access to DigitalOcean dashboard"
echo ""
read -p "Press Enter to continue..."

echo ""
echo "🔑 Step 1: Get SECRET_KEY from DigitalOcean"
echo "--------------------------------------------"
echo ""
echo "Please do the following:"
echo "  1. Go to https://cloud.digitalocean.com/"
echo "  2. Navigate to Apps → Your Siloq App → Settings"
echo "  3. Find SECRET_KEY in Environment Variables"
echo "  4. Copy the value"
echo ""
read -p "Paste your SECRET_KEY here (or press Enter to skip): " SECRET_KEY

if [ -z "$SECRET_KEY" ]; then
    echo "⚠️  SECRET_KEY not provided. You'll need to set it manually."
    echo "   Run: export SECRET_KEY='your-key-here'"
else
    export SECRET_KEY="$SECRET_KEY"
    echo "✅ SECRET_KEY set (for this session only)"
fi

echo ""
echo "🐍 Step 2: Setup Python Environment"
echo "-----------------------------------"
echo ""

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

echo "Activating virtual environment..."
source venv/bin/activate

# Check if python-jose is installed
if ! python -c "from jose import jwt" 2>/dev/null; then
    echo "Installing python-jose..."
    python -m pip install 'python-jose[cryptography]' > /dev/null 2>&1
    echo "✅ python-jose installed"
else
    echo "✅ python-jose already installed"
fi

echo ""
echo "🎫 Step 3: Generate JWT Token"
echo "-----------------------------"
echo ""

if [ -z "$SECRET_KEY" ]; then
    echo "⚠️  SECRET_KEY not set. Please export it first:"
    echo "   export SECRET_KEY='your-key-here'"
    echo ""
    echo "Then run: python3 generate_token.py 'user-123' 'account-456'"
else
    read -p "Enter User ID (or press Enter for 'test-user-123'): " USER_ID
    USER_ID=${USER_ID:-"test-user-123"}
    
    read -p "Enter Account ID (or press Enter for 'test-account-456'): " ACCOUNT_ID
    ACCOUNT_ID=${ACCOUNT_ID:-"test-account-456"}
    
    echo ""
    echo "Generating JWT token..."
    python3 generate_token.py "$USER_ID" "$ACCOUNT_ID"
    
    echo ""
    echo "✅ Token generated! Copy it from above."
fi

echo ""
echo "🌐 Step 4: Test API Connection"
echo "-------------------------------"
echo ""

API_URL="https://siloq-app-edwlr.ondigitalocean.app"
echo "Testing connection to: $API_URL"
echo ""

# Test health endpoint
HEALTH_RESPONSE=$(curl -s "$API_URL/health" 2>/dev/null || echo "ERROR")

if [[ "$HEALTH_RESPONSE" == *"healthy"* ]] || [[ "$HEALTH_RESPONSE" == *"status"* ]]; then
    echo "✅ API is reachable!"
    echo "Response: $HEALTH_RESPONSE"
else
    echo "⚠️  Could not reach API. Please check:"
    echo "   - App is deployed and running"
    echo "   - URL is correct: $API_URL"
fi

echo ""
echo "📝 Next Steps:"
echo "=============="
echo ""
echo "1. Create a Site:"
echo "   curl -X POST $API_URL/api/v1/sites \\"
echo "     -H 'Authorization: Bearer YOUR_JWT_TOKEN' \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"name\": \"My Site\", \"domain\": \"example.com\"}'"
echo ""
echo "2. Generate API Key (after creating site):"
echo "   curl -X POST $API_URL/api/v1/api-keys \\"
echo "     -H 'Authorization: Bearer YOUR_JWT_TOKEN' \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"site_id\": \"YOUR_SITE_ID\", \"name\": \"WordPress Key\"}'"
echo ""
echo "3. Configure WordPress Plugin:"
echo "   - API URL: $API_URL/api/v1"
echo "   - API Key: (from step 2)"
echo "   - Site ID: (from step 1)"
echo ""
echo "📖 For detailed instructions, see: DIGITALOCEAN_SETUP_GUIDE.md"
echo ""
echo "✅ Setup script complete!"
