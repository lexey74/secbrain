"""
YouTube Video Downloader

Скачивает обычные YouTube видео (горизонтальные).
Использует ProductionYouTubeGrabber для обхода блокировок.
"""
import json
from pathlib import Path
from typing import Dict, List, Optional

from .downloader_base import (
    BaseDownloader,
    ContentSource,
    YouTubeContentType,
    YouTubeVideoResult,
    DownloadSettings
)
from .downloader_utils import (
    clean_filename,
    extract_video_id_youtube,
    print_progress,
    format_duration,
    format_count
)
from .youtube_grabber_v2 import ProductionYouTubeGrabber, ImprovedCookieManager


class YouTubeVideoDownloader(BaseDownloader):
    """
    Скачивает YouTube видео
    
    Поддерживает:
    - Обычные видео (горизонтальные)
    - Различное качество (best, 1080p, 720p и т.д.)
    - Автоматический обход блокировок через ProductionYouTubeGrabber
    """
    
    def __init__(self, settings: DownloadSettings):
        super().__init__(settings)
        
        # Создаем cookie manager
        cookie_manager = None
        if settings.youtube_cookies_dir:
            cookie_manager = ImprovedCookieManager(cookies_dir=settings.youtube_cookies_dir)
            # Добавляем все YouTube cookies
            for cookie_file in settings.youtube_cookies_dir.glob('youtube_cookies*.txt'):
                cookie_manager.add_cookies(cookie_file)
        elif settings.youtube_cookies:
            cookie_manager = ImprovedCookieManager(cookies_dir=settings.youtube_cookies.parent)
            cookie_manager.add_cookies(settings.youtube_cookies)
        
        # Инициализируем ProductionYouTubeGrabber
        self.grabber = ProductionYouTubeGrabber(cookie_manager=cookie_manager)
    
    def can_handle(self, url: str) -> bool:
        """Проверяет, может ли обработать URL"""
        url_lower = url.lower()
        # НЕ обрабатываем Shorts
        if '/shorts/' in url_lower:
            return False
        
        return ('youtube.com/watch' in url_lower or 
                'youtu.be/' in url_lower)
    
    def download(self, url: str) -> YouTubeVideoResult:
        """
        Скачивает YouTube видео
        
        Args:
            url: URL видео
            
        Returns:
            YouTubeVideoResult с результатами
        """
        print_progress(f"🎥 Анализ видео: {url}")
        
        # Извлекаем video ID
        video_id = extract_video_id_youtube(url)
        if not video_id:
            raise ValueError(f"Не удалось извлечь video ID из URL: {url}")
        
        # Получаем метаданные через ProductionYouTubeGrabber
        metadata = self.grabber.get_metadata(url)
        
        # Создаем папку
        channel = metadata.get('channel', 'unknown_channel')
        title = clean_filename(metadata.get('title', 'no_title'))
        folder_path = self.create_folder(
            prefix=f"youtube_{channel}",
            content_id=video_id,
            title=title
        )
        
        print_progress(f"📁 Папка: {folder_path}", "")
        
        # Скачиваем видео через ProductionYouTubeGrabber
        print_progress(f"⬇️  Скачивание видео качество={self.settings.video_quality}...", "")
        video_path = self.grabber.download_video(
            url=url,
            output_dir=folder_path,
            quality=self.settings.video_quality
        )
        print_progress(f"✅ Видео скачано: {video_path.name}", "")
        
        # Скачиваем субтитры если есть
        subtitles = self._download_subtitles(url, folder_path, video_id)
        if subtitles:
            print_progress(f"📝 Субтитры: {len(subtitles)} языков", "")
        
        # Сохраняем описание
        description_file = self.save_description(
            folder_path=folder_path,
            description=self._format_description(metadata)
        )
        
        # Скачиваем комментарии если нужно
        comments_file = None
        if self.settings.download_comments:
            print_progress("💬 Скачивание комментариев...", "")
            comments = self._download_comments(video_id)
            if comments:
                comments_file = self.save_comments(folder_path, comments)
                print_progress(f"✅ Комментариев: {len(comments)}", "")
        
        return YouTubeVideoResult(
            source=ContentSource.YOUTUBE,
            content_type=YouTubeContentType.VIDEO,
            url=url,
            content_id=video_id,
            folder_path=folder_path,
            media_files=[video_path] + subtitles,
            description_file=description_file,
            comments_file=comments_file,
            channel=channel,
            views=metadata.get('view_count', 0),
            likes=metadata.get('like_count', 0),
            duration=metadata.get('duration', 0)
        )
    
    def _download_subtitles(
        self, 
        url: str, 
        folder_path: Path, 
        video_id: str
    ) -> List[Path]:
        """
        Скачивает субтитры
        
        Args:
            url: URL видео
            folder_path: Папка для сохранения
            video_id: ID видео
            
        Returns:
            Список файлов субтитров
        """
        try:
            subtitle_paths = self.grabber.download_subtitles(
                url=url,
                output_dir=folder_path
            )
            return subtitle_paths
        except Exception as e:
            print_progress(f"⚠️  Субтитры недоступны: {e}", "")
            return []
    
    def _download_comments(self, video_id: str) -> List[Dict]:
        """
        Скачивает комментарии к видео
        
        Args:
            video_id: ID видео
            
        Returns:
            Список комментариев
        """
        try:
            comments = self.grabber.get_comments(
                video_id=video_id,
                max_comments=self.settings.max_comments
            )
            return comments
        except Exception as e:
            print_progress(f"⚠️  Комментарии недоступны: {e}", "")
            return []
    
    def _format_description(self, metadata: Dict) -> str:
        """
        Форматирует описание в Markdown
        
        Args:
            metadata: Метаданные
            
        Returns:
            Markdown текст
        """
        lines = [
            f"# {metadata.get('title', 'Без названия')}",
            f"",
            f"**Канал:** {metadata.get('channel', 'unknown')}",
            f"**Дата публикации:** {metadata.get('upload_date', 'unknown')}",
            f"**Длительность:** {format_duration(metadata.get('duration', 0))}",
            f"",
            f"## Статистика",
            f"",
            f"- 👁️ Просмотры: {format_count(metadata.get('view_count', 0))}",
            f"- 👍 Лайки: {format_count(metadata.get('like_count', 0))}",
            f"",
            f"## Описание",
            f"",
            metadata.get('description', 'Без описания'),
            f"",
            f"## Теги",
            f"",
        ]
        
        # Добавляем теги
        tags = metadata.get('tags', [])
        if tags:
            lines.append(", ".join([f"`{tag}`" for tag in tags]))
        else:
            lines.append("Нет тегов")
        
        # Категория
        category = metadata.get('category')
        if category:
            lines.append(f"")
            lines.append(f"**Категория:** {category}")
        
        return '\n'.join(lines)
