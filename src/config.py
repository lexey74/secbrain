"""
Configuration management for SecBrain
"""
from pathlib import Path
from typing import Dict
import json


DEFAULT_CONFIG = {
    # Paths
    'output_dir': 'SecondBrain_Inbox',
    'temp_dir': '.temp',
    'cookies_file': 'cookies.txt',
    'session_file': 'session.json',
    'tags_file': 'known_tags.json',
    
    # Models
    'whisper_model': 'base',  # tiny, base, small, medium, large
    'ollama_model': 'mistral-nemo',  # или llama3.2
    'device': 'cpu',  # или cuda
    
    # Limits
    'max_comments': 50,
    'max_tags': 15,
}


class Config:
    """Управление конфигурацией"""
    
    def __init__(self, config_file: Path = None):
        """
        Загрузка конфигурации
        
        Args:
            config_file: Путь к config.json (опционально)
        """
        self.config_file = config_file or Path('config.json')
        self.data = DEFAULT_CONFIG.copy()
        
        if self.config_file.exists():
            self.load()
        else:
            self.save()
    
    def load(self) -> None:
        """Загрузка из файла"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                self.data.update(user_config)
        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️  Ошибка чтения конфига: {e}")
    
    def save(self) -> None:
        """Сохранение в файл"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
    
    def get(self, key: str, default=None):
        """Получение значения"""
        return self.data.get(key, default)
    
    def set(self, key: str, value) -> None:
        """Установка значения"""
        self.data[key] = value
        self.save()
    
    def as_dict(self) -> Dict:
        """Возврат конфига как словаря"""
        return self.data.copy()
