import os
import asyncio
import sqlite3
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder
import aiohttp

# === НАСТРОЙКИ ===
BOT_TOKEN = os.getenv("7765104602:AAHrOaSMB7gq5Msk2YHduEYJ-ayEfNXnxTQ")
if not BOT_TOKEN:
    raise ValueError("❌ Не задан токен бота! Укажите переменную окружения BOT_TOKEN.")

HH_API_URL = "https://api.hh.ru/vacancies"
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
DB_PATH = "users.db"

# === БАЗА ДАННЫХ ===
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            role TEXT,
            experience TEXT,
            salary INTEGER,
            work_format TEXT,
            city TEXT,
            skills TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_user(user_id, **kwargs):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cols = ", ".join(kwargs.keys())
    placeholders = ", ".join(["?" for _ in kwargs])
    values = list(kwargs.values())
    cur.execute(f"INSERT OR REPLACE INTO users (user_id, {cols}) VALUES (?, {placeholders})", [user_id] + values)
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return {
            "user_id": row[0], "role": row[1], "experience": row[2], "salary": row[3],
            "work_format": row[4], "city": row[5], "skills": row[6]
        }
    return None

# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===
def get_area_id(city: str):
    if not city:
        return 113  # Россия
    c = city.lower()
    if "москв" in c:
        return 1
    elif "петербург" in c or "спб" in c:
        return 2
    elif "екатеринбург" in c:
        return 3
    elif "новосибирск" in c:
        return 4
    elif "казань" in c:
        return 88
    elif "удал" in c or "remote" in c or "рф" in c or "россия" in c:
        return 113
    return 113

# === КЛАВИАТУРЫ ===
def main_menu():
    kb = ReplyKeyboardBuilder()
    kb.button(text="💼 Вакансии")
    kb.button(text="🎯 Ежедневный чек-лист")
    kb.button(text="👤 Мой профиль")
    kb.button(text="🗣️ Симулятор собеседования")
    return kb.as_markup(resize_keyboard=True)

role_list = ["Frontend", "Backend", "QA", "Продуктовый менеджер", "Аналитик данных", "DevOps", "Дизайнер", "Маркетолог", "Другое"]
exp_list = ["Junior", "Middle", "Senior"]
format_list = ["Офис", "Удалёнка", "Гибрид"]

# === ОСНОВНЫЕ ХЕНДЛЕРЫ ===
@dp.message(Command("start"))
async def start(message: types.Message):
    user = get_user(message.from_user.id)
    if user and user["role"]:
        await message.answer(
            "👋 С возвращением! Я — ваш карьерный помощник.\n\n"
            "Чем могу помочь сегодня?",
            reply_markup=main_menu()
        )
    else:
        await message.answer(
            "🚀 Добро пожаловать в *«Карьера на автопилоте»*!\n\n"
            "Я помогу вам:\n"
            "• Найти подходящие вакансии\n"
            "• Подготовиться к собеседованиям\n"
            "• Составить карьерный план\n\n"
            "Давайте настроим ваш профиль — это займёт 2 минуты.",
            parse_mode="Markdown"
        )
        await ask_role(message)

async def ask_role(message: types.Message):
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=r)] for r in role_list], resize_keyboard=True)
    await message.answer("Какая у вас специальность?", reply_markup=kb)

@dp.message(lambda m: m.text in role_list)
async def process_role(message: types.Message):
    save_user(message.from_user.id, role=message.text)
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=e)] for e in exp_list], resize_keyboard=True)
    await message.answer("Ваш уровень опыта?", reply_markup=kb)

@dp.message(lambda m: m.text in exp_list)
async def process_exp(message: types.Message):
    save_user(message.from_user.id, experience=message.text)
    await message.answer("Какая зарплата вас интересует? (укажите цифру в рублях, например: 120000)", reply_markup=types.ReplyKeyboardRemove())

@dp.message(lambda m: m.text.isdigit())
async def process_salary(message: types.Message):
    save_user(message.from_user.id, salary=int(message.text))
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=f)] for f in format_list], resize_keyboard=True)
    await message.answer("Предпочтительный формат работы?", reply_markup=kb)

@dp.message(lambda m: m.text in format_list)
async def process_format(message: types.Message):
    save_user(message.from_user.id, work_format=message.text)
    await message.answer("В каком городе вы ищете работу? (например: Москва, Удалёнка, Россия)")

@dp.message(lambda m: m.text and m.text not in role_list + exp_list + format_list and not m.text.isdigit())
async def process_city_and_skills(message: types.Message):
    user = get_user(message.from_user.id)
    if not user or not user.get("work_format"):
        # Это город
        save_user(message.from_user.id, city=message.text)
        await message.answer("Перечислите ключевые навыки через запятую (например: Python, SQL, Docker, Agile)")
    else:
        # Это навыки
        save_user(message.from_user.id, skills=message.text)
        await message.answer(
            "✅ Профиль успешно настроен!\n\n"
            "Теперь вы можете:\n"
            "• Получать подборку вакансий\n"
            "• Проходить симуляции собеседований\n"
            "• Получать ежедневные рекомендации\n\n"
            "Выберите действие ниже 👇",
            reply_markup=main_menu()
        )

# === ВАКАНСИИ ===
async def fetch_vacancies_from_hh(user):
    text = user.get("role", "")
    area = get_area_id(user.get("city", ""))
    salary = user.get("salary")
    work_format = user.get("work_format", "")

    params = {
        "text": text,
        "area": area,
        "per_page": 3,
        "page": 0
    }
    if salary:
        params["salary"] = salary
        params["only_with_salary"] = True
    if "удал" in work_format.lower():
        params["schedule"] = "remote"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(HH_API_URL, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("items", [])[:3]
        except Exception as e:
            logging.error(f"Ошибка при запросе к hh.ru: {e}")
    return []

@dp.message(lambda m: m.text == "💼 Вакансии")
async def show_vacancies(message: types.Message):
    user = get_user(message.from_user.id)
    if not user or not user.get("role"):
        await message.answer("Сначала настройте профиль командой /start")
        return

    vacancies = await fetch_vacancies_from_hh(user)
    if not vacancies:
        await message.answer("❌ Не удалось найти вакансии по вашему запросу. Попробуйте позже или уточните профиль.")
        return

    for v in vacancies:
        name = v['name']
        url = v['alternate_url']
        employer = v['employer']['name']
        area = v.get('area', {}).get('name', '—')
        salary_info = "💰 Не указана"
        if v.get('salary'):
            s_from = v['salary'].get('from') or ''
            s_to = v['salary'].get('to') or ''
            currency = v['salary'].get('currency', 'RUB')
            salary_str = f"{s_from}–{s_to} {currency}".replace("–", "—") if s_from or s_to else "По договорённости"
            salary_info = f"💰 {salary_str}"

        text = f"🔹 [{name}]({url})\n" \
               f"🏢 {employer}\n" \
               f"{salary_info}\n" \
               f"📍 {area}"
        await message.answer(text, parse_mode="Markdown", disable_web_page_preview=True)

# === ЧЕК-ЛИСТ ===
@dp.message(lambda m: m.text == "🎯 Ежедневный чек-лист")
async def send_checklist(message: types.Message):
    await message.answer(
        "📌 *Ваш карьерный чек-лист на сегодня:*\n\n"
        "✅ Откликнитесь на 1 новую вакансию\n"
        "✅ Обновите раздел «Навыки» в резюме\n"
        "✅ Пройдите короткий курс: [Как вести переговоры о зарплате](https://example.com)\n\n"
        "Выполняйте по одному пункту — и карьера пойдёт вверх! 💪",
        parse_mode="Markdown"
    )

# === ПРОФИЛЬ ===
@dp.message(lambda m: m.text == "👤 Мой профиль")
async def show_profile(message: types.Message):
    user = get_user(message.from_user.id)
    if not user or not user.get("role"):
        await message.answer("Профиль не настроен. Начните с команды /start")
        return

    exp_emoji = {"Junior": "🌱", "Middle": "🌿", "Senior": "🌳"}.get(user["experience"], "")
    format_emoji = {"Офис": "🏢", "Удалёнка": "🏠", "Гибрид": "🔄"}.get(user["work_format"], "")

    text = (
        f"👤 *Ваш профиль:*\n\n"
        f"Роль: {user['role']}\n"
        f"Опыт: {exp_emoji} {user['experience']}\n"
        f"Зарплата: {user['salary']} ₽\n"
        f"Формат: {format_emoji} {user['work_format']}\n"
        f"Город: {user['city']}\n"
        f"Навыки: {user['skills'] or '—'}\n\n"
        "Чтобы изменить профиль — отправьте /start заново."
    )
    await message.answer(text, parse_mode="Markdown")

# === СОБЕСЕДОВАНИЕ ===
@dp.message(lambda m: m.text == "🗣️ Симулятор собеседования")
async def interview_sim(message: types.Message):
    await message.answer(
        "🧠 *Вопрос на собеседовании:*\n\n"
        "«Расскажите о себе и своём профессиональном опыте.»\n\n"
        "Ответьте текстом — я дам обратную связь по структуре и содержанию.",
        parse_mode="Markdown"
    )

# === ЗАПУСК ===
async def main():
    init_db()
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
