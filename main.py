import os
import io
import re
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
from openai import AsyncOpenAI


# =========================================================
# الإعدادات
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

BOT_PREFIX = "-"
SECURITY_CHANNEL_NAME = "📑┃حماية"

ROLE_JUSTICE = "𝗠𝗧 | Justice"
ROLE_POLICE = "𝗠𝗧 | LSPD"
ROLE_SWAT = "𝗠𝗧 | S.W.A.T"
ROLE_HEALTH = "𝗠𝗧 | PHMC"

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
# KEEP ALIVE
# =========================================================

web_app = Flask(__name__)


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
    Thread(
        target=run_web,
        daemon=True
    ).start()


# =========================================================
# DATABASE
# =========================================================

DB_FILE = "mt_bot.db"


def db_connect():
    return sqlite3.connect(DB_FILE)


def setup_database():

    db = db_connect()
    cursor = db.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            guild_id INTEGER PRIMARY KEY,
            ai_enabled INTEGER DEFAULT 0,
            ai_channel_id INTEGER DEFAULT 0
        )
    """)

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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deeds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            citizen_id INTEGER NOT NULL,
            officer_id INTEGER NOT NULL,
            property_name TEXT NOT NULL,
            details TEXT,
            created_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS warrants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            citizen_id INTEGER NOT NULL,
            officer_id INTEGER NOT NULL,
            warrant_type TEXT NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dispatches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            officer_id INTEGER NOT NULL,
            location TEXT NOT NULL,
            details TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS medical_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            citizen_id INTEGER NOT NULL,
            medic_id INTEGER NOT NULL,
            diagnosis TEXT NOT NULL,
            treatment TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    db.commit()
    db.close()


setup_database()


# =========================================================
# DATABASE HELPERS
# =========================================================

def now_utc():
    return datetime.datetime.now(
        datetime.timezone.utc
    ).isoformat()


def get_guild_settings(guild_id):

    db = db_connect()
    cursor = db.cursor()

    cursor.execute(
        """
        SELECT ai_enabled, ai_channel_id
        FROM settings
        WHERE guild_id = ?
        """,
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


def set_ai_settings(
    guild_id,
    enabled=None,
    channel_id=None
):

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


def save_security_log(
    guild_id,
    event_type,
    actor_id=None,
    target_id=None,
    details=""
):

    db = db_connect()
    cursor = db.cursor()

    cursor.execute(
        """
        INSERT INTO security_logs
        (
            guild_id,
            event_type,
            actor_id,
            target_id,
            details,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            guild_id,
            event_type,
            actor_id,
            target_id,
            details,
            now_utc()
        )
    )

    db.commit()
    db.close()


# =========================================================
# ROLE NORMALIZATION
# =========================================================

def normalize_text(text):

    if not text:
        return ""

    result = []

    for char in text:

        name = unicodedata.name(
            char,
            ""
        )

        # تحويل الحروف المزخرفة الرياضية إلى الحروف العادية
        if "MATHEMATICAL" in name:

            last = name.split()[-1]

            if len(last) == 1 and last.isalnum():
                result.append(last)
                continue

        result.append(char)

    text = "".join(result)

    text = unicodedata.normalize(
        "NFKC",
        text
    )

    text = "".join(
        char
        for char in text
        if unicodedata.category(char) != "Mn"
    )

    return re.sub(
        r"\s+",
        " ",
        text
    ).strip().casefold()


def role_matches(
    role_name,
    expected_name
):

    return (
        normalize_text(role_name)
        ==
        normalize_text(expected_name)
    )


def check_role(
    member,
    role_name
):

    if not member:
        return False

    return any(
        role_matches(
            role.name,
            role_name
        )
        for role in member.roles
    )


def is_whitelisted(
    member,
    guild=None
):

    if not member:
        return False

    if guild and member.id == guild.owner_id:
        return True

    if getattr(
        member.guild_permissions,
        "administrator",
        False
    ):
        return True

    for role in member.roles:

        for allowed_role in WHITELIST_ROLES:

            if role_matches(
                role.name,
                allowed_role
            ):
                return True

    return False


# =========================================================
# BOT
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
# OPENAI
# =========================================================

OPENAI_API_KEY = os.getenv(
    "OPENAI_API_KEY"
)

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
# AI
# =========================================================

async def ask_ai(
    question,
    guild_name
):

    if not ai_client:

        return (
            "⚠️ نظام الذكاء الاصطناعي غير مهيأ حاليًا."
        )

    system_prompt = f"""
أنت مساعد ذكي داخل سيرفر ديسكورد اسمه MT.

السيرفر MT هو سيرفر RP.

اسم السيرفر:
{guild_name}

افهم كلام العضو وسياقه بشكل طبيعي.

مهم جدًا:

إذا كان السؤال عن معلومة خاصة بسيرفر MT
وقد تكون متغيرة أو تحتاج مصدرًا رسميًا، مثل:

- متى يفتح الماب؟
- متى يبدأ الرول بلاي؟
- متى التقديم؟
- شروط القطاعات؟
- قرارات الإدارة؟
- تحديثات السيرفر؟
- مواعيد الفعاليات؟
- قوانين جديدة؟
- حالة السيرفر؟

لا تخترع الإجابة.

قل:
"يرجى التوجه إلى الدعم الفني للحصول على المعلومة الرسمية."

أما الأسئلة العامة، فأجب عنها بشكل طبيعي ومفيد.

لا تدّعي أنك من إدارة MT.

لا تخترع إعلانات أو قوانين رسمية.
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
# SECURITY CHANNEL
# =========================================================

async def get_security_channel(
    guild
):

    channel = discord.utils.get(
        guild.text_channels,
        name=SECURITY_CHANNEL_NAME
    )

    if channel:
        return channel

    try:

        overwrites = {
            guild.default_role:
                discord.PermissionOverwrite(
                    view_channel=False
                )
        }

        channel = await guild.create_text_channel(
            SECURITY_CHANNEL_NAME,
            overwrites=overwrites,
            reason="MT Security System"
        )

        return channel

    except Exception as error:

        logging.error(
            f"Security channel error: {error}"
        )

        return None


# =========================================================
# SECURITY REPORT
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

    save_security_log(
        guild.id,
        title,
        actor.id if actor else None,
        target.id if target else None,
        description
    )

    channel = await get_security_channel(
        guild
    )

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
            name="👤 المنفذ",
            value=actor.mention,
            inline=True
        )

    if target:

        embed.add_field(
            name="🎯 المستهدف",
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

    try:

        await channel.send(
            embed=embed
        )

    except Exception as error:

        logging.error(
            f"Security send error: {error}"
        )


# =========================================================
# AUDIT LOG ACTOR
# =========================================================

async def get_audit_actor(
    guild,
    action,
    target_id=None
):

    try:

        async for entry in guild.audit_logs(
            limit=8,
            action=action
        ):

            if target_id is not None:

                if getattr(
                    entry.target,
                    "id",
                    None
                ) != target_id:

                    continue

            if (
                datetime.datetime.now(
                    datetime.timezone.utc
                )
                -
                entry.created_at
            ).total_seconds() > 15:

                continue

            return entry.user

    except Exception as error:

        logging.error(
            f"Audit log error: {error}"
        )

    return None


# =========================================================
# BAN PROTECTION
# =========================================================

@bot.event
async def on_member_ban(
    guild,
    user
):

    await asyncio.sleep(0.25)

    actor = await get_audit_actor(
        guild,
        discord.AuditLogAction.ban,
        user.id
    )

    if not actor:

        await security_report(
            guild,
            "⚠️ حظر بدون تحديد المنفذ",
            f"تم حظر {user.mention} ولم يتمكن النظام من تحديد المنفذ.",
            discord.Color.orange(),
            target=user
        )

        return

    if actor.id == bot.user.id:

        return

    actor_member = guild.get_member(
        actor.id
    )

    if actor_member and is_whitelisted(
        actor_member,
        guild
    ):

        await security_report(
            guild,
            "✅ حظر مصرح",
            f"تم تنفيذ حظر مصرح به على {user.mention}.",
            discord.Color.green(),
            actor=actor_member,
            target=user
        )

        return

    # فك حظر الشخص المحظور
    try:

        await guild.unban(
            user,
            reason="MT Security: Unauthorized ban"
        )

        target_unbanned = "تم فك الحظر"

    except Exception as error:

        target_unbanned = (
            f"فشل فك الحظر: {error}"
        )

    # حظر المنفذ
    actor_banned = "لم يتم"

    if actor_member:

        try:

            if (
                actor_member != guild.owner
                and actor_member.top_role
                < guild.me.top_role
            ):

                await guild.ban(
                    actor_member,
                    reason="MT Security: Unauthorized ban"
                )

                actor_banned = "تم حظر المنفذ"

            else:

                actor_banned = (
                    "تعذر حظر المنفذ بسبب Owner/Role Hierarchy"
                )

        except Exception as error:

            actor_banned = (
                f"فشل حظر المنفذ: {error}"
            )

    await security_report(
        guild,
        "🚨 حظر غير مصرح به",
        "تم اكتشاف حظر غير مصرح به بواسطة عضو غير موجود في قائمة الحماية.",
        discord.Color.red(),
        actor=actor_member or actor,
        target=user,
        extra_fields=[
            ("🔓 حالة المستهدف", target_unbanned),
            ("🔨 حالة المنفذ", actor_banned)
        ]
    )


# =========================================================
# MEMBER JOIN SECURITY SCAN
# =========================================================

@bot.event
async def on_member_join(
    member
):

    await asyncio.sleep(0)

    if member.bot:

        if member.guild_permissions.administrator:

            if not is_whitelisted(
                member,
                member.guild
            ):

                try:

                    await member.ban(
                        reason="MT Security: Suspicious bot with Administrator"
                    )

                    result = "تم حظر البوت تلقائيًا."

                except Exception as error:

                    result = (
                        f"فشل الحظر: {error}"
                    )

                await security_report(
                    member.guild,
                    "🚨 بوت مشبوه",
                    "تم اكتشاف بوت جديد يمتلك صلاحيات Administrator.",
                    discord.Color.red(),
                    target=member,
                    extra_fields=[
                        ("⚡ الإجراء", result)
                    ]
                )

                return

    await security_report(
        member.guild,
        "👋 عضو جديد",
        "تم تسجيل دخول عضو جديد إلى السيرفر.",
        discord.Color.blue(),
        target=member,
        extra_fields=[
            ("🤖 Bot", str(member.bot))
        ]
    )


# =========================================================
# ROLE UPDATE PROTECTION
# =========================================================

@bot.event
async def on_guild_role_update(
    before,
    after
):

    if before.permissions == after.permissions:

        return

    actor = await get_audit_actor(
        after.guild,
        discord.AuditLogAction.role_update,
        after.id
    )

    if not actor:

        return

    actor_member = after.guild.get_member(
        actor.id
    )

    if actor_member and is_whitelisted(
        actor_member,
        after.guild
    ):

        await security_report(
            after.guild,
            "🛡️ تعديل صلاحيات مصرح",
            f"تم تعديل صلاحيات الرتبة {after.mention}.",
            discord.Color.green(),
            actor=actor_member,
            extra_fields=[
                ("🎭 الرتبة", after.name)
            ]
        )

        return

    try:

        if (
            not after.managed
            and after < after.guild.me.top_role
        ):

            await after.edit(
                permissions=before.permissions,
                reason="MT Security: Unauthorized permission change"
            )

            result = "تمت استعادة الصلاحيات السابقة."

        else:

            result = "تعذر الاستعادة بسبب Hierarchy."

    except Exception as error:

        result = (
            f"فشل الاستعادة: {error}"
        )

    await security_report(
        after.guild,
        "🚨 تعديل صلاحيات غير مصرح",
        "تم اكتشاف تعديل غير مصرح على صلاحيات رتبة.",
        discord.Color.red(),
        actor=actor_member or actor,
        extra_fields=[
            ("🎭 الرتبة", after.name),
            ("🔄 الإجراء", result)
        ]
    )


# =========================================================
# CHANNEL DELETE PROTECTION
# =========================================================

@bot.event
async def on_guild_channel_delete(
    channel
):

    actor = await get_audit_actor(
        channel.guild,
        discord.AuditLogAction.channel_delete,
        channel.id
    )

    if not actor:

        await security_report(
            channel.guild,
            "🚨 حذف روم",
            f"تم حذف الروم `{channel.name}` ولم يتم تحديد المنفذ.",
            discord.Color.orange()
        )

        return

    actor_member = channel.guild.get_member(
        actor.id
    )

    if actor_member and is_whitelisted(
        actor_member,
        channel.guild
    ):

        await security_report(
            channel.guild,
            "✅ حذف روم مصرح",
            f"تم حذف الروم `{channel.name}` بواسطة عضو مصرح.",
            discord.Color.green(),
            actor=actor_member
        )

        return

    await security_report(
        channel.guild,
        "🚨 حذف روم غير مصرح",
        f"تم اكتشاف حذف الروم `{channel.name}` بواسطة عضو غير مصرح.",
        discord.Color.red(),
        actor=actor_member or actor,
        extra_fields=[
            ("🆔 Channel ID", channel.id)
        ]
    )

    if actor_member:

        try:

            if (
                actor_member != channel.guild.owner
                and actor_member.top_role
                < channel.guild.me.top_role
            ):

                await channel.guild.ban(
                    actor_member,
                    reason="MT Security: Unauthorized channel deletion"
                )

        except Exception:
            pass


# =========================================================
# MESSAGE SECURITY
# =========================================================

@bot.event
async def on_message(
    message
):

    if message.author.bot:
        return

    if not message.guild:
        return

    member = message.author

    # -----------------------------------------------------
    # منع @everyone و @here
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # منع الروابط
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # AI
    # -----------------------------------------------------

    settings = get_guild_settings(
        message.guild.id
    )

    if (
        settings["ai_enabled"]
        and
        settings["ai_channel_id"]
        == message.channel.id
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

    await bot.process_commands(
        message
    )


# =========================================================
# TICKET SYSTEM
# =========================================================

SECTOR_OPTIONS = {
    "justice": ROLE_JUSTICE,
    "police": ROLE_POLICE,
    "swat": ROLE_SWAT,
    "health": ROLE_HEALTH
}


def find_role(
    guild,
    role_name
):

    for role in guild.roles:

        if role_matches(
            role.name,
            role_name
        ):

            return role

    return None


class TicketCloseView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    @discord.ui.button(
        label="إغلاق التذكرة",
        emoji="🔒",
        style=discord.ButtonStyle.danger,
        custom_id="mt_ticket_close"
    )
    async def close_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        channel = interaction.channel

        db = db_connect()
        cursor = db.cursor()

        cursor.execute(
            """
            SELECT user_id, sector
            FROM tickets
            WHERE channel_id = ?
            AND closed = 0
            """,
            (channel.id,)
        )

        row = cursor.fetchone()

        db.close()

        if not row:

            await interaction.response.send_message(
                "❌ هذه التذكرة غير مسجلة.",
                ephemeral=True
            )

            return

        if not (
            is_whitelisted(
                interaction.user,
                interaction.guild
            )
            or interaction.user.id == row[0]
        ):

            await interaction.response.send_message(
                "❌ ما عندك صلاحية إغلاق هذه التذكرة.",
                ephemeral=True
            )

            return

        await interaction.response.send_message(
            "🔒 جاري إغلاق التذكرة وحفظ التقرير...",
            ephemeral=True
        )

        # Transcript
        lines = []

        try:

            async for msg in channel.history(
                limit=500,
                oldest_first=True
            ):

                timestamp = msg.created_at.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )

                content = msg.content

                if not content:
                    content = "[Embed / Attachment]"

                lines.append(
                    f"[{timestamp}] "
                    f"{msg.author} ({msg.author.id}): "
                    f"{content}"
                )

        except Exception as error:

            lines.append(
                f"Transcript error: {error}"
            )

        transcript = "\n".join(
            lines
        )

        db = db_connect()
        cursor = db.cursor()

        cursor.execute(
            """
            UPDATE tickets
            SET closed = 1
            WHERE channel_id = ?
            """,
            (channel.id,)
        )

        db.commit()
        db.close()

        security = await get_security_channel(
            interaction.guild
        )

        if security:

            file = discord.File(
                io.BytesIO(
                    transcript.encode(
                        "utf-8",
                        errors="replace"
                    )
                ),
                filename=f"ticket-{channel.id}.txt"
            )

            await security.send(
                content=(
                    f"🔒 **تم إغلاق تذكرة**\n"
                    f"القناة: `{channel.name}`\n"
                    f"بواسطة: {interaction.user.mention}"
                ),
                file=file
            )

        await asyncio.sleep(2)

        try:
            await channel.delete(
                reason="MT Ticket Closed"
            )
        except Exception:
            pass


class TicketSelectView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    @discord.ui.select(
        placeholder="اختر القطاع لفتح التذكرة",
        custom_id="mt_ticket_sector",
        options=[
            discord.SelectOption(
                label="Justice",
                value="justice",
                emoji="⚖️"
            ),
            discord.SelectOption(
                label="LSPD",
                value="police",
                emoji="🚓"
            ),
            discord.SelectOption(
                label="S.W.A.T",
                value="swat",
                emoji="🛡️"
            ),
            discord.SelectOption(
                label="PHMC",
                value="health",
                emoji="🏥"
            )
        ]
    )
    async def select_sector(
        self,
        interaction: discord.Interaction,
        select: discord.ui.Select
    ):

        guild = interaction.guild
        member = interaction.user

        sector_key = select.values[0]
        sector_role_name = SECTOR_OPTIONS[
            sector_key
        ]

        db = db_connect()
        cursor = db.cursor()

        cursor.execute(
            """
            SELECT channel_id
            FROM tickets
            WHERE guild_id = ?
            AND user_id = ?
            AND closed = 0
            """,
            (
                guild.id,
                member.id
            )
        )

        existing = cursor.fetchone()
        db.close()

        if existing:

            existing_channel = guild.get_channel(
                existing[0]
            )

            if existing_channel:

                await interaction.response.send_message(
                    f"❌ عندك تذكرة مفتوحة بالفعل: {existing_channel.mention}",
                    ephemeral=True
                )

                return

        category_name = (
            f"📂 تذاكر قطاع - "
            f"{sector_role_name}"
        )

        category = discord.utils.get(
            guild.categories,
            name=category_name
        )

        if not category:

            category = await guild.create_category(
                category_name
            )

        sector_role = find_role(
            guild,
            sector_role_name
        )

        overwrites = {

            guild.default_role:
                discord.PermissionOverwrite(
                    view_channel=False
                ),

            member:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                ),

            guild.me:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    manage_channels=True,
                    read_message_history=True
                )
        }

        if sector_role:

            overwrites[
                sector_role
            ] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )

        channel = await guild.create_text_channel(
            name=f"ticket-{member.name}",
            category=category,
            overwrites=overwrites,
            reason="MT Ticket System"
        )

        db = db_connect()
        cursor = db.cursor()

        cursor.execute(
            """
            INSERT INTO tickets
            (
                guild_id,
                user_id,
                channel_id,
                sector,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                guild.id,
                member.id,
                channel.id,
                sector_role_name,
                now_utc()
            )
        )

        db.commit()
        db.close()

        embed = discord.Embed(
            title="🎫 تذكرة MT",
            description=(
                f"مرحبًا {member.mention}\n\n"
                f"**القطاع:** {sector_role_name}\n\n"
                "اكتب مشكلتك بالتفصيل، "
                "وسيتم خدمتك من المختصين.\n\n"
                "عند الانتهاء استخدم زر الإغلاق."
            ),
            color=discord.Color.blurple()
        )

        await channel.send(
            content=member.mention,
            embed=embed,
            view=TicketCloseView()
        )

        await interaction.response.send_message(
            f"✅ تم إنشاء تذكرتك: {channel.mention}",
            ephemeral=True
        )

        await security_report(
            guild,
            "🎫 فتح تذكرة",
            "تم فتح تذكرة جديدة.",
            discord.Color.blue(),
            actor=member,
            extra_fields=[
                ("📂 القطاع", sector_role_name),
                ("📍 القناة", channel.mention)
            ]
        )


# =========================================================
# TICKET PANEL
# =========================================================

@bot.tree.command(
    name="ticket-panel",
    description="إرسال لوحة التذاكر"
)
async def ticket_panel(
    interaction: discord.Interaction
):

    if not is_whitelisted(
        interaction.user,
        interaction.guild
    ):

        await interaction.response.send_message(
            "❌ ما عندك صلاحية.",
            ephemeral=True
        )

        return

    embed = discord.Embed(
        title="🎫 نظام تذاكر MT",
        description=(
            "اختر القطاع المناسب من القائمة "
            "لفتح تذكرة.\n\n"
            "⚖️ Justice\n"
            "🚓 LSPD\n"
            "🛡️ S.W.A.T\n"
            "🏥 PHMC"
        ),
        color=discord.Color.blurple()
    )

    await interaction.response.send_message(
        embed=embed,
        view=TicketSelectView()
    )


# =========================================================
# DOJ - CREATE DEED
# =========================================================

@bot.tree.command(
    name="create-deed",
    description="إنشاء سند ملكية"
)
@app_commands.describe(
    citizen="صاحب الملكية",
    property_name="اسم العقار",
    details="تفاصيل العقار"
)
async def create_deed(
    interaction: discord.Interaction,
    citizen: discord.Member,
    property_name: str,
    details: str = "لا توجد تفاصيل"
):

    if not check_role(
        interaction.user,
        ROLE_JUSTICE
    ):

        await interaction.response.send_message(
            "❌ الأمر مخصص لقطاع Justice.",
            ephemeral=True
        )

        return

    db = db_connect()
    cursor = db.cursor()

    cursor.execute(
        """
        INSERT INTO deeds
        (
            guild_id,
            citizen_id,
            officer_id,
            property_name,
            details,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            interaction.guild.id,
            citizen.id,
            interaction.user.id,
            property_name,
            details,
            now_utc()
        )
    )

    deed_id = cursor.lastrowid

    db.commit()
    db.close()

    embed = discord.Embed(
        title="📜 سند ملكية",
        color=discord.Color.green(),
        timestamp=datetime.datetime.now(
            datetime.timezone.utc
        )
    )

    embed.add_field(
        name="🔢 رقم السند",
        value=f"`DEED-{deed_id:05d}`"
    )

    embed.add_field(
        name="👤 المالك",
        value=citizen.mention
    )

    embed.add_field(
        name="🏠 العقار",
        value=property_name
    )

    embed.add_field(
        name="📝 التفاصيل",
        value=details[:1024],
        inline=False
    )

    embed.set_footer(
        text=f"تم الإصدار بواسطة {interaction.user}"
    )

    await interaction.response.send_message(
        embed=embed
    )

    await security_report(
        interaction.guild,
        "📜 إنشاء سند ملكية",
        "تم إنشاء سند ملكية جديد.",
        discord.Color.green(),
        actor=interaction.user,
        target=citizen,
        extra_fields=[
            ("🔢 رقم السند", f"DEED-{deed_id:05d}"),
            ("🏠 العقار", property_name)
        ]
    )


# =========================================================
# DOJ - WARRANT
# =========================================================

@bot.tree.command(
    name="issue-warrant",
    description="إصدار مذكرة"
)
@app_commands.describe(
    citizen="الشخص المطلوب",
    warrant_type="نوع المذكرة",
    reason="سبب المذكرة"
)
@app_commands.choices(
    warrant_type=[
        app_commands.Choice(
            name="مذكرة قبض",
            value="قبض"
        ),
        app_commands.Choice(
            name="مذكرة تفتيش",
            value="تفتيش"
        )
    ]
)
async def issue_warrant(
    interaction: discord.Interaction,
    citizen: discord.Member,
    warrant_type: app_commands.Choice[str],
    reason: str
):

    if not check_role(
        interaction.user,
        ROLE_JUSTICE
    ):

        await interaction.response.send_message(
            "❌ الأمر مخصص لقطاع Justice.",
            ephemeral=True
        )

        return

    db = db_connect()
    cursor = db.cursor()

    cursor.execute(
        """
        INSERT INTO warrants
        (
            guild_id,
            citizen_id,
            officer_id,
            warrant_type,
            reason,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            interaction.guild.id,
            citizen.id,
            interaction.user.id,
            warrant_type.value,
            reason,
            now_utc()
        )
    )

    warrant_id = cursor.lastrowid

    db.commit()
    db.close()

    embed = discord.Embed(
        title="⚖️ مذكرة رسمية",
        description=(
            "تم إصدار مذكرة رسمية."
        ),
        color=discord.Color.red()
    )

    embed.add_field(
        name="🔢 الرقم",
        value=f"`WARRANT-{warrant_id:05d}`"
    )

    embed.add_field(
        name="👤 المطلوب",
        value=citizen.mention
    )

    embed.add_field(
        name="📄 النوع",
        value=warrant_type.value
    )

    embed.add_field(
        name="📝 السبب",
        value=reason[:1024],
        inline=False
    )

    await interaction.response.send_message(
        embed=embed
    )

    await security_report(
        interaction.guild,
        "⚖️ إصدار مذكرة",
        "تم إصدار مذكرة جديدة.",
        discord.Color.red(),
        actor=interaction.user,
        target=citizen,
        extra_fields=[
            ("🔢 الرقم", f"WARRANT-{warrant_id:05d}"),
            ("📄 النوع", warrant_type.value),
            ("📝 السبب", reason)
        ]
    )


# =========================================================
# LSPD - 911
# =========================================================

@bot.tree.command(
    name="911-dispatch",
    description="إرسال بلاغ عمليات 911"
)
@app_commands.describe(
    location="موقع البلاغ",
    details="تفاصيل البلاغ"
)
async def dispatch_911(
    interaction: discord.Interaction,
    location: str,
    details: str
):

    if not check_role(
        interaction.user,
        ROLE_POLICE
    ):

        await interaction.response.send_message(
            "❌ الأمر مخصص لقطاع LSPD.",
            ephemeral=True
        )

        return

    db = db_connect()
    cursor = db.cursor()

    cursor.execute(
        """
        INSERT INTO dispatches
        (
            guild_id,
            officer_id,
            location,
            details,
            created_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            interaction.guild.id,
            interaction.user.id,
            location,
            details,
            now_utc()
        )
    )

    dispatch_id = cursor.lastrowid

    db.commit()
    db.close()

    embed = discord.Embed(
        title="🚨 911 DISPATCH",
        description="تم استلام بلاغ عمليات.",
        color=discord.Color.red()
    )

    embed.add_field(
        name="🔢 رقم البلاغ",
        value=f"`911-{dispatch_id:05d}`"
    )

    embed.add_field(
        name="📍 الموقع",
        value=location
    )

    embed.add_field(
        name="📝 التفاصيل",
        value=details[:1024],
        inline=False
    )

    await interaction.response.send_message(
        content="@everyone",
        embed=embed,
        allowed_mentions=discord.AllowedMentions(
            everyone=True
        )
    )

    await security_report(
        interaction.guild,
        "🚨 بلاغ 911",
        "تم إرسال بلاغ عمليات.",
        discord.Color.red(),
        actor=interaction.user,
        extra_fields=[
            ("🔢 الرقم", f"911-{dispatch_id:05d}"),
            ("📍 الموقع", location),
            ("📝 التفاصيل", details)
        ]
    )


# =========================================================
# LSPD - ADD RECORD
# =========================================================

@bot.tree.command(
    name="add-record",
    description="إضافة سجل جنائي"
)
@app_commands.describe(
    citizen="الشخص",
    crime="الجريمة",
    fine="الغرامة",
    jail_time="مدة السجن"
)
async def add_record(
    interaction: discord.Interaction,
    citizen: discord.Member,
    crime: str,
    fine: int,
    jail_time: str
):

    if not check_role(
        interaction.user,
        ROLE_POLICE
    ):

        await interaction.response.send_message(
            "❌ الأمر مخصص لقطاع LSPD.",
            ephemeral=True
        )

        return

    db = db_connect()
    cursor = db.cursor()

    cursor.execute(
        """
        INSERT INTO criminal_records
        (
            guild_id,
            citizen_id,
            officer_id,
            crime,
            fine,
            jail_time,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            interaction.guild.id,
            citizen.id,
            interaction.user.id,
            crime,
            max(0, fine),
            jail_time,
            now_utc()
        )
    )

    record_id = cursor.lastrowid

    db.commit()
    db.close()

    embed = discord.Embed(
        title="📁 سجل جنائي",
        color=discord.Color.dark_red()
    )

    embed.add_field(
        name="🔢 رقم السجل",
        value=f"`RECORD-{record_id:05d}`"
    )

    embed.add_field(
        name="👤 الشخص",
        value=citizen.mention
    )

    embed.add_field(
        name="⚠️ الجريمة",
        value=crime
    )

    embed.add_field(
        name="💰 الغرامة",
        value=f"{max(0, fine):,}"
    )

    embed.add_field(
        name="⛓️ السجن",
        value=jail_time
    )

    await interaction.response.send_message(
        embed=embed
    )

    await security_report(
        interaction.guild,
        "📁 إضافة سجل جنائي",
        "تمت إضافة سجل جنائي.",
        discord.Color.dark_red(),
        actor=interaction.user,
        target=citizen,
        extra_fields=[
            ("🔢 الرقم", f"RECORD-{record_id:05d}"),
            ("⚠️ الجريمة", crime),
            ("💰 الغرامة", f"{max(0, fine):,}"),
            ("⛓️ السجن", jail_time)
        ]
    )


# =========================================================
# LSPD - VIEW RECORDS
# =========================================================

@bot.tree.command(
    name="view-records",
    description="عرض السجل الجنائي"
)
@app_commands.describe(
    citizen="الشخص المطلوب سجله"
)
async def view_records(
    interaction: discord.Interaction,
    citizen: discord.Member
):

    if not check_role(
        interaction.user,
        ROLE_POLICE
    ):

        await interaction.response.send_message(
            "❌ الأمر مخصص لقطاع LSPD.",
            ephemeral=True
        )

        return

    db = db_connect()
    cursor = db.cursor()

    cursor.execute(
        """
        SELECT
            id,
            crime,
            fine,
            jail_time,
            created_at
        FROM criminal_records
        WHERE guild_id = ?
        AND citizen_id = ?
        ORDER BY id DESC
        LIMIT 15
        """,
        (
            interaction.guild.id,
            citizen.id
        )
    )

    rows = cursor.fetchall()

    db.close()

    if not rows:

        await interaction.response.send_message(
            f"📁 لا توجد سجلات على {citizen.mention}.",
            ephemeral=True
        )

        return

    embed = discord.Embed(
        title=f"📁 السجل الجنائي - {citizen}",
        color=discord.Color.dark_red()
    )

    for (
        record_id,
        crime,
        fine,
        jail_time,
        created_at
    ) in rows:

        embed.add_field(
            name=f"RECORD-{record_id:05d}",
            value=(
                f"⚠️ **الجريمة:** {crime}\n"
                f"💰 **الغرامة:** {fine:,}\n"
                f"⛓️ **السجن:** {jail_time}\n"
                f"🕒 **التاريخ:** {created_at[:19]}"
            ),
            inline=False
        )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# =========================================================
# SWAT
# =========================================================

@bot.tree.command(
    name="swat-deploy",
    description="إرسال انتشار S.W.A.T"
)
@app_commands.describe(
    zone="منطقة الانتشار",
    threat="مستوى الخطورة"
)
@app_commands.choices(
    threat=[
        app_commands.Choice(
            name="منخفض",
            value="منخفض"
        ),
        app_commands.Choice(
            name="متوسط",
            value="متوسط"
        ),
        app_commands.Choice(
            name="عالي",
            value="عالي"
        ),
        app_commands.Choice(
            name="حرج",
            value="حرج"
        )
    ]
)
async def swat_deploy(
    interaction: discord.Interaction,
    zone: str,
    threat: app_commands.Choice[str]
):

    if not check_role(
        interaction.user,
        ROLE_SWAT
    ):

        await interaction.response.send_message(
            "❌ الأمر مخصص لقطاع S.W.A.T.",
            ephemeral=True
        )

        return

    embed = discord.Embed(
        title="🛡️ S.W.A.T DEPLOYMENT",
        description=(
            "تم إصدار أمر انتشار S.W.A.T."
        ),
        color=discord.Color.orange()
    )

    embed.add_field(
        name="📍 المنطقة",
        value=zone
    )

    embed.add_field(
        name="🚨 مستوى الخطورة",
        value=threat.value
    )

    embed.add_field(
        name="👮 المسؤول",
        value=interaction.user.mention
    )

    await interaction.response.send_message(
        content="@everyone",
        embed=embed,
        allowed_mentions=discord.AllowedMentions(
            everyone=True
        )
    )

    await security_report(
        interaction.guild,
        "🛡️ S.W.A.T Deployment",
        "تم إصدار أمر انتشار S.W.A.T.",
        discord.Color.orange(),
        actor=interaction.user,
        extra_fields=[
            ("📍 المنطقة", zone),
            ("🚨 الخطورة", threat.value)
        ]
    )


# =========================================================
# PHMC - MEDICAL REPORT
# =========================================================

@bot.tree.command(
    name="medical-report",
    description="إصدار تقرير طبي"
)
@app_commands.describe(
    citizen="المواطن",
    diagnosis="التشخيص",
    treatment="العلاج"
)
async def medical_report(
    interaction: discord.Interaction,
    citizen: discord.Member,
    diagnosis: str,
    treatment: str
):

    if not check_role(
        interaction.user,
        ROLE_HEALTH
    ):

        await interaction.response.send_message(
            "❌ الأمر مخصص لقطاع PHMC.",
            ephemeral=True
        )

        return

    db = db_connect()
    cursor = db.cursor()

    cursor.execute(
        """
        INSERT INTO medical_reports
        (
            guild_id,
            citizen_id,
            medic_id,
            diagnosis,
            treatment,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            interaction.guild.id,
            citizen.id,
            interaction.user.id,
            diagnosis,
            treatment,
            now_utc()
        )
    )

    report_id = cursor.lastrowid

    db.commit()
    db.close()

    embed = discord.Embed(
        title="🏥 تقرير طبي",
        color=discord.Color.green()
    )

    embed.add_field(
        name="🔢 رقم التقرير",
        value=f"`MED-{report_id:05d}`"
    )

    embed.add_field(
        name="👤 المواطن",
        value=citizen.mention
    )

    embed.add_field(
        name="🩺 التشخيص",
        value=diagnosis[:1024]
    )

    embed.add_field(
        name="💊 العلاج",
        value=treatment[:1024]
    )

    embed.set_footer(
        text=f"PHMC • {interaction.user}"
    )

    await interaction.response.send_message(
        embed=embed
    )

    await security_report(
        interaction.guild,
        "🏥 تقرير طبي",
        "تم إنشاء تقرير طبي.",
        discord.Color.green(),
        actor=interaction.user,
        target=citizen,
        extra_fields=[
            ("🔢 الرقم", f"MED-{report_id:05d}"),
            ("🩺 التشخيص", diagnosis),
            ("💊 العلاج", treatment)
        ]
    )


# =========================================================
# AI COMMAND
# =========================================================

@bot.tree.command(
    name="ai",
    description="إدارة نظام الذكاء الاصطناعي"
)
@app_commands.describe(
    action="اختر الإجراء",
    channel="الروم الذي يعمل فيه AI"
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

    # -------------------------
    # تفعيل
    # -------------------------

    if action.value == "enable":

        if not settings["ai_channel_id"]:

            await interaction.response.send_message(
                "❌ حدد روم AI أولًا.",
                ephemeral=True
            )

            return

        set_ai_settings(
            interaction.guild.id,
            enabled=True
        )

        await interaction.response.send_message(
            "✅ تم تفعيل AI.",
            ephemeral=True
        )

        await security_report(
            interaction.guild,
            "🤖 AI Enabled",
            "تم تفعيل نظام الذكاء الاصطناعي.",
            discord.Color.green(),
            actor=interaction.user,
            extra_fields=[
                (
                    "📍 الروم",
                    f"<#{settings['ai_channel_id']}>"
                )
            ]
        )

    # -------------------------
    # تعطيل
    # -------------------------

    elif action.value == "disable":

        set_ai_settings(
            interaction.guild.id,
            enabled=False
        )

        await interaction.response.send_message(
            "🛑 تم تعطيل AI.",
            ephemeral=True
        )

        await security_report(
            interaction.guild,
            "🛑 AI Disabled",
            "تم تعطيل نظام الذكاء الاصطناعي.",
            discord.Color.red(),
            actor=interaction.user
        )

    # -------------------------
    # تحديد روم
    # -------------------------

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
            f"✅ تم تحديد روم AI إلى {channel.mention}.",
            ephemeral=True
        )

        await security_report(
            interaction.guild,
            "📍 AI Channel Changed",
            "تم تغيير روم الذكاء الاصطناعي.",
            discord.Color.blue(),
            actor=interaction.user,
            extra_fields=[
                ("📍 الروم الجديد", channel.mention)
            ]
        )


# =========================================================
# READY
# =========================================================

@bot.event
async def on_ready():

    if not getattr(
        bot,
        "_mt_views_loaded",
        False
    ):

        bot.add_view(
            TicketSelectView()
        )

        bot.add_view(
            TicketCloseView()
        )

        bot._mt_views_loaded = True

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

    TOKEN = os.getenv("TOKEN")

    if not TOKEN:

        raise RuntimeError(
            "❌ لم يتم العثور على Environment Variable باسم TOKEN في Render."
        )

    bot.run(TOKEN)
