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

TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- Google Sheets ---
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds_json = json.loads(os.getenv("GOOGLE_CREDS"))

creds = ServiceAccountCredentials.from_json_keyfile_dict(
    creds_json, scope
)
client = gspread.authorize(creds)

sheet = client.open("Учет расходов и доходов").sheet1


# --- МЕСЯЦЫ ---
months_map = {
    "январь": "01", "февраль": "02", "март": "03",
    "апрель": "04", "май": "05", "июнь": "06",
    "июль": "07", "август": "08", "сентябрь": "09",
    "октябрь": "10", "ноябрь": "11", "декабрь": "12"
}


# --- Категории ---
expense_categories = [
    "🏠 ЖКХ","🛒 Продукты","💊 Лекарства","🚗 Автомобиль",
    "🎉 Развлечения и отдых","👕 Одежда и обувь","🚌 Транспорт",
    "💄 Бьюти","🍽 Обеды","📱 Связь","📦 Прочие расходы"
]

income_categories = [
    "💰 Влад Зарплата","💰 Влад Аванс","💰 Влад Премия",
    "💰 Настя Зарплата","💰 Настя Аванс"
]


# --- Клавиатуры ---
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💸 Расходы"), KeyboardButton(text="💰 Доходы")],
        [KeyboardButton(text="📅 Планируемые расходы")],
        [KeyboardButton(text="🏦 Накопления")],
        [KeyboardButton(text="📊 Баланс"), KeyboardButton(text="📅 Заработок за месяц")],
        [KeyboardButton(text="📊 План vs Факт"), KeyboardButton(text="📈 Аналитика расходов")],
        [KeyboardButton(text="📊 График расходов")]
    ],
    resize_keyboard=True
)

expense_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🏠 ЖКХ"), KeyboardButton(text="🛒 Продукты")],
        [KeyboardButton(text="💊 Лекарства"), KeyboardButton(text="🚗 Автомобиль")],
        [KeyboardButton(text="🎉 Развлечения и отдых")],
        [KeyboardButton(text="👕 Одежда и обувь"), KeyboardButton(text="🚌 Транспорт")],
        [KeyboardButton(text="💄 Бьюти"), KeyboardButton(text="🍽 Обеды")],
        [KeyboardButton(text="📱 Связь"), KeyboardButton(text="📦 Прочие расходы")],
        [KeyboardButton(text="⬅️ Назад")]
    ],
    resize_keyboard=True
)

income_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💰 Влад Зарплата"), KeyboardButton(text="💰 Влад Аванс")],
        [KeyboardButton(text="💰 Влад Премия")],
        [KeyboardButton(text="💰 Настя Зарплата"), KeyboardButton(text="💰 Настя Аванс")],
        [KeyboardButton(text="⬅️ Назад")]
    ],
    resize_keyboard=True
)

plan_keyboard = expense_keyboard

savings_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Пополнить"), KeyboardButton(text="➖ Снять")],
        [KeyboardButton(text="⬅️ Назад")]
    ],
    resize_keyboard=True
)


# --- Состояния ---
user_state = {}
plan_mode_users = set()
savings_mode = {}


# --- START ---
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("Выбери раздел 👇", reply_markup=main_keyboard)


# --- ОТЧЕТ ПО МЕСЯЦУ ---
@dp.message()
async def month_report(message: types.Message):
    text = message.text.lower().strip()

    if text not in months_map:
        return

    month_number = months_map[text]
    year = datetime.now().strftime("%Y")
    target = f"{year}-{month_number}"

    records = sheet.get_all_values()

    income = expense = savings_plus = savings_minus = 0

    for row in records[1:]:
        try:
            date = row[0]
            type_ = row[1]
            amount = float(row[3])

            if date.startswith(target):
                if type_ == "доход": income += amount
                elif type_ == "расход": expense += amount
                elif type_ == "накопление_плюс": savings_plus += amount
                elif type_ == "накопление_минус": savings_minus += amount
        except:
            continue

    balance = income - expense - savings_plus + savings_minus

    await message.answer(
        f"📅 Отчёт за {text}:\n\n"
        f"💰 Доходы: {income} ₽\n"
        f"💸 Расходы: {expense} ₽\n"
        f"🏦 Накопления: {savings_plus} ₽\n"
        f"🏦 Снято: {savings_minus} ₽\n\n"
        f"🟢 Баланс: {balance} ₽"
    )


# --- БАЛАНС ---
@dp.message(lambda m: m.text == "📊 Баланс")
async def balance_handler(message: types.Message):
    records = sheet.get_all_values()

    income = expense = savings_plus = savings_minus = 0

    for row in records[1:]:
        try:
            t = row[1]
            a = float(row[3])

            if t == "доход": income += a
            elif t == "расход": expense += a
            elif t == "накопление_плюс": savings_plus += a
            elif t == "накопление_минус": savings_minus += a
        except:
            continue

    balance = income - expense - savings_plus + savings_minus

    await message.answer(f"📊 Баланс: {balance} ₽")


# --- ГРАФИК ---
@dp.message(lambda m: m.text == "📊 График расходов")
async def chart(message: types.Message):
    records = sheet.get_all_values()
    mth = datetime.now().strftime("%Y-%m")

    data = {}

    for r in records[1:]:
        try:
            if r[1] == "расход" and r[0].startswith(mth):
                data[r[2]] = data.get(r[2], 0) + float(r[3])
        except:
            continue

    if not data:
        await message.answer("Нет данных")
        return

    plt.figure()
    plt.pie(data.values(), labels=data.keys(), autopct='%1.1f%%')
    plt.savefig("chart.png")
    plt.close()

    with open("chart.png", "rb") as p:
        await message.answer_photo(p)


# --- ОСНОВНАЯ ЛОГИКА ---
@dp.message()
async def handle(message: types.Message):
    t = message.text.strip()
    uid = message.from_user.id

    if t == "💸 Расходы":
        await message.answer("Категория 👇", reply_markup=expense_keyboard); return
    if t == "💰 Доходы":
        await message.answer("Категория 👇", reply_markup=income_keyboard); return
    if t == "📅 Планируемые расходы":
        plan_mode_users.add(uid)
        await message.answer("Категория 👇", reply_markup=plan_keyboard); return
    if t == "🏦 Накопления":
        await message.answer("Действие 👇", reply_markup=savings_keyboard); return
    if t == "➕ Пополнить":
        savings_mode[uid] = "плюс"; await message.answer("Сумма?"); return
    if t == "➖ Снять":
        savings_mode[uid] = "минус"; await message.answer("Сумма?"); return
    if t == "⬅️ Назад":
        await message.answer("Меню", reply_markup=main_keyboard); return

    if uid in savings_mode:
        try:
            a = float(t)
            typ = "накопление_плюс" if savings_mode[uid]=="плюс" else "накопление_минус"
            sheet.append_row([datetime.now().strftime("%Y-%m-%d"), typ, "Накопления", a])
            await message.answer("🏦 Готово", reply_markup=main_keyboard)
            del savings_mode[uid]
        except:
            await message.answer("Ошибка")
        return

    if t in expense_categories:
        user_state[uid] = ("план" if uid in plan_mode_users else "расход", t)
        await message.answer("Сумма?"); return

    if t in income_categories:
        user_state[uid] = ("доход", t)
        await message.answer("Сумма?"); return

    if uid in user_state:
        typ, cat = user_state[uid]
        try:
            a = float(t)
            clean = cat.split(" ",1)[1]
            sheet.append_row([datetime.now().strftime("%Y-%m-%d"), typ, clean, a])
            await message.answer("✅ Записано", reply_markup=main_keyboard)
            del user_state[uid]
            plan_mode_users.discard(uid)
        except:
            await message.answer("Ошибка")
        return

    await message.answer("Выбери действие 👇", reply_markup=main_keyboard)


# --- RUN ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())