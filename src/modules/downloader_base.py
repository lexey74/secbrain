"""
Base classes for Module 1 - Content Downloader

Базовые классы для всех подмодулей загрузки контента.
"""
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod


# ============================================================================
# ENUMS - Типы контента
# ============================================================================

class ContentSource(Enum):
    """Источник контента"""
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"
    UNKNOWN = "unknown"


class InstagramContentType(Enum):
    """Тип контента Instagram"""
    POST = "post"          # Обычный пост с изображением
    CAROUSEL = "carousel"  # Карусель (несколько изображений)
    REELS = "reels"        # Короткое видео (вертикальное)
    UNKNOWN = "unknown"


class YouTubeContentType(Enum):
    """Тип контента YouTube"""
    VIDEO = "video"        # Полнометражное видео (горизонтальное)
    SHORT = "short"        # YouTube Shorts (вертикальное, до 60 сек)
    UNKNOWN = "unknown"


# ============================================================================
# DATA CLASSES - Результаты загрузки
# ============================================================================

@dataclass
class DownloadResult:
    """
    Базовый результат загрузки контента
    
    Все подмодули возвращают этот класс или его наследников.
    """
    # Метаданные
    source: ContentSource
    content_type: str  # Enum.value из InstagramContentType или YouTubeContentType
    url: str
    content_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    author: Optional[str] = None
    date: Optional[str] = None
    
    # Пути к файлам
    folder_path: Optional[Path] = None
    media_files: List[Path] = field(default_factory=list)
    description_file: Optional[Path] = None
    comments_file: Optional[Path] = None
    
    # Дополнительная информация
    duration: Optional[int] = None  # Для видео (секунды)
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    comment_count: Optional[int] = None
    
    def __post_init__(self):
        """Валидация после создания"""
        if not isinstance(self.media_files, list):
            self.media_files = []


@dataclass
class InstagramPostResult(DownloadResult):
    """Результат загрузки Instagram поста"""
    author: str = ""
    likes: int = 0
    comments_count: int = 0
    post_date: Optional[str] = None
    hashtags: List[str] = field(default_factory=list)
    mentions: List[str] = field(default_factory=list)


@dataclass
class InstagramReelsResult(DownloadResult):
    """Результат загрузки Instagram Reels"""
    author: str = ""
    likes: int = 0
    comments_count: int = 0
    views: int = 0
    duration: int = 0
    hashtags: List[str] = field(default_factory=list)
    mentions: List[str] = field(default_factory=list)
    music_title: Optional[str] = None


@dataclass
class YouTubeVideoResult(DownloadResult):
    """Результат загрузки YouTube видео"""
    channel: str = ""
    views: int = 0
    likes: int = 0
    duration: int = 0
    tags: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    thumbnail_path: Optional[Path] = None


# ============================================================================
# SETTINGS - Настройки загрузки
# ============================================================================

@dataclass
class DownloadSettings:
    """
    Настройки загрузки контента
    
    Передаются во все подмодули для конфигурации поведения.
    """
    # Что скачивать
    download_video: bool = True
    download_audio_only: bool = False  # Только аудио для YouTube
    download_comments: bool = False
    download_thumbnail: bool = True
    
    # Качество
    video_quality: str = 'best'  # best, worst, 720p, 1080p, etc.
    
    # Лимиты
    max_comments: int = 100
    max_media_files: int = 50  # Для каруселей
    
    # Cookies
    instagram_cookies: Optional[Path] = None
    youtube_cookies: Optional[Path] = None  # Один файл или None
    youtube_cookies_dir: Optional[Path] = None  # Папка с множественными cookies
    
    # Прочее
    timeout: int = 600  # Секунды
    retry_attempts: int = 3


# ============================================================================
# ABSTRACT BASE - Базовый класс для всех подмодулей
# ============================================================================

class BaseDownloader(ABC):
    """
    Абстрактный базовый класс для всех подмодулей загрузки.
    
    Все подмодули должны наследоваться от этого класса и
    реализовать метод download().
    """
    
    def __init__(self, settings: DownloadSettings, output_dir: Path = None):
        """
        Args:
            settings: Настройки загрузки
            output_dir: Директория для сохранения
        """
        self.settings = settings
        # Базовая директория для загрузок
        self.output_dir = Path(output_dir) if output_dir else Path('downloads')
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """
        Проверяет, может ли этот подмодуль обработать данный URL
        
        Args:
            url: URL для проверки
            
        Returns:
            True если может обработать, False иначе
        """
        pass
    
    @abstractmethod
    def download(self, url: str) -> Optional[DownloadResult]:
        """
        Скачивает контент по URL
        
        Args:
            url: URL контента
            
        Returns:
            DownloadResult или None при ошибке
        """
        pass

    def download_comments_only(self, url: str, folder_path: Path) -> Optional[Path]:
        """
        Скачивает только комментарии (если поддерживается)
        
        Args:
            url: URL контента
            folder_path: Папка для сохранения
            
        Returns:
            Путь к файлу комментариев или None
        """
        return None
    
    def create_folder(self, prefix: str, content_id: str, title: str) -> Path:
        """
        Создает папку для контента
        
        Args:
            prefix: Префикс (instagram, youtube)
            content_id: ID контента
            title: Название (будет очищено)
            
        Returns:
            Path к созданной папке
        """
        from datetime import datetime
        from .downloader_utils import clean_filename
        
        # Получаем текущую дату и время
        now = datetime.now()
        date_prefix = now.strftime("%Y-%m-%d")
        time_prefix = now.strftime("%H-%M")
        
        # Очищаем название
        clean_title = clean_filename(title)
        
        # Ограничиваем длину
        if len(clean_title) > 50:
            clean_title = clean_title[:50]
        
        # Формируем имя папки: {YYYY-MM-DD}_{HH-MM}_{Platform}_{SlugTitle}
        folder_name = f"{date_prefix}_{time_prefix}_{prefix}_{clean_title}"
        folder_path = self.output_dir / folder_name
        folder_path.mkdir(parents=True, exist_ok=True)
        
        return folder_path
    
    def save_description(self, folder_path: Path, description: str, 
                        author: str = None, date: str = None,
                        additional_info: dict = None) -> Path:
        """
        Сохраняет описание в Markdown
        
        Args:
            folder_path: Путь к папке контента
            description: Текст описания
            author: Автор
            date: Дата
            additional_info: Дополнительная информация (словарь)
            
        Returns:
            Path к файлу description.md
        """
        desc_file = folder_path / 'description.md'
        
        # Формируем YAML frontmatter
        from datetime import datetime
        
        with open(desc_file, 'w', encoding='utf-8') as f:
            # YAML frontmatter
            f.write('---\n')
            if author:
                f.write(f'author: {author}\n')
            if date:
                f.write(f'date: {date}\n')
            else:
                f.write(f'date: {datetime.now().strftime("%Y-%m-%d")}\n')
            f.write(f'type: description\n')
            if additional_info:
                for key, value in additional_info.items():
                    # Экранируем специальные символы для YAML
                    safe_value = str(value).replace(':', ' -').replace('\n', ' ')
                    f.write(f'{key}: {safe_value}\n')
            f.write('---\n\n')
            
            # Markdown body
            f.write('# Description\n\n')
            
            if author:
                f.write(f'**Author:** {author}\n\n')
            
            if date:
                f.write(f'**Date:** {date}\n\n')
            
            if additional_info:
                f.write('## Info\n\n')
                for key, value in additional_info.items():
                    f.write(f'- **{key}:** {value}\n')
                f.write('\n')
            
            f.write('## Content\n\n')
            f.write(description)
        
        return desc_file
    
    def save_comments(self, folder_path: Path, comments: List[dict]) -> Path:
        """
        Сохраняет комментарии в Markdown
        
        Args:
            folder_path: Путь к папке контента
            comments: Список комментариев (словарей)
            
        Returns:
            Path к файлу comments.md
        """
        comments_file = folder_path / 'comments.md'
        
        with open(comments_file, 'w', encoding='utf-8') as f:
            f.write(f'# Comments ({len(comments)})\n\n')
            
            for i, comment in enumerate(comments, 1):
                author = comment.get('author', 'Unknown')
                text = comment.get('text', '')
                likes = comment.get('likes', 0)
                date = comment.get('date', '')
                
                f.write(f'## Comment {i}\n\n')
                f.write(f'**Author:** {author}\n\n')
                if date:
                    f.write(f'**Date:** {date}\n\n')
                if likes:
                    f.write(f'**Likes:** {likes}\n\n')
                f.write(f'{text}\n\n')
                f.write('---\n\n')
        
        return comments_file
