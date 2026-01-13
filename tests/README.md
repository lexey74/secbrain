# Unit Tests

Pytest-based unit test suite for SecBrain modules.

## Test Results ✅

**Total: 23 unit tests** | **Status: All Passing**

- ✅ TagManager: 9 tests (86% coverage)
- ✅ LocalEars (Whisper): 4 tests (76% coverage)  
- ✅ LocalBrain (AI): 5 tests (28% coverage)
- ✅ HybridGrabber (Downloader): 5 tests (38% coverage)

## Structure

```
tests/
├── __init__.py              # Package initialization
├── conftest.py              # Pytest fixtures and shared mocks
├── test_tag_manager.py      # TagManager tests (9 tests)
├── test_local_ears.py       # LocalEars/Whisper tests (4 tests)
├── test_local_brain.py      # LocalBrain/AI tests (5 tests)
└── test_hybrid_grabber.py   # HybridGrabber/Downloaders tests (5 tests)
```

## Running Tests

### Install test dependencies:
```bash
pip install pytest pytest-mock pytest-cov
```

### Run all tests:
```bash
pytest tests/
```

### Run specific test file:
```bash
pytest tests/test_tag_manager.py
pytest tests/test_local_ears.py -v
```

### Run with coverage:
```bash
pytest --cov=modules --cov-report=html tests/
```

### Run with verbose output:
```bash
pytest -v tests/
```

## Test Coverage

- **TagManager** (9 tests, 86% coverage):
  - Initialization with new/existing files
  - Adding single/multiple/duplicate tags
  - Tag normalization (lowercase, strip)
  - get_tags_string() functionality
  - File save/load operations

- **LocalEars/Whisper** (4 tests, 76% coverage):
  - Initialization with default/custom configs
  - Basic transcription with mocked WhisperModel
  - Timestamp formatting (MM:SS format)

- **LocalBrain/AI** (5 tests, 28% coverage):
  - Model initialization (default/custom)
  - Prompt building with caption/transcript/comments
  - Core logic without actual LLM calls

- **HybridGrabber/Downloaders** (5 tests, 38% coverage):
  - Grabber initialization
  - Username extraction from URLs
  - Gallery-dl integration (mocked)
  - InstagramContent dataclass

## Fixtures (conftest.py)

- `temp_dir` - Temporary directory for tests
- `mock_tags_file` - Mock tags JSON file
- `sample_tags` - Sample tag list
- `sample_transcript` - Sample transcription text
- `sample_description` - Sample content description
- `mock_ollama_response` - Mock AI response
- `mock_whisper_result` - Mock Whisper transcription result

## Mocking Strategy

- **WhisperModel**: Mocked with `@patch('modules.local_ears.WhisperModel')`
- **Ollama**: Mocked with `@patch('modules.local_brain.ollama')`
- **subprocess.run**: Mocked for downloader tests
- **File I/O**: Using `tmp_path` fixture for safe file operations

## CI/CD Integration

Add to `.github/workflows/tests.yml`:
```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - run: pip install -r requirements.txt
      - run: pytest tests/ --cov=modules --cov-report=xml
      - uses: codecov/codecov-action@v3
```

## Best Practices

✅ Use fixtures for shared test data  
✅ Mock external dependencies (Ollama, Whisper, downloaders)  
✅ Use `tmp_path` for file operations  
✅ Test both success and error cases  
✅ Use descriptive test names  
✅ Keep tests isolated and independent  

## Notes

- Tests use mocks to avoid real API calls
- No actual downloads or AI inference during tests
- All file operations use temporary directories
- Tests are fast and can run offline
