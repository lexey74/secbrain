#!/usr/bin/env python3
"""
Тест YouTube Shorts Downloader
"""
import sys
from pathlib import Path

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from modules.youtube_shorts_downloader import YouTubeShortsDownloader
from modules.downloader_base import DownloadSettings


def test_youtube_shorts():
    """Тест скачивания YouTube Shorts"""
    
    print("=" * 70)
    print("🧪 ТЕСТ: YouTube Shorts Downloader")
    print("=" * 70)
    print()
    
    # Проверка cookies
    print("🍪 Проверка cookies:")
    cookies_dir = Path('cookies')
    youtube_cookies = list(cookies_dir.glob('youtube_cookies*.txt'))
    
    if youtube_cookies:
        print(f"   ✅ YouTube cookies найдены: {len(youtube_cookies)} файлов")
        for cookie_file in youtube_cookies:
            print(f"      - {cookie_file.name}")
    else:
        print(f"   ⚠️  YouTube cookies не найдены (необязательно)")
    print()
    
    # Настройки
    settings = DownloadSettings(
        youtube_cookies_dir=cookies_dir if youtube_cookies else None
    )
    
    # Создаем downloader
    downloader = YouTubeShortsDownloader(settings)
    
    # Тест can_handle
    print("🔍 Тест can_handle():")
    test_urls = [
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", True),
        ("https://youtube.com/shorts/abc123", True),
        ("https://youtu.be/dQw4w9WgXcQ", False),  # Обычное видео
        ("https://www.youtube.com/watch?v=abc123", False),
    ]
    
    for url, expected in test_urls:
        result = downloader.can_handle(url)
        status = "✅" if result == expected else "❌"
        print(f"   {status} {url}: {result}")
    print()
    
    # Запрос URL
    print("📝 Введите YouTube Shorts URL для теста:")
    print("   Пример: https://www.youtube.com/shorts/dQw4w9WgXcQ")
    print("   Или нажмите Enter для пропуска")
    print()
    
    url = input("URL: ").strip()
    
    if not url:
        print("⏭️  Тест пропущен")
        return
    
    if not downloader.can_handle(url):
        print(f"❌ URL не поддерживается: {url}")
        print("   Это должен быть YouTube Shorts URL (/shorts/)")
        return
    
    # Скачивание
    print()
    print("⬇️  Начинаем скачивание...")
    print()
    
    try:
        result = downloader.download(url)
        
        print()
        print("=" * 70)
        print("✅ УСПЕШНО")
        print("=" * 70)
        print(f"📍 Источник: {result.source}")
        print(f"📌 Тип: {result.content_type}")
        print(f"🆔 ID: {result.content_id}")
        print(f"📂 Папка: {result.folder_path}")
        print(f"📺 Канал: {result.channel}" if hasattr(result, 'channel') and result.channel else "")
        print(f"👁️  Просмотры: {result.views:,}" if hasattr(result, 'views') and result.views else "")
        print(f"❤️  Лайки: {result.likes:,}" if hasattr(result, 'likes') and result.likes else "")
        print(f"⏱️  Длительность: {result.duration}" if hasattr(result, 'duration') and result.duration else "")
        print()
        
        print(f"📦 Файлы ({len(result.media_files)}):")
        for file in result.media_files:
            size_mb = file.stat().st_size / (1024 * 1024)
            print(f"   - {file.name} ({size_mb:.1f} MB)")
        print()
        
        if result.description_file:
            print(f"📄 Описание: {result.description_file}")
        
        if result.comments_file:
            print(f"💬 Комментарии: {result.comments_file}")
        
        print("=" * 70)
        
    except Exception as e:
        print()
        print("=" * 70)
        print("❌ ОШИБКА")
        print("=" * 70)
        print(f"Ошибка: {e}")
        print()
        import traceback
        traceback.print_exc()
        print("=" * 70)


if __name__ == "__main__":
    test_youtube_shorts()
