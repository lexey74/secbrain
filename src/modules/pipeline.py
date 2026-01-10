"""
Pipeline - Оркестрация всего процесса обработки Instagram контента
"""
from pathlib import Path
from typing import Optional
from datetime import datetime
import re
from .tag_manager import TagManager
from .hybrid_grabber import HybridGrabber
from .local_ears import LocalEars
from .local_brain import LocalBrain


class SecBrainPipeline:
    """Главный пайплайн обработки"""
    
    def __init__(self, config: dict):
        """
        Инициализация пайплайна
        
        Args:
            config: Словарь с конфигурацией
        """
        self.config = config
        
        # Инициализация модулей
        self.tag_manager = TagManager()
        self.grabber = HybridGrabber(
            output_dir=Path(config['temp_dir']),
            cookies_file=Path(config.get('cookies_file', 'cookies.txt'))
        )
        self.ears = LocalEars(
            model_size=config.get('whisper_model', 'base'),
            device=config.get('device', 'cpu')
        )
        self.brain = LocalBrain(
            model=config.get('ollama_model', 'llama3.2')
        )
        
        # Настройка instagrapi если есть session
        session_file = Path(config.get('session_file', 'session.json'))
        if session_file.exists():
            self.grabber.setup_instagrapi(session_file)
    
    def process(self, url: str) -> Optional[Path]:
        """
        Полный цикл обработки Instagram URL
        
        Args:
            url: URL Instagram поста/рилса
            
        Returns:
            Путь к созданной заметке или None
        """
        print(f"\n{'='*60}")
        print(f"🚀 Обработка: {url}")
        print(f"{'='*60}\n")
        
        # Шаг 1: Загрузка контента
        content = self.grabber.grab(url)
        if not content.media_path:
            print("❌ Не удалось загрузить медиа")
            return None
        
        # Шаг 2: Транскрибация (если видео)
        transcript_result = self.ears.transcribe(content.media_path)
        transcript_text = transcript_result.timed_transcript if transcript_result else ""
        full_text = transcript_result.full_text if transcript_result else ""
        
        # Шаг 3: AI анализ
        known_tags_string = self.tag_manager.get_tags_string()
        
        ai_result = self.brain.analyze(
            caption=content.caption,
            transcript=transcript_text,
            comments=content.comments,
            author=content.author,
            known_tags=known_tags_string
        )
        
        if not ai_result:
            print("❌ Ошибка AI анализа")
            return None
        
        # Шаг 4: Обновление тегов
        new_tags = ai_result.get('tags', [])
        added_count = self.tag_manager.add_tags(new_tags)
        if added_count > 0:
            print(f"✅ Добавлено новых тегов: {added_count}")
        
        # Шаг 5: Создание Asset Bundle
        print("\n📝 Создание заметки...")
        try:
            note_path = self._create_note_bundle(
                content=content,
                ai_result=ai_result,
                transcript_text=transcript_text,
                full_text=full_text
            )
            print("   ✅ Заметка создана")
        except Exception as e:
            print(f"❌ Ошибка создания заметки: {e}")
            return None
        
        print(f"\n{'='*60}")
        print(f"✅ Готово! Заметка: {note_path}")
        print(f"{'='*60}\n")
        
        return note_path
    
    def _create_note_bundle(
        self,
        content,
        ai_result: dict,
        transcript_text: str,
        full_text: str
    ) -> Path:
        """
        Создание Asset Bundle (папка + Note.md + медиа)
        
        Args:
            content: InstagramContent
            ai_result: Результат AI анализа
            transcript_text: Транскрипт с таймкодами
            full_text: Чистый текст транскрипта
            
        Returns:
            Путь к Note.md
        """
        # Формирование имени папки
        date_str = content.date or datetime.now().strftime("%Y-%m-%d")
        author = self._sanitize_filename(content.author or "unknown")
        slug = self._generate_slug(ai_result.get('summary', 'note'))
        
        bundle_name = f"{date_str}_{author}_{slug}"
        bundle_path = Path(self.config['output_dir']) / bundle_name
        bundle_path.mkdir(parents=True, exist_ok=True)
        
        # Перемещение медиа в bundle
        media_ext = ".jpg"  # default
        if content.media_path and content.media_path.exists():
            media_ext = content.media_path.suffix
            media_dest = bundle_path / f"media{media_ext}"
            content.media_path.rename(media_dest)
        
        # Генерация Note.md
        note_content = self._generate_markdown(
            content=content,
            ai_result=ai_result,
            transcript_text=transcript_text,
            full_text=full_text,
            media_filename=f"media{media_ext}"
        )
        
        note_path = bundle_path / "Note.md"
        note_path.write_text(note_content, encoding='utf-8')
        
        return note_path
    
    def _generate_markdown(
        self,
        content,
        ai_result: dict,
        transcript_text: str,
        full_text: str,
        media_filename: str
    ) -> str:
        """Генерация Markdown заметки по шаблону"""
        
        tags_yaml = "\n".join(f"  - {tag}" for tag in ai_result.get('tags', []))
        tags_yaml += "\n  - inbox"
        
        # Форматирование комментариев
        comments_md = ""
        for comment in ai_result.get('valuable_comments', []):
            comments_md += f"> {comment}\n\n"
        
        # Генерация заголовка
        title = f"{content.author}: {self._generate_slug(ai_result.get('summary', 'Note'))}"
        
        template = f"""---
created: {content.date or datetime.now().strftime("%Y-%m-%d")}
author: {content.author}
url: {content.url}
category: {ai_result.get('category', 'Other')}
tags:
{tags_yaml}
---

# {title}

![[{media_filename}]]

## 🧠 AI Summary
{ai_result.get('summary', 'No summary available')}

## 💬 Valuable Insights (Comments)
{comments_md if comments_md else '_No valuable comments found_'}

---
<details>
<summary>📂 Raw Data (Transcript & Caption)</summary>

### Caption
{content.caption if content.caption else '_No caption_'}

### Transcript
{transcript_text if transcript_text else '_No transcript (image or transcription failed)_'}
</details>
"""
        return template
    
    def _sanitize_filename(self, text: str) -> str:
        """Очистка текста для использования в имени файла"""
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[-\s]+', '_', text)
        return text[:30].lower()
    
    def _generate_slug(self, text: str) -> str:
        """Генерация короткого slug из текста"""
        # Если это список, берём первый элемент
        if isinstance(text, list):
            text = text[0] if text else "note"
        # Если не строка, конвертируем
        if not isinstance(text, str):
            text = str(text)
        
        words = text.split()[:4]
        slug = "_".join(words)
        return self._sanitize_filename(slug)
