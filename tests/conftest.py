"""
Pytest Configuration and Fixtures
==================================

Общие фикстуры и настройки для всех тестов.
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))


@pytest.fixture
def temp_dir(tmp_path):
    """Временная директория для тестов"""
    return tmp_path


@pytest.fixture
def mock_tags_file(tmp_path):
    """Mock файл с тегами"""
    tags_file = tmp_path / "test_tags.json"
    tags_file.write_text('{"tags": ["test", "example", "mock"]}')
    return tags_file


@pytest.fixture
def sample_tags():
    """Образец тегов для тестов"""
    return ["python", "ai", "testing", "automation"]


@pytest.fixture
def sample_transcript():
    """Образец транскрипции"""
    return """[00:00] Привет, это тестовая транскрипция
[00:05] Здесь мы тестируем работу системы
[00:10] Проверяем правильность обработки текста"""


@pytest.fixture
def sample_description():
    """Образец описания контента"""
    return """Тестовое видео о программировании
    
#python #testing #automation

Автор: Test User
Ссылка: https://example.com/test"""


@pytest.fixture
def mock_ollama_response():
    """Mock ответ от Ollama"""
    return {
        'summary': 'Это тестовое резюме контента',
        'tags': ['test', 'example', 'mock'],
        'title': 'Тестовое видео',
        'key_points': [
            'Первый ключевой момент',
            'Второй ключевой момент',
            'Третий ключевой момент'
        ]
    }


@pytest.fixture
def mock_whisper_result():
    """Mock результат транскрибации Whisper"""
    return {
        'text': 'Это тестовая транскрипция',
        'segments': [
            {'start': 0.0, 'end': 5.0, 'text': 'Привет, это тестовая транскрипция'},
            {'start': 5.0, 'end': 10.0, 'text': 'Здесь мы тестируем работу системы'},
            {'start': 10.0, 'end': 15.0, 'text': 'Проверяем правильность обработки текста'}
        ]
    }
