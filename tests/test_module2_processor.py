import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from module2_transcribe import TranscriptionProcessor
from src.modules.local_ears import TranscriptResult

class TestTranscriptionProcessor:
    @pytest.fixture
    def processor(self, tmp_path):
        return TranscriptionProcessor(content_dir=tmp_path / "downloads")

    def test_find_content_folders(self, processor, tmp_path):
        # Create some folders
        d1 = tmp_path / "downloads" / "folder1"
        d1.mkdir(parents=True)
        d2 = tmp_path / "downloads" / "folder2"
        d2.mkdir(parents=True)
        file1 = tmp_path / "downloads" / "file.txt"
        file1.touch()
        
        folders = processor.find_content_folders()
        assert len(folders) == 2
        assert d1 in folders
        assert d2 in folders

    def test_find_media_files(self, processor, tmp_path):
        folder = tmp_path / "downloads" / "folder1"
        folder.mkdir(parents=True)
        
        (folder / "video.mp4").touch()
        (folder / "audio.mp3").touch()
        (folder / "text.txt").touch()
        
        media = processor.find_media_files(folder)
        assert len(media) == 2
        assert any(f.name == "video.mp4" for f in media)
        assert any(f.name == "audio.mp3" for f in media)

    @patch('module2_transcribe.LocalEars')
    def test_process_folder_success(self, mock_local_ears, processor, tmp_path):
        # Setup folder with video
        folder = tmp_path / "downloads" / "test_folder"
        folder.mkdir(parents=True)
        video = folder / "video.mp4"
        video.touch()
        
        # Mock Transcription result
        mock_instance = mock_local_ears.return_value
        # Important: inject the mock instance into the processor because it's initialized in __init__
        # But we are testing limits of patching. simpler to patch processor.ears directly after init
        
        mock_result = TranscriptResult(
            full_text="Test transcription content",
            timed_transcript="[00:00] Test transcription content",
            language="en",
            duration=10.0
        )
        processor.ears.transcribe = Mock(return_value=mock_result)
        processor.ears.model_size = "small" # needed for Markdown generation
        
        stats = processor.process_folder(folder)
        
        assert stats['success'] is True
        assert (folder / "transcript.md").exists()
        
        content = (folder / "transcript.md").read_text()
        assert "Test transcription content" in content
        assert "duration: 10.0" in content

    def test_process_folder_skip_existing(self, processor, tmp_path):
        folder = tmp_path / "downloads" / "test_folder_existing"
        folder.mkdir(parents=True)
        (folder / "transcript.md").touch()
        
        stats = processor.process_folder(folder)
        
        assert stats['already_has_transcript'] is True
        assert stats['success'] is False

    def test_process_folder_no_media(self, processor, tmp_path):
        folder = tmp_path / "downloads" / "test_folder_empty"
        folder.mkdir(parents=True)
        
        stats = processor.process_folder(folder)
        
        assert stats['no_media'] is True
        assert stats['success'] is False
