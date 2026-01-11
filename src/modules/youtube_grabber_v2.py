"""
Production-Ready YouTube Grabber v2
Применены лучшие практики из youtube-dl и Hitomi-Downloader
"""
from pathlib import Path
from typing import Optional, List, Dict
from dataclasses import dataclass
import subprocess
import json
import re
import time
import random
from functools import wraps
from threading import Lock
import hashlib


# ============================================================================
# DECORATORS (взято из Hitomi-Downloader)
# ============================================================================

def rate_limit(calls: int = 1, period: float = 1.0):
    """
    Rate limiting декоратор
    
    Args:
        calls: Максимум вызовов
        period: Период в секундах
    
    Example:
        @rate_limit(calls=1, period=1.5)  # Максимум 1 запрос за 1.5 секунды
        def api_call():
            pass
    """
    def decorator(func):
        timestamps = []
        lock = Lock()
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            with lock:
                now = time.time()
                # Удаляем старые timestamps
                nonlocal timestamps
                timestamps = [t for t in timestamps if now - t < period]
                
                if len(timestamps) >= calls:
                    # Ждём до следующего слота
                    sleep_time = period - (now - timestamps[0])
                    if sleep_time > 0:
                        print(f"⏱️  Rate limit: пауза {sleep_time:.1f}с")
                        time.sleep(sleep_time)
                    timestamps = timestamps[1:]
                
                timestamps.append(time.time())
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


def smart_retry(max_attempts: int = 3, base_delay: float = 1.0, backoff: float = 2.0):
    """
    Retry с экспоненциальной задержкой + jitter
    
    Args:
        max_attempts: Максимум попыток
        base_delay: Базовая задержка (секунды)
        backoff: Множитель для экспоненциального роста
    
    Example:
        @smart_retry(max_attempts=4, base_delay=2.0)
        def unstable_function():
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    
                    # Экспоненциальная задержка: 1s, 2s, 4s, 8s...
                    delay = base_delay * (backoff ** attempt)
                    # Jitter: ±10% для избежания синхронизации
                    jitter = random.uniform(-delay * 0.1, delay * 0.1)
                    total_delay = delay + jitter
                    
                    print(f"🔄 Попытка {attempt + 1}/{max_attempts} не удалась: {str(e)[:100]}")
                    print(f"⏳ Повтор через {total_delay:.1f}с...")
                    time.sleep(total_delay)
        return wrapper
    return decorator


# ============================================================================
# YOUTUBE CLIENTS (взято из youtube-dl)
# ============================================================================

YOUTUBE_CLIENTS = {
    'web': {
        'name': 'WEB',
        'version': '2.20250111.00.00',
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'headers': {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
    },
    'android': {
        'name': 'ANDROID',
        'version': '19.09.36',
        'user_agent': 'com.google.android.youtube/19.09.36 (Linux; U; Android 13) gzip',
        'headers': {
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
        }
    },
    'ios': {
        'name': 'IOS',
        'version': '19.09.3',
        'user_agent': 'com.google.ios.youtube/19.09.3 (iPhone14,3; U; CPU iOS 15_6 like Mac OS X)',
        'headers': {
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
        }
    },
}


# ============================================================================
# COOKIE MANAGER
# ============================================================================

@dataclass
class CookieStats:
    """Статистика использования cookies"""
    file_path: Path
    usage_count: int = 0
    success_count: int = 0
    fail_count: int = 0
    last_used: Optional[float] = None
    blocked: bool = False
    
    @property
    def success_rate(self) -> float:
        if self.usage_count == 0:
            return 100.0
        return (self.success_count / self.usage_count) * 100
    
    @property
    def health_score(self) -> float:
        """Score: чем меньше, тем лучше"""
        return self.usage_count * 10 + self.fail_count * 100


class ImprovedCookieManager:
    """Улучшенный менеджер cookies с session handling"""
    
    def __init__(self, cookies_dir: Path = Path('cookies')):
        self.cookies_dir = cookies_dir
        self.cookies_dir.mkdir(exist_ok=True)
        self.stats: Dict[str, CookieStats] = {}
        self.lock = Lock()
    
    def add_cookies(self, cookie_file: Path) -> CookieStats:
        """Добавляет cookies файл в пул"""
        with self.lock:
            if cookie_file.name not in self.stats:
                self.stats[cookie_file.name] = CookieStats(file_path=cookie_file)
            return self.stats[cookie_file.name]
    
    def get_best_cookie(self) -> Optional[Path]:
        """Возвращает лучший (наименее использованный и незаблокированный) cookies"""
        with self.lock:
            available = [
                stats for stats in self.stats.values()
                if not stats.blocked
            ]
            
            if not available:
                return None
            
            # Сортируем по health score
            best = min(available, key=lambda s: s.health_score)
            return best.file_path
    
    def mark_usage(self, cookie_file: Path, success: bool):
        """Отмечает использование cookies"""
        with self.lock:
            stats = self.stats.get(cookie_file.name)
            if not stats:
                stats = self.add_cookies(cookie_file)
            
            stats.usage_count += 1
            stats.last_used = time.time()
            
            if success:
                stats.success_count += 1
                # Сбрасываем счётчик неудач при успехе
                stats.fail_count = max(0, stats.fail_count - 1)
            else:
                stats.fail_count += 1
                # Блокируем после 3 последовательных неудач
                if stats.fail_count >= 3:
                    stats.blocked = True
                    print(f"🚫 Cookies {cookie_file.name} заблокирован (3+ неудачи)")
    
    def unblock_all(self):
        """Разблокирует все cookies (после обновления)"""
        with self.lock:
            for stats in self.stats.values():
                stats.blocked = False
                stats.fail_count = 0
    
    def print_stats(self):
        """Выводит статистику"""
        print("\n" + "="*70)
        print("🍪 СТАТИСТИКА COOKIES")
        print("="*70)
        
        with self.lock:
            for name, stats in sorted(self.stats.items()):
                status = "🚫" if stats.blocked else "✅"
                print(f"{status} {name}")
                print(f"   Использований: {stats.usage_count}")
                print(f"   Успешных: {stats.success_count}")
                print(f"   Неудачных: {stats.fail_count}")
                print(f"   Success Rate: {stats.success_rate:.1f}%")
                print(f"   Health Score: {stats.health_score:.1f}")
        
        print("="*70)


# ============================================================================
# YOUTUBE GRABBER V2
# ============================================================================

class ProductionYouTubeGrabber:
    """
    Production-ready YouTube grabber с лучшими практиками:
    - Rate limiting через декораторы
    - Smart retry с экспоненциальной задержкой
    - Client rotation
    - Cookie management с health tracking
    - Session cookies handling
    """
    
    def __init__(
        self,
        output_dir: Path = Path('downloads'),
        cookie_manager: Optional[ImprovedCookieManager] = None,
        client_rotation: bool = True,
        rate_limit_calls: int = 1,
        rate_limit_period: float = 2.0,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Cookie management
        self.cookie_manager = cookie_manager or ImprovedCookieManager()
        
        # Client rotation
        self.client_rotation = client_rotation
        self.current_client = 'web'
        
        # Rate limiting
        self.rate_limit_calls = rate_limit_calls
        self.rate_limit_period = rate_limit_period
        
        # Stats
        self.total_requests = 0
        self.successful_requests = 0
        
        self._check_ytdlp()
    
    def _check_ytdlp(self):
        """Проверка yt-dlp"""
        try:
            result = subprocess.run(
                ['yt-dlp', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                print(f"✅ yt-dlp: {result.stdout.strip()}")
            else:
                raise FileNotFoundError
        except (FileNotFoundError, subprocess.TimeoutExpired):
            raise RuntimeError("yt-dlp не установлен. Установите: pip install yt-dlp")
    
    def _rotate_client(self):
        """Ротация YouTube client"""
        if not self.client_rotation:
            return
        
        clients = list(YOUTUBE_CLIENTS.keys())
        current_idx = clients.index(self.current_client)
        self.current_client = clients[(current_idx + 1) % len(clients)]
        print(f"🔄 Переключение на client: {self.current_client}")
    
    def _get_client_config(self) -> Dict:
        """Получает конфигурацию текущего client"""
        return YOUTUBE_CLIENTS[self.current_client]
    
    def _build_command(self, url: str, extra_args: List[str] = None) -> List[str]:
        """Строит команду yt-dlp с обходом блокировок"""
        cmd = ['yt-dlp']
        
        # Client config - disabled, yt-dlp default works better
        # client_config = self._get_client_config()
        # cmd.extend(['--user-agent', client_config['user_agent']])
        
        # Headers - disabled, can cause YouTube blocks
        # for key, value in client_config['headers'].items():
        #     cmd.extend(['--add-header', f'{key}:{value}'])
        
        # Cookies
        cookie_file = self.cookie_manager.get_best_cookie()
        if cookie_file:
            cmd.extend(['--cookies', str(cookie_file)])
            print(f"🍪 Используем: {cookie_file.name}")
        
        # Rate limiting
        cmd.extend([
            '--sleep-interval', str(self.rate_limit_period),
            '--max-sleep-interval', str(self.rate_limit_period * 1.5),
        ])
        
        # No warnings and quiet mode for clean JSON output
        cmd.extend(['--no-warnings', '--quiet'])
        
        # Extra args
        if extra_args:
            cmd.extend(extra_args)
        
        # URL
        cmd.append(url)
        
        return cmd
    
    @rate_limit(calls=1, period=2.0)
    @smart_retry(max_attempts=4, base_delay=2.0, backoff=2.0)
    def get_metadata(self, url: str) -> Optional[Dict]:
        """
        Получает метаданные видео
        
        Args:
            url: YouTube URL
        
        Returns:
            Словарь с метаданными или None
        """
        print(f"📊 Метаданные: {url}")
        
        self.total_requests += 1
        cookie_file = self.cookie_manager.get_best_cookie()
        
        try:
            cmd = self._build_command(url, ['--dump-json'])
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                error = result.stderr.lower()
                
                # Определяем тип ошибки
                if 'sign in' in error or 'bot' in error:
                    print(f"🚫 Блокировка cookies")
                    if cookie_file:
                        self.cookie_manager.mark_usage(cookie_file, success=False)
                    # Пробуем другой client
                    self._rotate_client()
                    raise Exception("Cookies blocked")
                
                elif 'geo' in error or 'location' in error:
                    print(f"🌍 Гео-блокировка")
                    raise Exception("Geo-restricted")
                
                else:
                    print(f"❌ Ошибка: {result.stderr[:200]}")
                    if cookie_file:
                        self.cookie_manager.mark_usage(cookie_file, success=False)
                    raise Exception(result.stderr)
            
            # Успех
            metadata = json.loads(result.stdout)
            self.successful_requests += 1
            if cookie_file:
                self.cookie_manager.mark_usage(cookie_file, success=True)
            
            print(f"✅ Получено: {metadata.get('title', 'Unknown')}")
            return metadata
            
        except subprocess.TimeoutExpired:
            print("⏱️  Timeout")
            if cookie_file:
                self.cookie_manager.mark_usage(cookie_file, success=False)
            raise
        except json.JSONDecodeError as e:
            print(f"❌ JSON ошибка: {e}")
            raise
    
    @rate_limit(calls=1, period=3.0)
    @smart_retry(max_attempts=3, base_delay=3.0, backoff=2.0)
    def download_video(
        self,
        url: str,
        output_dir: Optional[Path] = None,
        quality: str = 'best'
    ) -> Optional[Path]:
        """
        Скачивает видео
        
        Args:
            url: YouTube URL
            output_dir: Директория для сохранения (если None, используется self.output_dir)
            quality: Качество видео
        
        Returns:
            Путь к скачанному файлу или None
        """
        print(f"📥 Загрузка: {url}")
        
        self.total_requests += 1
        cookie_file = self.cookie_manager.get_best_cookie()
        
        # Используем переданную директорию или дефолтную
        target_dir = output_dir if output_dir else self.output_dir
        
        # Извлекаем video ID (поддерживает /watch, /shorts, youtu.be)
        video_id_match = re.search(r'(?:youtube\.com/(?:watch\?v=|shorts/)|youtu\.be/)([a-zA-Z0-9_-]{11})', url)
        if not video_id_match:
            print("❌ Невалидный URL")
            return None
        
        video_id = video_id_match.group(1)
        output_template = str(target_dir / f"{video_id}.%(ext)s")
        
        try:
            cmd = self._build_command(url, [
                '-f', quality,
                '-o', output_template,
            ])
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600
            )
            
            if result.returncode != 0:
                print(f"❌ Ошибка загрузки: {result.stderr[:200]}")
                if cookie_file:
                    self.cookie_manager.mark_usage(cookie_file, success=False)
                self._rotate_client()
                raise Exception(result.stderr)
            
            # Ищем скачанный файл в правильной директории
            video_files = list(target_dir.glob(f"{video_id}.*"))
            if video_files:
                video_path = video_files[0]
                self.successful_requests += 1
                if cookie_file:
                    self.cookie_manager.mark_usage(cookie_file, success=True)
                
                print(f"✅ Загружено: {video_path.name} ({video_path.stat().st_size / 1024 / 1024:.1f} MB)")
                return video_path
            else:
                print("❌ Файл не найден после загрузки")
                return None
                
        except subprocess.TimeoutExpired:
            print("⏱️  Timeout при загрузке")
            if cookie_file:
                self.cookie_manager.mark_usage(cookie_file, success=False)
            raise
    
    def print_stats(self):
        """Выводит статистику загрузчика"""
        success_rate = 0
        if self.total_requests > 0:
            success_rate = (self.successful_requests / self.total_requests) * 100
        
        print("\n" + "="*70)
        print("📊 СТАТИСТИКА ЗАГРУЗЧИКА V2")
        print("="*70)
        print(f"Всего запросов: {self.total_requests}")
        print(f"Успешных: {self.successful_requests}")
        print(f"Неудачных: {self.total_requests - self.successful_requests}")
        print(f"Success Rate: {success_rate:.1f}%")
        print(f"Текущий client: {self.current_client}")
        print("="*70)
        
        # Статистика cookies
        self.cookie_manager.print_stats()


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == '__main__':
    # Пример использования
    from pathlib import Path
    
    # Создаём cookie manager
    cookie_mgr = ImprovedCookieManager(Path('cookies'))
    
    # Добавляем cookies файлы
    for cookie_file in Path('cookies').glob('*.txt'):
        cookie_mgr.add_cookies(cookie_file)
    
    # Создаём grabber
    grabber = ProductionYouTubeGrabber(
        output_dir=Path('downloads'),
        cookie_manager=cookie_mgr,
        client_rotation=True,
        rate_limit_calls=1,
        rate_limit_period=2.0,
    )
    
    # Тестовые URL
    test_urls = [
        "https://youtu.be/jNQXAC9IVRw",  # Me at the zoo
    ]
    
    for url in test_urls:
        try:
            # Получаем метаданные
            metadata = grabber.get_metadata(url)
            if metadata:
                print(f"Название: {metadata['title']}")
                print(f"Длительность: {metadata['duration']}с")
            
            # Скачиваем
            # video_path = grabber.download_video(url, quality='worst')
            
        except Exception as e:
            print(f"Ошибка: {e}")
    
    # Статистика
    grabber.print_stats()
