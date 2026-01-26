"""
Configuration management for SecBrain
"""
import os
from pathlib import Path
from typing import Dict, Any
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Config:
    """Управление конфигурацией с поддержкой переменных окружения"""
    
    def __init__(self, config_file: Path = None):
        """
        Загрузка конфигурации
        
        Приоритет:
        1. Переменные окружения
        2. Файл config.json
        3. Значения по умолчанию
        """
        self.config_file = config_file or Path('config.json')
        
        # Base Data Directory
        # В Docker это будет /app/data, локально - ./data
        self.data_dir = Path(os.getenv('DATA_DIR', 'data'))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Default Configuration
        self.defaults = {
            # Paths (relative to data_dir unless absolute)
            'output_dir': str(self.data_dir / 'inbox'),
            'temp_dir': str(self.data_dir / 'temp'),
            'config_dir': str(self.data_dir / 'config'), # Для куки, сессий и т.д.
            
            # Models
            'whisper_model': 'base',
            'whisper_compute_type': 'int8',
            'ollama_base_url': 'http://localhost:11434', # URL для Ollama
            'ollama_model': 'mistral-nemo',
            'device': 'cpu',
            
            # Performance
            'num_threads': 4,
            'num_ctx': 8192,
            
            # Limits
            'max_comments': 50,
            'max_tags': 15,
            
            # RAG
            'RAG_EMBEDDING_MODEL': 'all-MiniLM-L6-v2',
            'RAG_SEARCH_TOP_K': 5,
        }
        
        # In-memory config
        self.data = self.defaults.copy()
        
        # Load from file
        if self.config_file.exists():
            self.load_from_file()
            
        # Override with Environment Variables
        self.load_from_env()
        
        # Ensure directories exist
        self._ensure_dirs()
        
    def load_from_file(self) -> None:
        """Загрузка из файла config.json"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                self.data.update(user_config)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"⚠️ Ошибка чтения конфига: {e}")

    def load_from_env(self) -> None:
        """Переопределение настроек из переменных окружения"""
        # Mapping: Env Var -> Config Key
        env_map = {
            'OUTPUT_DIR': 'output_dir',
            'TEMP_DIR': 'temp_dir',
            'WHISPER_MODEL': 'whisper_model',
            'OLLAMA_HOST': 'ollama_base_url', # Standard Ollama env var is usually OLLAMA_HOST or OLLAMA_BASE_URL
            'OLLAMA_MODEL': 'ollama_model',
            'DEVICE': 'device',
            'NUM_THREADS': 'num_threads'
        }
        
        for env_key, config_key in env_map.items():
            val = os.getenv(env_key)
            if val is not None:
                # Basic type conversion if needed
                if config_key == 'num_threads':
                    try:
                        val = int(val)
                    except ValueError:
                        continue
                self.data[config_key] = val
                
    def _ensure_dirs(self):
        """Создание необходимых директорий"""
        for key in ['output_dir', 'temp_dir']:
            path = Path(self.data[key])
            try:
                path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.error(f"Could not create directory {path}: {e}")

    # --- Backward Compatibility APIs ---
    
    def get(self, key: str, default=None):
        return self.data.get(key, default)
    
    def __getattr__(self, key: str):
        if key in self.data:
            return self.data[key]
        # Specific getters for derived paths
        if key == 'cookies_file':
            return str(Path(self.data.get('config_dir', 'data/config')) / 'cookies.txt')
        if key == 'session_file':
            return str(Path(self.data.get('config_dir', 'data/config')) / 'session.json')
        if key == 'tags_file':
            return str(Path(self.data.get('config_dir', 'data/config')) / 'known_tags.json')
            
        return object.__getattribute__(self, key)
