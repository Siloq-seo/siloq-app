# Test Execution Instructions

## Quick Start

1. Activate virtual environment:
   ```bash
   source venv/bin/activate
   ```

2. Install dependencies (if not already installed):
   ```bash
   pip install -r requirements.txt
   ```

3. Set required environment variables:
   ```bash
   export SILOQ_MASTER_ENCRYPTION_KEY="test-key-32-bytes-long-12345678"
   export OPENAI_API_KEY="test-key"
   ```

4. Run tests:
   ```bash
   python -m pytest tests/unit/ -v
   ```

## Test Structure

- Unit tests: `tests/unit/` (15 test files, 1,226 lines)
- Integration tests: `tests/integration/` (1 test file)
- Configuration: `pytest.ini`
- Fixtures: `tests/conftest.py`

## Common Commands

```bash
# All unit tests
python -m pytest tests/unit/ -v

# Specific test file
python -m pytest tests/unit/services/test_image_placeholder.py -v

# With coverage
python -m pytest tests/ --cov=app --cov-report=term

# Specific test
python -m pytest tests/unit/services/test_image_placeholder.py::TestImagePlaceholderInjector::test_has_image_tags -v
```
