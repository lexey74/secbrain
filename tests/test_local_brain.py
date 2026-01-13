"""
Unit Tests for LocalBrain (AI Analysis)
========================================

Тесты для модуля AI анализа контента через Ollama.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock

from modules.local_brain import LocalBrain


class TestLocalBrain:
    """Тесты для LocalBrain"""
    
    def test_init_default_model(self):
        """Тест инициализации с моделью по умолчанию"""
        brain = LocalBrain()
        
        assert brain.model == "llama3.2"
        assert brain.base_url == "http://localhost:11434"
    
    def test_init_custom_model(self):
        """Тест инициализации с кастомной моделью"""
        brain = LocalBrain(
            model="qwen2.5:7b",
            base_url="http://192.168.1.10:11434"
        )
        
        assert brain.model == "qwen2.5:7b"
        assert brain.base_url == "http://192.168.1.10:11434"
    
    def test_build_prompt_basic(self):
        """Тест построения промпта"""
        brain = LocalBrain()
        
        prompt = brain._build_prompt(
            caption="Test caption",
            transcript="",
            comments=[],
            author="test_user"
        )
        
        assert "test_user" in prompt
        assert "Test caption" in prompt
    
    def test_build_prompt_with_transcript(self, sample_transcript):
        """Тест построения промпта с транскрипцией"""
        brain = LocalBrain()
        
        prompt = brain._build_prompt(
            caption="Test",
            transcript=sample_transcript,
            comments=[],
            author="test_user"
        )
        
        assert "TRANSCRIPT" in prompt or sample_transcript in prompt
    
    def test_build_prompt_with_comments(self):
        """Тест построения промпта с комментариями"""
        brain = LocalBrain()
        
        comments = [
            "user1: Great video!",
            "user2: Thanks for sharing"
        ]
        
        prompt = brain._build_prompt(
            caption="Test",
            transcript="",
            comments=comments,
            author="test_user"
        )
        
        assert "user1" in prompt or "COMMENTS" in prompt

