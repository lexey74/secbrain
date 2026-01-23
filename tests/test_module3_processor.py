import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from module3_analyze import AIProcessor

class TestAIProcessor:
    @pytest.fixture
    def processor(self, tmp_path):
        return AIProcessor(
            content_dir=tmp_path / "downloads",
            tags_file=tmp_path / "known_tags.json"
        )

    def test_should_process_folder(self, processor, tmp_path):
        folder = tmp_path / "downloads" / "test_folder"
        folder.mkdir(parents=True)
        
        # 1. No content -> False
        should, reason = processor.should_process_folder(folder)
        assert not should
        assert "нет контента" in reason

        # 2. Only Description -> True
        (folder / "description.md").touch()
        should, reason = processor.should_process_folder(folder)
        assert should
        assert "description.md" in reason

        # 3. Video but no transcript -> False
        (folder / "video.mp4").touch()
        should, reason = processor.should_process_folder(folder)
        assert not should
        assert "требуется Модуль 2" in reason

        # 4. Video + Transcript -> True
        (folder / "transcript.md").touch()
        should, reason = processor.should_process_folder(folder)
        assert should
        assert "transcript.md" in reason

        # 5. Already has Knowledge -> False
        (folder / "Knowledge.md").touch()
        should, reason = processor.should_process_folder(folder)
        assert not should
        assert "Knowledge.md существует" in reason

    @patch('module3_analyze.LocalBrain')
    @patch('module3_analyze.TagManager')
    def test_process_folder_success(self, mock_tag_manager, mock_local_brain, processor, tmp_path):
        folder = tmp_path / "downloads" / "instagram_user_ID123_Title"
        folder.mkdir(parents=True)
        (folder / "description.md").write_text("Test description")
        (folder / "transcript.md").write_text("Test transcript")
        
        # Inject mocks
        processor.brain = mock_local_brain.return_value
        processor.tag_manager = mock_tag_manager.return_value
        
        # Mock AI response
        processor.brain.analyze.return_value = {
            'summary': 'AI generated summary',
            'tags': ['tag1', 'tag2'],
            'category': 'Test Category'
        }
        processor.tag_manager.get_tags_string.return_value = "existing_tag"
        processor.tag_manager.add_tags.return_value = 2

        stats = processor.process_folder(folder)
        
        assert stats['success'] is True
        assert (folder / "Knowledge.md").exists()
        
        content = (folder / "Knowledge.md").read_text()
        assert "AI generated summary" in content
        assert "#tag1" in content
        assert "#tag2" in content
        assert "Test Category" in content

    def test_find_images(self, processor, tmp_path):
        folder = tmp_path / "downloads" / "img_folder"
        folder.mkdir(parents=True)
        (folder / "1.jpg").touch()
        (folder / "2.png").touch()
        (folder / "video.mp4").touch()
        
        images = processor.find_images(folder)
        assert len(images) == 2
