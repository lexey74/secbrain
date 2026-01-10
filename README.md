# 🧠 SecBrain - Instagram to Knowledge Base

**Privacy-First** консольная утилита для автоматического сохранения Instagram контента (Posts, Reels, Live) в структурированные заметки для Obsidian.

## ✨ Особенности

- 🔒 **100% Privacy**: Только локальные нейросети (Ollama, Whisper)
- � **Безопасный скрапинг**: Playwright для комментариев (эмуляция браузера)
- �🎯 **Hybrid Scraping**: Gallery-dl для медиа, Playwright для комментариев
- 🏷️ **Smart Tagging**: Автоматическое накопление и переиспользование тегов
- 📝 **Asset Bundles**: Папка на каждый пост (медиа + заметка + метаданные)
- 🤖 **AI-Powered**: Суммаризация, категоризация, фильтрация комментариев
- ⚡ **Раздельная обработка**: download.py (быстро) + process.py (AI анализ)

## 📋 Требования (Pre-requisites)

Перед использованием установите:

### 1. Системные зависимости

- **Python 3.10+**
- **FFmpeg** ([скачать](https://ffmpeg.org/download.html))
  ```bash
  # macOS
  brew install ffmpeg
  
  # Ubuntu/Debian
  sudo apt install ffmpeg
  ```

### 2. Ollama

Скачайте и установите [Ollama](https://ollama.ai)

```bash
# Запустите сервер
ollama serve

# В другом терминале загрузите модель
ollama pull llama3.2
```

### 3. Instagram Cookies

Для работы `yt-dlp` нужны куки браузера:

1. Установите расширение [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
2. Войдите в Instagram
3. Экспортируйте cookies → сохраните как `cookies.txt` в корень проекта

### 4. Instagrapi Session (опционально)

Для получения комментариев:

```python
# Одноразовая настройка
from instagrapi import Client
cl = Client()
cl.login("username", "password")
cl.dump_settings("session.json")
```

## 🚀 Установка

```bash
# 1. Клонируйте репозиторий
git clone <repo-url>
cd secbrain

# 2. Создайте виртуальное окружение
python -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# 3. Установите зависимости
pip install -r requirements.txt

# 4. (Опционально) Скопируйте пример конфига
cp config.example.json config.json

# 5. Проверьте готовность окружения
python check_setup.py

# 6. Запустите
python src/main.py
```

## 📖 Использование

```bash
python src/main.py
```

Введите Instagram URL и утилита:
1. Скачает медиа (видео/фото)
2. Извлечёт текст и комментарии
3. Транскрибирует аудио (если видео)
4. Проанализирует через LLM
5. Создаст структурированную заметку в `SecondBrain_Inbox/`

## 📂 Структура вывода (Asset Bundle)

```
SecondBrain_Inbox/
└── 2024-01-25_username_ai_powered_note/
    ├── media.mp4          # Оригинальное видео
    └── Note.md            # Markdown заметка
```

### Пример Note.md

```markdown
---
created: 2024-01-25
author: tech_guru
url: https://instagram.com/p/ABC123
category: Tutorial
tags:
  - ai
  - coding
  - productivity
  - inbox
---

# tech_guru: AI-Powered Note Taking

![[media.mp4]]

## 🧠 AI Summary
- Рассказывает о новом инструменте для заметок
- [02:15] Демонстрация функции автоматической транскрибации
- Сравнение с Notion и Obsidian

## 💬 Valuable Insights (Comments)
> **user1**: Попробовал, работает лучше чем Otter.ai
> **user2**: На русском языке точность 90%+

---
<details>
<summary>📂 Raw Data</summary>

### Caption
Check out this amazing AI tool! #ai #productivity

### Transcript
[00:00] Привет всем...
[00:45] Сегодня покажу как...
</details>
```

## ⚙️ Конфигурация

Файл `config.json` создаётся автоматически при первом запуске:

```json
{
  "output_dir": "SecondBrain_Inbox",
  "whisper_model": "base",
  "ollama_model": "llama3.2",
  "device": "cpu",
  "max_comments": 50,
  "max_tags": 15
}
```

## 🏗️ Архитектура

```
src/
├── main.py                    # CLI точка входа
├── config.py                  # Управление конфигурацией
└── modules/
    ├── tag_manager.py         # База тегов (known_tags.json)
    ├── hybrid_grabber.py      # Парсинг (yt-dlp + instagrapi)
    ├── local_ears.py          # Транскрибация (faster-whisper)
    ├── local_brain.py         # AI анализ (Ollama)
    └── pipeline.py            # Оркестрация процесса
```

## 🔧 Troubleshooting

### Ошибка: "Ollama не отвечает"

```bash
# Проверьте, что Ollama запущен
ollama serve

# Проверьте модель
ollama list
```

### Ошибка: "yt-dlp не может скачать"

- Обновите cookies.txt (они устаревают)
- Убедитесь, что пост публичный или вы подписаны

### Ошибка: "faster-whisper Out of Memory"

Используйте меньшую модель в `config.json`:
```json
"whisper_model": "tiny"  // вместо "base"
```

## 📝 TODO

- [ ] Завершить реализацию `instagrapi` для комментариев
- [ ] Добавить прогресс-бар для транскрибации
- [ ] Поддержка карусели (множественные фото)
- [ ] Export в Notion API
- [ ] Batch processing (список URL из файла)

## 📄 Лицензия

MIT

## 🙏 Благодарности

- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [instagrapi](https://github.com/subzeroid/instagrapi)
- [faster-whisper](https://github.com/guillaumekln/faster-whisper)
- [Ollama](https://ollama.ai)
