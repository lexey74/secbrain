import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from src.modules.instagram_reels_downloader import InstagramReelsDownloader
from src.modules.downloader_base import DownloadSettings, ContentSource, InstagramContentType
from src.modules.hikerapi_client import MediaInfo

class TestInstagramReelsDownloader:
    @pytest.fixture
    def settings(self, tmp_path):
        return DownloadSettings(
            instagram_cookies=tmp_path / "cookies/instagram.txt"
        )

    @pytest.fixture
    def downloader(self, settings):
        return InstagramReelsDownloader(settings)

    def test_can_handle(self, downloader):
        assert downloader.can_handle("https://www.instagram.com/reel/123456/")
        assert downloader.can_handle("https://instagram.com/reels/123456/")
        assert not downloader.can_handle("https://instagram.com/p/123456/")
        assert not downloader.can_handle("https://youtube.com/watch?v=123")

    @patch('src.modules.instagram_reels_downloader.HikerAPIClient')
    def test_get_media_by_shortcode(self, mock_client_class, downloader):
        """Тест получения метаданных через HikerAPI"""
        mock_client = mock_client_class.return_value
        mock_client.get_media_by_shortcode.return_value = MediaInfo(
            media_id="123456789",
            shortcode="Code123",
            media_type="reel",
            caption="Test Reel Description",
            author_username="test_user",
            author_id="987654",
            like_count=100,
            comment_count=10,
            view_count=5000,
            duration=15.5,
            video_url="https://example.com/video.mp4"
        )
        
        # Force client initialization
        downloader._client = mock_client
        
        media_info = downloader.client.get_media_by_shortcode("Code123")
        
        assert media_info.author_username == "test_user"
        assert media_info.caption == "Test Reel Description"
        assert media_info.view_count == 5000
        assert media_info.duration == 15.5

    @patch('src.modules.instagram_reels_downloader.HikerAPIClient')
    @patch('src.modules.instagram_reels_downloader.BaseDownloader.create_folder')
    @patch('src.modules.instagram_reels_downloader.BaseDownloader.save_description')
    def test_download_success(self, mock_save_desc, mock_create_folder, mock_client_class, downloader, tmp_path):
        # Setup mocks
        folder_path = tmp_path / "downloads/instagram_reels_test_user_Code123_Test_Reel"
        folder_path.mkdir(parents=True, exist_ok=True)
        mock_create_folder.return_value = folder_path
        mock_save_desc.return_value = folder_path / "description.md"
        
        # Mock HikerAPI client
        mock_client = mock_client_class.return_value
        mock_client.get_media_by_shortcode.return_value = MediaInfo(
            media_id="123456789",
            shortcode="Code123",
            media_type="reel",
            caption="Test Reel",
            author_username="test_user",
            author_id="987654",
            like_count=100,
            comment_count=10,
            view_count=1000,
            duration=10.0,
            video_url="https://example.com/video.mp4"
        )
        
        # Mock download_media to create a fake video file
        def mock_download(url, path):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
            return True
        
        mock_client.download_media.side_effect = mock_download
        mock_client.get_media_comments.return_value = []
        
        # Inject mock
        downloader._client = mock_client

        result = downloader.download("https://www.instagram.com/reel/Code123/")
        
        assert result.content_type == InstagramContentType.REELS
        assert result.author == "test_user"
        assert result.views == 1000
        
        # Verify HikerAPI calls
        mock_client.get_media_by_shortcode.assert_called_once()
        mock_client.download_media.assert_called_once()
