from aiogram import Router, F
from aiogram.filters.command import Command
from aiogram.types import Message, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
import json
import os
import aiohttp
from config import OWM_TOKEN

router = Router()

async def fetch_data(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()

class PersonInfo(StatesGroup):
    weight = State()
    height = State()
    age = State()
    activity = State()
    temperature = State()
    water_goal = State()
    calorie_goal = State()

@router.message(Command("set_profile"))
async def start_form(message: Message, state: FSMContext):
    await message.reply("Введите ваш вес (в кг)")
    await state.set_state(PersonInfo.weight)

@router.message(PersonInfo.weight)
async def process_weight(message: Message, state: FSMContext):
    await state.update_data(weight=message.text)
    await message.reply("Введите ваш рост (в см)")
    await state.set_state(PersonInfo.height)

@router.message(PersonInfo.height)
async def process_height(message: Message, state: FSMContext):
    await state.update_data(height=message.text)
    await message.reply("Введите ваш возраст")
    await state.set_state(PersonInfo.age)

@router.message(PersonInfo.age)
async def process_age(message: Message, state: FSMContext):
    await state.update_data(age=message.text)
    await message.reply("Сколько минут активности у вас в день?")
    await state.set_state(PersonInfo.activity)

@router.message(PersonInfo.activity)
async def process_activity(message: Message, state: FSMContext):
    await state.update_data(activity=message.text)
    await message.reply("В каком городе вы находитесь? (по-английски)")
    await state.set_state(PersonInfo.temperature)

@router.message(PersonInfo.temperature)
async def process_city(message: Message, state: FSMContext):

    response = await fetch_data(f"https://api.openweathermap.org/data/2.5/weather?q={message.text}&appid={OWM_TOKEN}")

    if response['cod'] == 200:
        temp = round(float(response['main']['temp']) - 273.15, 2)
        await state.update_data(temp=temp)
        await state.update_data(city=message.text)

        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(
            text="Установить автоматически",
            callback_data="auto_water")
        )
        await message.reply(
            "Установите дневную норму воды (в мл)",
            reply_markup=builder.as_markup()
        )
        await state.set_state(PersonInfo.water_goal)
    else:
        await message.reply("Неверное имя города! Введите еще раз.")
        await state.set_state(PersonInfo.temperature)

@router.callback_query(F.data == "auto_water")
async def calculate_water(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    weight = int(data.get('weight'))
    activity = int(data.get('activity')) // 30
    is_hot = int(float(data.get('temp')) > 25)
    water_daily = int(weight * 30 + 500 * activity + 500 - 1000 * is_hot)
    await state.update_data(water_goal=water_daily, water_curr=water_daily)

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="Установить автоматически",
        callback_data="auto_calorie")
    )
    await callback.message.reply(
        "Установите дневную норму калорий",
        reply_markup=builder.as_markup()
    )
    await state.set_state(PersonInfo.calorie_goal)

@router.message(PersonInfo.water_goal)
async def process_water_goal(message: Message, state: FSMContext):
    await state.update_data(water_goal=int(message.text), water_curr=int(message.text))
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="Установить автоматически",
        callback_data="auto_calorie")
    )
    await message.reply(
        "Установите дневную норму калорий",
        reply_markup=builder.as_markup()
    )
    await state.set_state(PersonInfo.calorie_goal)

@router.callback_query(F.data == "auto_calorie")
async def calculate_water(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    weight = int(data.get('weight'))
    height = int(data.get('height'))
    age = int(data.get('age'))
    cal_daily = int(weight * 10 + 6.25 * height - 5 * age)
    await state.update_data(calorie_goal=cal_daily, calorie_curr=cal_daily)

    data = await state.get_data()
    await callback.message.answer(f"""
    Ваши данные:
        Вес: {data.get('weight')}
        Рост: {data.get('height')}
        Возраст: {data.get('age')}
        Активность: {data.get('activity')}
        Город: {data.get('city')}
        Норма воды: {data.get('water_goal')}
        Норма калорий: {data.get('calorie_goal')}
    """)

    builder = InlineKeyboardBuilder()
    builder.button(
        text="Да", callback_data="accept_info"
    )
    await callback.message.answer(
        "Подтвердить информацию?",
        reply_markup=builder.as_markup()
    )

@router.message(PersonInfo.calorie_goal)
async def process_calorie_goal(message: Message, state: FSMContext):
    await state.update_data(calorie_goal=int(message.text), calorie_curr=int(message.text))

    data = await state.get_data()
    await message.answer(f"""
    Ваши данные:
        Вес: {data.get('weight')}
        Рост: {data.get('height')}
        Возраст: {data.get('age')}
        Активность: {data.get('activity')}
        Город: {data.get('city')}
        Норма воды: {data.get('water_goal')}
        Норма калорий: {data.get('calorie_goal')}
    """)
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="Да",
        callback_data="accept_info")
    )
    await message.answer(
        "Подтвердить информацию?",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data == "accept_info")
async def write_info(callback: CallbackQuery, state: FSMContext):
    user_info = {str(callback.message.chat.id): await state.get_data()}
    if user_info == {}:
        callback.message.answer("Правильно заполните поля!")
        await state.clear()
    else:
        if os.path.exists("user_infos.json"):
            try:
                with open("user_infos.json", "r", encoding="utf-8") as f:
                    user_infos = json.load(f)
            except json.JSONDecodeError:
                user_infos = {}
        else:
            user_infos = {}
        
        user_infos.update(user_info)
        with open("user_infos.json", "w", encoding="utf-8") as f:
            json.dump(user_infos, f, ensure_ascii=False)

        await state.clear()