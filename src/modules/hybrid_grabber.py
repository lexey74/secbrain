"""
HybridGrabber - Парсинг Instagram через yt-dlp + instagrapi
"""
import subprocess
from pathlib import Path
from typing import Dict, Optional, List
from dataclasses import dataclass
import re


@dataclass
class InstagramContent:
    """Структура данных Instagram поста"""
    url: str
    media_path: Optional[Path] = None
    caption: str = ""
    author: str = ""
    date: str = ""
    comments: List[str] = None
    media_type: str = "unknown"  # video, image, carousel
    
    def __post_init__(self):
        if self.comments is None:
            self.comments = []


class HybridGrabber:
    """Гибридный парсер Instagram контента"""
    
    def __init__(self, output_dir: Path, cookies_file: Path = None):
        """
        Инициализация grabber
        
        Args:
            output_dir: Директория для сохранения медиа
            cookies_file: Путь к cookies.txt для yt-dlp
        """
        self.output_dir = output_dir
        self.cookies_file = cookies_file
        self.instagrapi_client = None
    
    def grab(self, url: str) -> InstagramContent:
        """
        Основной метод: комбинированный парсинг
        
        Args:
            url: URL Instagram поста/рилса
            
        Returns:
            InstagramContent с медиа и метаданными
        """
        content = InstagramContent(url=url)
        
        # Шаг 1: Попытка загрузки через yt-dlp (для видео)
        print("📥 Попытка загрузки через yt-dlp...")
        content.media_path = self._download_with_ytdlp(url)
        
        # Шаг 2: Парсинг метаданных через instagrapi
        print("📝 Получение метаданных через instagrapi...")
        try:
            metadata = self._fetch_with_instagrapi(url)
            content.caption = metadata.get('caption', '')
            content.author = metadata.get('author', '')
            content.date = metadata.get('date', '')
            content.comments = metadata.get('comments', [])
            content.media_type = metadata.get('media_type', 'unknown')
            
            # Шаг 3: Если yt-dlp не смог скачать (фото/карусель), используем instagrapi
            if not content.media_path and self.instagrapi_client:
                print("📸 Загрузка медиа через instagrapi...")
                content.media_path = self._download_with_instagrapi(url)
                
        except Exception as e:
            print(f"⚠️  Ошибка instagrapi: {e}")
            print("ℹ️  Продолжаем только с медиа из yt-dlp...")
        
        return content
    
    def _download_with_ytdlp(self, url: str) -> Optional[Path]:
        """
        Загрузка медиафайла через yt-dlp
        
        Args:
            url: URL Instagram
            
        Returns:
            Путь к скачанному файлу или None
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Временное имя файла (будет переименовано позже)
        output_template = str(self.output_dir / "media.%(ext)s")
        
        cmd = [
            "yt-dlp",
            "--no-playlist",
            "-o", output_template,
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
            for file in self.output_dir.glob("media.*"):
                if file.suffix in ['.mp4', '.jpg', '.png', '.webp']:
                    return file
            
            return None
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Ошибка yt-dlp: {e.stderr}")
            return None
    
    def _fetch_with_instagrapi(self, url: str) -> Dict:
        """
        Парсинг метаданных через instagrapi
        
        Args:
            url: URL Instagram
            
        Returns:
            Словарь с метаданными
        """
        # Если клиент не инициализирован, возвращаем базовые данные
        if not self.instagrapi_client:
            return {
                'caption': '',
                'author': self._extract_username_from_url(url),
                'date': '',
                'comments': [],
                'media_type': 'unknown'
            }
        
        try:
            # Извлечение media_pk из URL
            media_pk = self._extract_media_pk(url)
            if not media_pk:
                raise ValueError("Не удалось извлечь media ID из URL")
            
            # Получение информации о медиа
            media = self.instagrapi_client.media_info(media_pk)
            
            # Парсинг данных
            result = {
                'caption': media.caption_text or '',
                'author': media.user.username,
                'date': media.taken_at.strftime("%Y-%m-%d") if media.taken_at else '',
                'media_type': str(media.media_type).split('.')[-1].lower(),
                'comments': []
            }
            
            # Получение комментариев (ограничено)
            try:
                comments = self.instagrapi_client.media_comments(media_pk, amount=50)
                result['comments'] = [
                    f"{c.user.username}: {c.text}" 
                    for c in comments[:50] 
                    if c.text
                ]
            except Exception as e:
                print(f"⚠️  Не удалось получить комментарии: {e}")
            
            return result
            
        except Exception as e:
            print(f"⚠️  Ошибка instagrapi: {e}")
            # Возврат минимальных данных
            return {
                'caption': '',
                'author': self._extract_username_from_url(url),
                'date': '',
                'comments': [],
                'media_type': 'unknown'
            }
    
    def _extract_media_pk(self, url: str) -> Optional[int]:
        """
        Извлечение media_pk (post ID) из URL
        
        Args:
            url: Instagram URL
            
        Returns:
            media_pk или None
        """
        if not self.instagrapi_client:
            return None
        
        try:
            # instagrapi имеет встроенный метод для этого
            return self.instagrapi_client.media_pk_from_url(url)
        except Exception as e:
            print(f"⚠️  Ошибка извлечения media_pk: {e}")
            return None
    
    def _extract_username_from_url(self, url: str) -> str:
        """Извлечение username из URL"""
        match = re.search(r'instagram\.com/([^/]+)/', url)
        return match.group(1) if match else 'unknown'
    
    def setup_instagrapi(self, session_file: Path) -> None:
        """
        Настройка клиента instagrapi
        
        Args:
            session_file: Путь к session.json
        """
        try:
            from instagrapi import Client
            
            self.instagrapi_client = Client()
            
            if session_file.exists():
                self.instagrapi_client.load_settings(session_file)
                print("✅ Сессия Instagrapi загружена")
            else:
                print("⚠️  Файл session.json не найден")
                
        except ImportError:
            print("⚠️  Библиотека instagrapi не установлена")
        except Exception as e:
            print(f"⚠️  Ошибка настройки instagrapi: {e}")
    
    def _download_with_instagrapi(self, url: str) -> Optional[Path]:
        """
        Загрузка медиа через instagrapi (для фото и каруселей)
        
        Args:
            url: URL Instagram
            
        Returns:
            Путь к скачанному файлу или None
        """
        if not self.instagrapi_client:
            return None
        
        try:
            # Извлечение media_pk
            media_pk = self._extract_media_pk(url)
            if not media_pk:
                return None
            
            # Получение информации о медиа
            media = self.instagrapi_client.media_info(media_pk)
            
            self.output_dir.mkdir(parents=True, exist_ok=True)
            
            # Определяем тип медиа
            if media.media_type == 1:  # Фото
                print("  📷 Скачивание фото...")
                print("     ⏳ Загрузка...")
                file_path = self.instagrapi_client.photo_download(media_pk, self.output_dir)
                # Переименовываем в стандартное имя
                new_path = self.output_dir / f"media{file_path.suffix}"
                file_path.rename(new_path)
                print("     ✅ Фото загружено")
                return new_path
                
            elif media.media_type == 2:  # Видео
                print("  🎥 Скачивание видео...")
                print("     ⏳ Загрузка (может занять время)...")
                file_path = self.instagrapi_client.video_download(media_pk, self.output_dir)
                new_path = self.output_dir / f"media{file_path.suffix}"
                file_path.rename(new_path)
                print("     ✅ Видео загружено")
                return new_path
                
            elif media.media_type == 8:  # Карусель
                print("  🎠 Скачивание первого элемента карусели...")
                print("     ⏳ Загрузка...")
                # Скачиваем первый элемент карусели
                if media.resources and len(media.resources) > 0:
                    first_resource = media.resources[0]
                    # Проверяем тип первого элемента
                    if first_resource.media_type == 1:  # Фото
                        file_path = self.instagrapi_client.photo_download_by_url(
                            first_resource.thumbnail_url, 
                            filename=str(self.output_dir / "media")
                        )
                    else:  # Видео
                        file_path = self.instagrapi_client.video_download_by_url(
                            first_resource.video_url,
                            filename=str(self.output_dir / "media")
                        )
                    print("     ✅ Элемент карусели загружен")
                    return Path(file_path) if file_path else None
                return None
            
            return None
            
        except Exception as e:
            print(f"  ❌ Ошибка загрузки через instagrapi: {e}")
            return None
