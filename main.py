import os
import asyncio
import datetime
import logging
import sqlite3
import unicodedata
from threading import Thread

from flask import Flask
import discord
from discord import app_commands
from discord.ext import commands

# AI
from openai import AsyncOpenAI


# =========================================================
# الإعدادات العامة
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

BOT_PREFIX = "-"

SECURITY_CHANNEL_NAME = "📑┃حماية"

# رتب القطاعات
ROLE_JUSTICE = "𝗠𝗧 | Justice"
ROLE_POLICE = "𝗠𝗧 | LSPD"
ROLE_SWAT = "𝗠𝗧 | S.W.A.T"
ROLE_HEALTH = "𝗠𝗧 | PHMC"

# رتب الحماية
WHITELIST_ROLES = [
    "#",
    "MT | Owner ↔",
    "MT | COowner ↔",
    "MT | Ceo",
    "Appy",
    "Bot",
    "bot"
]

# =========================================================
# Keep Alive
# =========================================================

web_app = Flask("")


@web_app.route("/")
def home():
    return "MT Bot Core & Security System is Online!"


def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(
        host="0.0.0.0",
        port=port
    )


def keep_alive():
    thread = Thread(
        target=run_web,
        daemon=True
    )
    thread.start()


# =========================================================
# قاعدة البيانات
# =========================================================

DB_FILE = "mt_bot.db"


def db_connect():
    return sqlite3.connect(DB_FILE)


def setup_database():

    db = db_connect()
    cursor = db.cursor()

    # إعدادات عامة
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            guild_id INTEGER PRIMARY KEY,
            ai_enabled INTEGER DEFAULT 0,
            ai_channel_id INTEGER DEFAULT 0
        )
    """)

    # السجلات الجنائية
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS criminal_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            citizen_id INTEGER NOT NULL,
            officer_id INTEGER NOT NULL,
            crime TEXT NOT NULL,
            fine INTEGER DEFAULT 0,
            jail_time TEXT,
            created_at TEXT NOT NULL
        )
    """)

    # التحذيرات
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS warnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            moderator_id INTEGER NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # لوق الحماية
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS security_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            actor_id INTEGER,
            target_id INTEGER,
            details TEXT,
            created_at TEXT NOT NULL
        )
    """)

    # إعدادات التذاكر
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            sector TEXT NOT NULL,
            claimed_by INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            closed INTEGER DEFAULT 0
        )
    """)

    db.commit()
    db.close()


setup_database()


# =========================================================
# أدوات قاعدة البيانات
# =========================================================

def get_guild_settings(guild_id):

    db = db_connect()
    cursor = db.cursor()

    cursor.execute(
        "SELECT ai_enabled, ai_channel_id FROM settings WHERE guild_id = ?",
        (guild_id,)
    )

    row = cursor.fetchone()

    if not row:
        cursor.execute(
            """
            INSERT INTO settings
            (guild_id, ai_enabled, ai_channel_id)
            VALUES (?, 0, 0)
            """,
            (guild_id,)
        )
        db.commit()
        db.close()

        return {
            "ai_enabled": False,
            "ai_channel_id": 0
        }

    db.close()

    return {
        "ai_enabled": bool(row[0]),
        "ai_channel_id": row[1]
    }


def set_ai_settings(guild_id, enabled=None, channel_id=None):

    current = get_guild_settings(guild_id)

    if enabled is None:
        enabled = current["ai_enabled"]

    if channel_id is None:
        channel_id = current["ai_channel_id"]

    db = db_connect()
    cursor = db.cursor()

    cursor.execute(
        """
        INSERT INTO settings
        (guild_id, ai_enabled, ai_channel_id)
        VALUES (?, ?, ?)
        ON CONFLICT(guild_id)
        DO UPDATE SET
            ai_enabled = excluded.ai_enabled,
            ai_channel_id = excluded.ai_channel_id
        """,
        (
            guild_id,
            int(enabled),
            int(channel_id)
        )
    )

    db.commit()
    db.close()


# =========================================================
# التعامل مع زخرفة الرتب
# =========================================================

def normalize_text(text):

    if not text:
        return ""

    text = unicodedata.normalize(
        "NFKD",
        text
    )

    result = []

    for char in text:
        # تجاهل العلامات المركبة
        if unicodedata.category(char) == "Mn":
            continue

        result.append(char)

    return "".join(result).lower().strip()


def role_matches(role_name, expected_name):

    return normalize_text(role_name) == normalize_text(expected_name)


def check_role(member, role_name):

    if not member:
        return False

    for role in member.roles:

        if role_matches(
            role.name,
            role_name
        ):
            return True

    return False


def is_whitelisted(member, guild):

    if not member or not guild:
        return False

    for role in member.roles:

        for allowed_role in WHITELIST_ROLES:

            if role_matches(
                role.name,
                allowed_role
            ):
                return True

    return False


# =========================================================
# البوت والـ Intents
# =========================================================

intents = discord.Intents.default()

intents.message_content = True
intents.members = True
intents.guilds = True
intents.bans = True
intents.moderation = True

bot = commands.Bot(
    command_prefix=BOT_PREFIX,
    intents=intents
)


# =========================================================
# OpenAI
# =========================================================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

ai_client = None

if OPENAI_API_KEY:

    ai_client = AsyncOpenAI(
        api_key=OPENAI_API_KEY
    )


AI_MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-5.6-luna"
)


# =========================================================
# نظام AI
# =========================================================

async def ask_ai(question, guild_name):

    if not ai_client:
        return (
            "⚠️ نظام الذكاء الاصطناعي غير مهيأ حاليًا."
        )

    system_prompt = f"""
أنت مساعد ذكي داخل سيرفر ديسكورد اسمه MT.
السيرفر MT هو سيرفر RP.

افهم سؤال العضو وسياقه ولا ترد بردود آلية غير مناسبة.

مهم جدًا:
إذا كان السؤال متعلقًا بمعلومة خاصة بسيرفر MT
مثل:
- متى يفتح الماب؟
- متى يبدأ الرول بلاي؟
- متى التقديم؟
- شروط قطاع معين؟
- قرارات الإدارة؟
- تحديثات السيرفر؟
- معلومات قد تتغير مع الوقت؟

لا تخترع أي معلومة.

بدل ذلك أخبر العضو باختصار:
"يرجى التوجه إلى الدعم الفني للحصول على المعلومة الرسمية."

أما الأسئلة العامة غير المرتبطة بمعلومات متغيرة خاصة بالسيرفر،
فأجب عنها بشكل طبيعي ومفيد.

لا تدّعي أنك من إدارة MT.
ولا تخترع قوانين أو مواعيد أو إعلانات رسمية.
"""

    try:

        response = await ai_client.responses.create(
            model=AI_MODEL,
            instructions=system_prompt,
            input=question
        )

        answer = response.output_text

        if not answer:
            return "⚠️ ما قدرت أجهز رد حاليًا."

        return answer[:4000]

    except Exception as error:

        logging.error(
            f"AI Error: {error}"
        )

        return (
            "⚠️ حدث خطأ مؤقت في نظام الذكاء الاصطناعي."
        )


# =========================================================
# روم الحماية
# =========================================================

async def get_security_channel(guild):

    channel = discord.utils.get(
        guild.text_channels,
        name=SECURITY_CHANNEL_NAME
    )

    if channel:
        return channel

    try:

        channel = await guild.create_text_channel(
            SECURITY_CHANNEL_NAME
        )

        return channel

    except Exception as error:

        logging.error(
            f"Security channel error: {error}"
        )

        return None


# =========================================================
# إرسال تقرير الحماية
# =========================================================

async def security_report(
    guild,
    title,
    description,
    color=discord.Color.red(),
    actor=None,
    target=None,
    extra_fields=None
):

    channel = await get_security_channel(guild)

    if not channel:
        return

    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.datetime.now(
            datetime.timezone.utc
        )
    )

    if actor:
        embed.add_field(
            name="👤 المبند / المنفذ",
            value=actor.mention,
            inline=True
        )

    if target:
        embed.add_field(
            name="🎯 المحظور / المستهدف",
            value=target.mention,
            inline=True
        )

    if extra_fields:

        for name, value in extra_fields:

            embed.add_field(
                name=name,
                value=str(value)[:1024],
                inline=False
            )

    await channel.send(
        embed=embed
    )


# =========================================================
# AI Message Handler
# =========================================================

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    if not message.guild:
        return

    member = message.author

    # =============================================
    # منع المنشن العام
    # =============================================

    if (
        "@everyone" in message.content
        or "@here" in message.content
    ):

        if not member.guild_permissions.administrator:

            try:
                await message.delete()
            except Exception:
                pass

            await security_report(
                message.guild,
                "⚠️ منع المنشن العام",
                "تم حذف رسالة تحتوي على منشن عام بدون صلاحية.",
                discord.Color.gold(),
                actor=member,
                extra_fields=[
                    ("📍 القناة", message.channel.mention),
                    ("📝 المحتوى", message.content)
                ]
            )

            return

    # =============================================
    # منع الروابط
    # =============================================

    content_lower = message.content.lower()

    if (
        "discord.gg/" in content_lower
        or "http://" in content_lower
        or "https://" in content_lower
    ):

        if not is_whitelisted(
            member,
            message.guild
        ):

            try:
                await message.delete()
            except Exception:
                pass

            await security_report(
                message.guild,
                "🔗 حذف رابط مخالف",
                "تم حذف رسالة تحتوي على رابط غير مصرح به.",
                discord.Color.red(),
                actor=member,
                extra_fields=[
                    ("📍 القناة", message.channel.mention),
                    ("📝 المحتوى", message.content)
                ]
            )

            return

    # =============================================
    # نظام AI
    # =============================================

    settings = get_guild_settings(
        message.guild.id
    )

    if (
        settings["ai_enabled"]
        and settings["ai_channel_id"] == message.channel.id
    ):

        answer = await ask_ai(
            message.content,
            message.guild.name
        )

        await message.reply(
            answer,
            mention_author=False
        )

        return

    await bot.process_commands(message)


# =========================================================
# AI Command
# =========================================================

@bot.tree.command(
    name="AI",
    description="إدارة نظام الذكاء الاصطناعي"
)
@app_commands.describe(
    action="اختر الإجراء",
    channel="الروم الذي يعمل فيه الذكاء الاصطناعي"
)
@app_commands.choices(
    action=[
        app_commands.Choice(
            name="تفعيل",
            value="enable"
        ),
        app_commands.Choice(
            name="تعطيل",
            value="disable"
        ),
        app_commands.Choice(
            name="تحديد روم",
            value="channel"
        )
    ]
)
async def ai_command(
    interaction: discord.Interaction,
    action: app_commands.Choice[str],
    channel: discord.TextChannel = None
):

    if not is_whitelisted(
        interaction.user,
        interaction.guild
    ):

        await interaction.response.send_message(
            "❌ ما عندك صلاحية استخدام هذا الأمر.",
            ephemeral=True
        )

        return

    settings = get_guild_settings(
        interaction.guild.id
    )

    # =============================================
    # تفعيل
    # =============================================

    if action.value == "enable":

        if not settings["ai_channel_id"]:

            await interaction.response.send_message(
                "❌ حدد روم الذكاء الاصطناعي أولًا.",
                ephemeral=True
            )

            return

        set_ai_settings(
            interaction.guild.id,
            enabled=True
        )

        await interaction.response.send_message(
            "✅ تم **تفعيل AI** بنجاح.",
            ephemeral=True
        )

    # =============================================
    # تعطيل
    # =============================================

    elif action.value == "disable":

        set_ai_settings(
            interaction.guild.id,
            enabled=False
        )

        await interaction.response.send_message(
            "🛑 تم **تعطيل AI**.",
            ephemeral=True
        )

    # =============================================
    # تحديد الروم
    # =============================================

    elif action.value == "channel":

        if not channel:

            await interaction.response.send_message(
                "❌ لازم تحدد الروم.",
                ephemeral=True
            )

            return

        set_ai_settings(
            interaction.guild.id,
            channel_id=channel.id
        )

        await interaction.response.send_message(
            f"✅ تم تحديد روم AI إلى {channel.mention}",
            ephemeral=True
        )


# =========================================================
# تشغيل البوت
# =========================================================

@bot.event
async def on_ready():

    try:

        await bot.tree.sync()

        logging.info(
            "تمت مزامنة أوامر Slash بنجاح."
        )

    except Exception as error:

        logging.error(
            f"Sync Error: {error}"
        )

    logging.info(
        f"MT Bot Online: {bot.user}"
    )


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    keep_alive()

    TOKEN = os.getenv(
        "DISCORD_TOKEN"
    )

    if not TOKEN:

        print(
            "❌ لم يتم العثور على DISCORD_TOKEN"
            
