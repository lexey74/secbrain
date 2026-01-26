#!/bin/bash
# Скрипт запуска SecBrain (Bot + MCP Server)

# Определение директории скрипта
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# 1. Проверка и активация окружения
if [ ! -d "venv" ]; then
    echo "⚠️  Virtual environment not found. Creating..."
    python3 -m venv venv
    source venv/bin/activate
    echo "📦 Installing dependencies from requirements.txt..."
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# 2. Загрузка переменных (если есть) или дефолты
# Простой парсинг .env для скрипта (или полагаемся, что python сам загрузит)
# Но для uvicorn нам нужны аргументы здесь
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

MCP_HOST="${MCP_HOST:-0.0.0.0}"  # Используем 0.0.0.0 по умолчанию если не задано
MCP_PORT="${MCP_PORT:-8000}"

# 3. Запуск MCP Сервера
echo "🚀 Starting MCP Server on $MCP_HOST:$MCP_PORT..."
# Проверяем, не запущен ли уже
if pgrep -f "server_mcp:app" > /dev/null; then
    echo "⚠️  MCP Server appears to be already running. Skipping start."
else
    # Запуск в фоне
    nohup uvicorn server_mcp:app --host "$MCP_HOST" --port "$MCP_PORT" > logs/mcp.log 2>&1 &
    MCP_PID=$!
    echo "✅ MCP Server started with PID $MCP_PID (logs in logs/mcp.log)"
    
    # Гарантируем остановку сервера при выходе из скрипта
    trap "echo '🛑 Stopping MCP Server...'; kill $MCP_PID" EXIT
fi

# 4. Запуск Бота
echo "🤖 Starting Telegram Bot..."
python telegram_bot.py
