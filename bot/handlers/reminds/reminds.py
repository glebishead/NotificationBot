import re
from uuid import uuid4
from datetime import datetime, timedelta
from typing import Optional, Tuple

from aiogram import types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from apscheduler.triggers.cron import CronTrigger

from bot import bot, dp, scheduler
from bot.logs.logging_config import logger
from bot.handlers.reminds.storage import reminders, save_reminders, send_scheduled_message, make_urgency_keyboard

NUMBER_WORDS = {
    'один': 1, 'одна': 1, 'одну': 1, 'два': 2, 'две': 2, 'три': 3, 'четыре': 4, 'пять': 5,
    'шесть': 6, 'семь': 7, 'восемь': 8, 'девять': 9, 'десять': 10,
    'одиннадцать': 11, 'двенадцать': 12, 'тринадцать': 13, 'четырнадцать': 14,
    'пятнадцать': 15, 'шестнадцать': 16, 'семнадцать': 17, 'восемнадцать': 18,
    'девятнадцать': 19, 'двадцать': 20, 'тридцать': 30, 'сорок': 40,
    'пятьдесят': 50, 'шестьдесят': 60
}

def parse_relative_time(text: str) -> Optional[Tuple[int, int]]:
    """Парсит относительное время из текста"""
    text = text.lower().strip()
    
    # Обработка формата "через X минут/часов"
    match = re.match(
        r'(\d+|один|одна|одну|две|два|три|четыре|пять|шесть|семь|восемь|девять|десять|'
        r'одиннадцать|двенадцать|тринадцать|четырнадцать|пятнадцать|шестнадцать|'
        r'семнадцать|восемнадцать|девятнадцать|двадцать|тридцать|сорок|пятьдесят|шестьдесят)\s*'
        r'(час|ч|часа|часов|минут|мин|минуту|минуты)?\s*'
        r'(?:и\s*(\d+|один|одну|два|две|три|четыре|пять|шесть|семь|восемь|девять|десять)\s*'
        r'(минут|мин|минуту|минуты))?\s*',
        text
    )
    
    if not match:
        return None
    
    # Получаем числовое значение
    num1 = match.group(1)
    if num1.isdigit():
        num1 = int(num1)
    else:
        num1 = NUMBER_WORDS.get(num1, 0)
    
    unit1 = match.group(2)
    
    # Обработка второго числа (если есть)
    num2 = 0
    if match.group(3):
        num2_str = match.group(3)
        if num2_str.isdigit():
            num2 = int(num2_str)
        else:
            num2 = NUMBER_WORDS.get(num2_str, 0)
    
    # Определяем часы и минуты
    hours, minutes = 0, 0
    
    if unit1:
        if 'час' in unit1:
            hours = num1
            minutes = num2
        elif 'мин' in unit1:
            minutes = num1 + num2
    else:
        # Если единица измерения не указана, предполагаем минуты для небольших значений
        if num1 <= 60:
            minutes = num1
        else:
            hours = num1 // 60
            minutes = num1 % 60
    
    return hours, minutes
    
@dp.message(Command("add"))
async def cmd_add_reminder(message: types.Message):
    try:
        user_id = str(message.from_user.id)
        text = message.text.strip()
        
        # Генерируем уникальный ID для напоминания
        reminder_id = uuid4().hex[:8]
        
        # 1. Обработка относительного времени (через X минут/часов)
        if "через" in text.lower():
            # Извлекаем текст после "/add через"
            time_part = re.sub(r'^/add\s+через\s*', '', text, flags=re.IGNORECASE)
            
            # Парсим относительное время
            time_data = parse_relative_time(time_part)
            
            if not time_data:
                raise ValueError("Некорректный формат времени. Пример: /add через 2 часа Текст")
            
            hours, minutes = time_data
            
            # Извлекаем текст напоминания (все после временного выражения)
            time_expr = re.compile(
                r'^(\d+|[\w-]+)\s*(час|ч|часа|часов|минут|мин|минуту|минуты)?\s*'
                r'(?:и\s*(\d+|[\w-]+)\s*(минут|мин|минуту|минуты))?\s*',
                flags=re.IGNORECASE
            )

            match = time_expr.match(time_part)
            if match:
                # Берем текст после всего временного выражения
                reminder_text = time_part[match.end():].strip()
                # Удаляем возможные остаточные "ов" или "а" в начале
                reminder_text = re.sub(r'^[ов а у ы]+\s*', '', reminder_text)
            else:
                reminder_text = time_part.strip()
            
            if not reminder_text:
                raise ValueError("Не указан текст напоминания")
            
            # Проверяем валидность времени
            if hours == 0 and minutes == 0:
                raise ValueError("Укажите корректный интервал (например: 2 часа или 30 минут)")
            
            # Рассчитываем время выполнения
            run_date = datetime.now() + timedelta(hours=hours, minutes=minutes)
            time_str = format_relative_time(hours, minutes)
            frequency = "однократно"
            
            # Создаем задачу
            job = scheduler.add_job(
                send_scheduled_message,
                'date',
                run_date=run_date,
                args=[message.chat.id, user_id, reminder_id],
                timezone='Europe/Kaliningrad'
            )
        
        # 2. Обработка абсолютного времени (ежедневно/еженедельно/ежемесячно)
        else:
            # Парсим команду с абсолютным временем
            time_match = re.match(
                r'/add\s+(ежедневно|еженедельно|ежемесячно)\s+в?\s*(\d{1,2}[:.]\d{2})\s+(.+)', 
                text, 
                re.IGNORECASE
            )
            
            if not time_match or not time_match.group(3):
                raise ValueError("Некорректный формат. Пример: /add ежедневно 14:35 Текст")
            
            frequency = time_match.group(1).lower()
            time_str = time_match.group(2).replace('.', ':')
            reminder_text = time_match.group(3).strip()
            
            # Парсим время
            hour, minute = parse_time(time_str)
            
            # Создаем триггер
            trigger = create_trigger(frequency, hour, minute)
            
            # Добавляем задачу
            job = scheduler.add_job(
                send_scheduled_message,
                trigger=trigger,
                args=[message.chat.id, user_id, reminder_id],
                timezone='Europe/Kaliningrad'
            )
        
        # Сохраняем напоминание
        if user_id not in reminders:
            reminders[user_id] = {}
            
        reminders[user_id][reminder_id] = {
                "text": reminder_text,
                "time": time_str,
                "frequency": frequency,
                "job_id": job.id,
                "created_at": datetime.now().isoformat(),
                "urgent": False,
                "active": True
            }
        save_reminders(reminders)
        
        await message.answer("Выберите срочность:", reply_markup=make_urgency_keyboard(reminder_id))
        return
        
    except Exception as e:
        logger.error(f"Ошибка при добавлении напоминания: {e}", exc_info=True)
        await message.answer(
            f"❌ Ошибка: {str(e)}\n\n"
            "Правильные форматы:\n"
            "• <code>/add ежедневно 14:35 Тест</code>\n"
            "• <code>/add еженедельно в14.35 Тест</code>\n"
            "• <code>/add через 2 часа Тест</code>\n"
            "• <code>/add через 15 минут Тест</code>\n"
            "• <code>/add через шесть часов Тест</code>\n"
            "• <code>/add через один час и пять минут Тест</code>",
            parse_mode="HTML"
        )
        
def format_relative_time(hours: int, minutes: int) -> str:
    """Форматирует относительное время для отображения"""
    parts = []
    if hours > 0:
        parts.append(f"{hours} {pluralize(hours, 'час', 'часа', 'часов')}")
    if minutes > 0:
        parts.append(f"{minutes} {pluralize(minutes, 'минуту', 'минуты', 'минут')}")
    return ' '.join(parts) if parts else "сейчас"

def pluralize(number: int, form1: str, form2: str, form5: str) -> str:
    """Склоняет слова после числительных"""
    n = abs(number) % 100
    if 5 <= n <= 20:
        return form5
    n %= 10
    if n == 1:
        return form1
    if 2 <= n <= 4:
        return form2
    return form5

def parse_time(time_str: str) -> tuple[int, int]:
    """Парсит время в формате ЧЧ:ММ или ЧЧ.ММ"""
    try:
        time_cleaned = time_str.replace('.', ':')
        hour, minute = map(int, time_cleaned.split(':'))
        if not (0 <= hour < 24 and 0 <= minute < 60):
            raise ValueError
        return hour, minute
    except:
        raise ValueError("Некорректное время. Используйте ЧЧ:ММ")

def create_trigger(frequency: str, hour: int, minute: int):
    """Создает триггер для APScheduler"""
    freq = frequency.lower()
    if freq.startswith("ежедневно"):
        return CronTrigger(hour=hour, minute=minute)
    elif freq.startswith("еженедельно"):
        return CronTrigger(day_of_week='*', hour=hour, minute=minute)
    elif freq.startswith("ежемесячно"):
        return CronTrigger(day=1, hour=hour, minute=minute)
    else:
        raise ValueError("Неизвестная частота")

@dp.message(Command("check"))
async def cmd_check_reminders(message: types.Message):
    try:
        user_id = str(message.from_user.id)
        
        if user_id not in reminders or not reminders[user_id]:
            await message.answer("У вас нет активных напоминаний")
            return
        
        await message.answer("Ваши напоминания:")
        
        for reminder_id, data in reminders[user_id].items():
            text = data.get("text", "Текст не указан")
            time_info = data.get("time", "время не указано")
            freq_info = data.get("frequency", "частота не указана")
            
            # Создаем сообщение с информацией о напоминании
            await message.answer(
                f"• Текст: {text}\n"
                f"• Время: {time_info}\n"
                f"• Тип: {freq_info}",
                reply_markup=make_reminder_keyboard(reminder_id)
            )
            
    except Exception as e:
        logger.error(f"Ошибка при проверке напоминаний: {e}")
        await message.answer("Произошла ошибка при получении списка напоминаний")

@dp.callback_query(lambda c: c.data.startswith("delrem_"))
async def handle_delete_reminder(callback: types.CallbackQuery):
    try:
        user_id = str(callback.from_user.id)
        reminder_id = callback.data.split("_")[1]
        
        # Проверяем существование напоминания
        if user_id not in reminders or reminder_id not in reminders[user_id]:
            await callback.answer("Напоминание не найдено")
            return
            
        # Получаем данные о напоминании
        reminder_data = reminders[user_id][reminder_id]
        
        # Удаляем задачу из планировщика
        try:
            scheduler.remove_job(reminder_data["job_id"])
        except Exception as e:
            logger.error(f"Ошибка при удалении задачи из scheduler: {e}")
        
        # Удаляем напоминание из хранилища
        del reminders[user_id][reminder_id]
        save_reminders(reminders)
        
        # Редактируем исходное сообщение
        await callback.message.edit_text(
            "✅ Напоминание удалено",
            reply_markup=None
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при удалении напоминания: {e}")
        await callback.answer("Произошла ошибка при удалении напоминания")

def make_reminder_keyboard(reminder_id: str):
    """Создает инлайн-клавиатуру для удаления напоминания"""
    builder = InlineKeyboardBuilder()
    builder.add(
        types.InlineKeyboardButton(
            text="❌ Удалить",
            callback_data=f"delrem_{reminder_id}"
        )
    )
    return builder.as_markup()

@dp.callback_query(lambda c: c.data.startswith(("urgent_", "normal_")))
async def set_urgency(callback: types.CallbackQuery):
    urgency, reminder_id = callback.data.split("_")
    user_id = str(callback.from_user.id)
    
    if user_id in reminders and reminder_id in reminders[user_id]:
        is_urgent = (urgency == "urgent")
        reminders[user_id][reminder_id]['urgent'] = is_urgent
        save_reminders(reminders)
        
        text = reminders[user_id][reminder_id]['text']
        await callback.message.edit_text(
            text=f"✅ Напоминание создано!\nТекст: {text}\nТип: {'СРОЧНОЕ' if is_urgent else 'Обычное'}",
            reply_markup=None
        )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("stop_"))
async def stop_reminder(callback: types.CallbackQuery):
    reminder_id = callback.data.split("_")[1]
    user_id = str(callback.from_user.id)
    
    if user_id in reminders and reminder_id in reminders[user_id]:
        reminders[user_id][reminder_id]['active'] = False
        save_reminders(reminders)
        
        # Удаляем все запланированные уведомления для этого reminder_id
        for job in scheduler.get_jobs():
            if job.args and len(job.args) >= 3 and job.args[2] == reminder_id:
                job.remove()
        
        await callback.message.edit_text(
            text=f"⏸ Напоминание отключено: {reminders[user_id][reminder_id]['text']}",
            reply_markup=None
        )
        if reminders[user_id][reminder_id]["frequency"] == "однократно":
            del reminders[user_id][reminder_id]
            save_reminders(reminders)
    await callback.answer()