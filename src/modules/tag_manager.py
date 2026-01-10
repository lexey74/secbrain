"""
TagManager - Управление базой тегов для консистентности Knowledge Base
"""
import json
from pathlib import Path
from typing import List, Set


class TagManager:
    """Управляет списком известных тегов"""
    
    DEFAULT_TAGS = ["ai", "productivity", "coding", "health", "marketing"]
    
    def __init__(self, config=None):
        """
        Инициализация менеджера тегов
        
        Args:
            config: Config объект или путь к файлу known_tags.json
        """
        if config is None:
            tags_file = Path(__file__).parent.parent.parent / "known_tags.json"
        elif hasattr(config, 'tags_file'):
            tags_file = Path(config.tags_file)
        elif isinstance(config, (str, Path)):
            tags_file = Path(config)
        else:
            tags_file = Path(__file__).parent.parent.parent / "known_tags.json"
        
        self.tags_file = tags_file
        self.known_tags: Set[str] = set()
        self.load_tags()
    
    def load_tags(self) -> None:
        """Загрузка тегов из файла или создание с дефолтными"""
        if self.tags_file.exists():
            try:
                with open(self.tags_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.known_tags = set(data.get('tags', self.DEFAULT_TAGS))
            except (json.JSONDecodeError, IOError) as e:
                print(f"⚠️  Ошибка чтения {self.tags_file}: {e}")
                self.known_tags = set(self.DEFAULT_TAGS)
        else:
            # Создаем файл с дефолтными тегами
            self.known_tags = set(self.DEFAULT_TAGS)
            self.save_tags()
            print(f"✅ Создан новый файл тегов: {self.tags_file}")
    
    def save_tags(self) -> None:
        """Сохранение тегов в файл"""
        self.tags_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.tags_file, 'w', encoding='utf-8') as f:
            json.dump({
                'tags': sorted(list(self.known_tags))
            }, f, indent=2, ensure_ascii=False)
    
    def get_tags_string(self) -> str:
        """
        Возвращает строку с тегами для промпта
        
        Returns:
            Строка вида: "ai, productivity, coding, health, marketing"
        """
        return ", ".join(sorted(self.known_tags))
    
    def add_tags(self, new_tags: List[str]) -> int:
        """
        Добавляет новые уникальные теги в базу
        
        Args:
            new_tags: Список новых тегов
            
        Returns:
            Количество добавленных тегов
        """
        before_count = len(self.known_tags)
        
        # Нормализация и добавление
        normalized = {tag.strip().lower().replace(' ', '_') for tag in new_tags if tag.strip()}
        self.known_tags.update(normalized)
        
        added_count = len(self.known_tags) - before_count
        
        if added_count > 0:
            self.save_tags()
        
        return added_count
    
    def get_all_tags(self) -> List[str]:
        """Возвращает все известные теги"""
        return sorted(list(self.known_tags))
