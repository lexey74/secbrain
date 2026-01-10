#!/bin/bash
# Оптимизированный скрипт запуска SecBrain для VPS 8 cores / 24GB RAM

cd "$(dirname "$0")"

# Оптимизация для Ollama
export OLLAMA_NUM_PARALLEL=2              # Параллельные запросы
export OLLAMA_MAX_LOADED_MODELS=1         # Одна модель в памяти
export OLLAMA_NUM_THREAD=8                # Использовать все 8 ядер
export OLLAMA_FLASH_ATTENTION=1           # Ускорение attention

# Активация виртуального окружения
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "🚀 Запуск SecBrain (оптимизировано для 8 ядер)"
    python3 src/main.py
else
    echo "❌ Виртуальное окружение не найдено!"
    echo "Выполните: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi
