import asyncio
import json
import sqlite3
import logging
import random
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.types import LabeledPrice, PreCheckoutQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import Command
from aiogram.types import BotCommand, BotCommandScopeDefault

# ========== КОНФИГУРАЦИЯ ==========
TOKEN = "8078933687:AAGjKvWOQVrozbyUEWcUThuvC3RUjXmk5WY"  # ← ВСТАВЬТЕ СВОЙ ТОКЕН
WEBAPP_URL = "https://ваш-хостинг.com/index.html"  # ← ССЫЛКА НА HTML (после загрузки)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ========== БАЗА ДАННЫХ (SQLite) ==========
conn = sqlite3.connect('watermelon_bot.db', check_same_thread=False)
cursor = conn.cursor()

# Создаём все таблицы
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        watermelons INTEGER DEFAULT 0,
        stars_balance INTEGER DEFAULT 0,
        multiplier REAL DEFAULT 1.0,
        level INTEGER DEFAULT 1,
        total_earned INTEGER DEFAULT 0,
        total_spent_stars INTEGER DEFAULT 0,
        daily_streak INTEGER DEFAULT 0,
        last_daily DATE,
        boost_expires DATETIME,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        item_type TEXT,
        amount_stars INTEGER,
        purchase_date DATETIME DEFAULT CURRENT_TIMESTAMP
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS referrals (
        referrer_id INTEGER,
        referred_id INTEGER PRIMARY KEY,
        bonus_given INTEGER DEFAULT 0,
        date DATETIME DEFAULT CURRENT_TIMESTAMP
    )
''')

conn.commit()

# ========== ФУНКЦИИ РАБОТЫ С БД ==========
def get_user(user_id, username=None):
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    if row:
        return {
            'user_id': row[0],
            'username': row[1],
            'watermelons': row[2],
            'stars_balance': row[3],
            'multiplier': row[4],
            'level': row[5],
            'total_earned': row[6],
            'total_spent_stars': row[7],
            'daily_streak': row[8],
            'last_daily': row[9],
            'boost_expires': row[10]
        }
    else:
        cursor.execute('''
            INSERT INTO users (user_id, username, watermelons, stars_balance, multiplier, level, total_earned, total_spent_stars, daily_streak)
            VALUES (?, ?, 100, 0, 1.0, 1, 0, 0, 0)
        ''', (user_id, username))
        conn.commit()
        return get_user(user_id)

def update_user(user_id, **kwargs):
    for key, value in kwargs.items():
        cursor.execute(f'UPDATE users SET {key} = ? WHERE user_id = ?', (value, user_id))
    conn.commit()

def add_purchase(user_id, item_type, amount_stars):
    cursor.execute('INSERT INTO purchases (user_id, item_type, amount_stars) VALUES (?, ?, ?)',
                   (user_id, item_type, amount_stars))
    conn.commit()

# ========== КОМАНДЫ БОТА ==========
async def set_commands():
    commands = [
        BotCommand(command="start", description="🍉 Главное меню"),
        BotCommand(command="profile", description="📊 Мой профиль"),
        BotCommand(command="top", description="🏆 Топ игроков"),
        BotCommand(command="daily", description="🎁 Ежедневный бонус"),
        BotCommand(command="referral", description="👥 Пригласить друга"),
        BotCommand(command="shop", description="⭐ Магазин за Stars"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())

@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    user = get_user(user_id, username)
    
    # Реферальная система
    args = message.text.split()
    if len(args) > 1 and args[1].isdigit():
        referrer_id = int(args[1])
        if referrer_id != user_id:
            cursor.execute('SELECT * FROM referrals WHERE referred_id = ?', (user_id,))
            if not cursor.fetchone():
                cursor.execute('INSERT INTO referrals (referrer_id, referred_id, bonus_given) VALUES (?, ?, 0)', (referrer_id, user_id))
                conn.commit()
                update_user(referrer_id, stars_balance=get_user(referrer_id)['stars_balance'] + 20)
                update_user(user_id, stars_balance=user['stars_balance'] + 10)
                await bot.send_message(referrer_id, f"🎉 Друг пригласил вас! Вы получили +20 Stars!")
                await message.answer(f"🎉 Вы пришли по реферальной ссылке! +10 Stars на счёт!")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🍉 ИГРАТЬ", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton(text="⭐ Магазин", callback_data="shop_menu"),
         InlineKeyboardButton(text="🎁 Дейли бонус", callback_data="daily_claim")],
        [InlineKeyboardButton(text="📊 Профиль", callback_data="profile"),
         InlineKeyboardButton(text="👥 Рефералы", callback_data="referral_menu")],
        [InlineKeyboardButton(text="🏆 Топ игроков", callback_data="top_players")]
    ])
    
    await message.answer(
        f"🍉 *Добро пожаловать в Арбузную Математику!*\n\n"
        f"👤 {user['username']}\n"
        f"🍉 Арбузов: *{user['watermelons']}*\n"
        f"⭐ Stars: *{user['stars_balance']}*\n"
        f"📈 Множитель: x{user['multiplier']}\n"
        f"🎚️ Уровень: {user['level']}\n\n"
        f"Решай примеры → получай арбузы → покупай бусты за реальные Stars!",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.message(Command("profile"))
async def profile_cmd(message: types.Message):
    user = get_user(message.from_user.id)
    await message.answer(
        f"📊 *Ваш профиль*\n\n"
        f"👤 {user['username']}\n"
        f"🍉 Арбузов: {user['watermelons']}\n"
        f"⭐ Stars: {user['stars_balance']}\n"
        f"📈 Множитель: x{user['multiplier']}\n"
        f"🎚️ Уровень: {user['level']}\n"
        f"💰 Всего заработано: {user['total_earned']} 🍉\n"
        f"💸 Потрачено Stars: {user['total_spent_stars']}\n"
        f"🔥 Дейли-стрик: {user['daily_streak']} дней",
        parse_mode="Markdown"
    )

@dp.message(Command("top"))
async def top_cmd(message: types.Message):
    cursor.execute('SELECT username, watermelons, level FROM users ORDER BY watermelons DESC LIMIT 10')
    top_users = cursor.fetchall()
    text = "🏆 *Топ игроков по арбузам*\n\n"
    for i, (name, wm, lvl) in enumerate(top_users, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} {name} — {wm} 🍉 (ур.{lvl})\n"
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("daily"))
async def daily_cmd(message: types.Message):
    await claim_daily(message.from_user.id, message.chat.id)

async def claim_daily(user_id, chat_id):
    user = get_user(user_id)
    today = datetime.now().date()
    
    if user['last_daily']:
        last = datetime.strptime(user['last_daily'], '%Y-%m-%d').date()
        if last == today:
            await bot.send_message(chat_id, "🎁 Вы уже получили ежедневный бонус сегодня! Возвращайтесь завтра.")
            return
        streak = user['daily_streak'] + 1 if (today - last).days == 1 else 1
    else:
        streak = 1
    
    bonus = 50 + (streak * 10)
    update_user(user_id, watermelons=user['watermelons'] + bonus, daily_streak=streak, last_daily=today)
    await bot.send_message(chat_id, f"🎁 Ежедневный бонус! +{bonus} 🍉\n🔥 Стрик: {streak} дней!")

@dp.message(Command("referral"))
async def referral_cmd(message: types.Message):
    user_id = message.from_user.id
    link = f"https://t.me/{bot.username}?start={user_id}"
    cursor.execute('SELECT COUNT(*) FROM referrals WHERE referrer_id = ?', (user_id,))
    ref_count = cursor.fetchone()[0]
    await message.answer(
        f"👥 *Реферальная программа*\n\n"
        f"Приглашай друзей и получай бонусы:\n"
        f"• Ты получаешь *20 Stars* за каждого друга\n"
        f"• Друг получает *10 Stars* при старте\n\n"
        f"Твоя ссылка:\n`{link}`\n\n"
        f"Приглашено друзей: {ref_count}",
        parse_mode="Markdown"
    )

# ========== ПЛАТЕЖИ ЗА TELEGRAM STARS ==========
async def create_stars_invoice(chat_id, title, description, payload, amount_stars, photo_url=None):
    await bot.send_invoice(
        chat_id=chat_id,
        title=title,
        description=description,
        payload=payload,
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="⭐ Telegram Stars", amount=amount_stars)],
        start_parameter="watermelon_shop",
        photo_url=photo_url,
        photo_size=512
    )

@dp.callback_query(lambda c: c.data.startswith("buy_"))
async def process_purchase(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    data = callback.data
    
    shop_items = {
        "buy_boost_50": {"title": "🍉 Маленький буст", "desc": "+50 арбузов", "stars": 5, "payload": "boost_50"},
        "buy_boost_200": {"title": "🍉 Большой буст", "desc": "+200 арбузов", "stars": 15, "payload": "boost_200"},
        "buy_boost_1000": {"title": "🍉 Мега буст", "desc": "+1000 арбузов", "stars": 60, "payload": "boost_1000"},
        "buy_multiplier_x2": {"title": "✨ Множитель x2", "desc": "Навсегда удваивает арбузы", "stars": 25, "payload": "multiplier_2"},
        "buy_multiplier_x3": {"title": "🔥 Множитель x3", "desc": "Навсегда утраивает арбузы", "stars": 60, "payload": "multiplier_3"},
        "buy_24h_boost": {"title": "⏱️ Ускорение 24ч", "desc": "x1.5 к арбузам на 24 часа", "stars": 10, "payload": "temporary_boost"}
    }
    
    if data in shop_items:
        item = shop_items[data]
        await create_stars_invoice(
            chat_id=callback.message.chat.id,
            title=item["title"],
            description=item["desc"],
            payload=f"{item['payload']}_{user_id}",
            amount_stars=item["stars"]
        )
    await callback.answer()

@dp.pre_checkout_query()
async def pre_checkout(pre_checkout: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout.id, ok=True)

@dp.message(lambda m: m.successful_payment)
async def successful_payment(message: types.Message):
    user_id = message.from_user.id
    payload = message.successful_payment.invoice_payload
    stars_amount = message.successful_payment.total_amount
    
    user = get_user(user_id)
    
    if "boost_50" in payload:
        new_wm = user['watermelons'] + 50
        update_user(user_id, watermelons=new_wm, total_spent_stars=user['total_spent_stars'] + stars_amount)
        add_purchase(user_id, "boost_50", stars_amount)
        await message.answer(f"✅ +50 арбузов! Теперь у тебя {new_wm} 🍉")
        
    elif "boost_200" in payload:
        new_wm = user['watermelons'] + 200
        update_user(user_id, watermelons=new_wm, total_spent_stars=user['total_spent_stars'] + stars_amount)
        add_purchase(user_id, "boost_200", stars_amount)
        await message.answer(f"✅ +200 арбузов! Теперь у тебя {new_wm} 🍉")
        
    elif "boost_1000" in payload:
        new_wm = user['watermelons'] + 1000
        update_user(user_id, watermelons=new_wm, total_spent_stars=user['total_spent_stars'] + stars_amount)
        add_purchase(user_id, "boost_1000", stars_amount)
        await message.answer(f"✅ +1000 арбузов! Теперь у тебя {new_wm} 🍉")
        
    elif "multiplier_2" in payload:
        new_mult = max(user['multiplier'], 2.0)
        update_user(user_id, multiplier=new_mult, total_spent_stars=user['total_spent_stars'] + stars_amount)
        add_purchase(user_id, "multiplier_x2", stars_amount)
        await message.answer(f"✨ Множитель x2 активирован! Теперь x{new_mult}")
        
    elif "multiplier_3" in payload:
        new_mult = max(user['multiplier'], 3.0)
        update_user(user_id, multiplier=new_mult, total_spent_stars=user['total_spent_stars'] + stars_amount)
        add_purchase(user_id, "multiplier_x3", stars_amount)
        await message.answer(f"🔥 Множитель x3 активирован! Теперь x{new_mult}")
        
    elif "temporary_boost" in payload:
        expires = datetime.now() + timedelta(hours=24)
        update_user(user_id, boost_expires=expires, total_spent_stars=user['total_spent_stars'] + stars_amount)
        add_purchase(user_id, "24h_boost", stars_amount)
        await message.answer(f"⏱️ Ускорение активировано на 24 часа! x1.5 к арбузам")
    
    # Обновляем уровень
    new_level = 1 + (user['watermelons'] // 500)
    if new_level > user['level']:
        update_user(user_id, level=new_level)
        await message.answer(f"🎉 ПОЗДРАВЛЯЮ! Ты достиг {new_level} уровня! 🎉")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🍉 ИГРАТЬ", web_app=WebAppInfo(url=WEBAPP_URL))]
    ])
    await message.answer("🎉 Спасибо за покупку! Возвращайся в игру за новыми арбузами!", reply_markup=keyboard)

# ========== КЛАВИАТУРЫ ==========
@dp.callback_query(lambda c: c.data == "shop_menu")
async def shop_menu(callback: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🍉 +50 арбузов — 5⭐", callback_data="buy_boost_50")],
        [InlineKeyboardButton(text="🍉 +200 арбузов — 15⭐", callback_data="buy_boost_200")],
        [InlineKeyboardButton(text="🍉 +1000 арбузов — 60⭐", callback_data="buy_boost_1000")],
        [InlineKeyboardButton(text="✨ Множитель x2 — 25⭐", callback_data="buy_multiplier_x2")],
        [InlineKeyboardButton(text="🔥 Множитель x3 — 60⭐", callback_data="buy_multiplier_x3")],
        [InlineKeyboardButton(text="⏱️ Ускорение 24ч (x1.5) — 10⭐", callback_data="buy_24h_boost")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]
    ])
    await callback.message.edit_text(
        "⭐ *Магазин Telegram Stars*\n\n"
        "Выбери товар. Средства списываются с твоего баланса Stars в Telegram.",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "profile")
async def profile_callback(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    await callback.message.edit_text(
        f"📊 *Ваш профиль*\n\n"
        f"👤 {user['username']}\n"
        f"🍉 Арбузов: {user['watermelons']}\n"
        f"⭐ Stars: {user['stars_balance']}\n"
        f"📈 Множитель: x{user['multiplier']}\n"
        f"🎚️ Уровень: {user['level']}\n"
        f"💰 Всего заработано: {user['total_earned']} 🍉\n"
        f"💸 Потрачено Stars: {user['total_spent_stars']}\n"
        f"🔥 Дейли-стрик: {user['daily_streak']} дней",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]])
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "referral_menu")
async def referral_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    link = f"https://t.me/{bot.username}?start={user_id}"
    cursor.execute('SELECT COUNT(*) FROM referrals WHERE referrer_id = ?', (user_id,))
    ref_count = cursor.fetchone()[0]
    await callback.message.edit_text(
        f"👥 *Реферальная программа*\n\n"
        f"Приглашай друзей и получай бонусы:\n"
        f"• Ты получаешь *20 Stars* за каждого друга\n"
        f"• Друг получает *10 Stars* при старте\n\n"
        f"Твоя ссылка:\n`{link}`\n\n"
        f"Приглашено друзей: {ref_count}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]])
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "daily_claim")
async def daily_claim_callback(callback: types.CallbackQuery):
    await claim_daily(callback.from_user.id, callback.message.chat.id)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "top_players")
async def top_players_callback(callback: types.CallbackQuery):
    cursor.execute('SELECT username, watermelons, level FROM users ORDER BY watermelons DESC LIMIT 10')
    top_users = cursor.fetchall()
    text = "🏆 *Топ игроков по арбузам*\n\n"
    for i, (name, wm, lvl) in enumerate(top_users, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} {name} — {wm} 🍉 (ур.{lvl})\n"
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]])
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🍉 ИГРАТЬ", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton(text="⭐ Магазин", callback_data="shop_menu"),
         InlineKeyboardButton(text="🎁 Дейли бонус", callback_data="daily_claim")],
        [InlineKeyboardButton(text="📊 Профиль", callback_data="profile"),
         InlineKeyboardButton(text="👥 Рефералы", callback_data="referral_menu")],
        [InlineKeyboardButton(text="🏆 Топ игроков", callback_data="top_players")]
    ])
    await callback.message.edit_text(
        f"🍉 *Главное меню*\n\n"
        f"👤 {user['username']}\n"
        f"🍉 Арбузов: *{user['watermelons']}*\n"
        f"⭐ Stars: *{user['stars_balance']}*\n"
        f"📈 Множитель: x{user['multiplier']}\n"
        f"🎚️ Уровень: {user['level']}",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    await callback.answer()

# ========== ЗАПУСК ==========
async def main():
    await set_commands()
    logger.info("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())