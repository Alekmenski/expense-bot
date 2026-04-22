import asyncio
import os
import json

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import matplotlib.pyplot as plt


# --- TOKEN ---
TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()


# --- GOOGLE SHEETS (исправленный вариант 🔥) ---
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

raw = os.getenv("GOOGLE_CREDS")

# 🔥 фикс всех проблем с переносами строк
raw = raw.replace('\n', '\\n')
raw = raw.replace('\\\\n', '\\n')

creds_json = json.loads(raw)

creds = ServiceAccountCredentials.from_json_keyfile_dict(
    creds_json, scope
)

client = gspread.authorize(creds)
sheet = client.open("Учет расходов и доходов").sheet1


# ====== КАТЕГОРИИ ======

expense_categories = {
    "🏠 ЖКХ": "ЖКХ",
    "🛒 Продукты": "Продукты",
    "💊 Лекарства": "Лекарства",
    "🚗 Автомобиль": "Автомобиль",
    "🎮 Развлечения": "Развлечения",
    "👗 Одежда": "Одежда",
    "🚌 Транспорт": "Транспорт",
    "💄 Бьюти": "Бьюти",
    "🍽 Обеды": "Обеды",
    "📱 Связь": "Связь"
}

income_categories = {
    "💼 ЗП Влад": "ЗП Влад",
    "💰 Аванс Влад": "Аванс Влад",
    "🎁 Премия Влад": "Премия Влад",
    "💼 ЗП Настя": "ЗП Настя",
    "💰 Аванс Настя": "Аванс Настя"
}

months_map = {
    "Январь": 1, "Февраль": 2, "Март": 3,
    "Апрель": 4, "Май": 5, "Июнь": 6,
    "Июль": 7, "Август": 8, "Сентябрь": 9,
    "Октябрь": 10, "Ноябрь": 11, "Декабрь": 12
}

# ====== СОСТОЯНИЕ ======
user_state = {}

# ====== КНОПКИ ======

main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💸 Расходы"), KeyboardButton(text="💰 Доходы")],
        [KeyboardButton(text="📊 Аналитика"), KeyboardButton(text="📅 Выбрать месяц")],
        [KeyboardButton(text="📊 План vs Факт"), KeyboardButton(text="💼 Накопления")],
        [KeyboardButton(text="📌 Планируемые расходы")]
    ],
    resize_keyboard=True
)

def make_keyboard(items):
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=i)] for i in items],
        resize_keyboard=True
    )

# ====== START ======

@dp.message(lambda m: m.text == "/start")
async def start(message: types.Message):
    await message.answer("Выберите действие:", reply_markup=main_kb)

# ====== ВЫБОР РАЗДЕЛОВ ======

@dp.message(lambda m: m.text == "💸 Расходы")
async def expenses(message: types.Message):
    user_state[message.from_user.id] = {"type": "расход"}
    await message.answer("Выбери категорию:", reply_markup=make_keyboard(expense_categories.keys()))

@dp.message(lambda m: m.text == "💰 Доходы")
async def income(message: types.Message):
    user_state[message.from_user.id] = {"type": "доход"}
    await message.answer("Выбери категорию:", reply_markup=make_keyboard(income_categories.keys()))

@dp.message(lambda m: m.text == "📌 Планируемые расходы")
async def planned(message: types.Message):
    user_state[message.from_user.id] = {"type": "план"}
    await message.answer("Выбери категорию:", reply_markup=make_keyboard(expense_categories.keys()))

@dp.message(lambda m: m.text == "💼 Накопления")
async def savings(message: types.Message):
    user_state[message.from_user.id] = {"type": "накопление"}
    await message.answer("Введи сумму накоплений:")

# ====== КАТЕГОРИЯ ======

@dp.message()
async def handle(message: types.Message):
    user_id = message.from_user.id
    text = message.text

    # выбор категории
    if user_id in user_state and "category" not in user_state[user_id]:
        if text in expense_categories:
            user_state[user_id]["category"] = expense_categories[text]
            await message.answer("Введи сумму:")
            return

        if text in income_categories:
            user_state[user_id]["category"] = income_categories[text]
            await message.answer("Введи сумму:")
            return

    # ввод суммы
    if user_id in user_state and "category" in user_state[user_id]:
        try:
            amount = float(text)
        except:
            await message.answer("Введите число")
            return

        data = user_state[user_id]
        now = datetime.now()

        sheet.append_row([
            now.strftime("%Y-%m-%d"),
            data["type"],
            data["category"],
            amount
        ])

        await message.answer(
            f"✅ Записано:\n{data['type']} | {data['category']} | {amount}",
            reply_markup=main_kb
        )

        user_state.pop(user_id)
        return

# ====== АНАЛИТИКА ======

@dp.message(lambda m: m.text == "📊 Аналитика")
async def analytics(message: types.Message):
    records = sheet.get_all_values()

    expenses = {}

    for row in records[1:]:
        if row[1] == "расход":
            cat = row[2]
            amt = float(row[3])
            expenses[cat] = expenses.get(cat, 0) + amt

    plt.figure()
    plt.bar(expenses.keys(), expenses.values())
    plt.xticks(rotation=45)

    plt.savefig("chart.png")

    await message.answer_photo(types.FSInputFile("chart.png"))

# ====== ПЛАН VS ФАКТ ======

@dp.message(lambda m: m.text == "📊 План vs Факт")
async def plan_vs_fact(message: types.Message):
    records = sheet.get_all_values()

    plan = {}
    fact = {}

    for row in records[1:]:
        try:
            type_ = row[1]
            category = row[2]
            amount = float(row[3])

            if type_ == "план":
                plan[category] = plan.get(category, 0) + amount
            elif type_ == "расход":
                fact[category] = fact.get(category, 0) + amount
        except:
            continue

    text = "📊 План vs Факт:\n\n"

    categories = set(plan.keys()) | set(fact.keys())

    total_plan = 0
    total_fact = 0

    for cat in categories:
        p = plan.get(cat, 0)
        f = fact.get(cat, 0)

        total_plan += p
        total_fact += f

        status = "✅" if f <= p else "❌"

        text += f"{cat}\nПлан: {p} | Факт: {f} {status}\n\n"

    text += f"\nИТОГО:\nПлан: {total_plan}\nФакт: {total_fact}"

    await message.answer(text)

# ====== ЗАПУСК ======

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())