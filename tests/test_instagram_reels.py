import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import json

from src.modules.instagram_reels_downloader import InstagramReelsDownloader, InstagramReelsResult
from src.modules.downloader_base import DownloadSettings, ContentSource, InstagramContentType

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

    @patch('src.modules.instagram_reels_downloader.subprocess.run')
    def test_get_metadata_success(self, mock_run, downloader):
        # Mocking gallery-dl output
        mock_output = [
            [
                "code",
                {
                    "post_id": "123456789",
                    "username": "test_user",
                    "description": "Test Reel Description",
                    "likes": 100,
                    "comments": 10,
                    "video_view_count": 5000,
                    "video_duration": 15.5,
                    "date": "2024-01-01"
                }
            ]
        ]
        
        mock_run.return_value = Mock(
            stdout=json.dumps(mock_output),
            returncode=0
        )

        metadata = downloader._get_metadata("https://www.instagram.com/reel/Code123/")
        
        assert metadata['author'] == "test_user"
        assert metadata['title'] == "Test Reel Description"
        assert metadata['views'] == 5000
        assert metadata['duration'] == 15.5

    @patch('src.modules.instagram_reels_downloader.subprocess.run')
    @patch('src.modules.instagram_reels_downloader.BaseDownloader.create_folder')
    @patch('src.modules.instagram_reels_downloader.BaseDownloader.save_description')
    def test_download_success(self, mock_save_desc, mock_create_folder, mock_run, downloader, tmp_path):
        # Setup mocks
        mock_create_folder.return_value = tmp_path / "downloads/instagram_reels_test_user_Code123_Test_Reel"
        mock_save_desc.return_value = tmp_path / "description.md"
        
        # Mock metadata call (first subprocess call)
        mock_metadata_output = [[
            "code",
            {
                "post_id": "123456789",
                "username": "test_user", 
                "description": "Test Reel",
                "video_view_count": 1000,
                "video_duration": 10
            }
        ]]
        
        # Mock video download (second subprocess call)
        # We need to simulate the file creation since _download_video checks for existence
        def side_effect(cmd, **kwargs):
            if '--dump-json' in cmd:
                return Mock(stdout=json.dumps(mock_metadata_output), returncode=0)
            elif '--filename' in cmd:
                # Create a dummy file
                video_file = mock_create_folder.return_value / "reel.mp4"
                video_file.parent.mkdir(parents=True, exist_ok=True)
                video_file.touch()
                return Mock(returncode=0)
            return Mock(returncode=0)

        mock_run.side_effect = side_effect

        # Create dummy video file in advance because create_folder is mocked but _download_video uses the path
        # Actually _download_video uses the path returned by create_folder.
        # Since we mocked create_folder, we know where it is.
        
        result = downloader.download("https://www.instagram.com/reel/Code123/")
        
        assert isinstance(result, InstagramReelsResult)
        assert result.content_type == InstagramContentType.REELS
        assert result.author == "test_user"
        assert result.views == 1000
