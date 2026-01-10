#!/usr/bin/env python3
"""
Тест безопасного скрапера комментариев
Проверяет работу Playwright и cookies
"""

import sys
from pathlib import Path

# Добавляем src в PATH
sys.path.insert(0, str(Path(__file__).parent / "src"))

from modules.safe_comments import SafeCommentsScraper
from rich.console import Console

console = Console()


def test_playwright_installation():
    """Проверка установки Playwright"""
    console.print("\n🔍 Проверка Playwright...", style="bold cyan")
    
    try:
        from playwright.sync_api import sync_playwright
        console.print("   ✅ Playwright установлен", style="green")
        return True
    except ImportError:
        console.print("   ❌ Playwright не установлен", style="red")
        console.print("   💡 Установите: pip install playwright && playwright install chromium")
        return False


def test_cookies():
    """Проверка наличия cookies"""
    console.print("\n🔍 Проверка cookies...", style="bold cyan")
    
    cookies_file = Path("instagram_cookies.json")
    
    if cookies_file.exists():
        import json
        try:
            with open(cookies_file) as f:
                cookies = json.load(f)
            console.print(f"   ✅ Cookies найдены ({len(cookies)} записей)", style="green")
            return True
        except:
            console.print("   ⚠️  Cookies файл поврежден", style="yellow")
            return False
    else:
        console.print("   ⚠️  Cookies не найдены", style="yellow")
        console.print("   💡 Создайте instagram_cookies.json (см. PLAYWRIGHT_GUIDE.md)")
        return False


def test_scraper(test_url: str = None):
    """Тест скрапера"""
    console.print("\n🎭 Тест скрапера...", style="bold cyan")
    
    if not test_url:
        console.print("   ⚠️  URL не указан, пропускаем", style="yellow")
        return False
    
    try:
        scraper = SafeCommentsScraper(
            cookies_file="instagram_cookies.json",
            headless=True
        )
        
        console.print(f"   🔗 Тестируем на: {test_url}")
        comments = scraper.scrape_comments(test_url, scroll_duration=10)
        
        if comments:
            console.print(f"   ✅ Получено {len(comments)} комментариев", style="green")
            console.print("\n   📝 Примеры:")
            for comment in comments[:3]:
                console.print(f"      {comment['user']}: {comment['text'][:50]}...")
            return True
        else:
            console.print("   ⚠️  Комментарии не найдены", style="yellow")
            return False
            
    except Exception as e:
        console.print(f"   ❌ Ошибка: {e}", style="red")
        return False


def main():
    """Главная функция"""
    console.print("╔═══════════════════════════════════════════╗", style="bold cyan")
    console.print("║  🧪 Тест безопасного скрапера комментариев ║", style="bold cyan")
    console.print("╚═══════════════════════════════════════════╝", style="bold cyan")
    
    # Тест 1: Playwright
    playwright_ok = test_playwright_installation()
    
    # Тест 2: Cookies
    cookies_ok = test_cookies()
    
    # Тест 3: Скрапер (опционально)
    if len(sys.argv) > 1:
        test_url = sys.argv[1]
        scraper_ok = test_scraper(test_url)
    else:
        console.print("\n💡 Для полного теста запустите:", style="cyan")
        console.print("   python test_playwright.py https://www.instagram.com/p/YOUR_POST_URL/")
        scraper_ok = None
    
    # Результат
    console.print("\n" + "=" * 50)
    console.print("📊 Результаты:", style="bold")
    console.print(f"   Playwright: {'✅' if playwright_ok else '❌'}")
    console.print(f"   Cookies: {'✅' if cookies_ok else '⚠️'}")
    if scraper_ok is not None:
        console.print(f"   Scraper: {'✅' if scraper_ok else '❌'}")
    console.print("=" * 50)
    
    if playwright_ok and cookies_ok:
        console.print("\n✨ Всё готово к использованию!", style="green bold")
    else:
        console.print("\n⚠️  Требуется настройка (см. PLAYWRIGHT_GUIDE.md)", style="yellow bold")


if __name__ == "__main__":
    main()
