#!/usr/bin/env python3
"""
SecBrain Telegram Bot
=====================

Бот для сохранения контента из YouTube, Instagram и прямых загрузок.

Функции:
- URL YouTube/Instagram → скачивание + транскрибация
- Медиа файлы (фото/видео) → запрос описания → сохранение
- Текст → сохранение в description.md

Использование:
1. Создать бота через @BotFather
2. Добавить токен в .env или передать через TELEGRAM_BOT_TOKEN
3. Запустить: python telegram_bot.py
"""

import os
import sys
import re
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from dotenv import load_dotenv

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("⚠️  psutil не установлен. Установите: pip install psutil")

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent / "src"))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, User
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# Импорт модулей SecBrain
from modules.content_router import ContentRouter
from modules.downloader_base import DownloadSettings
from modules.local_ears import LocalEars, TranscriptResult
from modules.tag_manager import TagManager

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================================================================
# Конфигурация
# ============================================================================

@dataclass
class BotConfig:
    """Конфигурация бота"""
    token: str = ""
    users_dir: Path = Path("users")
    allowed_users: list = field(default_factory=list)  # Пустой = все разрешены
    whisper_model: str = "small"
    whisper_threads: int = 16
    
    # Файлы для логов процессов
    transcribe_log: Path = Path("logs/transcribe.log")
    ai_log: Path = Path("logs/ai.log")
    transcribe_pid: Path = Path("logs/transcribe.pid")
    ai_pid: Path = Path("logs/ai.pid")
    
    mcp_host: str = '0.0.0.0'
    mcp_port: int = 8000
    public_mcp_url: str = 'http://localhost:8000'
    auth_file: Path = Path('auth.json')

    @classmethod
    def from_env(cls) -> "BotConfig":
        """Загрузка конфигурации из окружения"""
        # Prefer real environment variables, but also load a .env file if
        # present to simplify local development. python-dotenv is used here
        # to avoid rolling our own parser.
        env_file = Path(__file__).parent / ".env"
        if env_file.exists():
            load_dotenv(dotenv_path=env_file)

        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        allowed_users_str = os.getenv("TELEGRAM_ALLOWED_USERS", "") or ""
        allowed_users = [int(u) for u in allowed_users_str.split(",") if u.strip()]

        config = cls(
            token=token,
            users_dir=Path(os.getenv("USERS_DIR", "users")),
            allowed_users=allowed_users,
            whisper_model=os.getenv("WHISPER_MODEL", "small"),
            whisper_threads=int(os.getenv("WHISPER_THREADS", "16")),
            mcp_host=os.getenv('MCP_HOST', '0.0.0.0'),
            mcp_port=int(os.getenv('MCP_PORT', '8000')),
            public_mcp_url=os.getenv('PUBLIC_MCP_URL', 'http://localhost:8000'),
            auth_file=Path(os.getenv('AUTH_FILE', 'auth.json')),
        )
        
        # Создаём папку для логов
        config.transcribe_log.parent.mkdir(parents=True, exist_ok=True)
        
        return config


# ============================================================================
# Глобальная очередь процессов
# ============================================================================

class ProcessQueue:
    """Глобальная очередь для управления процессами транскрибации и AI анализа"""
    
    def __init__(self):
        self.transcribe_queue: list = []  # [(user_id, username, timestamp)]
        self.ai_queue: list = []  # [(user_id, username, timestamp)]
        self.rag_queue: list = []  # [(user_id, username, timestamp)]
        self.transcribe_running: Optional[tuple] = None  # (user_id, username, pid)
        self.ai_running: Optional[tuple] = None  # (user_id, username, pid)
        self.rag_running: Optional[tuple] = None  # (user_id, username, pid)
    
    def add_to_transcribe_queue(self, user_id: int, username: str) -> int:
        """Добавляет пользователя в очередь транскрибации. Возвращает позицию в очереди."""
        # Проверяем, не в очереди ли уже
        for item in self.transcribe_queue:
            if item[0] == user_id:
                return self.transcribe_queue.index(item) + 1
        
        self.transcribe_queue.append((user_id, username, datetime.now()))
        return len(self.transcribe_queue)
    
    def add_to_ai_queue(self, user_id: int, username: str) -> int:
        """Добавляет пользователя в очередь AI анализа. Возвращает позицию в очереди."""
        # Проверяем, не в очереди ли уже
        for item in self.ai_queue:
            if item[0] == user_id:
                return self.ai_queue.index(item) + 1
        
        self.ai_queue.append((user_id, username, datetime.now()))
        return len(self.ai_queue)

    def add_to_rag_queue(self, user_id: int, username: str) -> int:
        """Добавляет пользователя в очередь RAG (semantic search)."""
        for item in self.rag_queue:
            if item[0] == user_id:
                return self.rag_queue.index(item) + 1

        self.rag_queue.append((user_id, username, datetime.now()))
        return len(self.rag_queue)
    
    def start_transcribe(self, user_id: int, username: str, pid: int):
        """Помечает процесс транскрибации как запущенный"""
        self.transcribe_running = (user_id, username, pid)
        # Удаляем из очереди
        self.transcribe_queue = [item for item in self.transcribe_queue if item[0] != user_id]
    
    def start_ai(self, user_id: int, username: str, pid: int):
        """Помечает процесс AI анализа как запущенный"""
        self.ai_running = (user_id, username, pid)
        # Удаляем из очереди
        self.ai_queue = [item for item in self.ai_queue if item[0] != user_id]

    def start_rag(self, user_id: int, username: str, pid: int):
        """Помечает процесс RAG как запущенный"""
        self.rag_running = (user_id, username, pid)
        self.rag_queue = [item for item in self.rag_queue if item[0] != user_id]
    
    def finish_transcribe(self):
        """Завершает процесс транскрибации"""
        self.transcribe_running = None
    
    def finish_ai(self):
        """Завершает процесс AI анализа"""
        self.ai_running = None

    def finish_rag(self):
        """Завершает процесс RAG"""
        self.rag_running = None
    
    def get_transcribe_status(self, user_id: int) -> dict:
        """Получает статус пользователя в очереди транскрибации"""
        # Проверяем, запущен ли процесс этим пользователем
        if self.transcribe_running and self.transcribe_running[0] == user_id:
            return {
                'status': 'running',
                'position': 0,
                'pid': self.transcribe_running[2]
            }
        
        # Проверяем позицию в очереди
        for i, item in enumerate(self.transcribe_queue):
            if item[0] == user_id:
                return {
                    'status': 'queued',
                    'position': i + 1,
                    'total': len(self.transcribe_queue)
                }
        
        return {'status': 'not_in_queue'}
    
    def get_ai_status(self, user_id: int) -> dict:
        """Получает статус пользователя в очереди AI анализа"""
        # Проверяем, запущен ли процесс этим пользователем
        if self.ai_running and self.ai_running[0] == user_id:
            return {
                'status': 'running',
                'position': 0,
                'pid': self.ai_running[2]
            }
        
        # Проверяем позицию в очереди
        for i, item in enumerate(self.ai_queue):
            if item[0] == user_id:
                return {
                    'status': 'queued',
                    'position': i + 1,
                    'total': len(self.ai_queue)
                }
        
        return {'status': 'not_in_queue'}

    def get_rag_status(self, user_id: int) -> dict:
        """Получает статус пользователя в очереди RAG"""
        if self.rag_running and self.rag_running[0] == user_id:
            return {
                'status': 'running',
                'position': 0,
                'pid': self.rag_running[2]
            }

        for i, item in enumerate(self.rag_queue):
            if item[0] == user_id:
                return {
                    'status': 'queued',
                    'position': i + 1,
                    'total': len(self.rag_queue)
                }

        return {'status': 'not_in_queue'}
    
    def can_start_transcribe(self) -> bool:
        """Проверяет, можно ли запустить транскрибацию"""
        return self.transcribe_running is None and len(self.transcribe_queue) > 0
    
    def can_start_ai(self) -> bool:
        """Проверяет, можно ли запустить AI анализ"""
        return self.ai_running is None and len(self.ai_queue) > 0

    def can_start_rag(self) -> bool:
        """Проверяет, можно ли запустить RAG задачу"""
        return self.rag_running is None and len(self.rag_queue) > 0


# ============================================================================
# Состояния для ConversationHandler
# ============================================================================

WAITING_DESCRIPTION = 1
WAITING_TITLE = 2
WAITING_COMMENTS_CONFIRMATION = 3


# ============================================================================
# Утилиты
# ============================================================================

async def start_transcribe_process(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                   config: BotConfig, queue: ProcessQueue, user_folder: Path):
    """Запускает процесс транскрибации для пользователя"""
    user = update.effective_user
    username = user.username or f"user_{user.id}"
    
    status_msg = await update.message.reply_text(
        "🎤 **Модуль 2: Транскрибация**\n\n"
        "Запускаю транскрибацию в фоновом режиме...",
        parse_mode='Markdown'
    )
    
    try:
        import subprocess
        
        # Очищаем лог-файл пользователя
        user_log = config.transcribe_log.parent / f"transcribe_{user.id}.log"
        user_log.write_text("")
        
        # Запускаем процесс только для папки пользователя
        process = subprocess.Popen(
            [sys.executable, "module2_transcribe.py", "--folder", str(user_folder)],
            cwd=Path(__file__).parent,
            stdout=open(user_log, 'w'),
            stderr=subprocess.STDOUT,
            start_new_session=True
        )
        
        # Сохраняем PID
        config.transcribe_pid.write_text(str(process.pid))
        
        # Обновляем очередь
        queue.start_transcribe(user.id, username, process.pid)
        
        await status_msg.edit_text(
            f"✅ Транскрибация запущена!\n\n"
            f"🆔 PID: {process.pid}\n"
            f"📂 Папка: `{user_folder.name}`\n\n"
            f"Используйте /check для отслеживания прогресса\n"
            f"Логи: `{user_log.name}`",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error starting transcribe process: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Ошибка запуска: {str(e)[:200]}")
        queue.finish_transcribe()


async def start_ai_process(update: Update, context: ContextTypes.DEFAULT_TYPE,
                           config: BotConfig, queue: ProcessQueue, user_folder: Path):
    """Запускает процесс AI анализа для пользователя"""
    user = update.effective_user
    username = user.username or f"user_{user.id}"
    
    status_msg = await update.message.reply_text(
        "🤖 **Модуль 3: AI Анализ**\n\n"
        "Запускаю анализ в фоновом режиме...",
        parse_mode='Markdown'
    )
    
    try:
        import subprocess
        
        # Очищаем лог-файл пользователя
        user_log = config.ai_log.parent / f"ai_{user.id}.log"
        user_log.write_text("")
        
        # Запускаем процесс только для папки пользователя
        process = subprocess.Popen(
            [sys.executable, "module3_analyze.py", "--folder", str(user_folder)],
            cwd=Path(__file__).parent,
            stdout=open(user_log, 'w'),
            stderr=subprocess.STDOUT,
            start_new_session=True
        )
        
        # Сохраняем PID
        config.ai_pid.write_text(str(process.pid))
        
        # Обновляем очередь
        queue.start_ai(user.id, username, process.pid)
        
        await status_msg.edit_text(
            f"✅ AI анализ запущен!\n\n"
            f"🆔 PID: {process.pid}\n"
            f"📂 Папка: `{user_folder.name}`\n\n"
            f"Используйте /check для отслеживания прогресса\n"
            f"Логи: `{user_log.name}`",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error starting AI process: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Ошибка запуска: {str(e)[:200]}")
        queue.finish_ai()


def get_user_folder(user: User, users_dir: Path) -> Path:
    """
    Получает папку downloads для конкретного пользователя
    
    Args:
        user: Telegram User объект
        users_dir: Базовая директория users/
        
    Returns:
        Path к папке downloads пользователя
    """
    if user.username:
        folder_name = sanitize_filename(user.username, max_length=50)
    else:
        folder_name = f"user_{user.id}"
    
    # users/{username}/downloads
    user_download_folder = users_dir / folder_name / "downloads"
    user_download_folder.mkdir(parents=True, exist_ok=True)
    
    return user_download_folder


def ensure_user_structure(user: User, users_dir: Path) -> Path:
    """
    Создает полную структуру папок для пользователя
    
    Args:
        user: Telegram User объект
        users_dir: Базовая директория users/
        
    Returns:
        Path к корневой папке пользователя
    """
    if user.username:
        folder_name = sanitize_filename(user.username, max_length=50)
    else:
        folder_name = f"user_{user.id}"
    
    user_root = users_dir / folder_name
    
    # Создаем структуру согласно structure.md
    subdirs = [
        "downloads",
        "Context",
        "Goals",
        "Reviews",
        "Projects",
        "Meetings",
        "achievements"
    ]
    
    for subdir in subdirs:
        (user_root / subdir).mkdir(parents=True, exist_ok=True)
    
    return user_root


def sanitize_filename(name: str, max_length: int = 80) -> str:
    """Очистка имени для использования в пути к файлу"""
    # Заменяем недопустимые символы
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    # Убираем множественные пробелы
    name = re.sub(r'\s+', '_', name)
    # Обрезаем до max_length
    if len(name) > max_length:
        name = name[:max_length]
    return name.strip('_')


def detect_url_type(text: str) -> Optional[str]:
    """Определяет тип URL"""
    text = text.strip()
    
    # YouTube patterns
    youtube_patterns = [
        r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=[\w-]+',
        r'(?:https?://)?(?:www\.)?youtube\.com/shorts/[\w-]+',
        r'(?:https?://)?youtu\.be/[\w-]+',
        r'(?:https?://)?(?:www\.)?youtube\.com/live/[\w-]+',
    ]
    
    for pattern in youtube_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return "youtube"
    
    # Instagram patterns
    instagram_patterns = [
        r'(?:https?://)?(?:www\.)?instagram\.com/p/[\w-]+',
        r'(?:https?://)?(?:www\.)?instagram\.com/reel/[\w-]+',
        r'(?:https?://)?(?:www\.)?instagram\.com/reels/[\w-]+',
    ]
    
    for pattern in instagram_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return "instagram"
    
    return None


def create_folder_name(content_type: str, title: str = "", source_id: str = "") -> str:
    """Создаёт имя папки для контента"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if title:
        safe_title = sanitize_filename(title, 60)
        return f"{content_type}_{safe_title}_{timestamp}"
    elif source_id:
        return f"{content_type}_{source_id}_{timestamp}"
    else:
        return f"{content_type}_{timestamp}"


# ============================================================================
# Обработчики команд
# ============================================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    user = update.effective_user
    
    welcome_text = f"""
🧠 **SecBrain - Personal Knowledge Manager**

👋 Привет, {user.first_name}!

Я помогу тебе сохранять и систематизировать контент из разных источников в твою персональную базу знаний.

━━━━━━━━━━━━━━━━━━━━━━━
📥 **Что я умею:**

🔗 **Социальные сети**
   • Instagram (Posts, Reels, Stories)
   • YouTube (Videos, Shorts)
   • TikTok (скоро)

🎤 **Транскрипция**
   • Распознавание речи (Whisper AI)
   • Поддержка 99+ языков
   • Сохранение в Markdown

🤖 **AI Анализ**
   • Автоматическое саммари
   • Умные теги
   • Категоризация

━━━━━━━━━━━━━━━━━━━━━━━
🚀 **Как использовать:**

1️⃣ Отправь ссылку (YouTube/Instagram)
2️⃣ Или отправь файл (фото/видео)
3️⃣ Или отправь текст для заметки

Я скачаю, транскрибирую и сохраню всё в Obsidian!

━━━━━━━━━━━━━━━━━━━━━━━
📋 **Команды:**
/start - Это сообщение
/help - Подробная справка
/check - Проверить состояние твоих папок
/transcribe - Транскрибировать последнее видео
/url - Скачать по ссылке
/ai - AI анализ (в разработке)
/tags - Просмотр тегов (в разработке)
/user - Информация о вас

━━━━━━━━━━━━━━━━━━━━━━━
👥 **Многопользовательский режим**
Твои данные хранятся отдельно от других пользователей.
Ты видишь только свой контент!

🔒 **Privacy-First:** Все AI модели работают локально!
🚀 Просто отправь мне что-нибудь!
"""
    await update.message.reply_text(welcome_text, parse_mode='Markdown')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help"""
    help_text = """
📖 **Полное руководство SecBrain**

**📥 1. Загрузка контента:**
Просто отправьте ссылку или файл.

• **YouTube:**
  - Видео (`watch?v=...`, `youtu.be/...`)
  - Shorts (`shorts/...`)
  - Комментарии (предложу скачать после видео)
  - _Скачаются: видео (best), описание, субтитры_

• **Instagram:**
  - Posts (`p/...`) - Фото/Карусели/Видео
  - Reels (`reel/...`) - Видео
  - Комментарии (предложу скачать после поста)
  - _Скачаются: медиа файлы, описание, метаданные_

• **Файлы и текст:**
  - Отправьте фото/видео/документ → сохраню в личную папку
  - Отправьте текст → сохраню как заметку

**🧠 2. Обработка и AI:**
Команды для работы с вашей базой знаний:

• `/transcribe` - Транскрибировать все видео в папке (Whisper)
• `/ai` - Запустить AI анализ: тегирование, саммари (Ollama)
• `/ask <вопрос>` - Умный поиск по вашей базе (RAG)
  _Пример: /ask о чем было видео про Python?_

**🔧 3. Интеграции:**
• `/mcp` - Получить ключ для подключения IDE (Cursor/Windsurf) через MCP
• `/check` - Проверить статус фоновых задач
• `/show` - Показать файлы последней сохраненной папки
• `/user` - Информация о вашем профиле

**📊 Как это работает:**
1. Вы скидываете контент → Бот сохраняет в `downloads/{user_id}/...`
2. Бот предлагает скачать комментарии (если есть)
3. Бот спрашивает название для папки
4. Вы запускаете `/transcribe` или `/ai` для обогащения данных
5. Ищете ответы через `/ask` или подключаетесь через MCP прямо из IDE
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')



async def transcribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /transcribe - запуск Модуля 2 (транскрибация всех папок)"""
    config: BotConfig = context.bot_data.get('config', BotConfig())
    queue: ProcessQueue = context.bot_data.get('process_queue', ProcessQueue())
    user = update.effective_user
    
    # Получаем пользовательскую папку
    user_folder = get_user_folder(user, config.users_dir)
    
    if not user_folder.exists() or not list(user_folder.iterdir()):
        await update.message.reply_text("📁 Ваша папка пуста")
        return
    
    # Проверяем статус в очереди
    status = queue.get_transcribe_status(user.id)
    
    if status['status'] == 'running':
        await update.message.reply_text(
            f"⚙️ Транскрибация уже запущена для вас (PID: {status['pid']})\n\n"
            f"Используйте /check для просмотра статуса"
        )
        return
    
    if status['status'] == 'queued':
        await update.message.reply_text(
            f"⏳ Вы уже в очереди транскрибации!\n\n"
            f"📊 Позиция: {status['position']} из {status['total']}\n\n"
            f"Дождитесь своей очереди или используйте /check для статуса"
        )
        return
    
    # Добавляем в очередь
    username = user.username or f"user_{user.id}"
    position = queue.add_to_transcribe_queue(user.id, username)
    
    if position == 1 and queue.transcribe_running is None:
        # Можем запускать сразу
        await start_transcribe_process(update, context, config, queue, user_folder)
    else:
        # Ждем в очереди
        await update.message.reply_text(
            f"⏳ Добавлено в очередь транскрибации\n\n"
            f"📊 Ваша позиция: {position}\n\n"
            f"Процесс запустится автоматически, когда подойдет очередь.\n"
            f"Используйте /check для отслеживания статуса.",
            parse_mode='Markdown'
        )


def get_process_info(pid: int) -> Optional[Dict[str, Any]]:
    """
    Получает информацию о процессе
    
    Args:
        pid: ID процесса
        
    Returns:
        Словарь с информацией или None если процесс не найден
    """
    if not PSUTIL_AVAILABLE:
        return None
    
    try:
        process = psutil.Process(pid)
        
        # Время работы
        create_time = datetime.fromtimestamp(process.create_time())
        uptime = datetime.now() - create_time
        
        # Форматируем время работы
        hours, remainder = divmod(int(uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            uptime_str = f"{hours}ч {minutes}м {seconds}с"
        elif minutes > 0:
            uptime_str = f"{minutes}м {seconds}с"
        else:
            uptime_str = f"{seconds}с"
        
        # CPU и память
        cpu_percent = process.cpu_percent(interval=0.1)
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / 1024 / 1024  # RSS в МБ
        
        return {
            'uptime': uptime_str,
            'cpu_percent': cpu_percent,
            'memory_mb': memory_mb,
            'status': process.status()
        }
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


def get_ollama_info() -> Optional[Dict[str, Any]]:
    """
    Находит и получает информацию о процессе Ollama
    
    Returns:
        Словарь с информацией об Ollama или None если не найден
    """
    if not PSUTIL_AVAILABLE:
        return None
    
    try:
        # Ищем процесс ollama runner (это процесс, который выполняет модель)
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if cmdline and 'ollama' in ' '.join(cmdline).lower() and 'runner' in ' '.join(cmdline).lower():
                    # Нашли Ollama runner
                    cpu_percent = proc.cpu_percent(interval=0.1)
                    memory_info = proc.memory_info()
                    memory_mb = memory_info.rss / 1024 / 1024
                    
                    # Извлекаем имя модели из cmdline
                    model_name = "unknown"
                    for part in cmdline:
                        if 'sha256' in part and 'blobs' in part:
                            # Это путь к модели, берём название из предыдущих частей
                            model_name = "qwen2.5:7b"  # По умолчанию
                            break
                    
                    return {
                        'pid': proc.pid,
                        'cpu_percent': cpu_percent,
                        'memory_mb': memory_mb,
                        'model': model_name
                    }
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        return None
    except Exception:
        return None


async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /check - проверка текущего состояния обработки"""
    config: BotConfig = context.bot_data.get('config', BotConfig())
    queue: ProcessQueue = context.bot_data.get('process_queue', ProcessQueue())
    user = update.effective_user
    
    # Получаем пользовательскую папку
    user_folder = get_user_folder(user, config.users_dir)
    
    if not user_folder.exists() or not list(user_folder.iterdir()):
        await update.message.reply_text(
            f"📁 Ваша папка пуста\n\n"
            f"Отправьте ссылку или медиафайл для начала работы!"
        )
        return
    
    # Получаем статус пользователя в очередях
    transcribe_status = queue.get_transcribe_status(user.id)
    ai_status = queue.get_ai_status(user.id)
    
    # Сканируем папки ТОЛЬКО текущего пользователя
    folders = sorted(
        [d for d in user_folder.iterdir() if d.is_dir()],
        key=lambda x: x.stat().st_mtime,
        reverse=True
    )
    
    # Расширения только для ВИДЕО/АУДИО (фото не требуют транскрибации)
    video_audio_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.mp3', '.m4a', '.wav', '.flac', '.ogg']
    
    # Статистика для транскрибации
    total_folders = len(folders)
    folders_without_media = 0
    folders_with_media = 0
    folders_transcribed = 0
    folders_need_transcribe = 0
    
    # Статистика для AI
    folders_ready_for_ai = 0
    folders_need_ai = 0
    folders_complete = 0
    
    # Сканируем все папки
    for folder in folders:
        video_audio_files = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in video_audio_extensions]
        has_transcript = (folder / "transcript.md").exists()
        has_description = (folder / "description.md").exists()
        has_analysis = (folder / "Knowledge.md").exists()
        
        # Статистика транскрибации
        if video_audio_files:
            folders_with_media += 1
            if has_transcript:
                folders_transcribed += 1
            else:
                folders_need_transcribe += 1
        else:
            folders_without_media += 1
        
        # Статистика AI
        if has_analysis:
            folders_complete += 1
        else:
            # Готово к AI если: (видео+транскрипт) ИЛИ (текст без видео)
            if video_audio_files and has_transcript:
                folders_ready_for_ai += 1
                folders_need_ai += 1
            elif not video_audio_files and has_description:
                folders_ready_for_ai += 1
                folders_need_ai += 1
    
    # ============================================================================
    # БЛОК 1: ТРАНСКРИБАЦИЯ
    # ============================================================================
    report = "📊 **СТАТУС СИСТЕМЫ**\n\n"
    report += "=" * 40 + "\n"
    report += "🎤 **МОДУЛЬ 2: ТРАНСКРИБАЦИЯ**\n"
    report += "=" * 40 + "\n\n"
    
    report += f"📂 Всего папок: **{total_folders}**\n"
    report += f"   • Без видео/аудио: {folders_without_media}\n"
    report += f"   • С видео/аудио: {folders_with_media}\n"
    report += f"   • Уже транскрибировано: {folders_transcribed}\n"
    report += f"   • **Требуют транскрибации: {folders_need_transcribe}**\n\n"
    
    # Статус пользователя в очереди транскрибации
    if transcribe_status['status'] == 'running':
        report += "⚙️ **Статус обработки:** ВЫПОЛНЯЕТСЯ\n"
        report += f"   • PID: {transcribe_status['pid']}\n"
    elif transcribe_status['status'] == 'queued':
        report += f"⏳ **Статус обработки:** В ОЧЕРЕДИ\n"
        report += f"   • Позиция: {transcribe_status['position']} из {transcribe_status['total']}\n"
    else:
        report += "⏸ **Статус обработки:** НЕ ЗАПУЩЕНО\n"
        if folders_need_transcribe > 0:
            report += f"\n💡 Используйте /transcribe для обработки {folders_need_transcribe} папок\n"
    
    # Глобальный статус транскрибации
    if queue.transcribe_running:
        running_user = queue.transcribe_running[1]
        report += f"\n📌 Сейчас обрабатывается: @{running_user}\n"
    if len(queue.transcribe_queue) > 0:
        report += f"📋 В очереди: {len(queue.transcribe_queue)} пользователей\n"
    
    # ============================================================================
    # БЛОК 2: AI АНАЛИЗ
    # ============================================================================
    report += "\n" + "=" * 40 + "\n"
    report += "🤖 **МОДУЛЬ 3: AI АНАЛИЗ**\n"
    report += "=" * 40 + "\n\n"
    
    report += f"📂 Всего папок: **{total_folders}**\n"
    report += f"   • Готовы к анализу: {folders_ready_for_ai}\n"
    report += f"   • **Требуют AI анализа: {folders_need_ai}**\n"
    report += f"   • Полностью обработано: {folders_complete}\n\n"
    
    # Статус пользователя в очереди AI
    if ai_status['status'] == 'running':
        report += "⚙️ **Статус обработки:** ВЫПОЛНЯЕТСЯ\n"
        report += f"   • PID: {ai_status['pid']}\n"
    elif ai_status['status'] == 'queued':
        report += f"⏳ **Статус обработки:** В ОЧЕРЕДИ\n"
        report += f"   • Позиция: {ai_status['position']} из {ai_status['total']}\n"
    else:
        report += "⏸ **Статус обработки:** НЕ ЗАПУЩЕНО\n"
        if folders_need_ai > 0:
            report += f"\n💡 Используйте /ai для обработки {folders_need_ai} папок\n"
    
    # Глобальный статус AI
    if queue.ai_running:
        running_user = queue.ai_running[1]
        report += f"\n📌 Сейчас обрабатывается: @{running_user}\n"
    if len(queue.ai_queue) > 0:
        report += f"📋 В очереди: {len(queue.ai_queue)} пользователей\n"
    
    # Добавляем информацию об Ollama если AI процесс запущен
    if queue.ai_running:
        ollama_info = get_ollama_info()
        if ollama_info:
            report += f"\n🧠 **Ollama LLM ({ollama_info['model']}):** АКТИВЕН\n"
            report += f"   • PID: {ollama_info['pid']}\n"
            report += f"   • CPU: {ollama_info['cpu_percent']:.1f}%\n"
            report += f"   • Память: {ollama_info['memory_mb']:.1f} МБ\n"
    else:
        report += "⏸ **Процесс обработки:** НЕ ЗАПУЩЕН\n"
        if folders_need_ai > 0:
            report += f"\n💡 Используйте /ai для обработки {folders_need_ai} папок\n"
    
    await update.message.reply_text(report, parse_mode='Markdown')


async def url_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /url - запрос URL"""
    await update.message.reply_text(
        "🔗 Отправьте мне URL:\n\n"
        "• YouTube (видео/shorts)\n"
        "• Instagram (посты/reels)\n\n"
        "Или просто отправьте ссылку без команды!"
    )


async def tags_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /tags - просмотр всех тегов в системе"""
    try:
        # Создаём TagManager для конкретного пользователя (папка пользователя)
        config: BotConfig = context.bot_data.get('config', BotConfig())
        user = update.effective_user
        user_folder = get_user_folder(user, config.users_dir)
        tags_file = user_folder / 'known_tags.json'
        tag_manager = TagManager(tags_file)
        
        # Получаем все теги
        all_tags = tag_manager.get_all_tags()
        
        if not all_tags:
            await update.message.reply_text(
                "🏷 **Теги**\n\n"
                "Пока нет ни одного тега в системе.\n"
                "Теги будут добавляться автоматически при AI-анализе контента."
            )
            return
        
        # Форматируем вывод: группируем по категориям или просто список
        tags_text = "🏷 **Все теги в системе**\n\n"
        tags_text += f"📊 Всего тегов: {len(all_tags)}\n\n"
        
        # Выводим теги в несколько колонок для компактности
        tags_per_row = 3
        rows = []
        for i in range(0, len(all_tags), tags_per_row):
            row_tags = all_tags[i:i+tags_per_row]
            rows.append(" • ".join(f"`{tag}`" for tag in row_tags))
        
        tags_text += "\n".join(rows)
        tags_text += "\n\n💡 Используйте /ai для автоматического тегирования контента"
        
        await update.message.reply_text(tags_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in tags_command: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Ошибка при загрузке тегов.\n"
            f"Детали: {str(e)[:200]}"
        )


async def get_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /get - получение файлов из папки"""
    config: BotConfig = context.bot_data.get('config', BotConfig())
    user = update.effective_user
    
    # Получаем папку пользователя
    user_folder = get_user_folder(user, config.users_dir)
    
    if not user_folder.exists() or not list(user_folder.iterdir()):
        await update.message.reply_text(
            "📁 <b>Ваша папка пуста</b>\n\n"
            "Отправьте ссылку или медиафайл для начала работы!",
            parse_mode='HTML'
        )
        return
    
    # Получаем список папок
    folders = sorted(
        [d for d in user_folder.iterdir() if d.is_dir()],
        key=lambda x: x.stat().st_mtime,
        reverse=True  # Новые папки первыми
    )
    
    if not folders:
        await update.message.reply_text(
            "📁 <b>Нет доступных папок</b>\n\n"
            "Папки пусты или отсутствуют.",
            parse_mode='HTML'
        )
        return
    
    # Сохраняем список папок в context для callback
    context.user_data['get_folders'] = [f.name for f in folders]
    
    # Показываем первую страницу (page=0)
    await show_folders_page(update.message, context, page=0, edit=False)


async def show_folders_page(message, context: ContextTypes.DEFAULT_TYPE, page: int = 0, edit: bool = False):
    """Показывает страницу с папками"""
    folder_names = context.user_data.get('get_folders', [])
    
    logger.info(f"show_folders_page called: page={page}, folders={len(folder_names)}, edit={edit}")
    
    if not folder_names:
        text = "📁 <b>Нет доступных папок</b>"
        if edit:
            await message.edit_text(text, parse_mode='HTML')
        else:
            await message.reply_text(text, parse_mode='HTML')
        return
    
    # Пагинация
    folders_per_page = 10
    total_pages = (len(folder_names) + folders_per_page - 1) // folders_per_page
    page = max(0, min(page, total_pages - 1))  # Ограничиваем диапазон
    
    start_idx = page * folders_per_page
    end_idx = min(start_idx + folders_per_page, len(folder_names))
    
    # Создаём inline-кнопки для папок на текущей странице
    keyboard = []
    
    for idx in range(start_idx, end_idx):
        folder_name = folder_names[idx]
        # Показываем читаемое имя (без префикса даты)
        display_name = re.sub(r'^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}_', '', folder_name)
        if len(display_name) > 50:
            display_name = display_name[:47] + "..."
        
        keyboard.append([
            InlineKeyboardButton(
                f"📂 {display_name}",
                callback_data=f"get:{idx}"
            )
        ])
    
    # Кнопки навигации
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton("◀️ Назад", callback_data=f"page:{page-1}")
        )
    if page < total_pages - 1:
        nav_buttons.append(
            InlineKeyboardButton("Вперёд ▶️", callback_data=f"page:{page+1}")
        )
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        f"📂 <b>Выберите папку для загрузки</b>\n\n"
        f"Всего папок: {len(folder_names)}\n"
        f"Страница: {page + 1} из {total_pages}\n"
        f"Показаны папки {start_idx + 1}-{end_idx}"
    )
    
    if edit:
        await message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        await message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')



async def get_folder_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик callback для отправки файлов из папки"""
    query = update.callback_query
    await query.answer()
    
    config: BotConfig = context.bot_data.get('config', BotConfig())
    user = update.effective_user
    user_folder = get_user_folder(user, config.users_dir)
    
    # Извлекаем данные из callback_data
    callback_data = query.data
    
    # Обработка навигации по страницам
    if callback_data.startswith("page:"):
        try:
            page_num = int(callback_data.replace("page:", ""))
            await show_folders_page(query.message, context, page=page_num, edit=True)
            await query.answer()
            return
        except ValueError:
            await query.answer("❌ Неверный номер страницы", show_alert=True)
            return
    
    # Обработка выбора папки
    if not callback_data.startswith("get:"):
        await query.answer("❌ Неверный формат", show_alert=True)
        return
    
    # Получаем индекс папки
    try:
        folder_idx = int(callback_data.replace("get:", ""))
    except ValueError:
        await query.answer("❌ Неверный индекс", show_alert=True)
        return
    
    # Получаем список папок из context
    folder_names = context.user_data.get('get_folders', [])
    
    if folder_idx < 0 or folder_idx >= len(folder_names):
        await query.edit_message_text(
            "❌ <b>Папка не найдена</b>\n\n"
            "Индекс вне диапазона. Попробуйте вызвать /get снова.",
            parse_mode='HTML'
        )
        return
    
    folder_name = folder_names[folder_idx]
    folder_path = user_folder / folder_name
    
    if not folder_path.exists() or not folder_path.is_dir():
        await query.edit_message_text(
            "❌ <b>Папка не найдена</b>\n\n"
            "Возможно, она была удалена.",
            parse_mode='HTML'
        )
        return
    
    # Собираем все файлы из папки
    all_files = sorted(folder_path.iterdir(), key=lambda x: x.name)
    files_to_send = [f for f in all_files if f.is_file()]
    
    if not files_to_send:
        await query.edit_message_text(
            f"📂 <b>{folder_name}</b>\n\n"
            "❌ Папка пуста - нет файлов для отправки.",
            parse_mode='HTML'
        )
        return
    
    # Показываем читаемое имя
    display_name = re.sub(r'^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}_', '', folder_name)
    
    # Обновляем сообщение
    await query.edit_message_text(
        f"📂 <b>{display_name}</b>\n\n"
        f"📤 Отправляю {len(files_to_send)} файлов...",
        parse_mode='HTML'
    )
    
    # Отправляем файлы
    sent_count = 0
    error_count = 0
    skipped_large = []  # Список слишком больших файлов
    
    # Лимит размера файла Telegram (50 MB)
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB в байтах
    
    for file_path in files_to_send:
        try:
            # Проверяем размер файла
            file_size = file_path.stat().st_size
            if file_size > MAX_FILE_SIZE:
                size_mb = file_size / (1024 * 1024)
                logger.warning(f"Skipping large file {file_path.name}: {size_mb:.1f} MB (limit: 50 MB)")
                skipped_large.append((file_path.name, size_mb))
                continue
            
            # Определяем тип файла по расширению
            file_ext = file_path.suffix.lower()
            
            # Отправляем индикатор действия в зависимости от типа файла
            if file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                await context.bot.send_chat_action(
                    chat_id=query.message.chat_id,
                    action='upload_photo'
                )
            elif file_ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm']:
                await context.bot.send_chat_action(
                    chat_id=query.message.chat_id,
                    action='upload_video'
                )
            elif file_ext in ['.mp3', '.m4a', '.wav', '.flac', '.ogg']:
                await context.bot.send_chat_action(
                    chat_id=query.message.chat_id,
                    action='upload_audio'
                )
            else:
                await context.bot.send_chat_action(
                    chat_id=query.message.chat_id,
                    action='upload_document'
                )
            
            # Читаем файл
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            # Отправляем в зависимости от типа
            if file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=file_data,
                    caption=f"📷 {file_path.name}"
                )
            elif file_ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm']:
                await context.bot.send_video(
                    chat_id=query.message.chat_id,
                    video=file_data,
                    caption=f"🎥 {file_path.name}"
                )
            elif file_ext in ['.mp3', '.m4a', '.wav', '.flac', '.ogg']:
                await context.bot.send_audio(
                    chat_id=query.message.chat_id,
                    audio=file_data,
                    caption=f"🎵 {file_path.name}"
                )
            elif file_ext in ['.md', '.txt']:
                # Текстовые файлы отправляем как документ с превью
                await context.bot.send_document(
                    chat_id=query.message.chat_id,
                    document=file_data,
                    filename=file_path.name,
                    caption=f"📄 {file_path.name}"
                )
            else:
                # Все остальные как документы
                await context.bot.send_document(
                    chat_id=query.message.chat_id,
                    document=file_data,
                    filename=file_path.name
                )
            
            sent_count += 1
            
        except Exception as e:
            logger.error(f"Error sending file {file_path.name}: {e}", exc_info=True)
            error_count += 1
            continue
    
    # Финальное сообщение
    result_text = f"✅ <b>Отправка завершена</b>\n\n"
    result_text += f"📂 Папка: <code>{display_name}</code>\n"
    result_text += f"📤 Отправлено: {sent_count} файлов\n"
    
    if len(skipped_large) > 0:
        result_text += f"⚠️ Пропущено (размер > 50 MB): {len(skipped_large)} файлов\n"
        for fname, fsize in skipped_large[:3]:  # Показываем первые 3
            result_text += f"   • {fname} ({fsize:.1f} MB)\n"
        if len(skipped_large) > 3:
            result_text += f"   • и ещё {len(skipped_large) - 3}...\n"
    
    if error_count > 0:
        result_text += f"❌ Ошибок: {error_count} файлов\n"
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=result_text,
        parse_mode='HTML'
    )


async def user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /user - информация о пользователе"""
    user = update.effective_user
    
    user_info = f"""
👤 **Информация о пользователе**

🆔 ID: `{user.id}`
📝 Username: @{user.username if user.username else 'не указан'}
👤 Имя: {user.first_name} {user.last_name if user.last_name else ''}
🤖 Бот: {'Да' if user.is_bot else 'Нет'}
"""
    await update.message.reply_text(user_info, parse_mode='Markdown')


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик неизвестных команд"""
    command = update.message.text.split()[0] if update.message.text else "/"
    await update.message.reply_text(
        f"❌ **Команда не найдена**\n\n"
        f"Команда `{command}` не существует.\n"
        f"Используйте /help для списка доступных команд.",
        parse_mode='Markdown'
    )


async def ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /ai - запуск Модуля 3 (AI анализ и тегирование)"""
    config: BotConfig = context.bot_data.get('config', BotConfig())
    
    if not config.users_dir.exists():
        await update.message.reply_text("📁 Папка users пуста")
        return
    
    # Проверяем, не запущен ли уже процесс
    if config.ai_pid.exists():
        try:
            with open(config.ai_pid) as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)
            await update.message.reply_text(
                f"⚠️ AI анализ уже запущен (PID: {pid})\n\n"
                f"Используйте /check для просмотра статуса"
            )
            return
        except (ProcessLookupError, ValueError, OSError):
            config.ai_pid.unlink(missing_ok=True)
    
    status_msg = await update.message.reply_text(
        "🤖 **Модуль 3: AI Анализ**\n\n"
        "Запускаю AI обработку в фоновом режиме...",
        parse_mode='Markdown'
    )
    
    try:
        # Запускаем module3 в отдельном процессе
        import subprocess
        
        # Очищаем лог-файл
        config.ai_log.write_text("")
        
        # Запускаем процесс
        process = subprocess.Popen(
            [sys.executable, "module3_analyze.py"],
            cwd=Path(__file__).parent,
            stdout=open(config.ai_log, 'w'),
            stderr=subprocess.STDOUT,
            start_new_session=True
        )
        
        # Сохраняем PID
        config.ai_pid.write_text(str(process.pid))
        
        await status_msg.edit_text(
            f"✅ **AI Анализ запущен!**\n\n"
            f"📝 PID: {process.pid}\n"
            f"📋 Логи: `{config.ai_log}`\n\n"
            f"Используйте /check для просмотра прогресса",
            parse_mode='Markdown'
        )
        # Запускаем таск, который будет следить за логом и оповещать чат о новых тегах
        async def tail_ai_log(log_path: Path, pid_file: Path, chat_id: int, bot_obj):
            import re
            last_pos = 0
            # Ждём появления файла
            while not log_path.exists():
                await asyncio.sleep(0.5)

            try:
                while True:
                    try:
                        with open(log_path, 'r', encoding='utf-8') as lf:
                            lf.seek(last_pos)
                            new = lf.read()
                            if new:
                                lines = new.splitlines()
                                for line in lines:
                                    m = re.search(r"Добавлено новых тегов:\s*(\d+)", line)
                                    if m:
                                        cnt = int(m.group(1))
                                        # Отправляем сообщение в чат
                                        try:
                                            await bot_obj.send_message(
                                                chat_id=chat_id,
                                                text=f"✨ Добавлено новых тегов: {cnt}"
                                            )
                                        except Exception:
                                            logger.exception("Failed to send tag notification")
                            last_pos = lf.tell()
                    except Exception:
                        logger.exception("Error reading AI log")

                    # Если PID-файл удалён, процесс, вероятно, завершился — выходим
                    if not pid_file.exists():
                        break

                    await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                return

        # Запустим таск наблюдения за логом (фоновой)
        try:
            chat_id = update.effective_chat.id
            asyncio.create_task(tail_ai_log(Path(config.ai_log), config.ai_pid, chat_id, context.bot))
        except Exception:
            logger.exception("Failed to start log tail task")
        
    except Exception as e:
        logger.error(f"AI processing start error: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Ошибка запуска: {str(e)[:200]}")


async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /ask - semantic search over user's knowledge base (RAG)."""
    config: BotConfig = context.bot_data.get('config', BotConfig())
    queue: ProcessQueue = context.bot_data.get('process_queue', ProcessQueue())

    # Extract query text
    query_text = None
    if context.args:
        query_text = " ".join(context.args).strip()
    else:
        # Try raw message (if user typed '/ask something')
        if update.message and update.message.text:
            parts = update.message.text.split(' ', 1)
            if len(parts) > 1:
                query_text = parts[1].strip()

    if not query_text:
        await update.message.reply_text("Использование: /ask <вопрос>")
        return

    user = update.effective_user
    username = user.username or str(user.id)
    position = queue.add_to_rag_queue(user.id, username)

    await update.message.reply_text(f"🔎 Ваш запрос поставлен в очередь (позиция {position}).")

    # If first in RAG queue and no ongoing transcribe/ai, process immediately
    if position == 1 and queue.rag_running is None and queue.transcribe_running is None:
        await update.message.reply_text("🔎 Начинаю поиск по вашей базе знаний...")
        # prepare user folder
        user_folder = get_user_folder(user, config.users_dir)

        try:
            from src.modules.module4_rag import RAGEngine
        except Exception as e:
            await update.message.reply_text(f"❌ RAG недоступен: {e}")
            # remove from rag queue
            queue.rag_queue = [item for item in queue.rag_queue if item[0] != user.id]
            return

        rag = RAGEngine(user_folder)

        loop = asyncio.get_event_loop()

        def run_query():
            try:
                return rag.query(query_text)
            except Exception as e:
                return {'answer': f'Ошибка выполнения RAG: {e}', 'sources': [], 'chunks': []}

        result = await loop.run_in_executor(None, run_query)

        # Format and send result
        answer = result.get('answer', '')
        sources = result.get('sources', [])

        msg = f"📘 Ответ:\n{answer}\n\n" + ("Источники: " + ", ".join(sources) if sources else "Источники: нет данных")

        await update.message.reply_text(msg)

    # remove from rag queue
    queue.rag_queue = [item for item in queue.rag_queue if item[0] != user.id]


async def mcp_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /mcp - issues or returns an API key for MCP access."""
    config: BotConfig = context.bot_data.get('config', BotConfig())
    user = update.effective_user
    user_id = user.id

    # ensure auth file exists and check for existing key
    from src.modules.mcp_auth import get_key_for_user, create_key_for_user

    existing = get_key_for_user(user_id, path=config.auth_file)
    if existing:
        token = existing
    else:
        token = create_key_for_user(user_id, path=config.auth_file)

    url = f"{config.public_mcp_url.rstrip('/')}" + f"/sse?api_key={token}"

    await update.message.reply_text(
        f"Ваш MCP API ключ:\n`{token}`\n\nПодключение (SSE):\n`{url}`",
        parse_mode='Markdown'
    )


# ============================================================================
# Обработка URL
# ============================================================================

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка URL YouTube/Instagram"""
    config: BotConfig = context.bot_data.get('config', BotConfig())
    url = update.message.text.strip()
    url_type = detect_url_type(url)
    
    if not url_type:
        return ConversationHandler.END  # Не URL, пропускаем
    
    # Получаем пользовательскую папку
    user = update.effective_user
    user_folder = get_user_folder(user, config.users_dir)
    
    # Отправляем сообщение о начале обработки
    status_msg = await update.message.reply_text(
        f"⏳ Начинаю обработку {url_type.upper()} ссылки...\n"
        f"Это может занять несколько минут."
    )
    
    try:
        # Настройки загрузки
        cookies_dir = Path('cookies')
        
        # Ищем Instagram cookies
        instagram_cookies = None
        if (cookies_dir / 'instagram_cookies.txt').exists():
            instagram_cookies = cookies_dir / 'instagram_cookies.txt'
        elif (cookies_dir / 'instagram.txt').exists():
            instagram_cookies = cookies_dir / 'instagram.txt'
        
        # Проверяем наличие YouTube cookies
        youtube_cookies_files = list(cookies_dir.glob('youtube_cookies*.txt'))
        youtube_cookies_dir = cookies_dir if youtube_cookies_files else None
        
        settings = DownloadSettings(
            download_video=True,
            download_comments=False,
            video_quality='best',
            max_comments=100,
            instagram_cookies=instagram_cookies,
            youtube_cookies_dir=youtube_cookies_dir
        )
        
        # Создаём роутер
        router = ContentRouter(settings)
        
        # Устанавливаем output_dir для всех downloaders в пользовательскую папку
        for downloader in router.downloaders:
            downloader.output_dir = user_folder
        
        # Скачиваем контент
        await status_msg.edit_text("📥 Скачиваю контент...")
        
        # Запускаем в отдельном потоке (синхронный код)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, 
            lambda: router.download(url)
        )
        
        if not result or not result.folder_path:
            await status_msg.edit_text("❌ Не удалось скачать контент")
            return ConversationHandler.END
        
        output_dir = Path(result.folder_path)
        
        # Переименовываем папку во временную (внутри пользовательской папки)
        temp_folder_name = f"temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        temp_output_dir = user_folder / temp_folder_name
        output_dir.rename(temp_output_dir)
        output_dir = temp_output_dir
        
        # Сохраняем временную папку в контексте
        context.user_data['temp_folder'] = str(output_dir)
        context.user_data['content_type'] = url_type
        
        # Проверяем наличие комментариев
        if result.comment_count and result.comment_count > 0:
            # Сохраняем контекст для обработки ответа
            context.user_data['pending_comments'] = {
                'url': url,
                'folder_path': str(output_dir),
                'count': result.comment_count,
                'content_type': url_type
            }
            
            # Клавиатура для вопроса
            keyboard = [
                [
                    InlineKeyboardButton("Да", callback_data="download_comments_yes"),
                    InlineKeyboardButton("Нет", callback_data="download_comments_no")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await status_msg.edit_text(
                f"✅ **Контент скачан!**\n\n"
                f"Найдено комментариев: **{result.comment_count}**\n"
                f"Скачать их?",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            return WAITING_COMMENTS_CONFIRMATION

        # Если комментариев нет или они 0, переходим сразу к названию
        files_list = [f.name for f in output_dir.iterdir() if f.is_file()]
        
        success_text = f"""
        ✅ **Контент скачан!**

        📁 Файлы:
        {chr(10).join('• ' + f for f in files_list[:10])}
        {'...' if len(files_list) > 10 else ''}

        📝 **Как озаглавим эту информацию?**
        Отправьте название (или /skip для создания автоматического названия)
        """
        await status_msg.edit_text(success_text, parse_mode='Markdown')

        return WAITING_TITLE
        
    except Exception as e:
        logger.error(f"Error processing URL: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Ошибка: {str(e)[:200]}")
        return ConversationHandler.END


# ============================================================================
# Обработка медиа файлов
# ============================================================================


async def handle_comments_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка подтверждения скачивания комментариев"""
    query = update.callback_query
    await query.answer()
    
    config: BotConfig = context.bot_data.get('config', BotConfig())
    data = context.user_data.get('pending_comments', {})
    
    if not data:
        await query.edit_message_text("⚠️ Данные устарели")
        return ConversationHandler.END
        
    url = data['url']
    folder_path = Path(data['folder_path'])
    
    if query.data == "download_comments_yes":
        await query.edit_message_text(f"💬 Скачиваю {data['count']} комментариев...")
        
        try:
            # Настройки для скачивания комментариев
            cookies_dir = Path('cookies')
            # Ищем cookies (копируем логику из handle_url)
            instagram_cookies = None
            if (cookies_dir / 'instagram_cookies.txt').exists():
                instagram_cookies = cookies_dir / 'instagram_cookies.txt'
            elif (cookies_dir / 'instagram.txt').exists():
                instagram_cookies = cookies_dir / 'instagram.txt'
            
            youtube_cookies_files = list(cookies_dir.glob('youtube_cookies*.txt'))
            youtube_cookies_dir = cookies_dir if youtube_cookies_files else None
            
            settings = DownloadSettings(
                download_video=False,
                download_comments=True,
                max_comments=100,
                instagram_cookies=instagram_cookies,
                youtube_cookies_dir=youtube_cookies_dir
            )
            
            router = ContentRouter(settings)
            
            # Устанавливаем output_dir
            for downloader in router.downloaders:
                downloader.output_dir = folder_path.parent
                
            # Запускаем скачивание
            loop = asyncio.get_event_loop()
            comments_path = await loop.run_in_executor(
                None,
                lambda: router.download_comments(url, folder_path)
            )
            
            if comments_path:
                await query.edit_message_text(f"✅ Комментарии скачаны!")
            else:
                await query.edit_message_text(f"⚠️ Не удалось скачать комментарии")
                
        except Exception as e:
            logger.error(f"Error downloading comments: {e}", exc_info=True)
            await query.edit_message_text(f"⚠️ Ошибка при скачивании комментариев: {e}")
            
    elif query.data == "download_comments_no":
        await query.edit_message_text("⏩ Пропускаем комментарии")
    
    # Показываем финальный отчет и просим название
    files_list = [f.name for f in folder_path.iterdir() if f.is_file()]
    
    success_text = f"""
    ✅ **Контент готов!**

    📁 Файлы:
    {chr(10).join('• ' + f for f in files_list[:10])}
    {'...' if len(files_list) > 10 else ''}

    📝 **Как озаглавим эту информацию?**
    Отправьте название (или /skip для создания автоматического названия)
    """
    
    # Отправляем новое сообщение
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=success_text,
        parse_mode='Markdown'
    )
    
    return WAITING_TITLE


async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка фото/видео от пользователя"""
    config: BotConfig = context.bot_data.get('config', BotConfig())
    
    # Определяем тип медиа
    if update.message.photo:
        # Берём фото максимального разрешения
        photo = update.message.photo[-1]
        file_id = photo.file_id
        media_type = "photo"
        file_ext = ".jpg"
    elif update.message.video:
        file_id = update.message.video.file_id
        media_type = "video"
        file_ext = ".mp4"
    elif update.message.document:
        doc = update.message.document
        file_id = doc.file_id
        media_type = "document"
        # Определяем расширение
        if doc.file_name:
            file_ext = Path(doc.file_name).suffix or ".bin"
        else:
            file_ext = ".bin"
    else:
        return ConversationHandler.END
    
    # Получаем пользовательскую папку
    user = update.effective_user
    user_folder = get_user_folder(user, config.users_dir)
    
    # Создаём папку внутри пользовательской папки
    folder_name = create_folder_name(f"telegram_{media_type}")
    output_dir = user_folder / folder_name
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Скачиваем файл
    status_msg = await update.message.reply_text("📥 Скачиваю файл...")
    
    try:
        file = await context.bot.get_file(file_id)
        file_path = output_dir / f"media{file_ext}"
        await file.download_to_drive(file_path)
        
        # Сохраняем caption если есть
        if update.message.caption:
            caption_path = output_dir / "caption.md"
            with open(caption_path, 'w', encoding='utf-8') as f:
                f.write(f"# Caption\n\n{update.message.caption}")
        
        # Сохраняем информацию для описания
        context.user_data['pending_media'] = {
            'output_dir': str(output_dir),
            'file_path': str(file_path),
            'media_type': media_type,
        }
        
        # Если это видео, попросим описать материал (название/описание)
        if media_type == "video":
            await status_msg.edit_text(
                f"✅ Файл сохранён!\n\n"
                f"📂 Папка: `{folder_name}`\n\n"
                f"📝 **О чем этот материал?**\n\n"
                f"Опиши содержание в нескольких словах - это поможет организовать контент.\n\n"
                f"💡 Примеры:\n"
                f"• Лекция о нейросетях\n"
                f"• Рецепт пасты карбонара\n"
                f"• Заметки с митинга\n\n"
                f"Или отправь /skip чтобы пропустить",
                parse_mode='Markdown'
            )
        else:
            await status_msg.edit_text(
                f"✅ Файл сохранён!\n\n"
                f"📂 Папка: `{folder_name}`\n\n"
                f"📝 **О чем этот материал?**\n\n"
                f"Расскажи в нескольких словах - это поможет организовать контент.\n\n"
                f"💡 Примеры:\n"
                f"• Лекция о нейросетях\n"
                f"• Рецепт пасты карбонара\n"
                f"• Заметки с митинга\n\n"
                f"Или отправь /skip чтобы пропустить",
                parse_mode='Markdown'
            )
        
        return WAITING_DESCRIPTION
        
    except Exception as e:
        logger.error(f"Error downloading media: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Ошибка загрузки: {str(e)[:200]}")
        return ConversationHandler.END


async def handle_transcribe_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка callback кнопки транскрибации"""
    query = update.callback_query
    await query.answer()
    
    config: BotConfig = context.bot_data.get('config', BotConfig())
    pending = context.user_data.get('pending_media', {})
    
    if query.data == "transcribe" and pending.get('file_path'):
        await query.edit_message_text("🎤 Транскрибирую видео...\nЭто может занять несколько минут.")
        
        try:
            file_path = Path(pending['file_path'])
            output_dir = Path(pending['output_dir'])
            
            # Транскрибируем
            ears = LocalEars(
                model_size=config.whisper_model,
                num_threads=config.whisper_threads
            )
            
            loop = asyncio.get_event_loop()
            transcript_result = await loop.run_in_executor(
                None,
                lambda: ears.transcribe(file_path)
            )
            
            if transcript_result:
                # Сохраняем
                transcript_path = output_dir / "transcript.md"
                with open(transcript_path, 'w', encoding='utf-8') as f:
                    f.write(f"# Транскрипция\n\n")
                    f.write(f"**Язык:** {transcript_result.language}\n")
                    f.write(f"**Длительность:** {transcript_result.duration:.1f} сек\n\n")
                    f.write("## С таймкодами\n\n")
                    f.write(transcript_result.timed_transcript)
                    f.write("\n\n## Полный текст\n\n")
                    f.write(transcript_result.full_text)
                
                await query.edit_message_text(
                    f"✅ Транскрипция готова!\n\n"
                    f"📂 Папка: `{output_dir.name}`\n\n"
                    f"📝 **О чем это видео?**\n\n"
                    f"Опиши содержание в нескольких словах.\n\n"
                    f"💡 Например: _Лекция о Python_ или _Обзор нового гаджета_\n\n"
                    f"Или отправь /skip",
                    parse_mode='Markdown'
                )
            else:
                await query.edit_message_text(
                    "⚠️ Не удалось транскрибировать\n\n"
                    "📝 **О чем это видео?**\n\n"
                    "Опиши содержание в нескольких словах или отправь /skip",
                    parse_mode='Markdown'
                )
                
        except Exception as e:
            logger.error(f"Transcription error: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Ошибка транскрибации: {str(e)[:100]}\n\n"
                "📝 Опиши содержание видео (или /skip)",
                parse_mode='Markdown'
            )
    
    elif query.data == "skip_transcribe":
        await query.edit_message_text(
            "⏭ Транскрибация пропущена\n\n"
            "📝 **О чем этот материал?**\n\n"
            "Опиши содержание в нескольких словах или отправь /skip",
            parse_mode='Markdown'
        )
    
    return WAITING_DESCRIPTION


async def handle_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение описания от пользователя"""
    pending = context.user_data.get('pending_media', {})
    
    if not pending:
        await update.message.reply_text("⚠️ Нет ожидающего файла")
        return ConversationHandler.END
    
    output_dir = Path(pending['output_dir'])
    description = update.message.text
    
    # Сохраняем описание
    desc_path = output_dir / "description.md"
    with open(desc_path, 'w', encoding='utf-8') as f:
        f.write(f"# Описание\n\n{description}")
    
    # Переименовываем папку по описанию
    try:
        from datetime import datetime
        
        # Извлекаем компоненты из текущего имени папки
        # Формат: {YYYY-MM-DD}_{HH-MM}_{Platform}_{SlugTitle}
        old_name = output_dir.name
        parts = old_name.split('_', 3)  # Разделяем на 4 части максимум
        
        if len(parts) >= 3:
            date_part = parts[0]      # YYYY-MM-DD
            time_part = parts[1]      # HH-MM
            platform = parts[2]       # telegram/temp/etc
            
            # Очищаем описание для использования в имени
            clean_desc = sanitize_filename(description, max_length=50)
            
            # Формируем новое имя папки
            new_folder_name = f"{date_part}_{time_part}_{platform}_{clean_desc}"
            new_output_dir = output_dir.parent / new_folder_name
            
            # Переименовываем, если новое имя отличается
            if new_output_dir != output_dir:
                output_dir.rename(new_output_dir)
                output_dir = new_output_dir
                
                await update.message.reply_text(
                    f"✅ Описание сохранено и папка переименована!\n\n"
                    f"📂 Новое имя: `{new_folder_name}`",
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(
                    f"✅ Описание сохранено!\n\n"
                    f"📂 Папка: `{output_dir.name}`",
                    parse_mode='Markdown'
                )
        else:
            # Если формат папки не распознан, просто сохраняем описание
            await update.message.reply_text(
                f"✅ Описание сохранено!\n\n"
                f"📂 Папка: `{output_dir.name}`",
                parse_mode='Markdown'
            )
    
    except Exception as e:
        logger.error(f"Error renaming folder: {e}", exc_info=True)
        # Даже если переименование не удалось, описание уже сохранено
        await update.message.reply_text(
            f"✅ Описание сохранено!\n\n"
            f"📂 Папка: `{output_dir.name}`\n\n"
            f"⚠️ Не удалось переименовать папку: {str(e)[:100]}",
            parse_mode='Markdown'
        )
    
    # Очищаем состояние
    context.user_data.pop('pending_media', None)
    
    return ConversationHandler.END


async def skip_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Пропуск описания"""
    pending = context.user_data.get('pending_media', {})
    
    if pending:
        output_dir = Path(pending['output_dir'])
        await update.message.reply_text(
            f"⏭ Описание пропущено\n\n"
            f"📂 Папка: `{output_dir.name}`",
            parse_mode='Markdown'
        )
    
    context.user_data.pop('pending_media', None)
    return ConversationHandler.END


# ============================================================================
# Обработка текста
# ============================================================================

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка текстовых сообщений (не URL)"""
    config: BotConfig = context.bot_data.get('config', BotConfig())
    text = update.message.text.strip()
    
    # Игнорируем команды (начинаются с "/")
    if text.startswith('/'):
        return ConversationHandler.END
    
    # Проверяем, не URL ли это
    if detect_url_type(text):
        return await handle_url(update, context)
    
    # Получаем пользовательскую папку
    user = update.effective_user
    user_folder = get_user_folder(user, config.users_dir)
    
    # Создаём временную папку для заметки (внутри пользовательской папки)
    temp_folder_name = f"temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    output_dir = user_folder / temp_folder_name
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Сохраняем текст
    desc_path = output_dir / "description.md"
    with open(desc_path, 'w', encoding='utf-8') as f:
        f.write(f"# Заметка\n\n")
        f.write(f"**Дата:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write(text)
    
    # Сохраняем временную папку в контексте
    context.user_data['temp_folder'] = str(output_dir)
    context.user_data['content_type'] = 'note'
    
    await update.message.reply_text(
        f"📝 Заметка сохранена!\n\n"
        f"**Как озаглавим эту информацию?**\n"
        f"Отправьте название (или /skip для автоматического)"
    )
    
    return WAITING_TITLE


# ============================================================================
# Обработка названия
# ============================================================================

async def handle_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение названия от пользователя и переименование папки"""
    config: BotConfig = context.bot_data.get('config', BotConfig())
    title = update.message.text.strip()
    
    temp_folder = context.user_data.get('temp_folder')
    content_type = context.user_data.get('content_type', 'content')
    
    if not temp_folder:
        await update.message.reply_text("❌ Временная папка не найдена")
        return ConversationHandler.END
    
    temp_dir = Path(temp_folder)
    
    if not temp_dir.exists():
        await update.message.reply_text("❌ Временная папка не существует")
        return ConversationHandler.END
    
    try:
        # Создаём безопасное имя файла из названия
        safe_title = sanitize_filename(title, max_length=60)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Формируем новое имя папки
        new_folder_name = f"{content_type}_{safe_title}_{timestamp}"
        # Получаем user_folder (users/{user}/downloads)
        user_folder = get_user_folder(update.effective_user, config.users_dir)
        new_dir = user_folder / new_folder_name
        
        # Переименовываем папку
        temp_dir.rename(new_dir)

        # Сохраняем путь к последней сохранённой папке (показывается через /show)
        context.user_data['last_saved_folder'] = str(new_dir)

        # Очищаем временный контекст (но оставляем last_saved_folder)
        context.user_data.pop('temp_folder', None)
        context.user_data.pop('content_type', None)

        await update.message.reply_text(
            f"✅ **Готово!**\n\n"
            f"📂 Папка: `{new_folder_name}`\n\n"
            f"Для отправки сохранённого материала в эту переписку используйте команду /show",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error renaming folder: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Ошибка переименования: {str(e)[:200]}")
    
    return ConversationHandler.END


async def show_files(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отправка скачанных файлов в чат для предпросмотра"""
    temp_folder = context.user_data.get('temp_folder')
    
    if not temp_folder:
        await update.message.reply_text("❌ Временная папка не найдена")
        return WAITING_TITLE
    
    temp_dir = Path(temp_folder)
    
    if not temp_dir.exists():
        await update.message.reply_text("❌ Временная папка не существует")
        return WAITING_TITLE
    
    try:
        # Находим медиа файлы (изображения и видео)
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
        video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}
        audio_extensions = {'.mp3', '.wav', '.ogg', '.m4a'}
        
        media_files = []
        for file in temp_dir.iterdir():
            if file.is_file() and not file.name.startswith('.'):
                ext = file.suffix.lower()
                if ext in image_extensions or ext in video_extensions or ext in audio_extensions:
                    media_files.append(file)
        
        if not media_files:
            await update.message.reply_text(
                "📄 В этой папке нет медиа-файлов для предпросмотра.\n\n"
                "📝 Как озаглавим эту информацию?\n"
                "Отправьте название (или /skip для автоматического)"
            )
            return WAITING_TITLE
        
        # Отправляем файлы
        await update.message.reply_text(f"📤 Отправляю {len(media_files)} файл(ов)...")
        
        for file in media_files[:10]:  # Ограничение 10 файлов за раз
            try:
                ext = file.suffix.lower()
                
                if ext in image_extensions:
                    with open(file, 'rb') as f:
                        await update.message.reply_photo(
                            photo=f,
                            caption=f"🖼️ {file.name}"
                        )
                elif ext in video_extensions:
                    with open(file, 'rb') as f:
                        await update.message.reply_video(
                            video=f,
                            caption=f"🎬 {file.name}"
                        )
                elif ext in audio_extensions:
                    with open(file, 'rb') as f:
                        await update.message.reply_audio(
                            audio=f,
                            caption=f"🎵 {file.name}"
                        )
                        
            except Exception as e:
                logger.error(f"Error sending file {file.name}: {e}")
                await update.message.reply_text(f"⚠️ Не удалось отправить {file.name}")
        
        if len(media_files) > 10:
            await update.message.reply_text(f"ℹ️ Показано первые 10 из {len(media_files)} файлов")
        
        await update.message.reply_text(
            "📝 Как озаглавим эту информацию?\n"
            "Отправьте название (или /skip для автоматического)"
        )
        
    except Exception as e:
        logger.error(f"Error showing files: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Ошибка: {str(e)[:200]}")
    
    return WAITING_TITLE


async def show_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /show — отправляет файлы только из последней успешно сохранённой папки"""
    user = update.effective_user

    last_folder = context.user_data.get('last_saved_folder')
    if not last_folder:
        await update.message.reply_text("ℹ️ Нет недавно сохранённой папки для отображения.")
        return

    temp_dir = Path(last_folder)
    if not temp_dir.exists() or not temp_dir.is_dir():
        await update.message.reply_text("❌ Папка не найдена или уже удалена.")
        return

    try:
        # Находим медиа файлы
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
        video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}
        audio_extensions = {'.mp3', '.wav', '.ogg', '.m4a'}

        media_files = []
        for file in temp_dir.iterdir():
            if file.is_file() and not file.name.startswith('.'):
                ext = file.suffix.lower()
                if ext in image_extensions or ext in video_extensions or ext in audio_extensions:
                    media_files.append(file)

        if not media_files:
            await update.message.reply_text("📄 В папке нет медиа-файлов для отправки.")
            return

        await update.message.reply_text(f"📤 Отправляю {len(media_files)} файл(ов) из `{temp_dir.name}`...", parse_mode='Markdown')

        for file in media_files[:10]:
            try:
                ext = file.suffix.lower()
                if ext in image_extensions:
                    with open(file, 'rb') as f:
                        await update.message.reply_photo(photo=f, caption=f"🖼️ {file.name}")
                elif ext in video_extensions:
                    with open(file, 'rb') as f:
                        await update.message.reply_video(video=f, caption=f"🎬 {file.name}")
                elif ext in audio_extensions:
                    with open(file, 'rb') as f:
                        await update.message.reply_audio(audio=f, caption=f"🎵 {file.name}")
            except Exception as e:
                logger.error(f"Error sending file {file.name}: {e}")
                await update.message.reply_text(f"⚠️ Не удалось отправить {file.name}")

        if len(media_files) > 10:
            await update.message.reply_text(f"ℹ️ Показано первые 10 из {len(media_files)} файлов")

    except Exception as e:
        logger.error(f"Error in /show: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Ошибка: {str(e)[:200]}")


async def skip_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Пропуск названия - использование автоматического"""
    config: BotConfig = context.bot_data.get('config', BotConfig())
    
    temp_folder = context.user_data.get('temp_folder')
    content_type = context.user_data.get('content_type', 'content')
    
    if not temp_folder:
        await update.message.reply_text("❌ Временная папка не найдена")
        return ConversationHandler.END
    
    temp_dir = Path(temp_folder)
    
    if not temp_dir.exists():
        await update.message.reply_text("❌ Временная папка не существует")
        return ConversationHandler.END
    
    try:
        # Используем временное имя или генерируем автоматическое
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_folder_name = f"{content_type}_auto_{timestamp}"
        # Получаем user_folder (users/{user}/downloads)
        user_folder = get_user_folder(update.effective_user, config.users_dir)
        new_dir = user_folder / new_folder_name
        
        # Переименовываем папку
        temp_dir.rename(new_dir)
        
        # Очищаем контекст
        context.user_data.pop('temp_folder', None)
        context.user_data.pop('content_type', None)
        
        await update.message.reply_text(
            f"⏭ **Автоматическое название**\n\n"
            f"📂 Папка: `{new_folder_name}`",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error renaming folder: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Ошибка переименования: {str(e)[:200]}")
    
    return ConversationHandler.END


# ============================================================================
# Главная функция
# ============================================================================

def main():
    """Запуск бота"""
    # Загружаем конфигурацию
    config = BotConfig.from_env()

    if not config.token:
        print("❌ Ошибка: TELEGRAM_BOT_TOKEN не установлен!")
        print("\nУстановите токен одним из способов:")
        print("1. export TELEGRAM_BOT_TOKEN='your_token'")
        print("2. Создайте .env файл с TELEGRAM_BOT_TOKEN=your_token")
        sys.exit(1)

    # Создаём папку users
    config.users_dir.mkdir(parents=True, exist_ok=True)

    print(f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 SecBrain Telegram Bot
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📁 Users Dir: {config.users_dir}
🎤 Whisper:   {config.whisper_model} ({config.whisper_threads} потоков)
👥 Users:     {'Все' if not config.allowed_users else config.allowed_users}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚀 Бот запущен! Нажмите Ctrl+C для остановки.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")

    # Создаём приложение
    application = Application.builder().token(config.token).build()

    # Сохраняем конфигурацию и инициализируем очередь
    application.bot_data['config'] = config
    application.bot_data['process_queue'] = ProcessQueue()

    # MCP server is no longer started automatically by the bot. Run it
    # separately in production or development to keep process control
    # explicit. Example command (run in project root):
    #
    #   uvicorn server_mcp:app --host <HOST> --port <PORT> --reload
    #
    # The bot will still read PUBLIC_MCP_URL from environment/.env and
    # report it in the /mcp command.
    print(
        f"ℹ️ MCP server is not started automatically. Start it manually:\n"
        f"    uvicorn server_mcp:app --host {config.mcp_host} --port {config.mcp_port}\n"
        f"Public SSE URL: {config.public_mcp_url.rstrip('/')}/sse"
    )

    # ConversationHandler для медиа с описанием
    media_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL, handle_media),
        ],
        states={
            WAITING_DESCRIPTION: [
                CallbackQueryHandler(handle_transcribe_callback),
                CommandHandler("skip", skip_description),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_description),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", skip_description),
        ],
    )

    # ConversationHandler для URL/текста с запросом названия
    content_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text),
        ],
        states={
            WAITING_COMMENTS_CONFIRMATION: [
                CallbackQueryHandler(handle_comments_confirmation),
            ],
            WAITING_TITLE: [
                CommandHandler("skip", skip_title),
                CommandHandler("show", show_files),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_title),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", skip_title),
        ],
    )

    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("check", check_command))
    application.add_handler(CommandHandler("transcribe", transcribe_command))
    application.add_handler(CommandHandler("url", url_command))
    application.add_handler(CommandHandler("show", show_command))
    application.add_handler(CommandHandler("ai", ai_command))
    application.add_handler(CommandHandler("ask", ask_command))
    application.add_handler(CommandHandler("mcp", mcp_command))
    application.add_handler(CommandHandler("tags", tags_command))
    application.add_handler(CommandHandler("get", get_command))
    application.add_handler(CommandHandler("user", user_command))

    # Обработчик callback для /get (папки и пагинация)
    application.add_handler(CallbackQueryHandler(get_folder_callback, pattern="^(get:|page:)"))

    application.add_handler(media_conv_handler)
    application.add_handler(content_conv_handler)

    # Обработчик неизвестных команд (должен быть последним)
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    # Запускаем бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
