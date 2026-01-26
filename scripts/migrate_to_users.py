#!/usr/bin/env python3
"""
Скрипт миграции данных из старой структуры в новую.

Переносит:
  downloads/{username}/ → users/{username}/downloads/

Создает недостающие папки:
  Context/, Goals/, Reviews/, Projects/, Meetings/, achievements/
"""
import shutil
import os
from pathlib import Path

def migrate():
    old_dir = Path('downloads')
    new_dir = Path('users')
    
    # 1. Проверяем наличие старой папки
    if not old_dir.exists():
        print("ℹ️ Папка downloads не найдена, миграция не требуется")
        # Проверяем, создана ли уже новая структура
        if new_dir.exists():
            print("ℹ️ Папка users уже существует")
        else:
             print("ℹ️ Создаю папку users...")
             new_dir.mkdir(exist_ok=True)
        return
    
    print(f"🚀 Начинаем миграцию: {old_dir} -> {new_dir}")
    
    # Структура папок для каждого пользователя
    subdirs = ["downloads", "Context", "Goals", "Reviews", 
               "Projects", "Meetings", "achievements"]
    
    # Итерируемся по пользователям в старой папке
    for item in old_dir.iterdir():
        if not item.is_dir():
            continue
            
        username = item.name
        
        # Пропускаем hidden папки или файлы
        if username.startswith('.'):
            continue
            
        print(f"\n👤 Пользователь: {username}")
        
        new_user_root = new_dir / username
        new_downloads = new_user_root / "downloads"
        
        # Создаем структуру
        print("  creating structure...", end=" ")
        for subdir in subdirs:
            (new_user_root / subdir).mkdir(parents=True, exist_ok=True)
        print("OK")
        
        # Переносим контент из downloads/{username}/ в users/{username}/downloads/
        # Если в старой папке лежат папки контента (YYYY-MM-DD...)
        count = 0
        for content_item in item.iterdir():
            # Если это папка контента
            dest = new_downloads / content_item.name
            
            if dest.exists():
                print(f"  ⚠️  {content_item.name} уже существует в новом месте (пропуск)")
                continue
                
            try:
                # Перемещаем
                shutil.move(str(content_item), str(dest))
                count += 1
            except Exception as e:
                print(f"  ❌ Ошибка переноса {content_item.name}: {e}")
        
        print(f"  ✅ Перенесено {count} объектов")
        
        # Если старая папка пользователя стала пустой, удаляем её
        if not any(item.iterdir()):
            item.rmdir()
            print("  🗑️  Удалена пустая старая папка пользователя")
            
    # Проверяем, пуста ли downloads
    if old_dir.exists() and not any(old_dir.iterdir()):
        try:
            old_dir.rmdir()
            print("\n🗑️  Удалена пустая папка downloads/")
        except:
            pass
            
    print("\n✨ Миграция завершена!")
    print("Теперь бот будет работать с папкой `users/`.")

if __name__ == "__main__":
    migrate()
