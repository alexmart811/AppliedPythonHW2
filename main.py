import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.filters.command import Command
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import json
import os
from set_profile import router as set_profile_router
from middlewares import LoggingMiddleware
from config import BOT_TOKEN

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
dp.include_router(set_profile_router)

dp.message.middleware(LoggingMiddleware())

async def get_food_info(product_name):
    url = f"https://world.openfoodfacts.org/cgi/search.pl?action=process&search_terms={product_name}&json=true"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                products = data.get('products', [])
                if products:  # Проверяем, есть ли найденные продукты
                    first_product = products[0]
                    return {
                        'name': first_product.get('product_name', 'Неизвестно'),
                        'calories': first_product.get('nutriments', {}).get('energy-kcal_100g', 0)
                    }
                return None
            return None

class Food(StatesGroup):
    grams = State()

class Workout(StatesGroup):
    cardio = State()
    strength = State()

@dp.message(Command("show_profile"))
async def show_profile(message: Message):
    if os.path.exists("user_infos.json"):
        try:
            with open("user_infos.json", "r", encoding="utf-8") as f:
                user_infos = json.load(f)
        except json.JSONDecodeError:
            user_infos = {}
    else:
        user_infos = {}

    if str(message.chat.id) in user_infos:
        user_info = user_infos[str(message.chat.id)]
        await message.answer(f"""
        Ваши данные:
            Вес: {user_info['weight']}
            Рост: {user_info['height']}
            Возраст: {user_info['age']}
            Активность: {user_info['activity']}
            Город: {user_info['city']}
            Норма воды: {user_info['water_goal']}
            Норма калорий: {user_info['calorie_goal']}
        """)
    else:
        await message.reply("По вам нет никаких данных.")
        await message.answer("Заполните профиль с помощью /set_profile")

@dp.message(Command("reset"))
async def reset(message: Message):
    with open("user_infos.json", "r", encoding="utf-8") as f:
        user_infos = json.load(f)
    
    user_infos[str(message.chat.id)]["water_curr"] = user_infos[str(message.chat.id)]["water_goal"]
    user_infos[str(message.chat.id)]["calorie_curr"] = user_infos[str(message.chat.id)]["calorie_goal"]
    user_infos[str(message.chat.id)]["calorie_burned"] = 0

    await message.reply("Текущие данные сброшены")

    with open("user_infos.json", "w", encoding="utf-8") as f:
        json.dump(user_infos, f, ensure_ascii=False)

@dp.message(Command("log_water"))
async def log_water(message: Message, command: Command):
    with open("user_infos.json", "r", encoding="utf-8") as f:
        user_infos = json.load(f)
    
    user_infos[str(message.chat.id)]["water_curr"] -= int(command.args)

    await message.reply(f"Было выпито {command.args} мл воды")
    await message.answer(f"Осталось {user_infos[str(message.chat.id)]['water_curr']} мл")

    with open("user_infos.json", "w", encoding="utf-8") as f:
        json.dump(user_infos, f, ensure_ascii=False)

@dp.message(Command("log_food"))
async def log_food(message: Message, command: Command, state: FSMContext):
    product = await get_food_info(command.args)
    if product:
        await message.reply(f"{product['name']} - {product['calories']} ккал на 100 гр. "
                            "Сколько граммов вы съели?")
        await state.update_data(cal=float(product['calories']))
        await state.set_state(Food.grams)
    else:
        await message.reply("Неверное имя продукта!")

@dp.message(Food.grams)
async def log_grams(message: Message, state: FSMContext):
    with open("user_infos.json", "r", encoding="utf-8") as f:
        user_infos = json.load(f)

    food_info = await state.get_data()
    cal = food_info.get("cal")
    grams = int(message.text)
    res_cals = int(cal / 100 * grams)
    user_infos[str(message.chat.id)]["calorie_curr"] -= res_cals
    await message.reply(f"Было потреблено {res_cals} ккал")
    await message.answer(f"Осталось набрать {user_infos[str(message.chat.id)]['calorie_curr']} ккал")

    with open("user_infos.json", "w", encoding="utf-8") as f:
        json.dump(user_infos, f, ensure_ascii=False)

@dp.message(Command("log_workout"))
async def log_workout(message: Message):
    kb = [
        [
            KeyboardButton(text="Кардио"),
            KeyboardButton(text="Силовые упражнения")
        ],
    ]
    keyboard = ReplyKeyboardMarkup(
        keyboard=kb,
        resize_keyboard=True,
        input_field_placeholder="Выберите способ подачи"
    )
    await message.reply("Выберите тип тренировки", reply_markup=keyboard)

@dp.message(F.text.lower() == "кардио")
async def cardio(message: Message, state: FSMContext):
    await message.reply("Введите число минут, потраченных на тренировку.")
    await state.set_state(Workout.cardio)

@dp.message(F.text.lower() == "силовые упражнения")
async def strength(message: Message, state: FSMContext):
    await message.reply("Введите число минут, потраченных на тренировку.")
    await state.set_state(Workout.strength)

@dp.message(Workout.cardio)
async def cardio_res(message: Message):
    with open("user_infos.json", "r", encoding="utf-8") as f:
        user_infos = json.load(f)

    burned_cal = int(message.text) * 10
    water_to_drink = int(message.text) // 30 * 200

    await message.reply(f"Кардио {message.text} минут - {burned_cal} ккал.")
    if water_to_drink:
        await message.answer(f"Дополнительно выпейте {water_to_drink} мл воды.")

    if "calorie_burned" in user_infos[str(message.chat.id)]:
        user_infos[str(message.chat.id)]["calorie_burned"] += burned_cal
    else:
        user_infos[str(message.chat.id)]["calorie_burned"] = burned_cal
    user_infos[str(message.chat.id)]["calorie_curr"] += burned_cal
    user_infos[str(message.chat.id)]["water_curr"] += water_to_drink

    with open("user_infos.json", "w", encoding="utf-8") as f:
        json.dump(user_infos, f, ensure_ascii=False)

@dp.message(Workout.strength)
async def strength_res(message: Message):
    with open("user_infos.json", "r", encoding="utf-8") as f:
        user_infos = json.load(f)

    burned_cal = int(message.text) * 5
    water_to_drink = int(message.text) // 15 * 200

    await message.reply(f"Силовые {message.text} минут - {burned_cal} ккал.")
    if water_to_drink:
        await message.answer(f"Дополнительно выпейте {water_to_drink} мл воды.")

    if "calorie_burned" in user_infos[str(message.chat.id)]:
        user_infos[str(message.chat.id)]["calorie_burned"] += burned_cal
    else:
        user_infos[str(message.chat.id)]["calorie_burned"] = burned_cal
    user_infos[str(message.chat.id)]["calorie_curr"] += burned_cal
    user_infos[str(message.chat.id)]["water_curr"] += water_to_drink

    with open("user_infos.json", "w", encoding="utf-8") as f:
        json.dump(user_infos, f, ensure_ascii=False)

@dp.message(Command("check_progress"))
async def check_progress(message: Message):
    with open("user_infos.json", "r", encoding="utf-8") as f:
        user_infos = json.load(f)
        user_info = user_infos[str(message.chat.id)]
    await message.reply(f"""
    Прогресс:
    Вода:
    - Выпито: {user_info['water_goal'] - user_info['water_curr']} мл из {user_info['water_goal']} мл.
    - Осталось: {user_info['water_curr']} мл.

    Калории:
    - Потреблено: {user_info['calorie_goal'] - user_info['calorie_curr']} ккал из {user_info['calorie_goal']} ккал.
    - Сожжено: {user_info['calorie_burned']} ккал.
    - Осталось: {user_info['calorie_curr']} ккал.                       
    """)

# Запуск процесса поллинга новых апдейтов
async def main():
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
