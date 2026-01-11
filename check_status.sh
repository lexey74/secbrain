#!/bin/bash
# Быстрая проверка статуса транскрибации

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 БЫСТРАЯ ПРОВЕРКА ТРАНСКРИБАЦИИ"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "⏰ $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Проверяем процесс
if ps aux | grep "module2_transcribe.py" | grep -v grep > /dev/null; then
    echo "✅ Процесс работает"
    ps aux | grep "module2_transcribe.py" | grep -v grep | \
        awk '{printf "   PID: %s | CPU: %s%% | Memory: %s%%\n", $2, $3, $4}'
else
    echo "❌ Процесс не найден (возможно, завершился)"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📁 Транскрипции:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Считаем транскрипции
TOTAL=$(find downloads -name "transcript.md" 2>/dev/null | wc -l)
echo "📝 Всего: $TOTAL"

# Новые транскрипции (созданные недавно)
RECENT=$(find downloads -name "transcript.md" -mmin -60 2>/dev/null | wc -l)
echo "🆕 За последний час: $RECENT"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📄 Последние 30 строк лога:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -f "transcribe.log" ] && [ -s "transcribe.log" ]; then
    tail -30 transcribe.log
else
    echo "⚠️  Лог пока пуст или процесс только начался"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "💡 Команды:"
echo "   Полный мониторинг: ./monitor_transcription.sh"
echo "   Следить за логом:   tail -f transcribe.log"
echo "   Остановить:         kill \$(ps aux | grep module2_transcribe.py | grep -v grep | awk '{print \$2}')"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
