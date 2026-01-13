#!/usr/bin/env python3
"""
Модуль 2: Транскрибация видео и аудио

Проходит по папкам с контентом и создает транскрибации для видео/аудио файлов,
у которых еще нет файла транскрипции.
"""
from pathlib import Path
from typing import List, Optional
import sys

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent))

from src.modules.local_ears import LocalEars


class TranscriptionProcessor:
    """
    Процессор транскрибации
    
    Сканирует папки, находит видео/аудио без транскрипции,
    создает транскрипцию с таймингами и сохраняет в Markdown.
    """
    
    def __init__(self, content_dir: Path = Path("downloads")):
        """
        Args:
            content_dir: Директория с папками контента
        """
        self.content_dir = Path(content_dir)
        self.ears = LocalEars()
        
        # Поддерживаемые форматы
        self.video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm']
        self.audio_extensions = ['.mp3', '.m4a', '.wav', '.flac', '.ogg']
        self.media_extensions = self.video_extensions + self.audio_extensions
    
    def find_content_folders(self) -> List[Path]:
        """
        Находит все папки с контентом
        
        Returns:
            Список путей к папкам
        """
        if not self.content_dir.exists():
            print(f"❌ Директория не найдена: {self.content_dir}")
            return []
        
        # Сканируем ВСЕ папки в downloads (не только instagram/youtube)
        folders = []
        for item in self.content_dir.iterdir():
            if item.is_dir():
                folders.append(item)
        
        return sorted(folders)
    
    def find_media_files(self, folder: Path) -> List[Path]:
        """
        Находит медиа файлы в папке
        
        Args:
            folder: Папка для поиска
            
        Returns:
            Список путей к медиа файлам
        """
        media_files = []
        for file in folder.iterdir():
            if file.is_file() and file.suffix.lower() in self.media_extensions:
                media_files.append(file)
        return sorted(media_files)
    
    def has_transcript(self, folder: Path) -> bool:
        """
        Проверяет, есть ли уже транскрипция
        
        Args:
            folder: Папка для проверки
            
        Returns:
            True если transcript.md существует
        """
        transcript_file = folder / "transcript.md"
        return transcript_file.exists()
    
    def transcribe_file(self, media_file: Path, output_folder: Path) -> Optional[Path]:
        """
        Транскрибирует один медиа файл
        
        Args:
            media_file: Путь к медиа файлу
            output_folder: Папка для сохранения транскрипции
            
        Returns:
            Путь к созданному transcript.md или None при ошибке
        """
        file_size_mb = media_file.stat().st_size / 1024 / 1024
        
        print(f"\n{'='*70}")
        print(f"🎤 НАЧАТА ТРАНСКРИБАЦИЯ")
        print(f"{'='*70}")
        print(f"📄 Файл: {media_file.name}")
        print(f"📦 Размер: {file_size_mb:.1f} MB")
        print(f"📁 Папка: {output_folder.name}")
        print(f"{'='*70}")
        
        try:
            # Запускаем транскрибацию
            print(f"⏳ Запуск Whisper (модель: {self.ears.model_size})...")
            print(f"   Это может занять несколько минут...")
            
            import time
            start_time = time.time()
            
            transcript = self.ears.transcribe(media_file)
            
            elapsed_time = time.time() - start_time
            elapsed_time = time.time() - start_time
            
            if not transcript:
                print(f"\n❌ ОШИБКА: Whisper не вернул результат")
                print(f"{'='*70}\n")
                return None
            
            print(f"\n✅ Транскрибация завершена за {elapsed_time:.1f} секунд")
            print(f"   Язык: {transcript.language}")
            print(f"   Длительность: {transcript.duration:.1f} сек")
            
            # Создаем transcript.md
            transcript_file = output_folder / "transcript.md"
            
            print(f"\n📝 Сохранение в Markdown...")
            
            # Формируем Markdown с YAML frontmatter
            from datetime import datetime
            
            markdown = "---\n"
            markdown += f"title: Транскрипция {media_file.stem}\n"
            markdown += f"date: {datetime.now().strftime('%Y-%m-%d')}\n"
            markdown += f"media_file: {media_file.name}\n"
            markdown += f"whisper_model: {self.ears.model_size}\n"
            markdown += f"language: {transcript.language}\n"
            markdown += f"duration: {transcript.duration:.1f}\n"
            markdown += f"type: transcript\n"
            markdown += "---\n\n"
            
            markdown += f"# Транскрипция\n\n"
            markdown += f"**Файл**: `{media_file.name}`\n"
            markdown += f"**Модель**: `{self.ears.model_size}`\n"
            markdown += f"**Язык**: `{transcript.language}`\n"
            markdown += f"**Длительность**: `{transcript.duration:.1f}` секунд\n\n"
            markdown += "---\n\n"
            
            # Добавляем транскрипт с таймингами
            markdown += transcript.timed_transcript
            markdown += "\n\n---\n\n"
            markdown += "## Полный текст (без таймингов)\n\n"
            markdown += transcript.full_text
            markdown += "\n"
            
            # Сохраняем
            transcript_file.write_text(markdown, encoding='utf-8')
            
            print(f"✅ Сохранено: transcript.md ({transcript_file.stat().st_size / 1024:.1f} KB)")
            print(f"{'='*70}")
            print(f"🎉 ТРАНСКРИБАЦИЯ ЗАВЕРШЕНА УСПЕШНО")
            print(f"{'='*70}\n")
            
            return transcript_file
            
        except Exception as e:
            print(f"\n{'='*70}")
            print(f"❌ ОШИБКА ТРАНСКРИБАЦИИ")
            print(f"{'='*70}")
            print(f"Ошибка: {e}")
            import traceback
            traceback.print_exc()
            print(f"{'='*70}\n")
            return None
    
    def _format_timestamp(self, seconds: float) -> str:
        """
        Форматирует таймстемп из секунд в MM:SS
        
        Args:
            seconds: Время в секундах
            
        Returns:
            Строка формата MM:SS или HH:MM:SS
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"
    
    def process_folder(self, folder: Path) -> dict:
        """
        Обрабатывает одну папку
        
        Args:
            folder: Папка для обработки
            
        Returns:
            Статистика обработки
        """
        stats = {
            'folder': folder.name,
            'already_has_transcript': False,
            'no_media': False,
            'success': False,
            'error': None
        }
        
        print(f"\n📂 Проверка папки: {folder.name[:80]}...")
        
        # Проверяем, есть ли уже транскрипция
        if self.has_transcript(folder):
            print(f"   ⏭️  Пропуск: транскрипция уже существует")
            stats['already_has_transcript'] = True
            return stats
        
        # Ищем медиа файлы
        media_files = self.find_media_files(folder)
        
        if not media_files:
            print(f"   ⏭️  Пропуск: нет медиа файлов")
            stats['no_media'] = True
            return stats
        
        # Берем первый медиа файл (обычно один)
        media_file = media_files[0]
        
        print(f"   ▶️  Найден медиа файл: {media_file.name}")
        
        # Транскрибируем
        transcript_file = self.transcribe_file(media_file, folder)
        
        if transcript_file:
            stats['success'] = True
        else:
            stats['error'] = "Ошибка транскрибации"
        
        return stats
    
    def process_all(self) -> dict:
        """
        Обрабатывает все папки
        
        Returns:
            Общая статистика
        """
        print("\n" + "="*70)
        print("🎤 МОДУЛЬ 2: ТРАНСКРИБАЦИЯ")
        print("="*70)
        print(f"📁 Директория: {self.content_dir}")
        print(f"🤖 Модель Whisper: {self.ears.model_size}")
        print(f"⏱️  Время запуска: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)
        
        # Находим папки
        print(f"\n🔍 Сканирование директории...")
        folders = self.find_content_folders()
        
        if not folders:
            print("\n⚠️  Папки с контентом не найдены")
            print("="*70)
            return {'total_folders': 0}
        
        print(f"✅ Найдено папок: {len(folders)}")
        
        # Общая статистика
        total_stats = {
            'total_folders': len(folders),
            'already_has_transcript': 0,
            'no_media': 0,
            'successfully_transcribed': 0,
            'errors': 0,
            'start_time': __import__('time').time()
        }
        
        # Обрабатываем каждую папку
        for i, folder in enumerate(folders, 1):
            print(f"\n{'='*70}")
            print(f"📂 ПАПКА [{i}/{len(folders)}]")
            print(f"{'='*70}")
            print(f"📌 {folder.name[:80]}")
            print(f"{'='*70}")
            
            stats = self.process_folder(folder)
            
            if stats['already_has_transcript']:
                total_stats['already_has_transcript'] += 1
            elif stats['no_media']:
                total_stats['no_media'] += 1
            elif stats['success']:
                total_stats['successfully_transcribed'] += 1
                print(f"\n✅ [{i}/{len(folders)}] Завершено успешно")
            else:
                total_stats['errors'] += 1
                print(f"\n❌ [{i}/{len(folders)}] Ошибка обработки")
        
        # Вычисляем время
        elapsed_time = __import__('time').time() - total_stats['start_time']
        hours = int(elapsed_time // 3600)
        minutes = int((elapsed_time % 3600) // 60)
        seconds = int(elapsed_time % 60)
        
        # Итоговая статистика
        print("\n" + "="*70)
        print("📊 ИТОГОВАЯ СТАТИСТИКА")
        print("="*70)
        print(f"📂 Всего папок: {total_stats['total_folders']}")
        print(f"⏭️  Уже есть транскрипция: {total_stats['already_has_transcript']}")
        print(f"⏭️  Нет медиа файлов: {total_stats['no_media']}")
        print(f"✅ Успешно транскрибировано: {total_stats['successfully_transcribed']}")
        if total_stats['errors'] > 0:
            print(f"❌ Ошибок: {total_stats['errors']}")
        
        # Время выполнения
        if hours > 0:
            print(f"⏱️  Время выполнения: {hours}ч {minutes}м {seconds}с")
        elif minutes > 0:
            print(f"⏱️  Время выполнения: {minutes}м {seconds}с")
        else:
            print(f"⏱️  Время выполнения: {seconds}с")
        
        print("="*70)
        
        if total_stats['successfully_transcribed'] > 0:
            print(f"\n🎉 Транскрибация завершена успешно!")
        else:
            print(f"\n⚠️  Новых транскрипций не создано")
            
            # Подсчитываем, что осталось обработать
            pending_transcribe = 0
            pending_ai = 0
            
            for folder in folders:
                has_transcript = (folder / "transcript.md").exists()
                has_analysis = (folder / "Knowledge.md").exists()  # Модуль 3 создает Knowledge.md
                
                # Проверяем наличие медиа файлов (видео + аудио)
                media_files = [
                    f for f in folder.iterdir() 
                    if f.is_file() and f.suffix.lower() in self.media_extensions
                ]
                
                if media_files and not has_transcript:
                    pending_transcribe += 1
                elif has_transcript and not has_analysis:
                    pending_ai += 1
            
            if pending_transcribe > 0 or pending_ai > 0:
                print(f"\n📋 Статус обработки:")
                print(f"   🎤 Требуют транскрибации: {pending_transcribe}")
                print(f"   🤖 Требуют AI анализа: {pending_ai}")
        
        print("="*70 + "\n")
        
        return total_stats


def main():
    """Точка входа"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Модуль 2: Транскрибация видео и аудио"
    )
    parser.add_argument(
        '--dir',
        type=Path,
        default=Path('downloads'),
        help='Директория с контентом (по умолчанию: downloads)'
    )
    parser.add_argument(
        '--folder',
        type=str,
        help='Обработать только одну папку (имя папки)'
    )
    
    args = parser.parse_args()
    
    processor = TranscriptionProcessor(content_dir=args.dir)
    
    if args.folder:
        # Обработка одной папки
        folder_path = args.dir / args.folder
        if not folder_path.exists():
            print(f"❌ Папка не найдена: {folder_path}")
            sys.exit(1)
        
        print(f"\n🎯 Обработка одной папки: {args.folder}")
        stats = processor.process_folder(folder_path)
        
        print("\n" + "="*70)
        print("📊 СТАТИСТИКА")
        print("="*70)
        if stats['already_has_transcript']:
            print("⏭️  Транскрипция уже существует")
        elif stats['no_media']:
            print("⏭️  Нет медиа файлов")
        elif stats['success']:
            print("✅ Успешно транскрибировано")
        else:
            print(f"❌ Ошибка: {stats['error']}")
    else:
        # Обработка всех папок
        processor.process_all()


if __name__ == "__main__":
    main()
