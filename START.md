# 🚀 SecBrain - Инструкция по запуску

## Быстрый старт после перезагрузки VPS

### 1️⃣ Проверка сервисов

```bash
# Проверить что Ollama работает (запускается автоматически)
sudo systemctl status ollama

# Если не работает - запустить
sudo systemctl start ollama
```

### 2️⃣ Запуск модулей

#### Модуль 1: Скачивание контента (интерактивный)

```bash
cd /home/lexey/projects/secbrain
source venv/bin/activate
python module1_download.py
```

После запуска:
- Введите URL YouTube или Instagram
- Нажмите Enter
- Для выхода введите: `q`

#### Модуль 2: Транскрибация (фоновый)

```bash
cd /home/lexey/projects/secbrain
source venv/bin/activate
nohup python -u module2_transcribe.py > transcribe.log 2>&1 &
```

Мониторинг:
```bash
./check_status.sh           # Быстрая проверка
./monitor_transcription.sh  # Автоматический мониторинг
tail -f transcribe.log      # Следить за логом
```

#### Модуль 3: AI обработка

```bash
cd /home/lexey/projects/secbrain/src
source ../venv/bin/activate
python process.py
```

---

## 📋 Полный цикл обработки

### Шаг 1: Скачать контент
```bash
cd /home/lexey/projects/secbrain
source venv/bin/activate
python module1_download.py
# Ввести URL, дождаться скачивания
```

### Шаг 2: Транскрибировать видео
```bash
# Запустить в фоне
nohup python -u module2_transcribe.py > transcribe.log 2>&1 &

# Дождаться завершения (проверять через ./check_status.sh)
```

### Шаг 3: AI анализ
```bash
cd src
python process.py
```

---

## 🔧 Полезные команды

### Проверка процессов
```bash
# Whisper транскрибация
ps aux | grep module2_transcribe | grep -v grep

# Ollama
ps aux | grep ollama | grep -v grep
```

### Остановка процессов
```bash
# Остановить транскрибацию
pkill -f module2_transcribe

# Перезапустить Ollama
sudo systemctl restart ollama
```

### Проверка результатов
```bash
# Список скачанных папок
ls -la downloads/

# Список транскриптов
find downloads -name "transcript.md" | wc -l

# Последние транскрипты
find downloads -name "transcript.md" -mmin -60
```

---

## ⚙️ Конфигурация

### Файлы конфигурации
- `config.json` - основные настройки
- `src/config.py` - значения по умолчанию

### Текущие настройки (оптимизированы)
```json
{
  "whisper_model": "small",
  "ollama_model": "qwen2.5:7b",
  "num_threads": 16,
  "num_ctx": 8192
}
```

### Ollama systemd (оптимизирован)
```
OLLAMA_NUM_THREADS=16
OLLAMA_MAX_LOADED_MODELS=1
OLLAMA_NUM_PARALLEL=1
```

---

## 🔄 Автозапуск (опционально)

Для автоматического запуска транскрибации при старте системы:

```bash
# Создать systemd сервис
sudo tee /etc/systemd/system/secbrain-transcribe.service << 'EOF'
[Unit]
Description=SecBrain Transcription Service
After=network.target ollama.service

[Service]
Type=simple
User=lexey
WorkingDirectory=/home/lexey/projects/secbrain
ExecStart=/home/lexey/projects/secbrain/venv/bin/python -u module2_transcribe.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Включить автозапуск
sudo systemctl daemon-reload
sudo systemctl enable secbrain-transcribe
sudo systemctl start secbrain-transcribe
```

---

## 📊 Структура проекта

```
secbrain/
├── module1_download.py    # Скачивание контента
├── module2_transcribe.py  # Транскрибация Whisper
├── config.json            # Конфигурация
├── downloads/             # Скачанные файлы
├── cookies/               # Cookies для YouTube
├── src/
│   ├── process.py         # AI обработка
│   ├── config.py          # Настройки по умолчанию
│   └── modules/           # Модули системы
├── check_status.sh        # Скрипт проверки статуса
├── monitor_transcription.sh # Мониторинг транскрибации
└── transcribe.log         # Лог транскрибации
```

---

## ❓ Troubleshooting

### Ollama не отвечает
```bash
sudo systemctl restart ollama
curl http://localhost:11434/api/tags
```

### Транскрибация зависла
```bash
pkill -f module2_transcribe
# Перезапустить
nohup python -u module2_transcribe.py > transcribe.log 2>&1 &
```

### Ошибка "faster-whisper not found"
```bash
source venv/bin/activate
pip install faster-whisper
```

### Ошибка cookies YouTube
```bash
# Обновить cookies - см. YOUTUBE_COOKIES_UPDATE_GUIDE.md
```

---

## 📝 Примеры URL

```
# YouTube Video
https://www.youtube.com/watch?v=VIDEO_ID
https://youtu.be/VIDEO_ID

# YouTube Shorts
https://www.youtube.com/shorts/VIDEO_ID

# Instagram Reels
https://www.instagram.com/reel/POST_ID/
https://www.instagram.com/p/POST_ID/
```

---

*Последнее обновление: 2026-01-11*
