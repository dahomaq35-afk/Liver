# =========================================================
# Discord Bot + Flask
# إرسال رسالة خاصة من الموقع إلى مستخدم Discord
# =========================================================

import os
import asyncio
import threading

import discord
from discord.ext import commands
from flask import Flask, request, jsonify


# =========================================================
# إعداد Flask
# =========================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "Bot Core & Security System is Online!"


# =========================================================
# إعداد Discord Bot
# =========================================================

intents = discord.Intents.default()

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# =========================================================
# عند تشغيل البوت
# =========================================================

@bot.event
async def on_ready():
    print("=" * 50)
    print(f"Logged in as: {bot.user}")
    print(f"Bot ID: {bot.user.id}")
    print("Bot is online!")
    print("=" * 50)


# =========================================================
# إرسال رسالة خاصة
# =========================================================

async def send_dm(user_id: int, message: str):
    try:
        user = bot.get_user(user_id)

        if user is None:
            user = await bot.fetch_user(user_id)

        await user.send(message)

        return True, "تم إرسال الرسالة بالخاص بنجاح"

    except discord.NotFound:
        return False, "الشخص غير موجود"

    except discord.Forbidden:
        return False, "لا يمكن إرسال الخاص لهذا الشخص"

    except Exception as e:
        print(f"DM ERROR: {e}")
        return False, "حدث خطأ أثناء إرسال الرسالة"


# =========================================================
# API إرسال DM من الموقع
# =========================================================

@app.route("/admin/send-dm", methods=["POST"])
def send_dm_from_website():

    user_id = request.form.get("user_id")
    message = request.form.get("message")

    if not user_id or not message:
        return jsonify({
            "success": False,
            "message": "حدد ID الشخص واكتب الرسالة"
        }), 400

    try:
        user_id = int(user_id)

        future = asyncio.run_coroutine_threadsafe(
            send_dm(user_id, message),
            bot.loop
        )

        success, result = future.result(timeout=15)

        return jsonify({
            "success": success,
            "message": result
        })

    except ValueError:
        return jsonify({
            "success": False,
            "message": "Discord ID غير صحيح"
        }), 400

    except Exception as e:
        print(f"WEBSITE DM ERROR: {e}")

        return jsonify({
            "success": False,
            "message": "حدث خطأ أثناء الإرسال"
        }), 500


# =========================================================
# تشغيل Flask
# =========================================================

def run_flask():
    port = int(os.getenv("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
    )


# =========================================================
# تشغيل Flask في Thread مستقل
# =========================================================

flask_thread = threading.Thread(
    target=run_flask,
    daemon=True
)

flask_thread.start()


# =========================================================
# التوكن من Environment Variables
# =========================================================

TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise RuntimeError(
        "TOKEN غير موجود في Environment Variables"
    )


# =========================================================
# تشغيل البوت
# =========================================================

bot.run(TOKEN)
