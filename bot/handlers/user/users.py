import asyncio

from aiogram import types
from aiogram.filters import Command
from aiogram.types import Message

from bot import dp

from bot.logs.logging_config import logger

@dp.message(Command("start"))
async def cmd_start(message: Message):
    logger.info(f"Пользователь {message.from_user.id} запустил бота")
    await message.answer(f"Привет! Я - бот напоминалка, или будильник. Зови как хочешь!\n\n"
                         "Я могу предупредить тебя в нужный момент, только создай напоминание командой /add\n\n"
                         "<code>/add через 1 минуту Вот так я могу предупреждать!😝</code>\n\n"
                         "<code>/check</code> Чтобы посмотреть напоминания!", parse_mode="HTML")

@dp.errors()
async def errors_handler(update: types.Update, exception: Exception):
    logger.error(f"Ошибка: {exception}", exc_info=True)
    return True

@dp.message()
async def echo(message: Message):
    logger.info(f"Пользователь {message.from_user.id} написал: {message.text}")
    try:
        await message.delete()
        notification = await message.answer(text="Пожалуйста, используйте доступные команды", show_alert=True)
        await asyncio.sleep(3)
        await notification.delete()
    except Exception as e:
        logger.error(f"Не удалось удалить сообщение: {e}")
        