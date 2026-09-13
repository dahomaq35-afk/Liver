# =========================================================
# إرسال رسالة خاصة من البوت لشخص من الموقع
# =========================================================

import os
import discord
from flask import request, jsonify

# توكن البوت من Environment Variable وليس داخل الملف
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")


async def send_private_message(user_id: int, message: str):
    """
    يرسل رسالة خاصة من البوت إلى مستخدم Discord
    """

    try:
        user = bot.get_user(user_id)

        if user is None:
            user = await bot.fetch_user(user_id)

        await user.send(message)

        return True, "تم إرسال الرسالة بنجاح"

    except discord.Forbidden:
        return False, "لا يمكن إرسال الخاص لهذا المستخدم"

    except discord.NotFound:
        return False, "المستخدم غير موجود"

    except Exception as e:
        print(f"DM Error: {e}")
        return False, "حدث خطأ أثناء إرسال الرسالة"


# =========================================================
# دالة الموقع
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
            send_private_message(
                user_id,
                message
            ),
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
        print(f"Website DM Error: {e}")

        return jsonify({
            "success": False,
            "message": "حدث خطأ أثناء إرسال الرسالة"
        }), 500


# =========================================================
# تشغيل البوت
# =========================================================

if not DISCORD_TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN غير موجود في Environment Variables"
    )

bot.run(DISCORD_TOKEN)
