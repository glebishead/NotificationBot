import asyncio

from bot import dp, bot, scheduler
from bot.logs.logging_config import logger
from bot.handlers.reminds.storage import restore_reminders

from bot.handlers.reminds.reminds import *
from bot.handlers.user.users import *


async def main():
    try:
        logger.info("Бот запущен!")
        restore_reminders() 
        scheduler.start()
        await dp.start_polling(bot)
    except Exception as e:
        logger.critical(f"Бот упал с ошибкой: {e}")
    finally:
        scheduler.shutdown()
        await bot.session.close()
        logger.info("Бот остановлен")


if __name__ == "__main__":
    asyncio.run(main())