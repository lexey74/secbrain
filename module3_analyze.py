#!/usr/bin/env python3
"""
Модуль 3: AI Анализ контента

Анализирует изображения, описания и транскрипции.
Создает теги, саммари и сохраняет в Obsidian-совместимый Markdown.
"""
from pathlib import Path
from typing import List, Optional, Dict
import sys
from datetime import datetime

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.modules.local_brain import LocalBrain
from src.modules.tag_manager import TagManager
import threading


class AIProcessor:
    """
    Процессор AI анализа
    
    Анализирует контент, создает теги и саммари,
    сохраняет в Obsidian-совместимый формат.
    """
    
    def __init__(
        self,
        content_dir: Path = Path("downloads"),
        tags_file: Path = Path("known_tags.json"),
        model: str = "qwen2.5:7b"
    ):
        """
        Args:
            content_dir: Директория с папками контента
            tags_file: Файл с базой тегов
            model: Модель Ollama для анализа
        """
        self.content_dir = Path(content_dir)
        self.brain = LocalBrain(model=model)
        self.tag_manager = TagManager(tags_file)  # Передаём путь напрямую
        
        # Поддерживаемые форматы изображений
        self.image_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
    
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
    
    def has_analysis(self, folder: Path) -> bool:
        """
        Проверяет, есть ли уже AI анализ
        
        Args:
            folder: Папка для проверки
            
        Returns:
            True если Knowledge.md существует
        """
        note_file = folder / "Knowledge.md"
        return note_file.exists()
    
    def read_description(self, folder: Path) -> Optional[str]:
        """
        Читает описание из description.md
        
        Args:
            folder: Папка с контентом
            
        Returns:
            Текст описания или None
        """
        desc_file = folder / "description.md"
        if desc_file.exists():
            return desc_file.read_text(encoding='utf-8')
        return None
    
    def read_transcript(self, folder: Path) -> Optional[str]:
        """
        Читает транскрипцию из transcript.md
        
        Args:
            folder: Папка с контентом
            
        Returns:
            Текст транскрипции или None
        """
        transcript_file = folder / "transcript.md"
        if transcript_file.exists():
            return transcript_file.read_text(encoding='utf-8')
        return None
    
    def find_images(self, folder: Path) -> List[Path]:
        """
        Находит изображения в папке
        
        Args:
            folder: Папка для поиска
            
        Returns:
            Список путей к изображениям
        """
        images = []
        for file in folder.iterdir():
            if file.is_file() and file.suffix.lower() in self.image_extensions:
                images.append(file)
        return sorted(images)
    
    def analyze_content(self, folder: Path) -> Optional[Dict]:
        """
        Анализирует контент папки
        
        Args:
            folder: Папка для анализа
            
        Returns:
            Словарь с результатами анализа или None
        """
        print(f"\n🧠 AI Анализ: {folder.name}")
        
        # Собираем данные
        description = self.read_description(folder)
        transcript = self.read_transcript(folder)
        images = self.find_images(folder)
        
        if not description and not transcript:
            print("⚠️  Нет данных для анализа (нет description.md и transcript.md)")
            return None
        
        # Формируем контекст для анализа
        context_parts = []
        
        if description:
            context_parts.append(f"## Описание\n\n{description}")
        
        if transcript:
            context_parts.append(f"## Транскрипция\n\n{transcript}")
        
        if images:
            context_parts.append(f"## Изображения\n\nКоличество: {len(images)}")
        
        context = "\n\n".join(context_parts)
        
        # AI анализ
        try:
            print("   🤖 Запуск AI анализа...")
            
            # Получаем строку с известными тегами
            known_tags_str = self.tag_manager.get_tags_string()
            
            # Создаем саммари
            summary = self.brain.analyze(
                caption=description or "",
                transcript=transcript or "",
                comments=[],  # Комментарии пока не используем
                author="",     # Автор не всегда известен
                known_tags=known_tags_str
            )
            
            if not summary:
                print("❌ AI не вернул результат")
                return None
            
            # Извлекаем теги из результата AI (summary уже содержит теги)
            print("   🏷️  Обработка тегов...")
            tags = summary.get('tags', [])
            
            # Добавляем новые теги в базу
            new_count = 0
            if tags:
                new_count = self.tag_manager.add_tags(tags)
                if new_count > 0:
                    print(f"   ✨ Добавлено новых тегов: {new_count}")
                print(f"   ✅ Теги: {', '.join(tags)}")
            else:
                print("   ⚠️  Теги не найдены")
            
            return {
                'summary': summary,
                'tags': tags,
                'new_tags_count': new_count,
                'has_description': description is not None,
                'has_transcript': transcript is not None,
                'image_count': len(images)
            }
            
        except Exception as e:
            print(f"❌ Ошибка AI анализа: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _extract_summary_text(self, summary_data: Dict) -> str:
        """
        Извлекает текст саммари из результата LLM.
        Обрабатывает разные форматы ответа.
        
        Args:
            summary_data: Словарь с результатом анализа от LLM
            
        Returns:
            Форматированный текст саммари
        """
        if not isinstance(summary_data, dict):
            return str(summary_data)
        
        # Стандартный формат: {'summary': '...', 'category': '...', ...}
        if 'summary' in summary_data:
            return summary_data['summary']
        
        # Альтернативный формат с key_points
        if 'key_points' in summary_data:
            parts = []
            if 'video_title' in summary_data:
                parts.append(f"**{summary_data['video_title']}**\n")
            
            key_points = summary_data['key_points']
            if isinstance(key_points, list):
                parts.append('\n'.join(f"- {point}" for point in key_points))
            else:
                parts.append(str(key_points))
            
            # Добавляем дополнительную информацию если есть
            if 'total_time' in summary_data:
                parts.append(f"\n**Время работы:** {summary_data['total_time']}")
            if 'cost_without_lighting' in summary_data:
                parts.append(f"**Стоимость:** {summary_data['cost_without_lighting']}")
            
            return '\n'.join(parts)
        
        # Если ничего не подошло, форматируем как список ключ-значение
        result_parts = []
        for key, value in summary_data.items():
            if key in ('tags', 'valuable_comments', 'category'):
                continue  # Эти поля обрабатываются отдельно
            if isinstance(value, list):
                result_parts.append(f"**{key}:**")
                for item in value:
                    result_parts.append(f"- {item}")
            elif isinstance(value, dict):
                continue  # Пропускаем вложенные словари
            else:
                result_parts.append(f"**{key}:** {value}")
        
        return '\n'.join(result_parts) if result_parts else 'Нет саммари'
    
    def create_obsidian_note(
        self, 
        folder: Path, 
        analysis: Dict
    ) -> Optional[Path]:
        """
        Создает Knowledge.md в формате Obsidian
        
        Args:
            folder: Папка для сохранения
            analysis: Результаты анализа
            
        Returns:
            Путь к созданному файлу или None
        """
        note_file = folder / "Knowledge.md"
        
        # Извлекаем название из имени папки
        folder_name = folder.name
        # Формат: источник_ID_название
        parts = folder_name.split('_', 2)
        title = parts[2] if len(parts) > 2 else folder_name
        title = title.replace('_', ' ')
        
        # Создаем Obsidian frontmatter
        tags_str = ', '.join(analysis['tags'])
        
        # Извлекаем данные из summary
        summary_data = analysis['summary']
        summary_text = self._extract_summary_text(summary_data)
        category = summary_data.get('category', 'Не указана') if isinstance(summary_data, dict) else 'Не указана'
        
        markdown = f"""---
title: {title}
date: {datetime.now().strftime('%Y-%m-%d')}
tags: [{', '.join(f'#{tag}' for tag in analysis['tags'])}]
source: {parts[0] if len(parts) > 0 else 'unknown'}
processed: true
---

# {title}

## 📊 Метаданные

- **Источник**: {parts[0].upper() if len(parts) > 0 else 'UNKNOWN'}
- **ID**: {parts[1] if len(parts) > 1 else 'unknown'}
- **Дата обработки**: {datetime.now().strftime('%Y-%m-%d %H:%M')}
- **Изображений**: {analysis['image_count']}
- **Транскрипция**: {'✅' if analysis['has_transcript'] else '❌'}

## 🏷️ Теги

{' '.join(f'#{tag}' for tag in analysis['tags'])}

## 📝 Саммари

{summary_text}

## 📂 Категория

{category}

## 💬 Ценные комментарии

"""
        
        # Добавляем ценные комментарии если есть
        if isinstance(analysis['summary'], dict) and analysis['summary'].get('valuable_comments'):
            for comment in analysis['summary']['valuable_comments']:
                markdown += f"- {comment}\n"
        else:
            markdown += "*Нет ценных комментариев*\n"
        
        markdown += "\n## 📎 Связанные файлы\n\n- [[description.md|Описание]]\n"
        
        if analysis['has_transcript']:
            markdown += "- [[transcript.md|Транскрипция]]\n"
        
        # Добавляем ссылки на изображения
        if analysis['image_count'] > 0:
            markdown += "\n## 🖼️ Изображения\n\n"
            images = self.find_images(folder)
            for i, img in enumerate(images, 1):
                markdown += f"![[{img.name}]]\n"
        
        markdown += "\n---\n\n*Создано автоматически модулем AI анализа [SecondBrain](https://t.me/sec_brainbot)*\n"
        
        try:
            note_file.write_text(markdown, encoding='utf-8')
            print(f"✅ Сохранено: Knowledge.md")
            # После успешного сохранения — попробуем индексировать в RAG (если модуль доступен)
            try:
                # Импортируем лениво — если модуль4 отсутствует, ничего не делаем
                from src.modules.module4_rag import RAGEngine

                try:
                    # Ищем корень пользователя (например downloads/{user_folder})
                    # Предположим, что папка контента лежит внутри папки пользователя
                    user_root = None
                    for p in note_file.parents:
                        if p.name and (p.parent.name == 'downloads' or '_' in p.name or p.parent == Path('downloads')):
                            user_root = p
                            break

                    rag = RAGEngine(user_root=user_root)
                    # Запускаем индексирование в фоне, чтобы не блокировать основной поток
                    def _run_index():
                        try:
                            indexed = rag.index_folder(folder)
                            print(f"   ✅ Indexed {indexed} chunks into user's RAG DB")
                        except Exception as e:
                            print(f"   ⚠️ RAG indexing failed (background): {e}")

                    t = threading.Thread(target=_run_index, daemon=True)
                    t.start()
                except Exception as e:
                    print(f"   ⚠️ RAG indexing failed: {e}")
            except ImportError:
                # module4 not installed — пропускаем
                pass

            return note_file
        except Exception as e:
            print(f"❌ Ошибка сохранения: {e}")
            return None
    
    def should_process_folder(self, folder: Path) -> tuple[bool, str]:
        """
        Проверяет, нужна ли AI обработка для папки
        
        Логика согласно ТЗ:
        - SKIP если Knowledge.md уже существует
        - SKIP если есть видео/аудио, но нет транскрипции (ждём Модуль 2)
        - PROCESS если есть видео/аудио + транскрипция
        - PROCESS если есть только фото/текст (без аудио) + description.md
        
        Args:
            folder: Папка для проверки
            
        Returns:
            (нужна_обработка, причина)
        """
        # 1. Если есть Knowledge.md - уже обработана
        if self.has_analysis(folder):
            return False, "Knowledge.md существует"
        
        # 2. Проверяем наличие ВИДЕО/АУДИО файлов (НЕ фото!)
        # Фото не требуют транскрибации и обрабатываются сразу
        video_audio_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.mp3', '.m4a', '.wav', '.flac', '.ogg']
        video_audio_files = [
            f for f in folder.iterdir() 
            if f.is_file() and f.suffix.lower() in video_audio_extensions
        ]
        
        has_transcript = (folder / "transcript.md").exists()
        has_description = (folder / "description.md").exists()
        
        # 3. Если есть ВИДЕО/АУДИО файлы
        if video_audio_files:
            # Нужна транскрибация сначала
            if not has_transcript:
                return False, "есть видео/аудио, но нет transcript.md (требуется Модуль 2)"
            # Есть транскрипция - можно обрабатывать
            return True, "есть видео/аудио + transcript.md"
        
        # 4. Если НЕТ видео/аудио (только фото или текст)
        if has_description:
            # Текстовая заметка или фото с описанием - можно обрабатывать сразу
            return True, "есть description.md (фото/текст без аудио)"
        
        # 5. Вообще нет контента для анализа
        return False, "нет контента для обработки"
    
    def _process_content_folder(self, folder: Path) -> dict:
        """
        Обрабатывает одну папку
        
        Args:
            folder: Папка для обработки
            
        Returns:
            Статистика обработки
        """
        stats = {
            'folder': folder.name,
            'already_processed': False,
            'success': False,
            'new_tags': 0,
            'error': None,
            'skip_reason': None
        }
        
        # Проверяем, нужна ли обработка
        should_process, reason = self.should_process_folder(folder)
        
        if not should_process:
            print(f"⏭️  Пропуск: {folder.name} ({reason})")
            if "Knowledge.md существует" in reason:
                stats['already_processed'] = True
            else:
                stats['skip_reason'] = reason
            return stats
        
        print(f"✅ Обработка: {folder.name} ({reason})")
        
        # Анализируем
        analysis = self.analyze_content(folder)
        
        if not analysis:
            stats['error'] = "Нет данных или ошибка анализа"
            return stats
        
        # Создаем Knowledge.md
        note_file = self.create_obsidian_note(folder, analysis)
        
        if note_file:
            stats['success'] = True
            stats['new_tags'] = analysis.get('new_tags_count', 0)
        else:
            stats['error'] = "Ошибка создания Knowledge.md"
        
        return stats
    
    def process_folder(self, folder: Path) -> dict:
        """
        Обрабатывает папку (рекурсивно, если это контейнер)
        """
        # Проверяем, выглядит ли папка как контент
        should, reason = self.should_process_folder(folder)
        
        # Если это контент (или уже обработанный контент)
        is_content = should or "Knowledge.md" in reason or "требуется Модуль 2" in reason
        
        if is_content:
            return self._process_content_folder(folder)
            
        # Если контента нет, пробуем рекурсию
        try:
            subfolders = [f for f in folder.iterdir() if f.is_dir()]
        except Exception:
            subfolders = []
            
        if not subfolders:
            # Нет подпапок - возвращаем результат как для пустой папки
            return self._process_content_folder(folder)
            
        print(f"📂 Папка {folder.name} — контейнер, проверяем {len(subfolders)} подпапок...")
        
        agg_stats = {
            'folder': folder.name,
            'success': False,
            'already_processed': False,
            'new_tags': 0,
            'success_count': 0,
            'error': None
        }
        
        for sub in subfolders:
            if sub.name.startswith('.'): continue
            
            sub_stats = self.process_folder(sub)
            
            if sub_stats.get('success'):
                agg_stats['success'] = True
                agg_stats['success_count'] += 1
                agg_stats['new_tags'] += sub_stats.get('new_tags', 0)
            elif sub_stats.get('already_processed'):
                agg_stats['already_processed'] = True
                
        if agg_stats['success']:
             print(f"✅ Обработано {agg_stats['success_count']} элементов в {folder.name}")
             
        return agg_stats

    def process_all(self) -> dict:
        """
        Обрабатывает все папки
        
        Returns:
            Общая статистика
        """
        print("\n" + "="*70)
        print("🧠 МОДУЛЬ 3: AI АНАЛИЗ")
        print("="*70)
        print(f"📁 Директория: {self.content_dir}")
        print(f"🏷️  База тегов: {self.tag_manager.tags_file}")
        
        # Находим папки
        folders = self.find_content_folders()
        
        if not folders:
            print("\n⚠️  Папки с контентом не найдены")
            return {'total_folders': 0}
        
        print(f"📊 Найдено папок: {len(folders)}")
        
        # Общая статистика
        total_stats = {
            'total_folders': len(folders),
            'already_processed': 0,
            'successfully_processed': 0,
            'need_transcription': 0,
            'no_content': 0,
            'errors': 0,
            'total_new_tags': 0
        }
        
        # Обрабатываем каждую папку
        for i, folder in enumerate(folders, 1):
            print(f"\n{'='*70}")
            print(f"📂 [{i}/{len(folders)}] {folder.name}")
            print(f"{'='*70}")
            
            stats = self.process_folder(folder)
            
            if stats['already_processed']:
                total_stats['already_processed'] += 1
            elif stats['success']:
                total_stats['successfully_processed'] += 1
                total_stats['total_new_tags'] += stats['new_tags']
            elif stats.get('skip_reason'):
                reason = stats['skip_reason']
                if "требуется транскрибация" in reason:
                    total_stats['need_transcription'] += 1
                elif "нет контента" in reason:
                    total_stats['no_content'] += 1
            else:
                total_stats['errors'] += 1
        
        # Итоговая статистика
        print("\n" + "="*70)
        print("📊 ИТОГОВАЯ СТАТИСТИКА")
        print("="*70)
        print(f"Всего папок: {total_stats['total_folders']}")
        print(f"Уже обработано (Knowledge.md): {total_stats['already_processed']}")
        print(f"Успешно обработано: {total_stats['successfully_processed']}")
        print(f"Новых тегов создано: {total_stats['total_new_tags']}")
        
        if total_stats['need_transcription'] > 0:
            print(f"⏳ Требуют транскрибации: {total_stats['need_transcription']}")
        if total_stats['no_content'] > 0:
            print(f"⚠️  Нет контента: {total_stats['no_content']}")
        if total_stats['errors'] > 0:
            print(f"❌ Ошибок: {total_stats['errors']}")
        print("="*70)
        
        return total_stats


def main():
    """Точка входа"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Модуль 3: AI анализ контента"
    )
    parser.add_argument(
        '--dir',
        type=Path,
        default=Path('downloads'),
        help='Директория с контентом (по умолчанию: downloads)'
    )
    parser.add_argument(
        '--tags',
        type=Path,
        default=Path('known_tags.json'),
        help='Файл с базой тегов (по умолчанию: known_tags.json)'
    )
    parser.add_argument(
        '--model',
        type=str,
        default='qwen2.5:7b',
        help='Модель Ollama (по умолчанию: qwen2.5:7b)'
    )
    parser.add_argument(
        '--folder',
        type=str,
        help='Обработать только одну папку (имя папки)'
    )
    
    args = parser.parse_args()
    
    processor = AIProcessor(
        content_dir=args.dir,
        tags_file=args.tags,
        model=args.model
    )
    
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
        if stats['already_processed']:
            print("⏭️  Папка уже обработана")
        elif stats['success']:
            print("✅ Успешно обработано")
            if stats['new_tags'] > 0:
                print(f"✨ Новых тегов: {stats['new_tags']}")
        else:
            print(f"❌ Ошибка: {stats['error']}")
    else:
        # Обработка всех папок
        processor.process_all()


if __name__ == "__main__":
    main()
