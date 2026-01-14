"""
YouTube Grabber - Загрузка видео, метаданных и комментариев с YouTube
"""
from pathlib import Path
from typing import Optional, List, Dict
from dataclasses import dataclass
import subprocess
import json
import re


@dataclass
class YouTubeContent:
    """Структура данных YouTube видео"""
    video_id: str
    title: str
    author: str
    description: str
    duration: int  # секунды
    upload_date: str  # YYYYMMDD
    view_count: int
    like_count: int
    comment_count: int
    tags: List[str]
    categories: List[str]
    
    # Пути к файлам
    video_path: Optional[Path] = None
    audio_path: Optional[Path] = None
    thumbnail_path: Optional[Path] = None
    
    # Контент
    comments: List[Dict] = None
    
    def __post_init__(self):
        if self.comments is None:
            self.comments = []


class YouTubeGrabber:
    """Загрузчик контента с YouTube"""
    
    def __init__(self, output_dir: Path = Path('temp'), cookies_file: Optional[str] = None):
        """
        Инициализация
        
        Args:
            output_dir: Директория для сохранения файлов
            cookies_file: Путь к файлу с cookies (для защищённых видео)
        """
        self.output_dir = Path(output_dir)
        self.cookies_file = cookies_file
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Проверяем наличие yt-dlp
        self._check_ytdlp()
    
    def _check_ytdlp(self) -> None:
        """Проверка наличия yt-dlp"""
        try:
            result = subprocess.run(
                ['yt-dlp', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                print(f"✅ yt-dlp версия: {result.stdout.strip()}")
            else:
                raise FileNotFoundError
        except (FileNotFoundError, subprocess.TimeoutExpired):
            print("❌ yt-dlp не найден!")
            print("📦 Установите: pip install yt-dlp")
            raise RuntimeError("yt-dlp не установлен")
    
    def _extract_video_id(self, url: str) -> Optional[str]:
        """
        Извлекает video ID из YouTube URL
        
        Args:
            url: YouTube URL
            
        Returns:
            Video ID или None
        """
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
            r'youtube\.com/v/([a-zA-Z0-9_-]{11})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    def get_metadata(self, url: str) -> Optional[Dict]:
        """
        Получает метаданные видео без загрузки
        
        Args:
            url: YouTube URL
            
        Returns:
            Словарь с метаданными
        """
        print(f"📊 Получение метаданных: {url}")
        
        try:
            cmd = ['yt-dlp', '--dump-json', '--no-warnings']
            
            # Добавляем cookies если указаны
            if self.cookies_file:
                cmd.extend(['--cookies', self.cookies_file])
            
            cmd.append(url)
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                print(f"❌ Ошибка получения метаданных: {result.stderr}")
                return None
            
            metadata = json.loads(result.stdout)
            print(f"✅ Метаданные получены: {metadata.get('title', 'Unknown')}")
            return metadata
            
        except subprocess.TimeoutExpired:
            print("⏱️  Timeout при получении метаданных")
            return None
        except json.JSONDecodeError as e:
            print(f"❌ Ошибка парсинга JSON: {e}")
            return None
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return None
    
    def download_video(self, url: str, quality: str = 'best') -> Optional[Path]:
        """
        Скачивает видео
        
        Args:
            url: YouTube URL
            quality: Качество (best, worst, 720p, 1080p, etc.)
            
        Returns:
            Путь к скачанному файлу
        """
        print(f"📥 Загрузка видео: {url}")
        print(f"   Качество: {quality}")
        
        video_id = self._extract_video_id(url)
        if not video_id:
            print("❌ Не удалось извлечь video ID")
            return None
        
        output_template = str(self.output_dir / f"{video_id}.%(ext)s")
        
        try:
            # Формируем команду
            cmd = [
                'yt-dlp',
                '-f', f'{quality}',
                '-o', output_template,
                '--no-warnings'
            ]
            
            # Добавляем cookies если указаны
            if self.cookies_file:
                cmd.extend(['--cookies', self.cookies_file])
            
            cmd.append(url)
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10 минут
            )
            
            if result.returncode != 0:
                print(f"❌ Ошибка загрузки: {result.stderr}")
                return None
            
            # Ищем скачанный файл
            video_files = list(self.output_dir.glob(f"{video_id}.*"))
            if video_files:
                video_path = video_files[0]
                print(f"✅ Видео загружено: {video_path.name}")
                return video_path
            else:
                print("❌ Файл не найден после загрузки")
                return None
                
        except subprocess.TimeoutExpired:
            print("⏱️  Timeout при загрузке видео")
            return None
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return None
    
    def download_audio(self, url: str) -> Optional[Path]:
        """
        Скачивает только аудио (для транскрибации)
        
        Args:
            url: YouTube URL
            
        Returns:
            Путь к аудио файлу
        """
        print(f"🎵 Загрузка аудио: {url}")
        
        video_id = self._extract_video_id(url)
        if not video_id:
            print("❌ Не удалось извлечь video ID")
            return None
        
        output_template = str(self.output_dir / f"{video_id}_audio.%(ext)s")
        
        try:
            cmd = [
                'yt-dlp',
                '-f', 'bestaudio/best',  # Используем bestaudio или best если недоступен
                '-x',  # Извлечь аудио
                '--audio-format', 'mp3',
                '--audio-quality', '0',  # Лучшее качество
                '--newline',  # Каждый прогресс на новой строке
                '--progress',  # Показывать прогресс
                '-o', output_template
            ]
            
            # Добавляем cookies если указаны
            if self.cookies_file:
                cmd.extend(['--cookies', self.cookies_file])
            
            cmd.append(url)
            
            # Запускаем без capture_output чтобы видеть прогресс
            result = subprocess.run(
                cmd,
                timeout=900  # 15 минут для больших файлов
            )
            
            if result.returncode != 0:
                print(f"❌ Ошибка загрузки аудио")
                return None
            
            # Ищем аудио файл
            audio_files = list(self.output_dir.glob(f"{video_id}_audio.*"))
            # Исключаем .part файлы
            audio_files = [f for f in audio_files if not str(f).endswith('.part')]
            if audio_files:
                audio_path = audio_files[0]
                print(f"\n✅ Аудио загружено: {audio_path.name}")
                return audio_path
            else:
                print("❌ Аудио файл не найден")
                return None
                
        except subprocess.TimeoutExpired:
            print("⏱️  Timeout при загрузке аудио (15 минут)")
            return None
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return None
    
    def download_thumbnail(self, url: str) -> Optional[Path]:
        """
        Скачивает превью (thumbnail)
        
        Args:
            url: YouTube URL
            
        Returns:
            Путь к файлу превью
        """
        print(f"🖼️  Загрузка thumbnail: {url}")
        
        video_id = self._extract_video_id(url)
        if not video_id:
            return None
        
        output_template = str(self.output_dir / f"{video_id}_thumb.%(ext)s")
        
        try:
            cmd = [
                'yt-dlp',
                '--write-thumbnail',
                '--skip-download',
                '-o', output_template,
                '--no-warnings'
            ]
            
            # Добавляем cookies если указаны
            if self.cookies_file:
                cmd.extend(['--cookies', self.cookies_file])
            
            cmd.append(url)
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                print(f"⚠️  Не удалось загрузить thumbnail")
                return None
            
            thumb_files = list(self.output_dir.glob(f"{video_id}_thumb.*"))
            if thumb_files:
                print(f"✅ Thumbnail загружен: {thumb_files[0].name}")
                return thumb_files[0]
            
            return None
            
        except Exception as e:
            print(f"⚠️  Ошибка загрузки thumbnail: {e}")
            return None
    
    def get_comments(self, url: str, max_comments: int = 100) -> List[Dict]:
        """
        Получает комментарии к видео
        
        Args:
            url: YouTube URL
            max_comments: Максимальное количество комментариев
            
        Returns:
            Список комментариев
        """
        print(f"💬 Загрузка комментариев: {url}")
        print(f"   Максимум: {max_comments}")
        
        try:
            cmd = [
                'yt-dlp',
                '--dump-json',
                '--skip-download',
                '--write-comments',
                '--extractor-args', f'youtube:max_comments={max_comments}',
                '--no-warnings'
            ]
            
            # Добавляем cookies если указаны
            if self.cookies_file:
                cmd.extend(['--cookies', self.cookies_file])
            
            cmd.append(url)
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                print(f"⚠️  Не удалось загрузить комментарии: {result.stderr}")
                return []
            
            data = json.loads(result.stdout)
            comments_data = data.get('comments', [])
            
            # Форматируем комментарии
            comments = []
            for comment in comments_data[:max_comments]:
                comments.append({
                    'author': comment.get('author', 'Unknown'),
                    'text': comment.get('text', ''),
                    'likes': comment.get('like_count', 0),
                    'timestamp': comment.get('timestamp', 0),
                    'is_favorited': comment.get('is_favorited', False),
                })
            
            print(f"✅ Загружено комментариев: {len(comments)}")
            return comments
            
        except subprocess.TimeoutExpired:
            print("⏱️  Timeout при загрузке комментариев")
            return []
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return []
    
    def grab(self, url: str, download_video: bool = True, download_audio: bool = True, max_comments: int = 100) -> Optional[YouTubeContent]:
        """
        Полная загрузка: метаданные + видео + аудио + комментарии
        
        Args:
            url: YouTube URL
            download_video: Скачивать ли видео
            download_audio: Скачивать ли аудио (для транскрибации)
            max_comments: Максимальное количество комментариев
            
        Returns:
            YouTubeContent с данными
        """
        print("\n" + "="*60)
        print(f"🎬 YouTube Grabber: {url}")
        print("="*60 + "\n")
        
        # 1. Метаданные
        metadata = self.get_metadata(url)
        if not metadata:
            return None
        
        video_id = self._extract_video_id(url)
        
        # 2. Создаем объект контента
        content = YouTubeContent(
            video_id=video_id or metadata.get('id', 'unknown'),
            title=metadata.get('title', 'Unknown'),
            author=metadata.get('uploader', 'Unknown'),
            description=metadata.get('description', ''),
            duration=metadata.get('duration', 0),
            upload_date=metadata.get('upload_date', ''),
            view_count=metadata.get('view_count', 0),
            like_count=metadata.get('like_count', 0),
            comment_count=metadata.get('comment_count', 0),
            tags=metadata.get('tags', []),
            categories=metadata.get('categories', [])
        )
        
        # 3. Загружаем видео (опционально)
        if download_video:
            content.video_path = self.download_video(url, quality='worst')
        
        # 4. Загружаем аудио (для транскрибации)
        if download_audio:
            content.audio_path = self.download_audio(url)
        
        # 5. Загружаем thumbnail
        content.thumbnail_path = self.download_thumbnail(url)
        
        # 6. Загружаем комментарии
        content.comments = self.get_comments(url, max_comments=max_comments)
        
        print("\n" + "="*60)
        print("✅ Загрузка завершена")
        print(f"   Видео: {'✅' if content.video_path else '❌'}")
        print(f"   Аудио: {'✅' if content.audio_path else '❌'}")
        print(f"   Комментарии: {len(content.comments)}")
        print("="*60 + "\n")
        
        return content
