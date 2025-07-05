import os
import json

from bot import scheduler, bot
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


async def send_scheduled_message(chat_id: int, user_id: str, reminder_name: str):
    try:
        await bot.send_message(chat_id, f"🔔 Напоминание: {reminder_name}")
        
        if user_id in reminders and reminder_name in reminders[user_id]:
            del reminders[user_id][reminder_name]
            save_reminders(reminders)
            
    except Exception as e:
        logger.error(f"Ошибка отправки напоминания: {e}")