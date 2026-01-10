#!/usr/bin/env python3
"""
Скрипт для быстрой проверки готовности окружения SecBrain
"""
import sys
import subprocess
from pathlib import Path


def check_python():
    """Проверка версии Python"""
    version = sys.version_info
    if version.major >= 3 and version.minor >= 10:
        print(f"✅ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"❌ Python {version.major}.{version.minor} (требуется 3.10+)")
        return False


def check_command(cmd, name):
    """Проверка доступности команды"""
    try:
        result = subprocess.run(
            [cmd, '--version'],
            capture_output=True,
            check=True,
            timeout=5
        )
        print(f"✅ {name} установлен")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        print(f"❌ {name} не найден")
        return False


def check_python_package(package_name, import_name=None):
    """Проверка установленного Python пакета"""
    if import_name is None:
        import_name = package_name
    
    try:
        __import__(import_name)
        print(f"✅ {package_name} установлен")
        return True
    except ImportError:
        print(f"❌ {package_name} не установлен")
        return False


def check_ollama():
    """Проверка Ollama сервера"""
    try:
        import ollama
        client = ollama.Client()
        models = client.list()
        model_names = [m['name'] for m in models.get('models', [])]
        
        if model_names:
            print(f"✅ Ollama работает (модели: {', '.join(model_names[:3])})")
            return True
        else:
            print("⚠️  Ollama работает, но нет загруженных моделей")
            print("   Выполните: ollama pull llama3.2")
            return False
    except Exception as e:
        print(f"❌ Ollama не доступен: {e}")
        print("   Запустите: ollama serve")
        return False


def check_files():
    """Проверка конфигурационных файлов"""
    files = {
        'cookies.txt': 'Опционально (для yt-dlp)',
        'session.json': 'Опционально (для instagrapi)',
        'config.json': 'Будет создан автоматически'
    }
    
    print("\n📁 Конфигурационные файлы:")
    for file, desc in files.items():
        path = Path(file)
        if path.exists():
            print(f"  ✅ {file} - {desc}")
        else:
            print(f"  ⚠️  {file} отсутствует - {desc}")


def main():
    """Главная функция проверки"""
    print("🔍 SecBrain - Проверка окружения\n")
    print("=" * 50)
    
    checks = []
    
    # Системные требования
    print("\n1️⃣  Системные зависимости:")
    checks.append(check_python())
    checks.append(check_command('ffmpeg', 'FFmpeg'))
    checks.append(check_command('yt-dlp', 'yt-dlp'))
    
    # Python пакеты
    print("\n2️⃣  Python библиотеки:")
    checks.append(check_python_package('ollama'))
    checks.append(check_python_package('faster_whisper', 'faster_whisper'))
    checks.append(check_python_package('instagrapi'))
    checks.append(check_python_package('rich'))
    
    # Ollama
    print("\n3️⃣  Ollama сервер:")
    checks.append(check_ollama())
    
    # Файлы
    check_files()
    
    # Итог
    print("\n" + "=" * 50)
    passed = sum(checks)
    total = len(checks)
    
    if passed == total:
        print(f"✅ Все проверки пройдены ({passed}/{total})")
        print("\n🚀 Готово к запуску: python src/main.py")
        return 0
    else:
        print(f"⚠️  Пройдено проверок: {passed}/{total}")
        print("\n📖 См. SETUP.md для инструкций по установке")
        return 1


if __name__ == "__main__":
    sys.exit(main())
