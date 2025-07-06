import os
import json
from datetime import datetime, timedelta

from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot import bot, scheduler
from bot.logs.logging_config import logger


def load_reminders():
    if os.path.exists(REMINDERS_FILE):
        with open(REMINDERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_reminders(reminders):
    with open(REMINDERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(reminders, f, ensure_ascii=False, indent=2)
        
        
REMINDERS_FILE = "reminders.json"
reminders = load_reminders()

async def send_scheduled_message(chat_id: int, user_id: str, reminder_id: str):
    try:
        if user_id in reminders and reminder_id in reminders[user_id]:
            reminder = reminders[user_id][reminder_id]
            
            # Первое уведомление
            await send_repeated_alert(chat_id, user_id, reminder_id, reminder.get('urgent', False))
            
    except Exception as e:
        logger.error(f"Ошибка отправки напоминания: {e}")

async def send_repeated_alert(chat_id: int, user_id: str, reminder_id: str, urgent: bool):
    if user_id not in reminders or reminder_id not in reminders[user_id]:
        return
        
    reminder = reminders[user_id][reminder_id]
    
    # Если напоминание отключено
    if not reminder.get('active', True):
        return
        
    text = f"🔔 {reminder['text']}" + (" (СРОЧНО!)" if urgent else "")
    
    # Создаем клавиатуру с кнопкой отключения
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏸ Остановить", callback_data=f"stop_{reminder_id}")]
    ])
    
    await bot.send_message(chat_id, text, reply_markup=keyboard)
    
    # Планируем следующее уведомление
    if urgent:
        interval = 10  # Каждые 10 секунд для срочных
    else:
        interval = 60  # Каждую минуту для обычных
        
    scheduler.add_job(
        send_repeated_alert,
        'date',
        run_date=datetime.now() + timedelta(seconds=interval),
        args=[chat_id, user_id, reminder_id, urgent],
        timezone='Europe/Kaliningrad'
    )

def make_urgency_keyboard(reminder_id: str):
    """Создает инлайн-клавиатуру для срочности напоминания"""
    builder = InlineKeyboardBuilder()
    builder.add(
        types.InlineKeyboardButton(
            text="🔴 Срочное",
            callback_data=f"urgent_{reminder_id}"
        ))
    builder.add(
        types.InlineKeyboardButton(
            text="🟢 Обычное",
            callback_data=f"normal_{reminder_id}"
        )
    )
    return builder.as_markup()

def restore_reminders():
    for user_id, user_reminders in reminders.items():
        for reminder_name, data in user_reminders.items():
            try:
                hour, minute = map(int, data['time'].split(':'))
                
                scheduler.add_job(
                    send_scheduled_message,
                    'cron',
                    hour=hour,
                    minute=minute,
                    args=[int(user_id), user_id, reminder_name],
                    timezone='Europe/Kaliningrad',
                    id=data['job_id']
                )
            except Exception as e:
                logger.error(f"Ошибка восстановления напоминания: {e}")
