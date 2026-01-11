"""
Instagram Reels Downloader

Скачивает Instagram Reels (вертикальные видео).
"""
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

from .downloader_base import (
    BaseDownloader,
    ContentSource,
    InstagramContentType,
    InstagramReelsResult,
    DownloadSettings
)
from .downloader_utils import (
    clean_filename,
    extract_shortcode_instagram,
    print_progress,
    format_duration,
    format_count
)


def get_gallery_dl_command():
    """Возвращает правильную команду gallery-dl"""
    venv_path = Path(sys.prefix)
    gallery_dl_venv = venv_path / 'bin' / 'gallery-dl'
    
    if gallery_dl_venv.exists():
        return str(gallery_dl_venv)
    
    return 'gallery-dl'


class InstagramReelsDownloader(BaseDownloader):
    """
    Скачивает Instagram Reels
    
    Поддерживает:
    - Reels с музыкой
    - Reels с оригинальным аудио
    """
    
    def __init__(self, settings: DownloadSettings):
        super().__init__(settings)
    
    def can_handle(self, url: str) -> bool:
        """Проверяет, может ли обработать URL"""
        url_lower = url.lower()
        return ('instagram.com' in url_lower and 
                ('/reel/' in url_lower or '/reels/' in url_lower))
    
    def download(self, url: str) -> InstagramReelsResult:
        """
        Скачивает Instagram Reel
        
        Args:
            url: URL reels
            
        Returns:
            InstagramReelsResult с результатами
        """
        print_progress(f"🎬 Анализ Reels: {url}")
        
        # Извлекаем shortcode
        shortcode = extract_shortcode_instagram(url)
        if not shortcode:
            raise ValueError(f"Не удалось извлечь shortcode из URL: {url}")
        
        # Получаем метаданные
        metadata = self._get_metadata(url)
        
        # Создаем папку
        author = metadata.get('author', 'unknown')
        title = self._extract_title(metadata)
        folder_path = self.create_folder(
            prefix=f"instagram_reels_{author}",
            content_id=shortcode,
            title=title
        )
        
        print_progress(f"📁 Папка: {folder_path}", "")
        
        # Скачиваем видео
        video_path = self._download_video(url, folder_path)
        print_progress(f"✅ Видео скачано: {video_path.name}", "")
        
        # Сохраняем описание
        description_file = self.save_description(
            folder_path=folder_path,
            description=self._format_description(metadata)
        )
        
        # Скачиваем комментарии если нужно
        comments_file = None
        if self.settings.download_comments:
            print_progress("💬 Скачивание комментариев...", "")
            comments = self._download_comments(shortcode)
            if comments:
                comments_file = self.save_comments(folder_path, comments)
                print_progress(f"✅ Комментариев: {len(comments)}", "")
        
        return InstagramReelsResult(
            source=ContentSource.INSTAGRAM,
            content_type=InstagramContentType.REELS,
            url=url,
            content_id=shortcode,
            folder_path=folder_path,
            media_files=[video_path],
            description_file=description_file,
            comments_file=comments_file,
            author=author,
            likes=metadata.get('likes', 0),
            comments_count=metadata.get('comments', 0),
            views=metadata.get('views', 0),
            duration=metadata.get('duration', 0)
        )
    
    def _get_metadata(self, url: str) -> Dict:
        """
        Получает метаданные Reels через gallery-dl
        
        Args:
            url: URL reels
            
        Returns:
            Словарь с метаданными
        """
        try:
            cmd = [
                get_gallery_dl_command(),
                '--dump-json',
                '--no-download',
            ]
            
            # Добавляем cookies
            if self.settings.instagram_cookies and self.settings.instagram_cookies.exists():
                cmd.extend(['--cookies', str(self.settings.instagram_cookies)])
            
            cmd.append(url)
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Парсим JSON array от gallery-dl
            # Формат: [[code, metadata], [code, url, metadata], ...]
            data = json.loads(result.stdout)
            
            # Ищем первый dict с reel метаданными
            metadata = None
            for item in data:
                if isinstance(item, list) and len(item) >= 2:
                    if isinstance(item[1], dict) and ('post_id' in item[1] or 'username' in item[1]):
                        metadata = item[1]
                        break
            
            if not metadata:
                raise ValueError("Не удалось найти метаданные в ответе gallery-dl")
            
            return {
                'author': metadata.get('username', 'unknown'),
                'title': metadata.get('description', ''),
                'likes': metadata.get('likes', 0),
                'comments': metadata.get('comments', 0),
                'views': metadata.get('video_view_count', 0),
                'duration': metadata.get('video_duration', 0),
                'date': metadata.get('date'),
            }
            
        except subprocess.CalledProcessError as e:
            raise Exception(f"Ошибка gallery-dl: {e.stderr}")
        except json.JSONDecodeError as e:
            raise Exception(f"Ошибка парсинга JSON: {e}")
    
    def _download_video(self, url: str, folder_path: Path) -> Path:
        """
        Скачивает видео Reels
        
        Args:
            url: URL reels
            folder_path: Папка для сохранения
            
        Returns:
            Путь к видео файлу
        """
        try:
            cmd = [
                get_gallery_dl_command(),
                '--directory', str(folder_path),
                '--filename', 'reel.{extension}',
            ]
            
            # Добавляем cookies
            if self.settings.instagram_cookies and self.settings.instagram_cookies.exists():
                cmd.extend(['--cookies', str(self.settings.instagram_cookies)])
            
            cmd.append(url)
            
            # Выполняем
            subprocess.run(cmd, check=True, capture_output=True)
            
            # Ищем видео файл
            video_files = list(folder_path.glob("reel.mp4"))
            if not video_files:
                raise Exception("Видео файл не найден")
            
            return video_files[0]
            
        except subprocess.CalledProcessError as e:
            raise Exception(f"Ошибка скачивания: {e.stderr.decode()}")
    
    def _download_comments(self, shortcode: str) -> List[Dict]:
        """
        Скачивает комментарии к Reels
        
        Args:
            shortcode: Shortcode reels
            
        Returns:
            Список комментариев
        """
        # TODO: Реализовать через API или scraping
        return []
    
    def _extract_title(self, metadata: Dict) -> str:
        """Извлекает заголовок из описания"""
        description = metadata.get('title', '')
        if not description:
            return 'no_title'
        
        # Берем первые 50 символов
        title = description[:50]
        return clean_filename(title)
    
    def _format_description(self, metadata: Dict) -> str:
        """
        Форматирует описание в Markdown
        
        Args:
            metadata: Метаданные
            
        Returns:
            Markdown текст
        """
        lines = [
            f"# Instagram Reels",
            f"",
            f"**Автор:** @{metadata.get('author', 'unknown')}",
            f"**Дата:** {metadata.get('date', 'unknown')}",
            f"**Длительность:** {format_duration(metadata.get('duration', 0))}",
            f"",
            f"## Статистика",
            f"",
            f"- 👁️ Просмотры: {format_count(metadata.get('views', 0))}",
            f"- ❤️ Лайки: {format_count(metadata.get('likes', 0))}",
            f"- 💬 Комментарии: {format_count(metadata.get('comments', 0))}",
            f"",
            f"## Описание",
            f"",
            metadata.get('title', 'Без описания'),
        ]
        
        return '\n'.join(lines)
