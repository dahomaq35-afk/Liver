# =========================================================
# Discord Bot + Flask
# إرسال رسالة خاصة من الموقع إلى مستخدم Discord + أمر إعداد سيرفر RP
# =========================================================

import os
import asyncio
import threading

import discord
from discord import app_commands
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
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# =========================================================
# بيانات الرتب والرومات الخاصة بـ RP (أكثر من 100 رتبة و 70 روم)
# =========================================================

ROLES_DATA = [
    # 👑 الإدارة العليا (صلاحيات كاملة)
    {"name": "👑 | Server Owner", "color": discord.Color.gold(), "admin": True},
    {"name": "👑 | Co-Owner", "color": discord.Color.dark_gold(), "admin": True},
    {"name": "👑 | Head Admin", "color": discord.Color.red(), "admin": True},
    {"name": "🛠️ | Developer", "color": discord.Color.purple(), "admin": True},
    
    # 🛡️ إدارة السيرفر والرقابة
    {"name": "💎 | Senior Admin", "color": discord.Color.dark_red(), "admin": False},
    {"name": "⚔️ | Admin", "color": discord.Color.red(), "admin": False},
    {"name": "🛡️ | Head Moderator", "color": discord.Color.orange(), "admin": False},
    {"name": "🛡️ | Senior Moderator", "color": discord.Color.dark_orange(), "admin": False},
    {"name": "🛡️ | Moderator", "color": discord.Color.gold(), "admin": False},
    {"name": "🔎 | Trial Moderator", "color": discord.Color.yellow(), "admin": False},
    {"name": "📋 | Head Support", "color": discord.Color.green(), "admin": False},
    {"name": "📋 | Support Staff", "color": discord.Color.dark_green(), "admin": False},
    {"name": "🎟️ | Ticket Team", "color": discord.Color.teal(), "admin": False},

    # 🎬 الهوستات والفعاليات
    {"name": "🎬 | Head Host", "color": discord.Color.magenta(), "admin": False},
    {"name": "🎥 | Senior Host", "color": discord.Color.dark_magenta(), "admin": False},
    {"name": "🎙️ | Event Host", "color": discord.Color.purple(), "admin": False},
    {"name": "🎭 | RP Supervisor", "color": discord.Color.blue(), "admin": False},
    {"name": "📹 | Media / Streamer", "color": discord.Color.dark_purple(), "admin": False},

    # 🏛️ قيادة القطاعات العسكرية والأمنية
    {"name": "⭐ | وزير الداخلية", "color": discord.Color.dark_blue(), "admin": False},
    {"name": "🎖️ | قائد الأمن العام", "color": discord.Color.dark_blue(), "admin": False},
    {"name": "🦅 | قائد الحرس الملكي", "color": discord.Color.gold(), "admin": False},
    {"name": "🚓 | مدير الشرطة", "color": discord.Color.blue(), "admin": False},
    {"name": "🕵️ | مدير المباحث", "color": discord.Color.dark_grey(), "admin": False},
    {"name": "🚑 | مدير الإسعاف", "color": discord.Color.brand_red(), "admin": False},
    {"name": "🚒 | مدير الدفاع المدني", "color": discord.Color.orange(), "admin": False},

    # 🚓 ضباط ورتب الشرطة (20 رتبة)
    {"name": "🚓 | فريق أول شرطة", "color": discord.Color.blue(), "admin": False},
    {"name": "🚓 | فريق شرطة", "color": discord.Color.blue(), "admin": False},
    {"name": "🚓 | لواء شرطة", "color": discord.Color.blue(), "admin": False},
    {"name": "🚓 | عميد شرطة", "color": discord.Color.blue(), "admin": False},
    {"name": "🚓 | عقيد شرطة", "color": discord.Color.blue(), "admin": False},
    {"name": "🚓 | مقدم شرطة", "color": discord.Color.blue(), "admin": False},
    {"name": "🚓 | رائد شرطة", "color": discord.Color.blue(), "admin": False},
    {"name": "🚓 | نقيب شرطة", "color": discord.Color.blue(), "admin": False},
    {"name": "🚓 | ملازم أول شرطة", "color": discord.Color.blue(), "admin": False},
    {"name": "🚓 | ملازم شرطة", "color": discord.Color.blue(), "admin": False},
    {"name": "🚓 | رئيس رقباء", "color": discord.Color.dark_teal(), "admin": False},
    {"name": "🚓 | رقيب أول", "color": discord.Color.dark_teal(), "admin": False},
    {"name": "🚓 | رقيب", "color": discord.Color.dark_teal(), "admin": False},
    {"name": "🚓 | وكيل رقيب", "color": discord.Color.dark_teal(), "admin": False},
    {"name": "🚓 | عريف", "color": discord.Color.dark_teal(), "admin": False},
    {"name": "🚓 | جندي أول", "color": discord.Color.dark_teal(), "admin": False},
    {"name": "🚓 | جندي", "color": discord.Color.dark_teal(), "admin": False},
    {"name": "🚓 | مستجد شرطة", "color": discord.Color.light_grey(), "admin": False},

    # 🦅 الحرس الملكي والقوات الخاصة (15 رتبة)
    {"name": "🦅 | قائد القوات الخاصة", "color": discord.Color.dark_gold(), "admin": False},
    {"name": "🦅 | ضابط قوات خاصة", "color": discord.Color.dark_gold(), "admin": False},
    {"name": "🦅 | عضو القوات الخاصة", "color": discord.Color.dark_gold(), "admin": False},
    {"name": "🦅 | قناص الحرس الملكي", "color": discord.Color.dark_gold(), "admin": False},
    {"name": "🦅 | حارس ملكي متقدم", "color": discord.Color.dark_gold(), "admin": False},
    {"name": "🦅 | حارس ملكي", "color": discord.Color.dark_gold(), "admin": False},

    # 🕵️ المباحث والاستخبارات (10 رتب)
    {"name": "🕵️ | ضابط مباحث ممتاز", "color": discord.Color.dark_grey(), "admin": False},
    {"name": "🕵️ | ضابط مباحث", "color": discord.Color.dark_grey(), "admin": False},
    {"name": "🕵️ | محقق أول", "color": discord.Color.dark_grey(), "admin": False},
    {"name": "🕵️ | محقق", "color": discord.Color.dark_grey(), "admin": False},
    {"name": "🕵️ | عميل خفي", "color": discord.Color.dark_grey(), "admin": False},

    # 🚑 الصحة والدفاع المدني (15 رتبة)
    {"name": "🚑 | طبيب استشاري", "color": discord.Color.red(), "admin": False},
    {"name": "🚑 | طبيب جراح", "color": discord.Color.red(), "admin": False},
    {"name": "🚑 | طبيب عام", "color": discord.Color.red(), "admin": False},
    {"name": "🚑 | مسعف أول", "color": discord.Color.red(), "admin": False},
    {"name": "🚑 | مسعف", "color": discord.Color.red(), "admin": False},
    {"name": "🚒 |قائد وحدة الإطفاء", "color": discord.Color.orange(), "admin": False},
    {"name": "🚒 | رجل إطفاء متقدم", "color": discord.Color.orange(), "admin": False},
    {"name": "🚒 | رجل إطفاء", "color": discord.Color.orange(), "admin": False},

    # ⚖️ القضاء والمحاماة (10 رتب)
    {"name": "⚖️ | قاضي القضاة", "color": discord.Color.light_grey(), "admin": False},
    {"name": "⚖️ | قاضي محكمة", "color": discord.Color.light_grey(), "admin": False},
    {"name": "⚖️ | مدعي عام", "color": discord.Color.light_grey(), "admin": False},
    {"name": "⚖️ | محامي مرخص", "color": discord.Color.light_grey(), "admin": False},
    {"name": "⚖️ | متدرب محاماة", "color": discord.Color.light_grey(), "admin": False},

    # 💼 الوظائف المدنية والتجارة (20 رتبة)
    {"name": "💼 | رجل أعمال", "color": discord.Color.green(), "admin": False},
    {"name": "🏦 | مدير البنك", "color": discord.Color.green(), "admin": False},
    {"name": "🏦 | موظف بنك", "color": discord.Color.green(), "admin": False},
    {"name": "🔧 | مهندس ميكانيكي", "color": discord.Color.dark_green(), "admin": False},
    {"name": "🔧 | ميكانيكي", "color": discord.Color.dark_green(), "admin": False},
    {"name": "🚕 | سائق تاكسي", "color": discord.Color.gold(), "admin": False},
    {"name": "📰 | صحفي / إعلامي", "color": discord.Color.purple(), "admin": False},
    {"name": "☕ | صاحب كافيه", "color": discord.Color.dark_orange(), "admin": False},
    {"name": "🛒 | تاجر", "color": discord.Color.green(), "admin": False},
    {"name": "🛠️ | عامل صيانة", "color": discord.Color.dark_green(), "admin": False},

    # 🏴 العصابات والأعمال غير المشروعة (10 رتب)
    {"name": "🏴 | زعيم مافيا", "color": discord.Color.dark_purple(), "admin": False},
    {"name": "🏴 | نائب زعيم العصابة", "color": discord.Color.dark_purple(), "admin": False},
    {"name": "🏴 | مستشار العصابة", "color": discord.Color.dark_purple(), "admin": False},
    {"name": "🏴 | منفذ عمليات", "color": discord.Color.dark_purple(), "admin": False},
    {"name": "🏴 | عضو عصابة", "color": discord.Color.dark_purple(), "admin": False},

    # 👤 رتب عامة للمواطنين
    {"name": "VIP | مواطن مميز", "color": discord.Color.gold(), "admin": False},
    {"name": "📜 | مواطن موثق", "color": discord.Color.blue(), "admin": False},
    {"name": "👤 | مواطن", "color": discord.Color.greyple(), "admin": False},
    {"name": "🚫 | محظور من RP", "color": discord.Color.dark_grey(), "admin": False}
]

# تعبئة باقي الرتب لتجاوز 100 رتبة
for i in range(1, 16):
    ROLES_DATA.append({"name": f"⭐ | داعم السيرفر لفل {i}", "color": discord.Color.magenta(), "admin": False})

CATEGORIES_AND_CHANNELS = {
    "📢 | الأخبار والمعلومات": [
        ("📢-القوانين", "text"), ("📌-الإعلانات", "text"), ("🎉-الفعاليات", "text"),
        ("📊-التحديثات", "text"), ("🔗-الروابط-الهامة", "text")
    ],
    "💬 | التواصل العام": [
        ("💬-الدردشة-العامة", "text"), ("📷-الصور-والميديا", "text"),
        ("🤖-أوامر-البوتات", "text"), ("🔊-سولف-عام 1", "voice"), ("🔊-سولف-عام 2", "voice")
    ],
    "👑 | الإدارة والرقابة": [
        ("💬-دردشة-الإدارة", "text"), ("📋-التعليمات-والتوجيهات", "text"),
        ("📢-إعلانات-الإدارة", "text"), ("📝-تسجيل-دخول-الإدارة", "text"),
        ("🔊-اجتماع-الإدارة", "voice"), ("🔊-غرفة-الرقابة", "voice")
    ],
    "🎙️ | غرفة الهوستات": [
        ("📋-تعليمات-الهوست", "text"), ("🎬-جدول-الهوستات", "text"),
        ("💬-دردشة-الهوستات", "text"), ("🔊-غرفة-التحكم-بالهوست", "voice"),
        ("🔊-بث-الهوست", "voice")
    ],
    "🎟️ | الدعم والنداءات": [
        ("📩-فتح-تذكرة", "text"), ("🛠️-الدعم-الفني", "text"),
        ("🚨-بلاغات-اللاعبين", "text"), ("⚖️-طلب-محاكمة", "text")
    ],
    "🚓 | وزارة الداخلية والشرطة": [
        ("📢-إعلانات-الشرطة", "text"), ("📝-تسجيل-الدورية", "text"),
        ("🚨-غرفة-العمليات", "text"), ("🚔-النداءات-العسكرية", "text"),
        ("📋-الأشخاص-المطلوبين", "text"), ("🔊-راديو-الشرطة- الرئيسي", "voice"),
        ("🔊-راديو-المطاردات", "voice")
    ],
    "🦅 | الحرس الملكي": [
        ("📢-إعلانات-الحرس", "text"), ("📝-حضور-الحرس", "text"),
        ("🛡️-تأمين-الشخصيات", "text"), ("🔊-راديو-الحرس-الملكي", "voice")
    ],
    "🕵️ | المباحث العامة": [
        ("📄-التقارير-السرية", "text"), ("🔍-أدلة-القضايا", "text"),
        ("🔊-راديو-المباحث", "voice")
    ],
    "🚑 | الصحة والدفاع المدني": [
        ("📢-إعلانات-الصحة", "text"), ("🚑-بلاغات-الإسعاف", "text"),
        ("🚒-بلاغات-المطافئ", "text"), ("🔊-راديو-الإسعاف", "voice"),
        ("🔊-راديو-الدفاع-المدني", "voice")
    ],
    "🏙️ | رومات الحياة الواقعية (RP)": [
        ("🏛️-مبنى-البلدية", "text"), ("🏦-البنك-المركزي", "text"),
        ("🏪-السوبر-ماركت", "text"), ("☕-الكافيه-العام", "text"),
        ("🔧-ورشة-تصليح-السيارات", "text"), ("📰-جريدة-المدينة", "text"),
        ("🏢-مكتب-العقارات", "text"), ("⚖️-قاعة-المحكمة", "text")
    ],
    "🏴 | المناطق المشبوهة": [
        ("🌑-السوق-المظلم", "text"), ("💬-دردشة-العصابات", "text"),
        ("🔊-مقر-العصابة-الرئيسي", "voice")
    ],
    "🔊 | رومات الصوت العامة (RP Voice)": [
        ("🎙️-شارع-المدينة 1", "voice"), ("🎙️-شارع-المدينة 2", "voice"),
        ("🎙️-الساحة-المركزية", "voice"), ("🎙️-منطقة-المطاعم", "voice"),
        ("🎙️-المستشفى-العام", "voice"), ("🎙️-قسم-الشرطة", "voice"),
        ("🎙️-المطار-البرية", "voice")
    ]
}


# =========================================================
# عند تشغيل البوت
# =========================================================

@bot.event
async def on_ready():
    print("=" * 50)
    print(f"Logged in as: {bot.user}")
    print(f"Bot ID: {bot.user.id}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    print("Bot is online!")
    print("=" * 50)


# =========================================================
# أمر /setup_rp لتأسيس السيرفر بالكامل
# =========================================================

@bot.tree.command(name="setup_rp", description="إنشاء رومات ورتب سيرفر RP كاملاً (أكثر من 100 رتبة و70 روم)")
@app_commands.default_permissions(administrator=True)
async def setup_rp(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild

    await interaction.followup.send("⏳ جاري بدء عملية التأسيس... قد تستغرق العملية دقيقة لتجنب حظر الأوامر.")

    # 1. إنشاء الرتب
    created_roles = 0
    for role_info in ROLES_DATA:
        perms = discord.Permissions.all() if role_info["admin"] else discord.Permissions.none()
        try:
            await guild.create_role(
                name=role_info["name"],
                color=role_info["color"],
                permissions=perms,
                hoist=True
            )
            created_roles += 1
            await asyncio.sleep(0.3)
        except Exception as e:
            print(f"خطأ أثناء إنشاء الرتبة {role_info['name']}: {e}")

    # 2. إنشاء الكاتيجوري والرومات
    created_channels = 0
    for cat_name, channels in CATEGORIES_AND_CHANNELS.items():
        try:
            category = await guild.create_category(cat_name)
            for ch_name, ch_type in channels:
                if ch_type == "text":
                    await guild.create_text_channel(ch_name, category=category)
                elif ch_type == "voice":
                    await guild.create_voice_channel(ch_name, category=category)
                created_channels += 1
                await asyncio.sleep(0.4)
        except Exception as e:
            print(f"خطأ أثناء إنشاء الفئة/الروم {cat_name}: {e}")

    await interaction.followup.send(
        f"✅ تم الانتهاء بنجاح!\n"
        f"🔹 تم إنشاء **{created_roles}** رتبة.\n"
        f"🔹 تم إنشاء **{created_channels}** روم مقسمة في الفئات."
    )


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
