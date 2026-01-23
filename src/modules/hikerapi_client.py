"""
HikerAPI Client for Instagram

Клиент для работы с HikerAPI SaaS (Instagram Private API).
Документация: https://hikerapi.com/docs
"""
import os
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import requests
from pathlib import Path

logger = logging.getLogger(__name__)

HIKERAPI_BASE_URL = "https://api.hikerapi.com/v1"


@dataclass
class MediaInfo:
    """Информация о медиа-контенте Instagram"""
    media_id: str
    shortcode: str
    media_type: str  # 'photo', 'video', 'carousel', 'reel'
    caption: Optional[str] = None
    author_username: str = ""
    author_id: str = ""
    like_count: int = 0
    comment_count: int = 0
    view_count: int = 0
    duration: float = 0.0
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    image_urls: List[str] = None
    taken_at: Optional[str] = None
    
    def __post_init__(self):
        if self.image_urls is None:
            self.image_urls = []


class HikerAPIClient:
    """
    Клиент для HikerAPI SaaS
    
    Требует API ключ в переменной окружения HIKERAPI_TOKEN
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("HIKERAPI_TOKEN")
        if not self.api_key:
            raise ValueError(
                "HIKERAPI_TOKEN не найден. "
                "Установите переменную окружения или передайте api_key в конструктор."
            )
        
        self.base_url = HIKERAPI_BASE_URL
        self.headers = {
            "accept": "application/json",
            "x-access-key": self.api_key,
        }
        self.timeout = 30
    
    def _request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Выполняет GET запрос к API"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = requests.get(
                url,
                params=params,
                headers=self.headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"Ресурс не найден: {endpoint}")
                return None
            elif e.response.status_code == 401:
                logger.error("Неверный API ключ HikerAPI")
                raise ValueError("Invalid HIKERAPI_TOKEN")
            else:
                logger.error(f"HTTP ошибка: {e}")
                raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка запроса к HikerAPI: {e}")
            raise
    
    def get_media_by_shortcode(self, shortcode: str) -> Optional[MediaInfo]:
        """
        Получает информацию о посте/Reels по shortcode
        
        Args:
            shortcode: Код из URL (например, CxyzABC123)
            
        Returns:
            MediaInfo или None
        """
        data = self._request("/media/by/code", params={"code": shortcode})
        
        if not data:
            return None
        
        # Парсим ответ
        media = data.get("media") or data
        
        # Определяем тип медиа
        media_type = "photo"
        product_type = media.get("product_type", "")
        if product_type == "clips":
            media_type = "reel"
        elif media.get("video_url"):
            media_type = "video"
        elif media.get("carousel_media"):
            media_type = "carousel"
        
        # Собираем URL изображений/видео
        video_url = media.get("video_url")
        image_urls = []
        
        if media_type == "carousel":
            for item in media.get("carousel_media", []):
                if item.get("video_url"):
                    image_urls.append(item["video_url"])
                elif item.get("image_versions2"):
                    candidates = item["image_versions2"].get("candidates", [])
                    if candidates:
                        image_urls.append(candidates[0]["url"])
        else:
            if media.get("image_versions2"):
                candidates = media["image_versions2"].get("candidates", [])
                if candidates:
                    image_urls.append(candidates[0]["url"])
        
        user = media.get("user", {})
        
        return MediaInfo(
            media_id=str(media.get("pk", "")),
            shortcode=shortcode,
            media_type=media_type,
            caption=media.get("caption_text") or (media.get("caption", {}).get("text") if media.get("caption") else None),
            author_username=user.get("username", ""),
            author_id=str(user.get("pk", "")),
            like_count=media.get("like_count", 0),
            comment_count=media.get("comment_count", 0),
            view_count=media.get("view_count", 0) or media.get("play_count", 0),
            duration=media.get("video_duration", 0.0),
            video_url=video_url,
            thumbnail_url=media.get("thumbnail_url"),
            image_urls=image_urls,
            taken_at=media.get("taken_at"),
        )
    
    def get_user_info(self, username: str) -> Optional[Dict]:
        """Получает информацию о пользователе"""
        data = self._request("/user/by/username", params={"username": username})
        if data and data.get("status") == "ok":
            return data.get("user")
        return None
    
    def get_media_comments(self, media_id: str, count: int = 50) -> List[Dict]:
        """Получает комментарии к посту"""
        data = self._request("/media/comments", params={
            "media_id": media_id,
            "count": count
        })
        if data:
            return data.get("comments", [])
        return []
    
    def download_media(self, url: str, save_path: Path) -> bool:
        """
        Скачивает медиа-файл по URL
        
        Args:
            url: URL файла
            save_path: Путь для сохранения
            
        Returns:
            True если успешно
        """
        try:
            response = requests.get(url, timeout=60, stream=True)
            response.raise_for_status()
            
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return True
        except Exception as e:
            logger.error(f"Ошибка скачивания {url}: {e}")
            return False
