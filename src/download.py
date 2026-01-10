#!/usr/bin/env python3
"""
SecBrain Download Script
Скачивает контент из Instagram и подготавливает сырые данные для последующей AI обработки.
НЕ создаёт Note.md - только сохраняет медиа, caption.md, transcript.md, comments.md.
"""

import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

from config import Config
from modules.hybrid_grabber import HybridGrabber
from modules.local_ears import LocalEars

console = Console()


def print_banner():
    """Отображает баннер программы"""
    banner = """
    ╔═══════════════════════════════════════════╗
    ║   📥 SecBrain - Download & Prepare Data  ║
    ║     Instagram Content Downloader         ║
    ╚═══════════════════════════════════════════╝
    """
    console.print(Panel(banner, style="bold cyan"))


def save_raw_data(content, output_dir: Path):
    """
    Сохраняет сырые данные в структурированном виде
    
    Args:
        content: Объект InstagramContent с загруженными данными
        output_dir: Директория для сохранения
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Сохраняем caption
    if content.caption:
        caption_file = output_dir / "caption.md"
        caption_file.write_text(content.caption, encoding='utf-8')
        console.print(f"   ✅ Сохранён caption.md")
    
    # Сохраняем transcript
    if content.transcript:
        transcript_file = output_dir / "transcript.md"
        
        transcript_md = f"# Транскрипция видео\n\n"
        transcript_md += f"**Источник:** {content.url}\n"
        transcript_md += f"**Автор:** {content.author}\n"
        transcript_md += f"**Дата:** {content.date}\n\n"
        transcript_md += "---\n\n"
        transcript_md += "## С таймкодами\n\n"
        transcript_md += content.transcript + "\n\n"
        transcript_md += "---\n\n"
        transcript_md += "## Чистый текст\n\n"
        transcript_md += content.transcript_clean + "\n"
        
        transcript_file.write_text(transcript_md, encoding='utf-8')
        console.print(f"   ✅ Сохранён transcript.md")
    
    # Комментарии НЕ сохраняем здесь - только через Playwright


def safe_scrape_comments(url: str, output_dir: Path, config: Config) -> bool:
    """
    Безопасный скрапинг комментариев через Playwright
    
    Args:
        url: Instagram URL
        output_dir: Директория для сохранения
        config: Конфигурация
        
    Returns:
        True если успешно
    """
    try:
        from modules.safe_comments import SafeCommentsScraper
        
        console.print("\n🎭 Запуск безопасного скрапера комментариев...")
        console.print("   ⚠️  Это займет 15-30 секунд...")
        
        scraper = SafeCommentsScraper(
            cookies_file=str(Path(config.get('cookies_file', 'instagram_cookies.json'))),
            headless=config.get('headless_browser', True)
        )
        
        comments = scraper.scrape_comments(url, scroll_duration=15)
        
        if comments:
            # Сохраняем комментарии
            comments_file = output_dir / "comments.md"
            
            comments_md = f"# Комментарии\n\n"
            comments_md += f"**Пост:** {url}\n"
            comments_md += f"**Всего комментариев:** {len(comments)}\n\n"
            comments_md += "---\n\n"
            
            for i, comment in enumerate(comments, 1):
                comments_md += f"### Комментарий {i}\n\n"
                comments_md += f"**Автор:** {comment.get('user', 'Unknown')}\n"
                comments_md += f"**Лайков:** {comment.get('likes', 0)}\n\n"
                comments_md += f"{comment.get('text', '')}\n\n"
                comments_md += "---\n\n"
            
            comments_file.write_text(comments_md, encoding='utf-8')
            console.print(f"   ✅ Сохранены comments.md ({len(comments)} комментариев)")
            
            # Сохраняем сырые данные
            if config.get('save_raw_comments', False):
                scraper.save_raw_data(str(output_dir / "raw_comments.json"))
            
            return True
        else:
            console.print("   ⚠️  Комментарии не найдены", style="yellow")
            return False
            
    except ImportError:
        console.print("   ⚠️  Playwright не установлен. Используйте: pip install playwright && playwright install chromium", style="yellow")
        return False
    except Exception as e:
        console.print(f"   ❌ Ошибка скрапинга: {e}", style="red")
        return False


def download_content(url: str, config: Config, scrape_comments_safe: bool = False):
    """
    Скачивает контент и подготавливает сырые данные
    
    Args:
        url: Instagram URL
        config: Конфигурация
        
    Returns:
        Path к созданной директории или None при ошибке
    """
    console.print("\n" + "=" * 60)
    console.print(f"🚀 Обработка: {url}")
    console.print("=" * 60 + "\n")
    
    # Инициализация модулей
    grabber = HybridGrabber(
        output_dir=Path(config.temp_dir),
        cookies_file=Path(config.get('cookies_file', 'instagram_cookies.txt'))
    )
    ears = LocalEars(
        model_size=config.get('whisper_model', 'base'),
        device="cpu",
        num_threads=config.get('num_threads', 8),
        compute_type=config.get('whisper_compute_type', 'int8')
    )
    
    try:
        # 1. Скачивание контента через gallery-dl
        console.print("📥 Загрузка через gallery-dl...")
        content = grabber.grab(url)
        
        if not content:
            console.print("❌ Не удалось загрузить контент", style="red")
            return None
        
        console.print(f"✅ Загружено файлов: {len(content.media_paths)}")
        
        # 2. Транскрибация видео (если есть)
        video_files = [p for p in content.media_paths if p.suffix.lower() in ['.mp4', '.mov', '.avi', '.mkv']]
        if video_files:
            console.print("🎤 Транскрибация аудиодорожки...")
            console.print("   ⏳ Обработка...")
            
            for video_path in video_files:
                result = ears.transcribe(video_path)
                if result:
                    content.transcript = result.timed_transcript
                    content.transcript_clean = result.full_text
                    
                    # Подсчитываем количество сегментов
                    segments = len([line for line in result.timed_transcript.split('\n') if line.strip().startswith('[')])
                    console.print(f"   ✅ Транскрибация завершена ({segments} сегментов)")
                    break
            
            if not content.transcript:
                console.print("   ⚠️  Транскрибация не удалась", style="yellow")
        
        # 3. Создание директории для сохранения
        date_prefix = content.date.split()[0] if content.date else "unknown"
        author = content.author or "unknown"
        title = (content.caption[:30] if content.caption else "без_описания").replace(" ", "_")
        
        folder_name = f"{date_prefix}_{author}_{title}"
        # Очистка имени от недопустимых символов
        folder_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in folder_name)
        
        output_dir = Path(config.output_dir) / folder_name
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 4. Перемещение медиа-файлов
        console.print(f"📁 Перемещение файлов в: {folder_name}")
        for i, media_path in enumerate(content.media_paths, 1):
            if i == 1:
                new_name = f"media{media_path.suffix}"
            else:
                new_name = f"media_{i}{media_path.suffix}"
            
            dest_path = output_dir / new_name
            media_path.rename(dest_path)
            console.print(f"   ✅ {new_name}")
        
        # 5. Сохранение сырых данных
        console.print("💾 Сохранение сырых данных...")
        save_raw_data(content, output_dir)
        
        # 6. Опционально: Безопасный скрапинг комментариев через Playwright
        if scrape_comments_safe:
            safe_scrape_comments(url, output_dir, config)
        
        console.print("\n" + "=" * 60)
        console.print(f"✅ Данные подготовлены: {output_dir}")
        console.print("=" * 60 + "\n")
        
        return output_dir
        
    except Exception as e:
        console.print(f"❌ Ошибка: {e}", style="red")
        return None


def main():
    """Главная функция"""
    print_banner()
    
    # Загрузка конфигурации
    config = Config()
    
    console.print(f"📁 Output: {config.output_dir}")
    console.print(f"🎙️  Whisper Model: {config.whisper_model}")
    console.print(f"🔧 CPU Threads: {config.num_threads}\n")
    
    # Спрашиваем, нужен ли скрапинг комментариев через Playwright
    use_safe_scraper = Confirm.ask(
        "💬 Скачивать комментарии через Playwright?",
        default=False
    )
    
    if use_safe_scraper:
        console.print("✅ Комментарии будут скачаны через Playwright (безопасно)\n", style="green")
    else:
        console.print("⚠️  Комментарии НЕ будут скачаны\n", style="yellow")
    
    # Основной цикл
    while True:
        console.print("─" * 60)
        url = Prompt.ask(
            "Instagram URL (или 'quit' для выхода)",
            default=""
        )
        
        if url.lower() in ['quit', 'exit', 'q']:
            console.print("👋 До встречи!")
            break
        
        if not url or not url.startswith('http'):
            console.print("⚠️  Введите корректный URL", style="yellow")
            continue
        
        # Скачивание и подготовка данных
        output_dir = download_content(url, config, scrape_comments_safe=use_safe_scraper)
        
        if output_dir:
            console.print(f"✨ Данные готовы к обработке: {output_dir}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n👋 Прервано пользователем")
        sys.exit(0)
