#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo '--- .env (token redacted) ---'
if [ -f .env ]; then
  sed -n '1,200p' .env | sed -E 's/(TELEGRAM_BOT_TOKEN=).*/\1<REDACTED>/'
else
  echo '.env not found'
fi

echo "\n--- processes matching telegram_bot.py (ps -ef) ---"
ps -ef | grep '[t]elegram_bot.py' || echo 'No matching processes'

# Find PIDs of running bot processes (match python command that includes telegram_bot.py)
PIDS=$(pgrep -f 'python.*telegram_bot.py' || true)
if [ -n "$PIDS" ]; then
  echo "Found bot PIDs: $PIDS"
  for pid in $PIDS; do
    # avoid killing this script or its parent shells
    if [ "$pid" -ne "$$" ] 2>/dev/null && [ "$pid" -ne "$BASHPID" ] 2>/dev/null; then
      echo "Killing PID: $pid"
      kill -9 "$pid" || true
    else
      echo "Skipping PID (this script): $pid"
    fi
  done
  sleep 1
else
  echo 'No running telegram_bot.py processes found.'
fi

mkdir -p logs
if [ -x ./venv/bin/python ]; then
  PY=./venv/bin/python
else
  PY=python3
fi

echo 'Starting single bot instance...'
nohup "$PY" telegram_bot.py > logs/bot.log 2>&1 &
echo $! > logs/bot.pid
echo "Started bot with PID: $(cat logs/bot.pid)"

sleep 2
echo "\n--- last 120 lines of logs/bot.log ---"
tail -n 120 logs/bot.log || echo 'No logs yet.'

# Extract token safely (without printing it)
TOKEN=$(grep -E '^TELEGRAM_BOT_TOKEN=' .env 2>/dev/null | sed -E 's/^TELEGRAM_BOT_TOKEN=//; s/^\"//; s/\"$//' || true)

if [ -n "$TOKEN" ]; then
  if grep -q 'Conflict: terminated by other getUpdates request' logs/bot.log 2>/dev/null; then
    echo '\nConflict detected in logs — fetching webhook info and deleting webhook.'
    echo 'getWebhookInfo:'
    curl -s "https://api.telegram.org/bot${TOKEN}/getWebhookInfo" | sed -n '1,200p'
    echo '\ndeleteWebhook:'
    curl -s -X POST "https://api.telegram.org/bot${TOKEN}/deleteWebhook" | sed -n '1,200p'
    echo '\nRestarting bot...'
    kill -9 $(cat logs/bot.pid) || true
    sleep 1
    nohup "$PY" telegram_bot.py > logs/bot.log 2>&1 &
    echo $! > logs/bot.pid
    echo 'New PID:' $(cat logs/bot.pid)
    sleep 2
    echo '--- new last 120 lines of logs/bot.log ---'
    tail -n 120 logs/bot.log || true
  else
    echo 'No Conflict detected in recent logs.'
  fi
else
  echo '\nNo TELEGRAM_BOT_TOKEN found in .env; skipping Telegram API webhook operations.'
fi

echo '\nDone.'
