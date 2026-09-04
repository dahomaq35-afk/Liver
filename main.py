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

ROLE_JUSTICE = "𝗠𝗧 | Justice"
ROLE_POLICE = "𝗠𝗧 | LSPD"
ROLE_SWAT = "𝗠𝗧 | S.W.A.T"
ROLE_HEALTH = "𝗠𝗧 | PHMC"


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

    # -----------------------------------------------------
    # SETTINGS
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            guild_id INTEGER PRIMARY KEY,
            ai_enabled INTEGER DEFAULT 0,
            ai_channel_id INTEGER DEFAULT 0
        )
    """)

    # -----------------------------------------------------
    # إضافة أعمدة اللوق إذا كانت قاعدة البيانات قديمة
    # -----------------------------------------------------

    cursor.execute(
        "PRAGMA table_info(settings)"
    )

    existing_columns = {
        row[1]
        for row in cursor.fetchall()
    }

    new_columns = {
        "security_log_channel_id": "INTEGER DEFAULT 0",
        "delete_log_channel_id": "INTEGER DEFAULT 0",
        "edit_log_channel_id": "INTEGER DEFAULT 0",
        "member_log_channel_id": "INTEGER DEFAULT 0",
        "mod_log_channel_id": "INTEGER DEFAULT 0",
        "role_log_channel_id": "INTEGER DEFAULT 0",
        "channel_log_channel_id": "INTEGER DEFAULT 0"
    }

    for column_name, column_type in new_columns.items():

        if column_name not in existing_columns:

            cursor.execute(
                f"""
                ALTER TABLE settings
                ADD COLUMN {column_name} {column_type}
                """
            )

    # -----------------------------------------------------
    # الرتب المستثناة
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS excluded_roles (
            guild_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,
            PRIMARY KEY (guild_id, role_id)
        )
    """)

    # -----------------------------------------------------
    # Criminal Records
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # Warnings
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # Security Logs
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # Tickets
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # Deeds
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # Warrants
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # Dispatches
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # Medical Reports
    # -----------------------------------------------------

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
        SELECT
            ai_enabled,
            ai_channel_id,
            security_log_channel_id,
            delete_log_channel_id,
            edit_log_channel_id,
            member_log_channel_id,
            mod_log_channel_id,
            role_log_channel_id,
            channel_log_channel_id
        FROM settings
        WHERE guild_id = ?
        """,
        (guild_id,)
    )

    row = cursor.fetchone()

    if not row:

        cursor.execute(
            """
            INSERT INTO settings (
                guild_id,
                ai_enabled,
                ai_channel_id,
                security_log_channel_id,
                delete_log_channel_id,
                edit_log_channel_id,
                member_log_channel_id,
                mod_log_channel_id,
                role_log_channel_id,
                channel_log_channel_id
            )
            VALUES (?, 0, 0, 0, 0, 0, 0, 0, 0, 0)
            """,
            (guild_id,)
        )

        db.commit()
        db.close()

        return {
            "ai_enabled": False,
            "ai_channel_id": 0,
            "security_log_channel_id": 0,
            "delete_log_channel_id": 0,
            "edit_log_channel_id": 0,
            "member_log_channel_id": 0,
            "mod_log_channel_id": 0,
            "role_log_channel_id": 0,
            "channel_log_channel_id": 0
        }

    db.close()

    return {
        "ai_enabled": bool(row[0]),
        "ai_channel_id": row[1] or 0,
        "security_log_channel_id": row[2] or 0,
        "delete_log_channel_id": row[3] or 0,
        "edit_log_channel_id": row[4] or 0,
        "member_log_channel_id": row[5] or 0,
        "mod_log_channel_id": row[6] or 0,
        "role_log_channel_id": row[7] or 0,
        "channel_log_channel_id": row[8] or 0
    }


def set_ai_settings(
    guild_id,
    enabled=None,
    channel_id=None
):

    current = get_guild_settings(
        guild_id
    )

    if enabled is None:
        enabled = current["ai_enabled"]

    if channel_id is None:
        channel_id = current["ai_channel_id"]

    db = db_connect()
    cursor = db.cursor()

    cursor.execute(
        """
        INSERT INTO settings
        (
            guild_id,
            ai_enabled,
            ai_channel_id
        )
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


def set_log_channel(
    guild_id,
    setting_name,
    channel_id
):

    allowed = {
        "security_log_channel_id",
        "delete_log_channel_id",
        "edit_log_channel_id",
        "member_log_channel_id",
        "mod_log_channel_id",
        "role_log_channel_id",
        "channel_log_channel_id"
    }

    if setting_name not in allowed:
        raise ValueError("Invalid log setting")

    get_guild_settings(guild_id)

    db = db_connect()
    cursor = db.cursor()

    cursor.execute(
        f"""
        UPDATE settings
        SET {setting_name} = ?
        WHERE guild_id = ?
        """,
        (
            channel_id,
            guild_id
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
# EXCLUDED ROLES DATABASE
# =========================================================

def get_excluded_role_ids(guild_id):

    db = db_connect()
    cursor = db.cursor()

    cursor.execute(
        """
        SELECT role_id
        FROM excluded_roles
        WHERE guild_id = ?
        """,
        (guild_id,)
    )

    rows = cursor.fetchall()

    db.close()

    return {
        row[0]
        for row in rows
    }


def add_excluded_role(
    guild_id,
    role_id
):

    db = db_connect()
    cursor = db.cursor()

    cursor.execute(
        """
        INSERT OR IGNORE INTO excluded_roles
        (
            guild_id,
            role_id
        )
        VALUES (?, ?)
        """,
        (
            guild_id,
            role_id
        )
    )

    added = cursor.rowcount > 0

    db.commit()
    db.close()

    return added


def remove_excluded_role(
    guild_id,
    role_id
):

    db = db_connect()
    cursor = db.cursor()

    cursor.execute(
        """
        DELETE FROM excluded_roles
        WHERE guild_id = ?
        AND role_id = ?
        """,
        (
            guild_id,
            role_id
        )
    )

    removed = cursor.rowcount > 0

    db.commit()
    db.close()

    return removed


def clear_excluded_roles(
    guild_id
):

    db = db_connect()
    cursor = db.cursor()

    cursor.execute(
        """
        DELETE FROM excluded_roles
        WHERE guild_id = ?
        """,
        (guild_id,)
    )

    count = cursor.rowcount

    db.commit()
    db.close()

    return count


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


# =========================================================
# WHITELIST / PROTECTED ROLES
# =========================================================

WHITELIST_ROLES = [
    "MT | CEO",
    "MT | COowner ↔",
    "MT | Owner",
    "Bot"
]


def is_whitelisted(
    member,
    guild=None
):

    if not member:
        return False

    if guild is None:
        guild = member.guild

    # Owner مستثنى دائمًا حتى لا يستطيع النظام حظره
    if member.id == guild.owner_id:
        return True

    # الرتب المحمية الثابتة
    # المطابقة تدعم اختلاف الكابيتال والزخارف
    for role in member.roles:

        for whitelist_role in WHITELIST_ROLES:

            if role_matches(
                role.name,
                whitelist_role
            ):

                return True

    # الرتب المستثناة الموجودة في قاعدة البيانات
    excluded_roles = get_excluded_role_ids(
        guild.id
    )

    return any(
        role.id in excluded_roles
        for role in member.roles
    )


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
# INTERNAL SECURITY ACTIONS
# =========================================================

security_internal_actions = set()


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

إذا كان السؤال عن معلومة خاصة بسيرفر MT
وقد تكون متغيرة أو تحتاج مصدرًا رسميًا مثل:

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

أما الأسئلة العامة فأجب عنها بشكل طبيعي ومفيد.

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
# GET LOG CHANNEL
# =========================================================

def get_log_channel(
    guild,
    setting_name
):

    settings = get_guild_settings(
        guild.id
    )

    channel_id = settings.get(
        setting_name,
        0
    )

    if not channel_id:
        return None

    return guild.get_channel(
        channel_id
    )


# =========================================================
# GENERIC LOG
# =========================================================

async def send_log(
    guild,
    setting_name,
    title,
    description,
    color=discord.Color.blurple(),
    actor=None,
    target=None,
    extra_fields=None
):

    channel = get_log_channel(
        guild,
        setting_name
    )

    if not channel:
        return False

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
            value=(
                actor.mention
                if hasattr(actor, "mention")
                else str(actor)
            ),
            inline=True
        )

    if target:

        embed.add_field(
            name="🎯 المستهدف",
            value=(
                target.mention
                if hasattr(target, "mention")
                else str(target)
            ),
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

        return True

    except Exception as error:

        logging.error(
            f"Log send error: {error}"
        )

        return False


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

    await send_log(
        guild,
        "security_log_channel_id",
        title,
        description,
        color,
        actor,
        target,
        extra_fields
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
            limit=10,
            action=action
        ):

            if target_id is not None:

                if getattr(
                    entry.target,
                    "id",
                    None
                ) != target_id:

                    continue

            age = (
                datetime.datetime.now(
                    datetime.timezone.utc
                )
                -
                entry.created_at
            ).total_seconds()

            if age > 15:

                continue

            return entry.user

    except Exception as error:

        logging.error(
            f"Audit log error: {error}"
        )

    return None


async def get_audit_actor_multiple(
    guild,
    actions,
    target_id=None
):

    for action in actions:

        actor = await get_audit_actor(
            guild,
            action,
            target_id
        )

        if actor:

            return actor

    return None


# =========================================================
# BAN ACTOR
# =========================================================

async def ban_unauthorized_actor(
    guild,
    actor,
    reason
):

    if not actor:
        return "لم يتم تحديد المنفذ."

    if actor.id == guild.owner_id:

        return "تعذر الحظر: المنفذ هو Owner."

    if bot.user and actor.id == bot.user.id:

        return "المنفذ هو البوت نفسه."

    actor_member = guild.get_member(
        actor.id
    )

    if not actor_member:

        return "المنفذ غير موجود داخل السيرفر."

    if is_whitelisted(
        actor_member,
        guild
    ):

        return "المنفذ مستثنى."

    me = guild.me

    if not me:

        return "تعذر معرفة رتبة البوت."

    if actor_member.top_role >= me.top_role:

        return "تعذر الحظر بسبب Role Hierarchy."

    try:

        await guild.ban(
            actor_member,
            reason=reason
        )

        return "تم حظر المنفذ تلقائيًا."

    except Exception as error:

        logging.error(
            f"Auto ban error: {error}"
        )

        return f"فشل الحظر: {error}"


# =========================================================
# MEMBER BAN PROTECTION
# =========================================================

@bot.event
async def on_member_ban(
    guild,
    user
):

    await asyncio.sleep(0.5)

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

        await send_log(
            guild,
            "mod_log_channel_id",
            "⚠️ حظر بدون تحديد المنفذ",
            f"تم حظر {user.mention}.",
            discord.Color.orange(),
            target=user
        )

        return

    if bot.user and actor.id == bot.user.id:
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

        await send_log(
            guild,
            "mod_log_channel_id",
            "✅ حظر مصرح",
            f"تم تنفيذ حظر مصرح به على {user.mention}.",
            discord.Color.green(),
            actor=actor_member,
            target=user
        )

        return

    try:

        await guild.unban(
            user,
            reason="MT Security: Unauthorized ban"
        )

        unban_result = "تم فك حظر المستهدف."

    except Exception as error:

        unban_result = f"فشل فك الحظر: {error}"

    actor_result = await ban_unauthorized_actor(
        guild,
        actor,
        "MT Security: Unauthorized ban"
    )

    await security_report(
        guild,
        "🚨 حظر غير مصرح به",
        "تم اكتشاف حظر غير مصرح به.",
        discord.Color.red(),
        actor=actor_member or actor,
        target=user,
        extra_fields=[
            ("🔓 المستهدف", unban_result),
            ("🔨 المنفذ", actor_result)
        ]
    )

    await send_log(
        guild,
        "mod_log_channel_id",
        "🚨 حظر غير مصرح به",
        "تم اكتشاف حظر غير مصرح به.",
        discord.Color.red(),
        actor=actor_member or actor,
        target=user,
        extra_fields=[
            ("🔓 المستهدف", unban_result),
            ("🔨 المنفذ", actor_result)
        ]
    )


# =========================================================
# MEMBER UNBAN
# =========================================================

@bot.event
async def on_member_unban(
    guild,
    user
):

    await asyncio.sleep(0.5)

    actor = await get_audit_actor(
        guild,
        discord.AuditLogAction.unban,
        user.id
    )

    await send_log(
        guild,
        "mod_log_channel_id",
        "🔓 فك حظر",
        f"تم فك حظر {user.mention}.",
        discord.Color.green(),
        actor=actor,
        target=user
    )


# =========================================================
# MEMBER JOIN
# =========================================================

@bot.event
async def on_member_join(
    member
):

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

                    result = f"فشل الحظر: {error}"

                await security_report(
                    member.guild,
                    "🚨 بوت مشبوه",
                    "تم اكتشاف بوت جديد يمتلك Administrator.",
                    discord.Color.red(),
                    target=member,
                    extra_fields=[
                        ("⚡ الإجراء", result)
                    ]
                )

                await send_log(
                    member.guild,
                    "member_log_channel_id",
                    "🚨 بوت مشبوه",
                    "تم اكتشاف بوت جديد يمتلك Administrator.",
                    discord.Color.red(),
                    target=member,
                    extra_fields=[
                        ("⚡ الإجراء", result)
                    ]
                )

                return

    await send_log(
        member.guild,
        "member_log_channel_id",
        "👋 دخول عضو",
        f"دخل العضو {member.mention} إلى السيرفر.",
        discord.Color.green(),
        target=member,
        extra_fields=[
            ("🤖 Bot", str(member.bot)),
            ("🆔 ID", member.id)
        ]
    )


# =========================================================
# MEMBER LEAVE
# =========================================================

@bot.event
async def on_member_remove(
    member
):

    await asyncio.sleep(0.5)

    actor = await get_audit_actor(
        member.guild,
        discord.AuditLogAction.kick,
        member.id
    )

    if actor:

        actor_member = member.guild.get_member(
            actor.id
        )

        if actor_member and is_whitelisted(
            actor_member,
            member.guild
        ):

            await send_log(
                member.guild,
                "member_log_channel_id",
                "👢 طرد عضو مصرح",
                f"تم طرد {member.mention}.",
                discord.Color.orange(),
                actor=actor_member,
                target=member
            )

        else:

            result = await ban_unauthorized_actor(
                member.guild,
                actor,
                "MT Security: Unauthorized kick"
            )

            await security_report(
                member.guild,
                "🚨 طرد غير مصرح",
                f"تم اكتشاف طرد غير مصرح للعضو {member.mention}.",
                discord.Color.red(),
                actor=actor_member or actor,
                target=member,
                extra_fields=[
                    ("🔨 الإجراء", result)
                ]
            )

        return

    await send_log(
        member.guild,
        "member_log_channel_id",
        "👋 خروج عضو",
        f"غادر العضو {member.mention} السيرفر.",
        discord.Color.orange(),
        target=member
    )


# =========================================================
# ROLE CREATE
# =========================================================

@bot.event
async def on_guild_role_create(
    role
):

    key = (
        role.guild.id,
        "role",
        role.id
    )

    if key in security_internal_actions:

        security_internal_actions.discard(key)

        return

    actor = await get_audit_actor(
        role.guild,
        discord.AuditLogAction.role_create,
        role.id
    )

    actor_member = (
        role.guild.get_member(actor.id)
        if actor
        else None
    )

    if actor_member and is_whitelisted(
        actor_member,
        role.guild
    ):

        await send_log(
            role.guild,
            "role_log_channel_id",
            "✅ إنشاء رتبة مصرح",
            f"تم إنشاء الرتبة `{role.name}`.",
            discord.Color.green(),
            actor=actor_member,
            extra_fields=[
                ("🆔 Role ID", role.id)
            ]
        )

        return

    result = "لم يتم تحديد المنفذ."

    if actor:

        result = await ban_unauthorized_actor(
            role.guild,
            actor,
            "MT Security: Unauthorized role creation"
        )

    await security_report(
        role.guild,
        "🚨 إنشاء رتبة غير مصرح",
        f"تم إنشاء الرتبة `{role.name}` بدون تصريح.",
        discord.Color.red(),
        actor=actor_member or actor,
        extra_fields=[
            ("🆔 Role ID", role.id),
            ("🔨 الإجراء", result)
        ]
    )

    await send_log(
        role.guild,
        "role_log_channel_id",
        "🚨 إنشاء رتبة غير مصرح",
        f"تم إنشاء الرتبة `{role.name}` بدون تصريح.",
        discord.Color.red(),
        actor=actor_member or actor,
        extra_fields=[
            ("🆔 Role ID", role.id),
            ("🔨 الإجراء", result)
        ]
    )


# =========================================================
# ROLE DELETE
# =========================================================

@bot.event
async def on_guild_role_delete(
    role
):

    key = (
        role.guild.id,
        "role_delete",
        role.id
    )

    if key in security_internal_actions:

        security_internal_actions.discard(key)

        return

    actor = await get_audit_actor(
        role.guild,
        discord.AuditLogAction.role_delete,
        role.id
    )

    actor_member = (
        role.guild.get_member(actor.id)
        if actor
        else None
    )

    if actor_member and is_whitelisted(
        actor_member,
        role.guild
    ):

        await send_log(
            role.guild,
            "role_log_channel_id",
            "✅ حذف رتبة مصرح",
            f"تم حذف الرتبة `{role.name}`.",
            discord.Color.green(),
            actor=actor_member
        )

        return

    result = "لم يتم تحديد المنفذ."

    if actor:

        result = await ban_unauthorized_actor(
            role.guild,
            actor,
            "MT Security: Unauthorized role deletion"
        )

    await security_report(
        role.guild,
        "🚨 حذف رتبة غير مصرح",
        f"تم حذف الرتبة `{role.name}`.",
        discord.Color.red(),
        actor=actor_member or actor,
        extra_fields=[
            ("🆔 Role ID", role.id),
            ("🔨 الإجراء", result)
        ]
    )

    await send_log(
        role.guild,
        "role_log_channel_id",
        "🚨 حذف رتبة غير مصرح",
        f"تم حذف الرتبة `{role.name}`.",
        discord.Color.red(),
        actor=actor_member or actor,
        extra_fields=[
            ("🆔 Role ID", role.id),
            ("🔨 الإجراء", result)
        ]
    )


# =========================================================
# ROLE UPDATE
# =========================================================

@bot.event
async def on_guild_role_update(
    before,
    after
):

    key = (
        after.guild.id,
        "role",
        after.id
    )

    if key in security_internal_actions:

        security_internal_actions.discard(key)

        return

    changed = []

    if before.name != after.name:

        changed.append(
            f"الاسم: `{before.name}` → `{after.name}`"
        )

    if before.permissions != after.permissions:

        changed.append(
            "تم تعديل صلاحيات الرتبة"
        )

    if before.position != after.position:

        changed.append(
            f"الموقع: `{before.position}` → `{after.position}`"
        )

    if before.colour != after.colour:

        changed.append(
            "تم تعديل لون الرتبة"
        )

    if before.hoist != after.hoist:

        changed.append(
            "تم تعديل إظهار الرتبة بشكل منفصل"
        )

    if before.mentionable != after.mentionable:

        changed.append(
            "تم تعديل قابلية المنشن"
        )

    if not changed:

        return

    actor = await get_audit_actor(
        after.guild,
        discord.AuditLogAction.role_update,
        after.id
    )

    actor_member = (
        after.guild.get_member(actor.id)
        if actor
        else None
    )

    details = "\n".join(
        changed
    )

    if actor_member and is_whitelisted(
        actor_member,
        after.guild
    ):

        await send_log(
            after.guild,
            "role_log_channel_id",
            "🛡️ تعديل رتبة مصرح",
            details,
            discord.Color.green(),
            actor=actor_member,
            extra_fields=[
                ("🎭 الرتبة", after.mention)
            ]
        )

        return

    restore_result = "لم تتم الاستعادة."

    if before.permissions != after.permissions:

        try:

            security_internal_actions.add(
                key
            )

            await after.edit(
                permissions=before.permissions,
                reason="MT Security: Restore unauthorized role permissions"
            )

            restore_result = (
                "تمت استعادة صلاحيات الرتبة."
            )

        except Exception as error:

            security_internal_actions.discard(
                key
            )

            restore_result = (
                f"فشل الاستعادة: {error}"
            )

    ban_result = "لم يتم تحديد المنفذ."

    if actor:

        ban_result = await ban_unauthorized_actor(
            after.guild,
            actor,
            "MT Security: Unauthorized role modification"
        )

    await security_report(
        after.guild,
        "🚨 تعديل رتبة غير مصرح",
        details,
        discord.Color.red(),
        actor=actor_member or actor,
        extra_fields=[
            ("🎭 الرتبة", after.mention),
            ("🔄 الاستعادة", restore_result),
            ("🔨 الإجراء", ban_result)
        ]
    )

    await send_log(
        after.guild,
        "role_log_channel_id",
        "🚨 تعديل رتبة غير مصرح",
        details,
        discord.Color.red(),
        actor=actor_member or actor,
        extra_fields=[
            ("🎭 الرتبة", after.mention),
            ("🔄 الاستعادة", restore_result),
            ("🔨 الإجراء", ban_result)
        ]
    )


# =========================================================
# CHANNEL CREATE
# =========================================================

@bot.event
async def on_guild_channel_create(
    channel
):

    actor = await get_audit_actor(
        channel.guild,
        discord.AuditLogAction.channel_create,
        channel.id
    )

    actor_member = (
        channel.guild.get_member(actor.id)
        if actor
        else None
    )

    if actor_member and is_whitelisted(
        actor_member,
        channel.guild
    ):

        await send_log(
            channel.guild,
            "channel_log_channel_id",
            "✅ إنشاء روم مصرح",
            f"تم إنشاء الروم {channel.mention}.",
            discord.Color.green(),
            actor=actor_member,
            extra_fields=[
                ("🆔 Channel ID", channel.id)
            ]
        )

        return

    result = "لم يتم تحديد المنفذ."

    if actor:

        result = await ban_unauthorized_actor(
            channel.guild,
            actor,
            "MT Security: Unauthorized channel creation"
        )

    await security_report(
        channel.guild,
        "🚨 إنشاء روم غير مصرح",
        f"تم إنشاء الروم `{channel.name}` بدون تصريح.",
        discord.Color.red(),
        actor=actor_member or actor,
        extra_fields=[
            ("🆔 Channel ID", channel.id),
            ("🔨 الإجراء", result)
        ]
    )

    await send_log(
        channel.guild,
        "channel_log_channel_id",
        "🚨 إنشاء روم غير مصرح",
        f"تم إنشاء الروم `{channel.name}` بدون تصريح.",
        discord.Color.red(),
        actor=actor_member or actor,
        extra_fields=[
            ("🆔 Channel ID", channel.id),
            ("🔨 الإجراء", result)
        ]
    )


# =========================================================
# CHANNEL DELETE
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

    actor_member = (
        channel.guild.get_member(actor.id)
        if actor
        else None
    )

    if actor_member and is_whitelisted(
        actor_member,
        channel.guild
    ):

        await send_log(
            channel.guild,
            "channel_log_channel_id",
            "✅ حذف روم مصرح",
            f"تم حذف الروم `{channel.name}`.",
            discord.Color.green(),
            actor=actor_member,
            extra_fields=[
                ("🆔 Channel ID", channel.id)
            ]
        )

        return

    result = "لم يتم تحديد المنفذ."

    if actor:

        result = await ban_unauthorized_actor(
            channel.guild,
            actor,
            "MT Security: Unauthorized channel deletion"
        )

    await security_report(
        channel.guild,
        "🚨 حذف روم غير مصرح",
        f"تم حذف الروم `{channel.name}`.",
        discord.Color.red(),
        actor=actor_member or actor,
        extra_fields=[
            ("🆔 Channel ID", channel.id),
            ("🔨 الإجراء", result)
        ]
    )

    await send_log(
        channel.guild,
        "channel_log_channel_id",
        "🚨 حذف روم غير مصرح",
        f"تم حذف الروم `{channel.name}`.",
        discord.Color.red(),
        actor=actor_member or actor,
        extra_fields=[
            ("🆔 Channel ID", channel.id),
            ("🔨 الإجراء", result)
        ]
    )


# =========================================================
# CHANNEL UPDATE
# =========================================================

@bot.event
async def on_guild_channel_update(
    before,
    after
):

    changes = []

    if before.name != after.name:

        changes.append(
            f"الاسم: `{before.name}` → `{after.name}`"
        )

    if before.category_id != after.category_id:

        changes.append(
            "تم تغيير التصنيف"
        )

    before_topic = getattr(
        before,
        "topic",
        None
    )

    after_topic = getattr(
        after,
        "topic",
        None
    )

    if before_topic != after_topic:

        changes.append(
            "تم تعديل وصف/موضوع الروم"
        )

    if before.slowmode_delay != after.slowmode_delay:

        changes.append(
            f"Slowmode: `{before.slowmode_delay}` → `{after.slowmode_delay}`"
        )

    permission_changed = (
        before.overwrites != after.overwrites
    )

    if permission_changed:

        changes.append(
            "🚨 تم تعديل صلاحيات الروم"
        )

    if not changes:

        return

    actor = await get_audit_actor_multiple(
        after.guild,
        [
            discord.AuditLogAction.overwrite_update,
            discord.AuditLogAction.overwrite_create,
            discord.AuditLogAction.overwrite_delete,
            discord.AuditLogAction.channel_update
        ],
        after.id
    )

    actor_member = (
        after.guild.get_member(actor.id)
        if actor
        else None
    )

    details = "\n".join(
        changes
    )

    if actor_member and is_whitelisted(
        actor_member,
        after.guild
    ):

        await send_log(
            after.guild,
            "channel_log_channel_id",
            "🛡️ تعديل روم مصرح",
            details,
            discord.Color.green(),
            actor=actor_member,
            extra_fields=[
                ("📍 الروم", after.mention)
            ]
        )

        return

    ban_result = "لم يتم تحديد المنفذ."

    if actor:

        ban_result = await ban_unauthorized_actor(
            after.guild,
            actor,
            "MT Security: Unauthorized channel modification"
        )

    await security_report(
        after.guild,
        "🚨 تعديل روم غير مصرح",
        details,
        discord.Color.red(),
        actor=actor_member or actor,
        extra_fields=[
            ("📍 الروم", after.mention),
            ("🔨 الإجراء", ban_result)
        ]
    )

    await send_log(
        after.guild,
        "channel_log_channel_id",
        "🚨 تعديل روم غير مصرح",
        details,
        discord.Color.red(),
        actor=actor_member or actor,
        extra_fields=[
            ("📍 الروم", after.mention),
            ("🔨 الإجراء", ban_result)
        ]
    )


# =========================================================
# MESSAGE DELETE LOG
# =========================================================

@bot.event
async def on_message_delete(
    message
):

    if not message.guild:
        return

    if message.author.bot:
        return

    content = message.content

    if not content:

        content = (
            "[لا يوجد محتوى نصي — ربما صورة/ملف/Embed]"
        )

    await send_log(
        message.guild,
        "delete_log_channel_id",
        "🗑️ رسالة محذوفة",
        f"تم حذف رسالة من {message.channel.mention}.",
        discord.Color.red(),
        actor=message.author,
        extra_fields=[
            ("📍 القناة", message.channel.mention),
            ("📝 المحتوى", content[:1000]),
            ("🆔 Message ID", message.id)
        ]
    )


# =========================================================
# MESSAGE EDIT LOG
# =========================================================

@bot.event
async def on_message_edit(
    before,
    after
):

    if not after.guild:
        return

    if after.author.bot:
        return

    if before.content == after.content:
        return

    old_content = before.content or "[فارغ]"
    new_content = after.content or "[فارغ]"

    await send_log(
        after.guild,
        "edit_log_channel_id",
        "✏️ رسالة معدلة",
        f"تم تعديل رسالة في {after.channel.mention}.",
        discord.Color.orange(),
        actor=after.author,
        extra_fields=[
            ("📍 القناة", after.channel.mention),
            ("📝 قبل التعديل", old_content[:1000]),
            ("📝 بعد التعديل", new_content[:1000]),
            ("🆔 Message ID", after.id)
        ]
    )


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
    # @everyone / @here
    # -----------------------------------------------------

    if (
        "@everyone" in message.content
        or "@here" in message.content
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
                "⚠️ منع المنشن العام",
                "تم حذف رسالة تحتوي على منشن عام بدون استثناء.",
                discord.Color.gold(),
                actor=member,
                extra_fields=[
                    ("📍 القناة", message.channel.mention),
                    ("📝 المحتوى", message.content[:1000])
                ]
            )

            return

    # -----------------------------------------------------
    # الروابط
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
                    ("📝 المحتوى", message.content[:1000])
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
# EXCLUDED ROLES COMMAND PERMISSION
# =========================================================

def can_manage_security(
    interaction
):

    if not interaction.guild:
        return False

    # -----------------------------------------------------
    # مالك السيرفر الحقيقي
    # -----------------------------------------------------

    if interaction.user.id == interaction.guild.owner_id:
        return True

    # -----------------------------------------------------
    # Owner + COowner فقط
    # -----------------------------------------------------

    allowed_roles = [
        "MT | Owner",
        "MT | COowner ↔"
    ]

    return any(
        role_matches(
            role.name,
            allowed_role
        )
        for role in interaction.user.roles
        for allowed_role in allowed_roles
    )


# =========================================================
# SET EXCLUDED ROLE
# =========================================================

@bot.tree.command(
    name="set-excluded-role",
    description="إضافة رتبة إلى الرتب المستثناة من الحماية"
)
@app_commands.describe(
    role="الرتبة التي تريد استثنائها"
)
async def set_excluded_role(
    interaction: discord.Interaction,
    role: discord.Role
):

    if not can_manage_security(
        interaction
    ):

        await interaction.response.send_message(
            "❌ هذا الأمر للـ Owner و COowner فقط.",
            ephemeral=True
        )

        return

    added = add_excluded_role(
        interaction.guild.id,
        role.id
    )

    if not added:

        await interaction.response.send_message(
            f"⚠️ الرتبة {role.mention} مستثناة بالفعل.",
            ephemeral=True
        )

        return

    await interaction.response.send_message(
        f"✅ تمت إضافة {role.mention} إلى الرتب المستثناة.",
        ephemeral=True
    )

    await security_report(
        interaction.guild,
        "🛡️ إضافة رتبة مستثناة",
        f"تمت إضافة الرتبة `{role.name}` إلى قائمة الاستثناءات.",
        discord.Color.green(),
        actor=interaction.user,
        extra_fields=[
            ("🎭 الرتبة", role.mention),
            ("🆔 Role ID", role.id)
        ]
    )


# =========================================================
# REMOVE EXCLUDED ROLE
# =========================================================

@bot.tree.command(
    name="remove-excluded-role",
    description="إزالة رتبة من الرتب المستثناة"
)
@app_commands.describe(
    role="الرتبة التي تريد إزالتها"
)
async def remove_excluded_role_command(
    interaction: discord.Interaction,
    role: discord.Role
):

    if not can_manage_security(
        interaction
    ):

        await interaction.response.send_message(
            "❌ هذا الأمر للـ Owner و COowner فقط.",
            ephemeral=True
        )

        return

    removed = remove_excluded_role(
        interaction.guild.id,
        role.id
    )

    if not removed:

        await interaction.response.send_message(
            f"⚠️ الرتبة {role.mention} ليست ضمن الاستثناءات.",
            ephemeral=True
        )

        return

    await interaction.response.send_message(
        f"✅ تمت إزالة {role.mention} من الرتب المستثناة.",
        ephemeral=True
    )

    await security_report(
        interaction.guild,
        "🔓 إزالة رتبة مستثناة",
        f"تمت إزالة الرتبة `{role.name}` من الاستثناءات.",
        discord.Color.orange(),
        actor=interaction.user,
        extra_fields=[
            ("🎭 الرتبة", role.mention)
        ]
    )


# =========================================================
# CLEAR EXCLUDED ROLES
# =========================================================

@bot.tree.command(
    name="clear-excluded-roles",
    description="حذف جميع الرتب المستثناة"
)
async def clear_excluded_roles_command(
    interaction: discord.Interaction
):

    if not can_manage_security(
        interaction
    ):

        await interaction.response.send_message(
            "❌ هذا الأمر للـ Owner و COowner فقط.",
            ephemeral=True
        )

        return

    count = clear_excluded_roles(
        interaction.guild.id
    )

    await interaction.response.send_message(
        f"🗑️ تم حذف **{count}** رتبة من قائمة الاستثناءات.",
        ephemeral=True
    )

    await security_report(
        interaction.guild,
        "🗑️ مسح الرتب المستثناة",
        f"تم حذف جميع الرتب المستثناة وعددها **{count}**.",
        discord.Color.red(),
        actor=interaction.user
    )


# =========================================================
# LIST EXCLUDED ROLES
# =========================================================

@bot.tree.command(
    name="list-excluded-roles",
    description="عرض جميع الرتب المستثناة"
)
async def list_excluded_roles_command(
    interaction: discord.Interaction
):

    if not can_manage_security(
        interaction
    ):

        await interaction.response.send_message(
            "❌ هذا الأمر للـ Owner و COowner فقط.",
            ephemeral=True
        )

        return

    role_ids = get_excluded_role_ids(
        interaction.guild.id
    )

    if not role_ids:

        await interaction.response.send_message(
            "📋 لا توجد أي رتب مستثناة حاليًا.",
            ephemeral=True
        )

        return

    lines = []

    for index, role_id in enumerate(
        sorted(role_ids),
        1
    ):

        role = interaction.guild.get_role(
            role_id
        )

        if role:

            lines.append(
                f"**{index}.** {role.mention} — `{role.name}`"
            )

        else:

            lines.append(
                f"**{index}.** رتبة محذوفة — `{role_id}`"
            )

    description = "\n".join(
        lines
    )

    embed = discord.Embed(
        title="🛡️ الرتب المستثناة",
        description=description[:4000],
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="📊 العدد",
        value=str(len(role_ids)),
        inline=False
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# =========================================================
# GENERIC SET LOG COMMAND
# =========================================================

async def set_log_command(
    interaction,
    setting_name,
    title,
    channel
):

    if not can_manage_security(
        interaction
    ):

        await interaction.response.send_message(
            "❌ هذا الأمر للـ Owner و COowner فقط.",
            ephemeral=True
        )

        return

    set_log_channel(
        interaction.guild.id,
        setting_name,
        channel.id
    )

    await interaction.response.send_message(
        f"✅ تم تعيين {title} إلى {channel.mention}.",
        ephemeral=True
    )

    await security_report(
        interaction.guild,
        f"📍 تغيير {title}",
        f"تم تعيين {title} إلى {channel.mention}.",
        discord.Color.blue(),
        actor=interaction.user
    )


# =========================================================
# SECURITY LOG
# =========================================================

@bot.tree.command(
    name="set-security-log",
    description="تحديد روم سجل الحماية"
)
@app_commands.describe(
    channel="روم سجل الحماية"
)
async def set_security_log(
    interaction: discord.Interaction,
    channel: discord.TextChannel
):

    await set_log_command(
        interaction,
        "security_log_channel_id",
        "سجل الحماية",
        channel
    )


# =========================================================
# DELETE LOG
# =========================================================

@bot.tree.command(
    name="set-delete-log",
    description="تحديد روم سجل الرسائل المحذوفة"
)
@app_commands.describe(
    channel="روم الرسائل المحذوفة"
)
async def set_delete_log(
    interaction: discord.Interaction,
    channel: discord.TextChannel
):

    await set_log_command(
        interaction,
        "delete_log_channel_id",
        "سجل الحذف",
        channel
    )


# =========================================================
# EDIT LOG
# =========================================================

@bot.tree.command(
    name="set-edit-log",
    description="تحديد روم سجل الرسائل المعدلة"
)
@app_commands.describe(
    channel="روم الرسائل المعدلة"
)
async def set_edit_log(
    interaction: discord.Interaction,
    channel: discord.TextChannel
):

    await set_log_command(
        interaction,
        "edit_log_channel_id",
        "سجل التعديل",
        channel
    )


# =========================================================
# MEMBER LOG
# =========================================================

@bot.tree.command(
    name="set-member-log",
    description="تحديد روم سجل دخول وخروج الأعضاء"
)
@app_commands.describe(
    channel="روم الأعضاء"
)
async def set_member_log(
    interaction: discord.Interaction,
    channel: discord.TextChannel
):

    await set_log_command(
        interaction,
        "member_log_channel_id",
        "سجل الأعضاء",
        channel
    )


# =========================================================
# MOD LOG
# =========================================================

@bot.tree.command(
    name="set-mod-log",
    description="تحديد روم سجل العمليات الإدارية"
)
@app_commands.describe(
    channel="روم العمليات الإدارية"
)
async def set_mod_log(
    interaction: discord.Interaction,
    channel: discord.TextChannel
):

    await set_log_command(
        interaction,
        "mod_log_channel_id",
        "سجل الإدارة",
        channel
    )


# =========================================================
# ROLE LOG
# =========================================================

@bot.tree.command(
    name="set-role-log",
    description="تحديد روم سجل الرتب"
)
@app_commands.describe(
    channel="روم الرتب"
)
async def set_role_log(
    interaction: discord.Interaction,
    channel: discord.TextChannel
):

    await set_log_command(
        interaction,
        "role_log_channel_id",
        "سجل الرتب",
        channel
    )


# =========================================================
# CHANNEL LOG
# =========================================================

@bot.tree.command(
    name="set-channel-log",
    description="تحديد روم سجل الرومات والصلاحيات"
)
@app_commands.describe(
    channel="روم الرومات"
)
async def set_channel_log(
    interaction: discord.Interaction,
    channel: discord.TextChannel
):

    await set_log_command(
        interaction,
        "channel_log_channel_id",
        "سجل الرومات",
        channel
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


# =========================================================
# TICKET CLOSE
# =========================================================

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

        security = get_log_channel(
            interaction.guild,
            "security_log_channel_id"
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

            try:

                await security.send(
                    content=(
                        f"🔒 **تم إغلاق تذكرة**\n"
                        f"القناة: `{channel.name}`\n"
                        f"بواسطة: {interaction.user.mention}"
                    ),
                    file=file
                )

            except Exception as error:

                logging.error(
                    f"Ticket transcript error: {error}"
                )

        await asyncio.sleep(2)

        try:

            await channel.delete(
                reason="MT Ticket Closed"
            )

        except Exception:
            pass


# =========================================================
# TICKET SELECT
# =========================================================

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
        description="تم إصدار مذكرة رسمية.",
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
        description="تم إصدار أمر انتشار S.W.A.T.",
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
# PHMC
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

    TOKEN = os.getenv(
        "TOKEN"
    )

    if not TOKEN:

        raise RuntimeError(
            "❌ لم يتم العثور على Environment Variable باسم TOKEN في Render."
        )

    bot.run(
        TOKEN
    )
