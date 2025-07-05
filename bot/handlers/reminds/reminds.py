from aiogram import types
from aiogram.filters import Command

from bot import dp, scheduler
from bot.handlers.reminds.storage import reminders, send_scheduled_message, save_reminders


@dp.message(Command("add"))
async def cmd_settime(message: types.Message):
    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            raise ValueError
        
        time_str = parts[1]
        reminder_name = parts[2]
        hour, minute = map(int, time_str.split(':'))
        
        user_id = str(message.from_user.id)
        
        if user_id in reminders and reminder_name in reminders[user_id]:
            await message.answer("❌ У вас уже есть напоминание с таким названием")
            return
        
        job = scheduler.add_job(
            send_scheduled_message,
            'cron',
            hour=hour,
            minute=minute,
            args=[message.chat.id, user_id, reminder_name],
            timezone='Europe/Kaliningrad'
        )
        
        if user_id not in reminders:
            reminders[user_id] = {}
            
        reminders[user_id][reminder_name] = {
            "time": time_str,
            "job_id": job.id
        }
        save_reminders(reminders)
        
        await message.answer(f"⏰ Напоминание создано:\n"
                           f"Название: {reminder_name}\n"
                           f"Время: {time_str}")
        
    except (IndexError, ValueError):
        await message.answer("❌ Формат команды:\n"
                           "/add ЧЧ:ММ название напоминания\n"
                           "Пример:\n"
                           "/add 12:41 убраться в комнате")

@dp.message(Command("check"))
async def cmd_myreminders(message: types.Message):
    user_id = str(message.from_user.id)
    
    if user_id not in reminders or not reminders[user_id]:
        await message.answer("У вас нет активных напоминаний")
        return
    
    reminders_list = [
        f"⏰ {reminder_name} - {data['time']}"
        for reminder_name, data in reminders[user_id].items()
    ]
    
    await message.answer("Ваши напоминания:\n" + "\n".join(reminders_list))

@dp.message(Command("delete"))
async def cmd_delreminder(message: types.Message):
    try:
        user_id = str(message.from_user.id)
        reminder_name = message.text.split(maxsplit=1)[1]
        
        if user_id not in reminders or reminder_name not in reminders[user_id]:
            await message.answer("❌ Напоминание не найдено")
            return
            
        scheduler.remove_job(reminders[user_id][reminder_name]["job_id"])
        
        del reminders[user_id][reminder_name]
        save_reminders(reminders)
        
        await message.answer(f"Напоминание '{reminder_name}' удалено")
        
    except IndexError:
        await message.answer("❌ Укажите название напоминания:\n"
                           "/delete название_напоминания")
 