#!/usr/bin/env python3
"""
Скрипт для проверки и удаления дубликатов медиа файлов во всех папках
"""
import hashlib
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple


def calculate_md5(file_path: Path) -> str:
    """Вычисляет MD5 хеш файла"""
    md5_hash = hashlib.md5()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            md5_hash.update(chunk)
    return md5_hash.hexdigest()


def find_duplicates_in_folder(folder: Path) -> Tuple[Dict[str, List[Path]], int, int]:
    """
    Находит дубликаты в одной папке
    
    Returns:
        (hash_to_files, total_files, duplicate_count)
    """
    media_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm', 
                       '.jpg', '.jpeg', '.png', '.gif', '.webp',
                       '.mp3', '.m4a', '.wav', '.flac', '.ogg'}
    
    hash_to_files = defaultdict(list)
    total_files = 0
    
    # Собираем все медиа файлы
    for file in folder.iterdir():
        if file.is_file() and file.suffix.lower() in media_extensions:
            total_files += 1
            file_hash = calculate_md5(file)
            hash_to_files[file_hash].append(file)
    
    # Подсчитываем дубликаты
    duplicate_count = sum(len(files) - 1 for files in hash_to_files.values() if len(files) > 1)
    
    return hash_to_files, total_files, duplicate_count


def scan_all_folders(base_dir: Path, dry_run: bool = True):
    """Сканирует все папки пользователей на дубликаты"""
    print(f"🔍 Сканирование папок в {base_dir}\n")
    print("=" * 80)
    
    total_folders = 0
    folders_with_duplicates = 0
    total_duplicates = 0
    total_files_deleted = 0
    total_space_saved = 0
    
    # Проходим по всем пользовательским папкам
    for user_folder in sorted(base_dir.iterdir()):
        if not user_folder.is_dir():
            continue
        
        # Проходим по всем папкам контента
        for content_folder in sorted(user_folder.iterdir()):
            if not content_folder.is_dir():
                continue
            
            total_folders += 1
            
            # Ищем дубликаты
            hash_to_files, total_files, duplicate_count = find_duplicates_in_folder(content_folder)
            
            if duplicate_count > 0:
                folders_with_duplicates += 1
                total_duplicates += duplicate_count
                
                print(f"\n📂 {content_folder.name}")
                print(f"   Всего файлов: {total_files}")
                print(f"   🔴 Найдено дубликатов: {duplicate_count}")
                
                # Показываем группы дубликатов
                for file_hash, files in hash_to_files.items():
                    if len(files) > 1:
                        file_size = files[0].stat().st_size
                        size_mb = file_size / (1024 * 1024)
                        wasted_space = file_size * (len(files) - 1)
                        total_space_saved += wasted_space
                        
                        print(f"\n   Группа дубликатов (хеш: {file_hash[:8]}...):")
                        print(f"   Размер файла: {size_mb:.2f} MB")
                        print(f"   Потрачено: {wasted_space / (1024 * 1024):.2f} MB")
                        
                        # Оставляем первый файл, остальные удаляем
                        for idx, file in enumerate(files):
                            if idx == 0:
                                print(f"      ✅ ОСТАВИТЬ: {file.name}")
                            else:
                                print(f"      ❌ УДАЛИТЬ:  {file.name}")
                                if not dry_run:
                                    file.unlink()
                                    total_files_deleted += 1
                                    print(f"         → Удален!")
    
    # Итоговая статистика
    print("\n" + "=" * 80)
    print(f"\n📊 ИТОГОВАЯ СТАТИСТИКА:\n")
    print(f"   Всего папок просканировано: {total_folders}")
    print(f"   Папок с дубликатами: {folders_with_duplicates}")
    print(f"   Всего дубликатов найдено: {total_duplicates}")
    print(f"   Потрачено места: {total_space_saved / (1024 * 1024):.2f} MB")
    
    if dry_run:
        print(f"\n⚠️  РЕЖИМ ПРОСМОТРА (--dry-run)")
        print(f"   Файлы не были удалены.")
        print(f"   Запустите с флагом --apply для удаления дубликатов.")
    else:
        print(f"\n✅ ФАЙЛОВ УДАЛЕНО: {total_files_deleted}")
        print(f"   Освобождено места: {total_space_saved / (1024 * 1024):.2f} MB")


def main():
    import sys
    
    base_dir = Path("downloads")
    
    if not base_dir.exists():
        print(f"❌ Папка {base_dir} не найдена!")
        return
    
    # Проверяем флаги
    dry_run = "--apply" not in sys.argv
    
    if dry_run:
        print("🔍 РЕЖИМ ПРОСМОТРА")
        print("   Дубликаты будут найдены, но не удалены")
        print("   Используйте --apply для реального удаления\n")
    else:
        print("⚠️  РЕЖИМ УДАЛЕНИЯ")
        print("   Дубликаты будут УДАЛЕНЫ!\n")
        response = input("Продолжить? (yes/no): ")
        if response.lower() not in ['yes', 'y', 'да']:
            print("❌ Отменено")
            return
        print()
    
    scan_all_folders(base_dir, dry_run=dry_run)


if __name__ == "__main__":
    main()
