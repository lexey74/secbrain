---
trigger: always_on
---

# Python Telegram Bot Standards (High-Performance Stack)

Используем **Aiogram 3.x** в связке с высокопроизводительными библиотеками. Приоритет — скорость обработки I/O и работа с тяжелым медиа-контентом.

## 1. Core Stack
- **Framework:** `aiogram >= 3.0`
- **Event Loop:** `uvloop` (обязательно для Linux/macOS сред). Устанавливать политику: `uvloop.install()`.
- **JSON Parser:** `orjson` (быстрее стандартного `json` в разы). Настроить aiogram на использование `orjson`.

## 2. Архитектура и Роутеры
- Использовать модульную структуру через `Router`.
- **Dispatcher:** Подключать роутеры через `dp.include_router()`.
- Изолировать логику: 1 фича = 1 роутер (напр. `routers/transcription.py`, `routers/admin.py`).

## 3. Data Validation
- Использовать **Pydantic v2** для валидации всех входящих данных и структур (особенно CallbackData).
- Не использовать словари (`dict`) для передачи данных между слоями сервиса — только Pydantic-модели.

## 4. Local Bot API Server (Критично для Media)
- Код должен уметь работать с локальным Bot API сервером.
- Конфигурация должна поддерживать флаг `is_local` и менять `base_url` бота.
- Использовать `FSInputFile` для загрузки файлов (это позволяет серверу API читать файлы прямо с диска VPS, без сетевого оверхеда).

## 5. Dependency Injection & Middleware
- Прокидывать сессии БД (SQLAlchemy/Aiosqlite) и HTTP-клиенты через Middleware.
- Не создавать `ClientSession` внутри хендлера. Создать один `aiohttp.ClientSession` при старте и прокидывать его.

## 6. Magic Filters & Type Hints
- Использовать магические фильтры: `F.video`, `F.text.startswith("!")`.
- Строгая типизация: `async def handler(message: Message, bot: Bot) -> None:`.

## 7. Error Handling
- Глобальный `ErrorRouter` для перехвата исключений.
- Обязательное логирование через `structlog` (JSON-логи) для удобного анализа в будущем.

## 8. Snippet: Правильный запуск с uvloop
```python
import asyncio
import uvloop
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer

async def main():
    # Настройка для Local Bot API (если нужно для видео > 20мб)
    session = AiohttpSession(
        api=TelegramAPIServer.from_base_url("http://localhost:8081")
    )
    bot = Bot(token="...", session=session)
    dp = Dispatcher()
    
    # ... include routers ...

    await dp.start_polling(bot)

if __name__ == "__main__":
    uvloop.install()
    asyncio.run(main())