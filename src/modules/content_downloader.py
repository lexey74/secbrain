"""
Content Downloader - Универсальный загрузчик контента из разных источников
"""
from pathlib import Path
from typing import Optional, Dict, Tuple
from dataclasses import dataclass
from enum import Enum
import re


class ContentSource(Enum):
    """Источник контента"""
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"
    UNKNOWN = "unknown"


class InstagramContentType(Enum):
    """Тип контента Instagram"""
    POST = "post"          # Обычный пост с изображением
    CAROUSEL = "carousel"  # Карусель (несколько изображений)
    REELS = "reels"        # Короткое видео
    UNKNOWN = "unknown"


class YouTubeContentType(Enum):
    """Тип контента YouTube"""
    VIDEO = "video"        # Обычное видео
    SHORT = "short"        # YouTube Shorts (аналог reels)
    UNKNOWN = "unknown"


@dataclass
class ContentInfo:
    """Информация о контенте"""
    source: ContentSource
    content_type: str  # InstagramContentType или YouTubeContentType
    url: str
    content_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    
    # Пути к загруженным файлам
    folder_path: Optional[Path] = None
    media_files: list = None  # Список путей к медиа файлам
    description_file: Optional[Path] = None
    
    def __post_init__(self):
        if self.media_files is None:
            self.media_files = []


class ContentDownloader:
    """
    Универсальный загрузчик контента
    
    Определяет источник (Instagram/YouTube), тип контента,
    создает папку и сохраняет медиа + описание.
    """
    
    def __init__(self, output_dir: Path = Path("downloads")):
        """
        Args:
            output_dir: Базовая директория для сохранения контента
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def detect_source(self, url: str) -> ContentSource:
        """
        Определяет источник контента по URL
        
        Args:
            url: URL контента
            
        Returns:
            ContentSource
        """
        url_lower = url.lower()
        
        if 'instagram.com' in url_lower or 'instagr.am' in url_lower:
            return ContentSource.INSTAGRAM
        elif 'youtube.com' in url_lower or 'youtu.be' in url_lower:
            return ContentSource.YOUTUBE
        else:
            return ContentSource.UNKNOWN
    
    def detect_instagram_type(self, url: str) -> InstagramContentType:
        """
        Определяет тип Instagram контента
        
        Args:
            url: Instagram URL
            
        Returns:
            InstagramContentType
        """
        if '/reel/' in url or '/reels/' in url:
            return InstagramContentType.REELS
        elif '/p/' in url:
            # Обычный пост или карусель
            # Точный тип определяется после загрузки метаданных
            return InstagramContentType.POST
        else:
            return InstagramContentType.UNKNOWN
    
    def detect_youtube_type(self, url: str) -> YouTubeContentType:
        """
        Определяет тип YouTube контента
        
        Args:
            url: YouTube URL
            
        Returns:
            YouTubeContentType
        """
        if '/shorts/' in url:
            return YouTubeContentType.SHORT
        elif '/watch?v=' in url or 'youtu.be/' in url:
            return YouTubeContentType.VIDEO
        else:
            return YouTubeContentType.UNKNOWN
    
    def extract_instagram_id(self, url: str) -> Optional[str]:
        """
        Извлекает ID поста/reels из Instagram URL
        
        Args:
            url: Instagram URL
            
        Returns:
            ID или None
        """
        patterns = [
            r'instagram\.com/(?:p|reel|reels)/([A-Za-z0-9_-]+)',
            r'instagr\.am/(?:p|reel)/([A-Za-z0-9_-]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    def extract_youtube_id(self, url: str) -> Optional[str]:
        """
        Извлекает video ID из YouTube URL
        
        Args:
            url: YouTube URL
            
        Returns:
            Video ID или None
        """
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    def create_folder(self, title: str, content_id: str, source: ContentSource) -> Path:
        """
        Создает папку для сохранения контента
        
        Args:
            title: Название контента
            content_id: ID контента
            source: Источник контента
            
        Returns:
            Path к созданной папке
        """
        # Безопасное имя папки
        safe_title = self._sanitize_filename(title)
        
        # Ограничиваем длину названия
        if len(safe_title) > 50:
            safe_title = safe_title[:50]
        
        # Формат: {YYYY-MM-DD}_{HH-MM}_{Platform}_{SlugTitle}
        from datetime import datetime
        now = datetime.now()
        date_prefix = now.strftime("%Y-%m-%d")
        time_prefix = now.strftime("%H-%M")
        
        folder_name = f"{date_prefix}_{time_prefix}_{source.value}_{safe_title}"
        folder_path = self.output_dir / folder_name
        
        # Создаем папку
        folder_path.mkdir(parents=True, exist_ok=True)
        
        return folder_path
    
    def _sanitize_filename(self, name: str) -> str:
        """
        Делает имя безопасным для файловой системы
        
        Args:
            name: Исходное имя
            
        Returns:
            Безопасное имя
        """
        # Убираем небезопасные символы
        safe = re.sub(r'[<>:"/\\|?*]', '', name)
        # Убираем множественные пробелы
        safe = re.sub(r'\s+', '_', safe)
        # Убираем точки в начале/конце
        safe = safe.strip('.')
        
        return safe or "untitled"
    
    def download_instagram(
        self, 
        url: str, 
        content_type: InstagramContentType
    ) -> Optional[ContentInfo]:
        """
        Загружает Instagram контент
        
        Args:
            url: Instagram URL
            content_type: Тип контента
            
        Returns:
            ContentInfo с информацией о загруженном контенте
        """
        from .hybrid_grabber import HybridGrabber
        
        print(f"\n📸 Instagram: {content_type.value}")
        print(f"   URL: {url}")
        
        # Извлекаем ID
        content_id = self.extract_instagram_id(url)
        if not content_id:
            print("❌ Не удалось извлечь ID из URL")
            return None
        
        # Используем HybridGrabber
        grabber = HybridGrabber(output_dir=self.output_dir)
        result = grabber.grab(url)
        
        if not result:
            print("❌ Ошибка загрузки Instagram контента")
            return None
        
        # Определяем точный тип после загрузки
        if result.media_type == "video":
            actual_type = InstagramContentType.REELS
        elif len(result.media_paths) > 1:
            actual_type = InstagramContentType.CAROUSEL
        else:
            actual_type = InstagramContentType.POST
        
        # Создаем папку проекта
        title = result.caption[:50] if result.caption else content_id
        folder_path = self.create_folder(title, content_id, ContentSource.INSTAGRAM)
        
        # Сохраняем описание в Markdown
        description_file = folder_path / "description.md"
        description_content = f"# {title}\n\n## Ссылка\n\n{url}\n\n## Описание\n\n{result.caption or 'Нет описания'}\n"
        description_file.write_text(description_content, encoding='utf-8')
        
        # Копируем медиа файлы в папку проекта
        media_files = []
        for i, media_path in enumerate(result.media_paths, 1):
            if media_path.exists():
                ext = media_path.suffix
                new_name = f"media_{i:02d}{ext}"
                new_path = folder_path / new_name
                
                # Копируем файл
                import shutil
                shutil.copy2(media_path, new_path)
                media_files.append(new_path)
                print(f"   ✅ {new_name}")
        
        print(f"✅ Сохранено в: {folder_path.name}")
        
        return ContentInfo(
            source=ContentSource.INSTAGRAM,
            content_type=actual_type.value,
            url=url,
            content_id=content_id,
            title=title,
            description=result.caption,
            folder_path=folder_path,
            media_files=media_files,
            description_file=description_file
        )
    
    def download_youtube(
        self, 
        url: str, 
        content_type: YouTubeContentType,
        download_video: bool = True
    ) -> Optional[ContentInfo]:
        """
        Загружает YouTube контент
        
        Args:
            url: YouTube URL
            content_type: Тип контента
            download_video: Скачивать ли видео файл
            
        Returns:
            ContentInfo с информацией о загруженном контенте
        """
        from .youtube_grabber import YouTubeGrabber
        
        print(f"\n🎬 YouTube: {content_type.value}")
        print(f"   URL: {url}")
        
        # Извлекаем ID
        content_id = self.extract_youtube_id(url)
        if not content_id:
            print("❌ Не удалось извлечь video ID из URL")
            return None
        
        # Используем YouTubeGrabber с cookies если есть
        # Ищем файл cookies в корне проекта
        project_root = Path(__file__).parent.parent.parent
        cookies_file = project_root / "youtube_cookies.txt"
        
        grabber = YouTubeGrabber(
            output_dir=self.output_dir,
            cookies_file=str(cookies_file) if cookies_file.exists() else None
        )
        
        # Сначала получаем метаданные
        metadata = grabber.get_metadata(url)
        if not metadata:
            print("❌ Ошибка получения метаданных")
            print("💡 Убедитесь, что файл youtube_cookies.txt существует в корне проекта")
            return None
        
        title = metadata.get('title', content_id)
        description = metadata.get('description', '')
        
        # Создаем папку проекта
        folder_path = self.create_folder(title, content_id, ContentSource.YOUTUBE)
        
        # Сохраняем описание в Markdown
        description_file = folder_path / "description.md"
        description_content = f"# {title}\n\n## Ссылка\n\n{url}\n\n## Описание\n\n{description}\n"
        description_file.write_text(description_content, encoding='utf-8')
        
        # Загружаем видео если нужно
        media_files = []
        if download_video:
            # Временно сохраняем в output_dir
            temp_grabber = YouTubeGrabber(
                output_dir=folder_path,
                cookies_file=str(cookies_file) if cookies_file.exists() else None
            )
            
            video_path = temp_grabber.download_video(url, quality='worst')
            if video_path:
                media_files.append(video_path)
                print(f"   ✅ {video_path.name}")
        
        print(f"✅ Сохранено в: {folder_path.name}")
        
        return ContentInfo(
            source=ContentSource.YOUTUBE,
            content_type=content_type.value,
            url=url,
            content_id=content_id,
            title=title,
            description=description,
            folder_path=folder_path,
            media_files=media_files,
            description_file=description_file
        )
    
    def download(self, url: str, download_video: bool = True) -> Optional[ContentInfo]:
        """
        Универсальная функция загрузки контента
        
        Определяет источник, тип контента и загружает
        
        Args:
            url: URL контента
            download_video: Скачивать ли видео (для YouTube)
            
        Returns:
            ContentInfo или None
        """
        print("\n" + "="*70)
        print(f"🔍 Анализ URL: {url}")
        
        # 1. Определяем источник
        source = self.detect_source(url)
        print(f"📍 Источник: {source.value}")
        
        if source == ContentSource.UNKNOWN:
            print("❌ Неизвестный источник")
            return None
        
        # 2. Определяем тип контента и загружаем
        if source == ContentSource.INSTAGRAM:
            content_type = self.detect_instagram_type(url)
            print(f"📌 Тип: {content_type.value}")
            return self.download_instagram(url, content_type)
        
        elif source == ContentSource.YOUTUBE:
            content_type = self.detect_youtube_type(url)
            print(f"📌 Тип: {content_type.value}")
            return self.download_youtube(url, content_type, download_video)
        
        return None


# Пример использования
if __name__ == "__main__":
    downloader = ContentDownloader(output_dir=Path("downloads"))
    
    # Instagram примеры
    # result = downloader.download("https://www.instagram.com/p/ABC123/")
    # result = downloader.download("https://www.instagram.com/reel/XYZ456/")
    
    # YouTube примеры
    # result = downloader.download("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    # result = downloader.download("https://www.youtube.com/shorts/abc123")
    
    print("✅ ContentDownloader готов к использованию")
