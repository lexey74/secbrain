#!/bin/bash
# Скрипт запуска SecBrain

cd "$(dirname "$0")"

# Активация виртуального окружения
if [ -d "venv" ]; then
    source venv/bin/activate
    python3 src/main.py
else
    echo "❌ Виртуальное окружение не найдено!"
    echo "Выполните: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi
