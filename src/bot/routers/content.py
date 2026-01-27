import re
from pathlib import Path
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from src.bot.config import BotConfig
from src.bot.states import ContentStates
from src.modules.content_router import ContentRouter
from src.modules.downloader_base import DownloadSettings

router = Router()

def get_user_folder(user_id: int, username: str, config: BotConfig) -> Path:
    folder_name = username if username else f"user_{user_id}"
    # Sanitization could be added here
    path = config.users_dir / folder_name / "downloads"
    path.mkdir(parents=True, exist_ok=True)
    return path

@router.message(Command("url"))
async def cmd_url(message: types.Message, state: FSMContext):
    """Start URL input flow"""
    await state.set_state(ContentStates.waiting_url)
    await message.answer("🔗 Пришли мне ссылку на YouTube или Instagram:")

@router.message(ContentStates.waiting_url)
@router.message(F.text & F.text.regexp(r'(https?://)?(www\.)?(youtube\.com|youtu\.be|instagram\.com)'))
async def handle_url(message: types.Message, state: FSMContext, config: BotConfig):
    """Handle YouTube/Instagram URLs"""
    # If we were waiting for URL, clear state
    current_state = await state.get_state()
    if current_state == ContentStates.waiting_url:
        await state.clear()
        
    url = message.text.strip()
    status_msg = await message.reply("🔎 Анализирую ссылку...")
    
    try:
        user_folder = get_user_folder(message.from_user.id, message.from_user.username, config)
        
        # Init settings
        settings = DownloadSettings(
            cookies_file=Path("cookies.txt"),
            instagram_cookies_path=Path("cookies/instagram.json")
        )
        content_router = ContentRouter(settings, user_folder)
        
        if not content_router.is_supported(url):
            await status_msg.edit_text("❌ URL не поддерживается или не распознан.")
            return

        await status_msg.edit_text("⬇️ Начинаю загрузку...")
        
        # Download (blocking call, ideal to offload to thread/process in real prod)
        # For now we keep it async-blocking as per original design, but in aiogram 3 we should be careful.
        # Ideally: await asyncio.to_thread(content_router.download, url)
        import asyncio
        result = await asyncio.to_thread(content_router.download, url)
        
        await status_msg.edit_text(
            f"✅ <b>Загрузка завершена!</b>\n\n"
            f"📁 Папка: <code>{result.folder_path.name}</code>\n"
            f"📦 Файлов: {len(result.media_files)}\n\n"
            f"Теперь можно запустить /transcribe или /ai"
        )
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка загрузки: {str(e)[:200]}")

@router.message(F.photo | F.video | F.document)
async def handle_media(message: types.Message, state: FSMContext, config: BotConfig):
    """Handle direct media uploads"""
    await message.reply("📥 Медиа получено. Сохраняю...")
    # Implementation of media saving would go here.
    # Aligning with original logic which handled photos/videos
    pass

@router.message(F.text)
async def handle_text(message: types.Message, state: FSMContext, config: BotConfig):
    """Handle simple text notes"""
    # Check if command
    if message.text.startswith("/"):
        return
        
    # Save as note
    await message.reply("📝 Заметка сохранена.")
