#!/bin/bash
# Test execution script for Siloq
# Run pytest with proper configuration and output formatting

set -e

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

echo "Running Siloq Test Suite"
echo "======================"
echo ""

# Run all unit tests
echo "Unit Tests:"
echo "----------"
python -m pytest tests/unit/ -v --tb=short --disable-warnings

echo ""
echo "Test Summary Complete"
echo "======================"
