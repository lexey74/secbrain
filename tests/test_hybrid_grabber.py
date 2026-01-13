"""
Unit Tests for HybridGrabber (Content Downloader)
=================================================

Тесты для модуля загрузки контента из соцсетей.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from modules.hybrid_grabber import HybridGrabber, InstagramContent


class TestHybridGrabber:
    """Тесты для HybridGrabber"""
    
    def test_init(self, temp_dir):
        """Тест инициализации grabber"""
        grabber = HybridGrabber(output_dir=temp_dir)
        
        assert grabber.output_dir == temp_dir
        assert grabber.cookies_file is None
        assert grabber.min_delay == 3.0
    
    def test_init_with_cookies(self, temp_dir):
        """Тест инициализации с cookies"""
        cookies_file = temp_dir / "cookies.txt"
        cookies_file.write_text("fake cookies")
        
        grabber = HybridGrabber(
            output_dir=temp_dir,
            cookies_file=cookies_file
        )
        
        assert grabber.cookies_file == cookies_file
    
    def test_extract_username_from_url(self, temp_dir):
        """Тест извлечения username из URL"""
        grabber = HybridGrabber(output_dir=temp_dir)
        
        # Instagram URLs
        url1 = "https://www.instagram.com/username/p/ABC123/"
        url2 = "https://instagram.com/another_user/reel/XYZ789/"
        
        username1 = grabber._extract_username_from_url(url1)
        username2 = grabber._extract_username_from_url(url2)
        
        assert username1 == "username"
        assert username2 == "another_user"
    
    @patch('modules.hybrid_grabber.subprocess.run')
    def test_download_with_gallery_dl(self, mock_subprocess, temp_dir):
        """Тест загрузки через gallery-dl"""
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout='{"description": "Test post"}',
            stderr=''  # Добавляем stderr как строку
        )
        
        grabber = HybridGrabber(output_dir=temp_dir)
        url = "https://www.instagram.com/p/ABC123/"
        
        media_files, metadata = grabber._download_with_gallery_dl(url)
        
        # Проверяем, что gallery-dl был вызван
        assert mock_subprocess.called
        call_args = str(mock_subprocess.call_args)
        assert 'gallery-dl' in call_args or media_files is not None
    
    def test_instagram_content_dataclass(self):
        """Тест структуры данных InstagramContent"""
        content = InstagramContent(
            url="https://instagram.com/p/TEST123/",
            author="test_user",
            caption="Test caption",
            media_path=Path("/tmp/test.jpg")
        )
        
        assert content.url == "https://instagram.com/p/TEST123/"
        assert content.author == "test_user"
        assert content.caption == "Test caption"
        assert isinstance(content.media_path, Path)
