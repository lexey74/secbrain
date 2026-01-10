# SETUP.md - Подробная инструкция по настройке

## Шаг 1: Установка системных зависимостей

### macOS
```bash
# Homebrew (если не установлен)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# FFmpeg
brew install ffmpeg

# Python 3.10+
brew install python@3.10
```

### Ubuntu/Debian
```bash
sudo apt update
sudo apt install -y python3.10 python3-pip ffmpeg

# Для Playwright (опционально, если нужен безопасный скрапинг)
sudo apt install -y libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
  libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
  libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2
```

### Windows
1. Скачайте Python 3.10+ с [python.org](https://www.python.org/downloads/)
2. Скачайте FFmpeg с [ffmpeg.org](https://ffmpeg.org/download.html)
3. Добавьте в PATH

## Шаг 2: Установка Ollama

### macOS/Linux
```bash
# Скачайте с официального сайта
curl -fsSL https://ollama.ai/install.sh | sh

# Или через Homebrew (macOS)
brew install ollama

# Запустите сервер
ollama serve
```

### В другом терминале загрузите модель
```bash
# Основная модель (рекомендуется)
ollama pull llama3.2

# Альтернатива
ollama pull mistral

# Проверка
ollama list
```

## Шаг 3: Настройка Instagram Cookies

### Способ 1: Расширение браузера (рекомендуется)

1. **Chrome/Edge:**
   - Установите [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)

2. **Firefox:**
   - Установите [cookies.txt](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/)

3. **Экспорт cookies:**
   - Откройте instagram.com
   - Войдите в свой аккаунт
   - Кликните по иконке расширения
   - Выберите "Export" → "Netscape format"
   - Сохраните как `cookies.txt` в корень проекта `secbrain/`

### Способ 2: Curl (для опытных)
```bash
# Экспорт через curl
curl 'https://www.instagram.com/' \
  -H 'Cookie: YOUR_COOKIES_HERE' \
  --cookie-jar cookies.txt
```

## Шаг 4: Установка Playwright (опционально, для безопасного скрапинга комментариев)

**Зачем нужен Playwright?**
- Безопасный скрапинг комментариев через настоящий браузер
- Эмуляция человеческого поведения
- Минимальный риск бана от Instagram

### Установка

```bash
# Активируйте venv
source venv/bin/activate

# Установите Playwright
pip install playwright

# Установите браузер Chromium
playwright install chromium

# Linux: установите системные зависимости
playwright install-deps chromium
```

### Настройка cookies для Playwright

1. **Расширение для Chrome (рекомендуется):**
   - Установите [EditThisCookie](https://chrome.google.com/webstore/detail/editthiscookie/fngmhnnpilhplaeedifhccceomclgfbg)
   - Войдите в Instagram
   - Кликните расширение → Export → **JSON формат**
   - Сохраните как `instagram_cookies.json` в корне проекта

2. **Ручной вход (первый запуск):**
   ```bash
   # Запустите с видимым окном
   python -c "
   from modules.safe_comments import SafeCommentsScraper
   scraper = SafeCommentsScraper(headless=False)
   # Войдите вручную, cookies сохранятся автоматически
   "
   ```

### Проверка

```bash
python -c "from playwright.sync_api import sync_playwright; print('✅ Playwright работает')"
```

Подробнее: [PLAYWRIGHT_GUIDE.md](PLAYWRIGHT_GUIDE.md)

---

## Шаг 5: Настройка Gallery-dl cookies (для gallery-dl метода)

Для получения комментариев и метаданных нужна авторизация:

```python
# Создайте временный скрипт setup_session.py
from instagrapi import Client

cl = Client()

# Вариант 1: Логин/пароль
cl.login("your_username", "your_password")

# Вариант 2: Двухфакторная аутентификация
# code = input("Введите код из SMS: ")
# cl.login("username", "password", verification_code=code)

# Сохранение сессии
cl.dump_settings("session.json")
print("✅ Session сохранена в session.json")
```

Запустите:
```bash
python setup_session.py
```

**Важно:** Не коммитьте `session.json` в git!

## Шаг 5: Установка Python зависимостей

```bash
# Перейдите в папку проекта
cd /Users/alexpost/Downloads/projects/secbrain

# Создайте виртуальное окружение
python3 -m venv venv

# Активируйте
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# Установите зависимости
pip install -r requirements.txt
```

## Шаг 6: Первый запуск

```bash
python src/main.py
```

Вы увидите:
```
╔═══════════════════════════════════════════╗
║     🧠 SecBrain - Instagram to Notes     ║
║   Privacy-First Knowledge Base Builder   ║
╚═══════════════════════════════════════════╝

📁 Output: SecondBrain_Inbox
🤖 Model: llama3.2

✅ Ollama library installed
✅ faster-whisper installed
✅ yt-dlp found
✅ FFmpeg found

────────────────────────────────────────────────────────────
Instagram URL (или 'quit' для выхода):
```

## Проверка работы

### Тест 1: Загрузка медиа
```bash
# Вставьте любой публичный Instagram пост
https://www.instagram.com/p/XXXXXXXXX/
```

### Тест 2: Проверка Whisper (видео)
```bash
# Вставьте ссылку на Reels или видео-пост
https://www.instagram.com/reel/XXXXXXXXX/
```

### Тест 3: Проверка LLM
После обработки проверьте:
- Создана ли папка в `SecondBrain_Inbox/`
- Есть ли файл `Note.md`
- Корректность summary и тегов

## Troubleshooting

### Ошибка: "ModuleNotFoundError: No module named 'ollama'"
```bash
pip install ollama
```

### Ошибка: "Connection refused (Ollama)"
```bash
# Запустите Ollama в отдельном терминале
ollama serve
```

### Ошибка: "HTTP Error 403: Forbidden (yt-dlp)"
- Обновите `cookies.txt` (куки устаревают)
- Проверьте, что пост публичный

### Ошибка: "CUDA out of memory (Whisper)"
Измените `config.json`:
```json
{
  "whisper_model": "tiny",
  "device": "cpu"
}
```

### Ошибка: "instagrapi login failed"
- Используйте App Password (если включена 2FA)
- Попробуйте через браузер (может требоваться капча)
- Используйте VPN если Instagram блокирует регион

## Структура файлов после настройки

```
secbrain/
├── venv/                    # Виртуальное окружение
├── src/                     # Исходный код
├── cookies.txt              # Instagram cookies (НЕ коммитить!)
├── session.json             # Instagrapi session (НЕ коммитить!)
├── config.json              # Конфигурация (создается автоматически)
├── known_tags.json          # База тегов (создается автоматически)
├── requirements.txt         # Зависимости
├── README.md               # Основная документация
└── .gitignore              # Исключения

SecondBrain_Inbox/          # Выходная папка (создается автоматически)
├── 2024-01-25_user1_note/
├── 2024-01-25_user2_note/
└── ...
```

## Готово!

Теперь можно использовать SecBrain для создания заметок из Instagram контента! 🎉
