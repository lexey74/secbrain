# Project Context
This is a "Second Brain" Telegram bot acting as a content ingestor.
Pipeline: Download (Social Media) -> Transcribe (Whisper) -> Analyze (Ollama) -> Save (Obsidian Markdown).

# Tech Stack
- **Core:** Python 3.12.3, `asyncio`, `dataclasses`.
- **Bot Framework:** `python-telegram-bot` (PTB) v20+ (Async).
- **Downloaders:** `yt-dlp` (Video), `gallery-dl` (Images/Instagram), `youtube-comment-downloader`.
- **Browser Automation:** `playwright` (for bypassing strict protections).
- **AI/ML:**
  - `faster-whisper` (ASR).
  - `ollama` (Models: `llama3.2`, `qwen2.5:7b`).
- **Utils:** `psutil` (Process monitoring), `rich` (Logging).
- **Testing:** `pytest`, `pytest-mock`, `pytest-cov` (23 unit tests, 76-86% coverage on core modules).

# Architecture & Patterns
1. **Modular Pipeline:** Strictly separate execution into 3 stages: `Download` -> `Transcribe` -> `Analyze`.
2. **Factory Pattern:** Use a `ContentRouter` to select the correct handler based on URL (Instagram vs YouTube vs TikTok).
3. **Strategy Pattern:** Implement specific `DownloaderStrategy` classes for each platform.
4. **Data Transfer:** Use `dataclasses` (e.g., `InstagramContent`, `TranscriptResult`) to pass data between layers. Never pass raw dictionaries.
5. **Dependency Injection:** Pass configuration objects (`Config`) explicitly to classes.

# Coding Guidelines

## 1. Concurrency (CRITICAL)
- **PTB Async:** The bot runs on `python-telegram-bot`'s async loop.
- **Blocking Code:** NEVER run `yt-dlp`, `gallery-dl`, `faster-whisper`, or `playwright` sync operations in the main loop.
- **Solution:** Use `loop.run_in_executor(None, blocking_func)` for blocking I/O or CPU-bound tasks.
  ```python
  # ✅ CORRECT - telegram_bot.py pattern
  loop = asyncio.get_event_loop()
  result = await loop.run_in_executor(None, lambda: router.download(url))
  ```
- **Playwright:** Use `async_playwright` API, ensure context closing.

## 2. Python Telegram Bot (PTB) Specifics
- Use `ApplicationBuilder` to construct the app.
- Use `ContextTypes.DEFAULT_TYPE` for type hinting in handlers.
- Prefer `ConversationHandler` only for multi-step flows; use stateless handlers where possible.

## 3. Data Formatting (Obsidian Target)
- **Output:** Files must be valid Markdown (`.md`).
- **Frontmatter:** Every file MUST start with YAML frontmatter delimited by `---`.
- **Fields:** Include `source_url`, `author`, `date`, `tags` (JSON array format), `summary`.

## 4. AI & Resource Management
- **Ollama:** Use specific models (`llama3.2` for summaries, `qwen2.5:7b` for complex logic). Keep prompts concise.
- **Whisper:** Check availability of CUDA before loading; fallback to CPU (int8) if needed.
- **PID Files:** When spawning background workers, write PID files to manage/kill "zombie" processes via `psutil`.

## 5. Error Handling & Logging
- Use `rich` for console output (color-coded levels).
- Exceptions in the `Download` phase should not stop the bot; notify the user and log the trace.
- Handle `Cookie` expiration errors specifically for Instagram.

## 6. Testing
- Use `pytest-mock` to mock `yt-dlp` network calls and `Ollama` responses.
- Do not make real network requests in unit tests.
- Test files location: `tests/` (NOT root directory)
- Integration tests (if needed): `archive/old_tests/` (deprecated)
