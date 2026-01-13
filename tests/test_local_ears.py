"""
Unit Tests for LocalEars (Whisper Transcription)
===============================================

Тесты для модуля транскрибации через faster-whisper.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock

from modules.local_ears import LocalEars, TranscriptResult


class TestLocalEars:
    """Тесты для LocalEars"""
    
    def test_init_default_config(self):
        """Тест инициализации с настройками по умолчанию"""
        ears = LocalEars()
        
        assert ears.model_size == "small"
        assert ears.device == "cpu"
        assert ears.num_threads == 16
        assert ears.compute_type == "int8"
    
    def test_init_custom_config(self):
        """Тест инициализации с кастомными настройками"""
        ears = LocalEars(
            model_size="base",
            device="cuda",
            num_threads=8,
            compute_type="float16"
        )
        
        assert ears.model_size == "base"
        assert ears.device == "cuda"
        assert ears.num_threads == 8
        assert ears.compute_type == "float16"
    
    @patch('modules.local_ears.LocalEars.load_model')
    def test_transcribe_basic(self, mock_load_model, tmp_path):
        """Тест базовой транскрибации"""
        # Создаём фейковый аудио файл
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("fake audio")
        
        ears = LocalEars()
        
        # Мокаем модель
        mock_model = MagicMock()
        mock_segment = MagicMock()
        mock_segment.start = 0.0
        mock_segment.end = 5.0
        mock_segment.text = " Тестовая транскрипция"
        
        # Создаём мок info с атрибутами (не словарь)
        mock_info = MagicMock()
        mock_info.language = "ru"
        mock_info.duration = 5.0
        
        mock_model.transcribe.return_value = (
            [mock_segment],  # segments
            mock_info  # info с атрибутами
        )
        ears.model = mock_model
        
        # Передаём Path, а не str
        result = ears.transcribe(audio_file)
        
        assert isinstance(result, TranscriptResult)
        assert result.language == "ru"
        assert "Тестовая транскрипция" in result.full_text
    
    def test_format_timestamp_seconds(self):
        """Тест форматирования таймкодов (секунды)"""
        ears = LocalEars()
        
        assert ears._format_timestamp(0) == "00:00"
        assert ears._format_timestamp(45) == "00:45"
        assert ears._format_timestamp(90) == "01:30"
        assert ears._format_timestamp(3600) == "60:00"  # 1 час = 60 минут

