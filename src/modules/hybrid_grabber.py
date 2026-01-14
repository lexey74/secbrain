"""
HybridGrabber - Парсинг Instagram через yt-dlp + gallery-dl
"""
import subprocess
from pathlib import Path
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass
import re
import json
import shutil
import hashlib


@dataclass
class InstagramContent:
    """Структура данных Instagram поста"""
    url: str
    media_path: Optional[Path] = None  # Первый файл (для обратной совместимости)
    media_paths: List[Path] = None  # Все файлы (для каруселей)
    caption: str = ""
    author: str = ""
    date: str = ""
    comments: List[str] = None
    media_type: str = "unknown"  # video, image, carousel
    transcript: str = ""  # Добавлено для транскрипции
    transcript_clean: str = ""  # Чистый текст без таймкодов
    
    def __post_init__(self):
        if self.comments is None:
            self.comments = []
        if self.media_paths is None:
            self.media_paths = []
            if self.media_path:
                self.media_paths = [self.media_path]


class HybridGrabber:
    """Гибридный парсер Instagram контента"""
    
    def __init__(self, output_dir: Path, cookies_file: Path = None):
        """
        Инициализация grabber
        
        Args:
            output_dir: Директория для сохранения медиа
            cookies_file: Путь к cookies.txt для gallery-dl и yt-dlp
        """
        self.output_dir = output_dir
        self.cookies_file = cookies_file
        self.last_request_time = 0
        self.min_delay = 3.0  # Минимальная задержка между запросами (секунды)
    
    def setup_instagrapi(self, session_file: Path):
        """
        Заглушка для совместимости с pipeline.py
        HybridGrabber использует gallery-dl, не требует instagrapi
        
        Args:
            session_file: Путь к файлу сессии (не используется)
        """
        print("ℹ️  HybridGrabber использует gallery-dl, setup_instagrapi не требуется")
        pass
    
    def grab(self, url: str) -> InstagramContent:
        """
        Основной метод: парсинг через gallery-dl
        
        Args:
            url: URL Instagram поста/рилса
            
        Returns:
            InstagramContent с медиа и метаданными
        """
        # Rate limiting - задержка между запросами
        import time
        import random
        
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_delay:
            delay = self.min_delay - time_since_last + random.uniform(0, 2)
            print(f"⏱️  Задержка {delay:.1f}с для защиты от бана...")
            time.sleep(delay)
        
        self.last_request_time = time.time()
        
        content = InstagramContent(url=url)
        
        # Используем gallery-dl для получения всего: медиа + метаданные + комментарии
        print("📥 Загрузка через gallery-dl...")
        media_files, metadata = self._download_with_gallery_dl(url)
        
        if media_files:
            content.media_path = media_files[0]  # Первый файл как основной
            content.media_paths = media_files  # Все файлы
            print(f"✅ Загружено файлов: {len(media_files)}")
        
        if metadata:
            content.caption = metadata.get('description', '')
            
            # Извлекаем username из owner объекта
            owner = metadata.get('owner', {})
            if isinstance(owner, dict):
                content.author = owner.get('username', self._extract_username_from_url(url))
            else:
                content.author = self._extract_username_from_url(url)
            
            # Форматируем дату
            timestamp = metadata.get('date')
            if timestamp:
                from datetime import datetime
                try:
                    # Пробуем как timestamp (int)
                    if isinstance(timestamp, (int, float)):
                        content.date = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
                    # Пробуем как строку ISO формата
                    elif isinstance(timestamp, str):
                        # Парсим различные форматы даты
                        for fmt in ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
                            try:
                                dt = datetime.strptime(timestamp.split('.')[0].split('+')[0], fmt)
                                content.date = dt.strftime("%Y-%m-%d")
                                break
                            except:
                                continue
                except Exception as e:
                    print(f"⚠️  Не удалось распарсить дату: {e}")
            
            # Извлекаем комментарии
            comments_data = metadata.get('comments', [])
            if comments_data:
                content.comments = [
                    f"{c.get('owner', {}).get('username', 'unknown')}: {c.get('text', '')}"
                    for c in comments_data
                    if c.get('text')
                ]
                print(f"💬 Получено комментариев: {len(content.comments)}")
            
            # Определяем тип медиа
            if metadata.get('typename') == 'GraphVideo':
                content.media_type = 'video'
            elif metadata.get('typename') == 'GraphSidecar':
                content.media_type = 'carousel'
            else:
                content.media_type = 'image'
        
        return content
    
    def _download_with_ytdlp(self, url: str) -> tuple[Optional[Path], Optional[Dict]]:
        """
        Загрузка медиафайла через yt-dlp
        
        Args:
            url: URL Instagram
            
        Returns:
            Кортеж (путь к скачанному файлу или None, метаданные или None)
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Временное имя файла (будет переименовано позже)
        output_template = str(self.output_dir / "media.%(ext)s")
        
        cmd = [
            "yt-dlp",
            "--no-playlist",
            "-o", output_template,
            "--write-info-json",  # Сохраняем метаданные
        ]
        
        if self.cookies_file and self.cookies_file.exists():
            cmd.extend(["--cookies", str(self.cookies_file)])
        
        cmd.append(url)
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Ищем созданный файл
            media_file = None
            for file in self.output_dir.glob("media.*"):
                if file.suffix in ['.mp4', '.jpg', '.png', '.webp']:
                    media_file = file
                    break
            
            # Читаем метаданные из .info.json
            metadata = None
            info_json = self.output_dir / "media.info.json"
            if info_json.exists():
                try:
                    import json
                    with open(info_json, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    info_json.unlink()  # Удаляем после чтения
                except Exception as e:
                    print(f"⚠️  Не удалось прочитать метаданные: {e}")
            
            return media_file, metadata
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Ошибка yt-dlp: {e.stderr}")
            return None, None
    
    def _extract_username_from_url(self, url: str) -> str:
        """Извлечение username из URL"""
        match = re.search(r'instagram\.com/([^/]+)/', url)
        return match.group(1) if match else 'unknown'
    
    def _download_with_gallery_dl(self, url: str) -> Tuple[List[Path], Optional[Dict]]:
        """
        Загрузка медиа и метаданных через gallery-dl с защитой от бана
        
        Args:
            url: URL Instagram
            
        Returns:
            Кортеж (список файлов, метаданные)
        """
        import time
        import random
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Очищаем URL от параметров img_index и igsh (они мешают скачивать всю карусель)
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        # Удаляем параметры, которые ограничивают скачивание
        query_params.pop('img_index', None)
        query_params.pop('igsh', None)
        query_params.pop('igshid', None)
        # Пересобираем URL
        clean_query = urlencode(query_params, doseq=True)
        clean_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, clean_query, parsed.fragment))
        
        # Путь к конфигу
        config_path = Path(__file__).parent.parent.parent / "gallery-dl.conf"
        
        cmd = [
            "gallery-dl",
            "--write-metadata",
            "--directory", str(self.output_dir),
            "--no-skip",  # Скачиваем все элементы карусели
        ]
        
        # Используем конфиг если существует
        if config_path.exists():
            cmd.extend(["--config", str(config_path)])
        
        if self.cookies_file and self.cookies_file.exists():
            cmd.extend(["--cookies", str(self.cookies_file)])
        
        cmd.append(clean_url)  # Используем очищенный URL
        
        # Retry с exponential backoff
        max_retries = 3
        base_delay = 5
        
        for attempt in range(max_retries):
            try:
                # Отладочный вывод команды
                print(f"🔧 Команда: {' '.join(cmd)}")
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=120  # 2 минуты таймаут
                )
                
                # Выводим результат gallery-dl
                if result.stdout:
                    print(f"📤 gallery-dl stdout: {result.stdout[:200]}")
                if result.stderr:
                    print(f"⚠️  gallery-dl stderr: {result.stderr[:200]}")
                
                # Собираем все скачанные медиа файлы
                media_files = []
                # gallery-dl создает структуру: gallery-dl/instagram/username/postid_*.ext
                for file in sorted(self.output_dir.rglob("*")):
                    if file.is_file() and file.suffix in ['.mp4', '.jpg', '.png', '.webp', '.jpeg']:
                        media_files.append(file)
                
                # Удаляем дубликаты по MD5 хешу
                print(f"📦 Найдено медиа файлов: {len(media_files)}")
                unique_files = []
                seen_hashes = set()
                
                for file in media_files:
                    # Вычисляем MD5 хеш файла
                    md5_hash = hashlib.md5()
                    with open(file, 'rb') as f:
                        # Читаем файл частями для экономии памяти
                        for chunk in iter(lambda: f.read(8192), b''):
                            md5_hash.update(chunk)
                    file_hash = md5_hash.hexdigest()
                    
                    # Проверяем, не встречали ли мы этот хеш ранее
                    if file_hash not in seen_hashes:
                        seen_hashes.add(file_hash)
                        unique_files.append(file)
                    else:
                        print(f"⚠️  Пропущен дубликат: {file.name} (хеш: {file_hash[:8]}...)")
                
                media_files = unique_files
                print(f"✅ Уникальных файлов: {len(media_files)}")
                
                # Переименовываем файлы и копируем в корень output_dir
                if media_files:
                    # Создаем простые имена media_1, media_2, etc
                    renamed_files = []
                    for idx, file in enumerate(media_files, 1):
                        if idx == 1:
                            new_name = self.output_dir / f"media{file.suffix}"
                        else:
                            new_name = self.output_dir / f"media_{idx}{file.suffix}"
                        
                        shutil.copy(file, new_name)
                        renamed_files.append(new_name)
                    
                    media_files = renamed_files
                
                # Читаем метаданные из JSON (gallery-dl создает файлы типа media.jpg.json)
                metadata = None
                json_files = []
                for media_file in media_files:
                    json_path = Path(str(media_file) + '.json')
                    if json_path.exists():
                        json_files.append(json_path)
                
                # Также ищем любые JSON в output_dir
                if not json_files:
                    json_files = list(self.output_dir.rglob("*.json"))
                
                if json_files:
                    try:
                        with open(json_files[0], 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                        # Удаляем JSON файлы после чтения
                        for jf in json_files:
                            jf.unlink()
                    except Exception as e:
                        print(f"⚠️  Не удалось прочитать метаданные: {e}")
                
                return media_files, metadata
                
            except subprocess.TimeoutExpired:
                print(f"⏱️  Таймаут на попытке {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 5)
                    print(f"⏳ Повтор через {delay:.1f}с...")
                    time.sleep(delay)
                    
            except subprocess.CalledProcessError as e:
                error_msg = e.stderr.lower()
                
                # Проверка на rate limit (429) или ban
                if '429' in error_msg or 'rate limit' in error_msg or 'too many requests' in error_msg:
                    if attempt < max_retries - 1:
                        delay = base_delay * (3 ** attempt) + random.uniform(10, 30)
                        print(f"⚠️  Rate limit! Ожидание {delay:.1f}с...")
                        time.sleep(delay)
                    else:
                        print(f"❌ Превышен лимит запросов Instagram. Попробуйте позже.")
                        return [], None
                        
                # Проверка на необходимость авторизации
                elif 'login' in error_msg or 'authentication' in error_msg:
                    print(f"❌ Требуется авторизация. Обновите cookies (instagram_cookies.txt)")
                    return [], None
                    
                else:
                    print(f"❌ Ошибка gallery-dl (попытка {attempt + 1}/{max_retries}): {e.stderr}")
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        print(f"⏳ Повтор через {delay}с...")
                        time.sleep(delay)
        
        print("❌ Не удалось загрузить после всех попыток")
        return [], None
