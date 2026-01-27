import asyncio
import sys
import logging
from pathlib import Path
import subprocess
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from src.bot.config import BotConfig
from src.bot.services.process_queue import queue
from src.modules.local_ears import LocalEars

router = Router()
logger = logging.getLogger(__name__)

async def run_transcription(file_path: Path, output_dir: Path, config: BotConfig, message: types.Message):
    """Run transcription in executor"""
    status_msg = await message.answer("🎤 Транскрибирую видео...\nЭто может занять несколько минут.")
    
    try:
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
            transcript_path = output_dir / "transcript.md"
            with open(transcript_path, 'w', encoding='utf-8') as f:
                f.write(f"# Транскрипция\n\n")
                f.write(f"**Язык:** {transcript_result.language}\n")
                f.write(f"**Длительность:** {transcript_result.duration:.1f} сек\n\n")
                f.write("## С таймкодами\n\n")
                f.write(transcript_result.timed_transcript)
                f.write("\n\n## Полный текст\n\n")
                f.write(transcript_result.full_text)
            
            await status_msg.edit_text(
                f"✅ Транскрипция готова!\n\n"
                f"📂 Папка: `{output_dir.name}`\n"
                f"📝 **О чем это видео?**\n"
                f"Опиши содержание в нескольких словах."
            )
        else:
             await status_msg.edit_text("⚠️ Не удалось транскрибировать.")

    except Exception as e:
        logger.error(f"Transcription error: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Ошибка транскрибации: {str(e)[:100]}")
    finally:
        queue.finish_transcribe()


@router.message(Command("transcribe"))
async def cmd_transcribe(message: types.Message, state: FSMContext, config: BotConfig):
    """Handler for /transcribe"""
    # Simply pick the last downloaded file from user folder? 
    # Or rely on FSM state set by content handler.
    # For now, let's assume we look at the last folder in user dir.
    
    user_folder = config.users_dir / message.from_user.username / "downloads"
    # Find latest folder
    if not user_folder.exists():
        await message.reply("📂 Нет загруженных файлов.")
        return

    # Sort by time
    folders = sorted([f for f in user_folder.iterdir() if f.is_dir()], key=lambda x: x.stat().st_mtime, reverse=True)
    if not folders:
        await message.reply("📂 Нет папок с контентом.")
        return
        
    latest_folder = folders[0]
    # Find video file
    video_files = list(latest_folder.glob("*.mp4")) + list(latest_folder.glob("*.mp3")) + list(latest_folder.glob("*.m4a"))
    
    if not video_files:
        await message.reply(f"⚠️ В папке {latest_folder.name} нет медиа для транскрибации.")
        return
        
    target_file = video_files[0]
    
    if not queue.can_start_transcribe():
        pos = queue.add_to_transcribe_queue(message.from_user.id, message.from_user.username)
        await message.reply(f"⏳ Добавлен в очередь транскрибации (позиция {pos})")
        return

    queue.start_transcribe(message.from_user.id, message.from_user.username, 0)
    asyncio.create_task(run_transcription(target_file, latest_folder, config, message))


@router.message(Command("ai"))
async def cmd_ai(message: types.Message, config: BotConfig, bot: Bot):
    """Handler for /ai"""
    if config.ai_pid.exists():
        await message.reply("⚠️ AI анализ уже запущен.")
        return

    status_msg = await message.reply("🤖 Запускаю AI обработку...")
    
    try:
        # Run module3_analyze.py
        # Assuming it's in root
        cmd = [sys.executable, "module3_analyze.py"]
        
        config.ai_log.parent.mkdir(parents=True, exist_ok=True)
        config.ai_log.write_text("")
        
        process = subprocess.Popen(
            cmd,
            cwd=Path.cwd(),
            stdout=open(config.ai_log, 'w'),
            stderr=subprocess.STDOUT,
            start_new_session=True
        )
        
        config.ai_pid.write_text(str(process.pid))
        
        await status_msg.edit_text(
            f"✅ **AI Анализ запущен!**\n"
            f"📝 PID: {process.pid}\n"
            f"📋 Логи: `{config.ai_log}`"
        )
        
        # Log tailing task would go here (simplified for now)
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка запуска: {e}")

@router.message(Command("check"))
async def cmd_check(message: types.Message, config: BotConfig):
    """Handler for /check"""
    status_text = "📊 **Статус задач:**\n\n"
    
    # Check Transcribe
    t_status = queue.get_transcribe_status(message.from_user.id)
    status_text += f"🎤 Transcribe: {t_status['status']}\n"
    
    # Check AI
    if config.ai_pid.exists():
        status_text += f"🤖 AI: Running (PID file exists)\n"
    else:
        status_text += f"🤖 AI: Idle\n"
        
    await message.reply(status_text, parse_mode="Markdown")
