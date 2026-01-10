#!/usr/bin/env python3
"""
SecBrain Process Script
Обрабатывает все необработанные папки в SecondBrain_Inbox:
- Запускает AI анализ через LocalBrain
- Создаёт теги через TagManager
- Формирует финальный Note.md
Пропускает папки, где Note.md уже существует.
"""

import sys
from pathlib import Path
from typing import List, Optional
from rich.console import Console
from rich.panel import Panel

from config import Config
from modules.local_brain import LocalBrain
from modules.tag_manager import TagManager

console = Console()


def print_banner():
    """Отображает баннер программы"""
    banner = """
    ╔═══════════════════════════════════════════╗
    ║     🧠 SecBrain - AI Processing          ║
    ║   Process Unprocessed Instagram Data     ║
    ╚═══════════════════════════════════════════╝
    """
    console.print(Panel(banner, style="bold magenta"))


class ContentData:
    """Класс для хранения сырых данных из папки"""
    def __init__(self, folder: Path):
        self.folder = folder
        self.caption = self._read_file("caption.md")
        self.transcript = self._read_file("transcript.md")
        self.comments = self._read_file("comments.md")
        self.media_files = self._get_media_files()
        
    def _read_file(self, filename: str) -> Optional[str]:
        """Читает файл из папки"""
        file_path = self.folder / filename
        if file_path.exists():
            return file_path.read_text(encoding='utf-8')
        return None
    
    def _get_media_files(self) -> List[Path]:
        """Получает список медиа-файлов"""
        extensions = {'.jpg', '.jpeg', '.png', '.mp4', '.mov', '.avi', '.mkv'}
        return sorted([
            f for f in self.folder.iterdir()
            if f.suffix.lower() in extensions
        ])
    
    def get_text_for_analysis(self) -> str:
        """Формирует текст для AI анализа"""
        parts = []
        
        if self.caption:
            # Извлекаем только текст caption без заголовков
            caption_text = self.caption.strip()
            parts.append(f"ОПИСАНИЕ ПОСТА:\n{caption_text}")
        
        if self.transcript:
            # Извлекаем чистый текст транскрипции
            lines = self.transcript.split('\n')
            clean_text = []
            in_clean_section = False
            
            for line in lines:
                if "## Чистый текст" in line:
                    in_clean_section = True
                    continue
                if in_clean_section and line.strip():
                    clean_text.append(line.strip())
            
            if clean_text:
                parts.append(f"ТРАНСКРИПЦИЯ ВИДЕО:\n{' '.join(clean_text)}")
        
        if self.comments:
            # Извлекаем комментарии
            lines = self.comments.split('\n')
            comments_text = []
            
            for line in lines:
                if line.startswith('**Автор:**') or line.startswith('###'):
                    continue
                if line.strip() and not line.startswith('#') and not line.startswith('**') and line != '---':
                    comments_text.append(line.strip())
            
            if comments_text:
                parts.append(f"КОММЕНТАРИИ:\n{' '.join(comments_text[:20])}")  # Ограничиваем количество
        
        return "\n\n".join(parts)


def find_unprocessed_folders(inbox_dir: Path) -> List[Path]:
    """
    Находит все папки без Note.md
    
    Args:
        inbox_dir: Путь к SecondBrain_Inbox
        
    Returns:
        Список путей к необработанным папкам
    """
    unprocessed = []
    
    if not inbox_dir.exists():
        console.print(f"⚠️  Директория {inbox_dir} не найдена", style="yellow")
        return unprocessed
    
    for folder in inbox_dir.iterdir():
        if folder.is_dir():
            note_file = folder / "Note.md"
            if not note_file.exists():
                # Проверяем, что есть хотя бы один из файлов данных
                has_data = (
                    (folder / "caption.md").exists() or
                    (folder / "transcript.md").exists() or
                    any(f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.mp4'] for f in folder.iterdir())
                )
                if has_data:
                    unprocessed.append(folder)
    
    return sorted(unprocessed)


def extract_metadata_from_folder(folder: Path) -> dict:
    """
    Извлекает метаданные из имени папки и файлов
    
    Args:
        folder: Путь к папке
        
    Returns:
        Словарь с метаданными
    """
    parts = folder.name.split('_', 2)
    
    metadata = {
        'date': parts[0] if len(parts) > 0 else 'unknown',
        'author': parts[1] if len(parts) > 1 else 'unknown',
        'title': parts[2] if len(parts) > 2 else folder.name,
        'url': 'unknown'
    }
    
    # Пытаемся извлечь URL из caption или transcript
    caption_file = folder / "caption.md"
    if caption_file.exists():
        caption_text = caption_file.read_text(encoding='utf-8')
        # Можно добавить парсинг URL если он есть в caption
    
    return metadata


def create_note(folder: Path, ai_summary: str, tags: List[str], metadata: dict, content_data: ContentData):
    """
    Создаёт финальный Note.md
    
    Args:
        folder: Путь к папке
        ai_summary: AI резюме
        tags: Список тегов
        metadata: Метаданные
        content_data: Объект с сырыми данными
    """
    note_path = folder / "Note.md"
    
    # Формируем frontmatter
    note_content = "---\n"
    note_content += f"created: {metadata['date']}\n"
    note_content += f"author: {metadata['author']}\n"
    note_content += f"url: {metadata['url']}\n"
    note_content += "category: inbox\n"
    note_content += "tags:\n"
    for tag in tags:
        note_content += f"  - {tag}\n"
    note_content += "---\n\n"
    
    # Заголовок
    note_content += f"# {metadata['author']}: {metadata['title']}\n\n"
    
    # Медиа-файлы
    for media_file in content_data.media_files:
        note_content += f"![[{media_file.name}]]\n"
    note_content += "\n"
    
    # AI Summary
    note_content += "## 🧠 AI Summary\n"
    note_content += f"{ai_summary}\n\n"
    
    # Valuable Insights (можно добавить извлечение из комментариев)
    note_content += "## 💬 Valuable Insights (Comments)\n"
    note_content += "_No valuable comments found_\n\n"
    
    note_content += "---\n"
    note_content += '<details>\n<summary>📂 Raw Data (Transcript & Caption)</summary>\n\n'
    
    # Caption
    if content_data.caption:
        note_content += "### Caption\n"
        note_content += f"{content_data.caption}\n\n"
    
    # Transcript (короткая версия)
    if content_data.transcript:
        lines = content_data.transcript.split('\n')
        clean_section = False
        transcript_lines = []
        
        for line in lines:
            if "## С таймкодами" in line:
                clean_section = True
                continue
            if "## Чистый текст" in line:
                break
            if clean_section and line.strip() and not line.startswith('#') and not line.startswith('**'):
                transcript_lines.append(line)
        
        if transcript_lines:
            note_content += "### Transcript\n"
            note_content += '\n'.join(transcript_lines[:20])  # Первые 20 строк
            note_content += "\n"
    
    note_content += "</details>\n"
    
    # Сохраняем
    note_path.write_text(note_content, encoding='utf-8')
    console.print(f"   ✅ Note.md создан")


def process_folder(folder: Path, config: Config, brain: LocalBrain, tag_manager: TagManager):
    """
    Обрабатывает одну папку
    
    Args:
        folder: Путь к папке
        config: Конфигурация
        brain: Экземпляр LocalBrain
        tag_manager: Экземпляр TagManager
    """
    console.print(f"\n📁 Обработка: [cyan]{folder.name}[/cyan]")
    
    try:
        # 1. Загружаем сырые данные
        console.print("   📖 Чтение данных...")
        content_data = ContentData(folder)
        
        if not content_data.media_files:
            console.print("   ⚠️  Нет медиа-файлов, пропускаем", style="yellow")
            return False
        
        # 2. Формируем текст для AI
        text_for_ai = content_data.get_text_for_analysis()
        
        if not text_for_ai.strip():
            console.print("   ⚠️  Нет текста для анализа", style="yellow")
            ai_summary = "Контент без текстового описания"
            ai_result = None
        else:
            # 3. AI анализ
            console.print("   🧠 AI анализ...")
            console.print(f"   📊 Размер текста: {len(text_for_ai)} символов")
            
            # Подготовка данных для analyze
            caption = content_data.caption or ""
            transcript = content_data.transcript or ""
            
            # Извлекаем комментарии как список
            comments_list = []
            if content_data.comments:
                lines = content_data.comments.split('\n')
                current_comment = ""
                for line in lines:
                    if line.strip() and not line.startswith('#') and not line.startswith('**') and line != '---':
                        current_comment += line.strip() + " "
                    if line == '---' and current_comment:
                        comments_list.append(current_comment.strip())
                        current_comment = ""
            
            # Получаем known_tags
            known_tags_str = ", ".join(sorted(tag_manager.known_tags))
            
            # Извлекаем автора из метаданных
            metadata = extract_metadata_from_folder(folder)
            author = metadata['author']
            
            # Вызываем analyze с правильными параметрами
            ai_result = brain.analyze(
                caption=caption,
                transcript=transcript,
                comments=comments_list,
                author=author,
                known_tags=known_tags_str
            )
            
            if not ai_result:
                console.print("   ⚠️  AI анализ не удался, использую дефолтные значения", style="yellow")
                ai_summary = "AI анализ не доступен"
            else:
                ai_summary = ai_result.get('summary', 'AI анализ не доступен')
        
        # 4. Генерация тегов
        console.print("   🏷️  Генерация тегов...")
        
        if ai_result and 'tags' in ai_result:
            tags = ai_result['tags']
            # Добавляем новые теги в базу
            tag_manager.add_tags(tags)
        else:
            tags = ['inbox']
        
        console.print(f"   📌 Теги: {', '.join(tags)}")
        
        # 5. Извлечение метаданных
        metadata = extract_metadata_from_folder(folder)
        
        # 6. Создание Note.md
        console.print("   📝 Создание Note.md...")
        create_note(folder, ai_summary, tags, metadata, content_data)
        
        console.print(f"   ✅ Папка обработана успешно\n")
        return True
        
    except KeyboardInterrupt:
        # Пробрасываем Ctrl+C выше
        raise
    except Exception as e:
        console.print(f"   ❌ Ошибка: {e}", style="red")
        import traceback
        console.print(f"   🔍 Traceback: {traceback.format_exc()[:500]}", style="dim")
        return False


def main():
    """Главная функция"""
    print_banner()
    
    # Загрузка конфигурации
    config = Config()
    
    console.print(f"📁 Inbox: {config.output_dir}")
    console.print(f"🤖 Model: {config.ollama_model}")
    console.print(f"🔧 Threads: {config.num_threads}\n")
    
    # Инициализация модулей
    console.print("⚙️  Инициализация AI модулей...")
    brain = LocalBrain(
        model=config.ollama_model,
        base_url=f"http://localhost:{config.get('ollama_port', 11434)}"
    )
    brain.num_threads = config.num_threads
    brain.num_ctx = config.get('num_ctx', 8192)
    
    # Прогрев модели
    brain.warm_up()
    
    tag_manager = TagManager(config)
    console.print("✅ Модули готовы\n")
    
    # Поиск необработанных папок
    inbox_path = Path(config.output_dir)
    console.print("🔍 Поиск необработанных папок...")
    
    unprocessed = find_unprocessed_folders(inbox_path)
    
    if not unprocessed:
        console.print("✅ Все папки уже обработаны!", style="green")
        return
    
    console.print(f"📊 Найдено необработанных папок: {len(unprocessed)}\n")
    
    # Обработка папок
    successful = 0
    failed = 0
    
    try:
        for i, folder in enumerate(unprocessed, 1):
            console.print(f"\n{'='*60}")
            console.print(f"[{i}/{len(unprocessed)}] Обработка: {folder.name}")
            console.print('='*60)
            
            result = process_folder(folder, config, brain, tag_manager)
            
            if result:
                successful += 1
            else:
                failed += 1
                
    except KeyboardInterrupt:
        console.print("\n\n⚠️  Прервано пользователем", style="yellow")
    
    # Статистика
    console.print("\n" + "=" * 60)
    console.print("📊 Статистика обработки:", style="bold")
    console.print(f"   ✅ Успешно: {successful}")
    console.print(f"   ❌ Ошибки: {failed}")
    console.print(f"   📁 Всего: {len(unprocessed)}")
    console.print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n👋 Прервано пользователем")
        sys.exit(0)
