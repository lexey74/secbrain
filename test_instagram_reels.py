#!/usr/bin/env python3
"""
Тест Instagram Reels Downloader
"""
import sys
from pathlib import Path

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from modules.instagram_reels_downloader import InstagramReelsDownloader
from modules.downloader_base import DownloadSettings


def test_instagram_reels():
    """Тест скачивания Instagram Reels"""
    
    print("=" * 70)
    print("🧪 ТЕСТ: Instagram Reels Downloader")
    print("=" * 70)
    print()
    
    # Проверка cookies
    print("🍪 Проверка cookies:")
    cookies_dir = Path('cookies')
    instagram_cookies = cookies_dir / 'instagram_cookies.txt'
    
    if not instagram_cookies.exists():
        instagram_cookies = cookies_dir / 'instagram.txt'
    
    if instagram_cookies.exists():
        print(f"   ✅ Instagram cookies найдены: {instagram_cookies}")
    else:
        print(f"   ❌ Instagram cookies не найдены")
        print(f"   Ожидаемый путь: {instagram_cookies}")
        return
    print()
    
    # Настройки
    settings = DownloadSettings(
        instagram_cookies=instagram_cookies
    )
    
    # Создаем downloader
    downloader = InstagramReelsDownloader(settings)
    
    # Тест can_handle
    print("🔍 Тест can_handle():")
    test_urls = [
        ("https://www.instagram.com/reel/ABC123/", True),
        ("https://www.instagram.com/p/XYZ789/", False),
    ]
    
    for url, expected in test_urls:
        result = downloader.can_handle(url)
        status = "✅" if result == expected else "❌"
        print(f"   {status} {url}: {result}")
    print()
    
    # Запрос URL
    print("📝 Введите Instagram Reel URL для теста:")
    print("   Пример: https://www.instagram.com/reel/ABC123/")
    print("   Или нажмите Enter для пропуска")
    print()
    
    url = input("URL: ").strip()
    
    if not url:
        print("⏭️  Тест пропущен")
        return
    
    if not downloader.can_handle(url):
        print(f"❌ URL не поддерживается: {url}")
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
        print(f"👤 Автор: {result.author}")
        print(f"❤️  Лайки: {result.likes:,}")
        print(f"💬 Комментарии: {result.comments_count}")
        print(f"👁️  Просмотры: {result.views:,}" if result.views else "")
        print(f"⏱️  Длительность: {result.duration}" if result.duration else "")
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
    test_instagram_reels()
