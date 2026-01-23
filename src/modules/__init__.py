"""
SecBrain modules - Modular Architecture

Модульная архитектура v2:
- Новые модули: content_router, platform-specific downloaders
- Legacy: content_downloader (монолитный, устарел)
"""

# ============================================================================
# НОВАЯ МОДУЛЬНАЯ АРХИТЕКТУРА (RECOMMENDED)
# ============================================================================

# Базовые классы
from .downloader_base import (
    ContentSource,
    InstagramContentType,
    YouTubeContentType,
    DownloadResult,
    InstagramPostResult,
    InstagramReelsResult,
    YouTubeVideoResult,
    DownloadSettings,
    BaseDownloader
)

# Утилиты
from .downloader_utils import (
    clean_filename,
    extract_video_id_youtube,
    extract_shortcode_instagram,
    is_youtube_short,
    is_instagram_reel,
    format_duration,
    format_count,
    get_file_size_mb,
    print_progress
)

# Скачиватели
from .instagram_post_downloader import InstagramPostDownloader
from .instagram_reels_downloader import InstagramReelsDownloader
from .youtube_video_downloader import YouTubeVideoDownloader
from .youtube_shorts_downloader import YouTubeShortsDownloader
from .youtube_comment_service import YouTubeCommentService

# Роутер (главный интерфейс)
from .content_router import ContentRouter

# YouTube grabber с обходом блокировок
from .youtube_grabber_v2 import ProductionYouTubeGrabber


# ============================================================================
# LEGACY (для обратной совместимости)
# ============================================================================

from .content_downloader import (
    ContentDownloader,
    ContentInfo,
)
from .hybrid_grabber import HybridGrabber
from .local_ears import LocalEars
from .local_brain import LocalBrain
from .tag_manager import TagManager

__all__ = [
    # ========== НОВАЯ АРХИТЕКТУРА (используйте это) ==========
    
    # Базовые классы
    'ContentSource',
    'InstagramContentType',
    'YouTubeContentType',
    'DownloadResult',
    'InstagramPostResult',
    'InstagramReelsResult',
    'YouTubeVideoResult',
    'DownloadSettings',
    'BaseDownloader',
    
    # Утилиты
    'clean_filename',
    'extract_video_id_youtube',
    'extract_shortcode_instagram',
    'is_youtube_short',
    'is_instagram_reel',
    'format_duration',
    'format_count',
    'get_file_size_mb',
    'print_progress',
    
    # Скачиватели
    'InstagramPostDownloader',
    'InstagramReelsDownloader',
    'YouTubeVideoDownloader',
    'YouTubeShortsDownloader',
    'YouTubeCommentService',
    
    # Роутер (главный интерфейс)
    'ContentRouter',
    
    # YouTube grabber
    'ProductionYouTubeGrabber',
    
    # ========== LEGACY (старый код) ==========
    
    # Content Downloader (Модуль 1 - монолитный)
    'ContentDownloader',
    'ContentInfo',
    
    # Grabbers
    'HybridGrabber',
    
    # Processing
    'LocalEars',
    'LocalBrain',
    'TagManager',
]
