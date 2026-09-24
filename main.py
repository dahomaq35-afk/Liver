import os
import io
import re
import time
import asyncio
import datetime
import logging
import sqlite3
import unicodedata

from keepalive import keep_alive

import discord
from discord import app_commands
from discord.ext import commands
from openai import AsyncOpenAI

# =========================================================
# SETTINGS
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
ROLE_INTERIOR = "𝗠𝗧 | Interior"

DB_FILE = "mt_bot.db"

SUPPORT_CHANNEL_ID = 1541582061893062656

WHITELIST_ROLES = [
    "MT | CEO",
    "MT | COowner",
    "MT | Owner",
    "Bot"
]

# =========================================================
# PERFORMANCE CACHE
# =========================================================

SETTINGS_CACHE = {}
EXCLUDED_ROLES_CACHE = {}

CACHE_TTL = 5.0

TICKET_LOCKS = {}


def cache_valid(cache, guild_id):
    item = cache.get(guild_id)

    if not item:
        return False

    return (
        time.monotonic() - item["time"]
    ) < CACHE_TTL


def invalidate_guild_cache(guild_id):
    SETTINGS_CACHE.pop(guild_id, None)
    EXCLUDED_ROLES_CACHE.pop(guild_id, None)


# =========================================================
# DATABASE
# =========================================================

def db_connect():
    db = sqlite3.connect(
        DB_FILE,
        timeout=5
    )

    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")
    db.execute("PRAGMA busy_timeout=5000")

    return db


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

    cursor.execute("PRAGMA table_info(settings)")

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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS excluded_roles (
            guild_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,
            PRIMARY KEY (guild_id, role_id)
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
        CREATE TABLE IF NOT EXISTS ticket_roles (
            guild_id INTEGER NOT NULL,
            department TEXT NOT NULL,
            option_key TEXT NOT NULL,
            role_id INTEGER NOT NULL,
            PRIMARY KEY (
                guild_id,
                department,
                option_key
            )
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

    # =====================================================
    # RULES SYSTEM
    # =====================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rules (
            guild_id INTEGER NOT NULL,
            rule_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (guild_id, rule_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rules_settings (
            guild_id INTEGER PRIMARY KEY,
            embed_enabled INTEGER DEFAULT 0,
            target_channel_id INTEGER DEFAULT 0,
            target_message_id INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_rules_guild
        ON rules(guild_id, rule_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_tickets_open_user
        ON tickets(guild_id, user_id, closed)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_tickets_channel
        ON tickets(channel_id, closed)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_security_guild
        ON security_logs(guild_id, created_at)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_records_citizen
        ON criminal_records(guild_id, citizen_id)
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

    if cache_valid(
        SETTINGS_CACHE,
        guild_id
    ):
        return SETTINGS_CACHE[guild_id]["data"]

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

        data = {
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

    else:

        data = {
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

    db.close()

    SETTINGS_CACHE[guild_id] = {
        "time": time.monotonic(),
        "data": data
    }

    return data


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

    invalidate_guild_cache(
        guild_id
    )


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
        raise ValueError(
            "Invalid log setting"
        )

    get_guild_settings(
        guild_id
    )

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

    invalidate_guild_cache(
        guild_id
    )


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
# OPENAI AI LOGIC
# =========================================================

ai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def ask_openai_chat(system_prompt: str, user_prompt: str) -> str:
    if not os.getenv("OPENAI_API_KEY"):
        return "⚠️ مفتاح OpenAI غير مفعّل في بيئة التشغيل."

    try:
        response = await ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=600,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"OpenAI Error: {e}")
        return "⚠️ حدث خطأ أثناء الاتصال بالذكاء الاصطناعي."


# =========================================================
# LOGGING SYSTEM HELPERS
# =========================================================

async def send_log_embed(guild: discord.Guild, setting_key: str, embed: discord.Embed):
    settings = get_guild_settings(guild.id)
    channel_id = settings.get(setting_key)
    if not channel_id:
        return

    channel = guild.get_channel(channel_id)
    if channel and channel.permissions_for(guild.me).send_messages:
        try:
            await channel.send(embed=embed)
        except Exception as e:
            logging.error(f"Failed to send log to channel {channel_id}: {e}")


# =========================================================
# DISCORD BOT SETUP
# =========================================================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.moderation = True

bot = commands.Bot(command_prefix=BOT_PREFIX, intents=intents)


@bot.event
async def on_ready():
    logging.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        synced = await bot.tree.sync()
        logging.info(f"Synced {len(synced)} slash commands.")
    except Exception as e:
        logging.error(f"Failed to sync slash commands: {e}")


# =========================================================
# ADVANCED AUDIT & LOGGING EVENTS
# =========================================================

@bot.event
async def on_message_delete(message: discord.Message):
    if not message.guild or message.author.bot:
        return

    embed = discord.Embed(
        title="🗑️ تم حذف رسالة",
        color=discord.Color.red(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    embed.add_field(name="المرسل:", value=f"{message.author.mention} (`{message.author.id}`)", inline=True)
    embed.add_field(name="القناة:", value=message.channel.mention, inline=True)
    embed.add_field(name="المحتوى:", value=message.content or "*محتوى فارغ أو مرفق*", inline=False)

    await send_log_embed(message.guild, "delete_log_channel_id", embed)


@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    if not before.guild or before.author.bot or before.content == after.content:
        return

    embed = discord.Embed(
        title="✏️ تم تعديل رسالة",
        color=discord.Color.gold(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    embed.add_field(name="المرسل:", value=f"{before.author.mention} (`{before.author.id}`)", inline=True)
    embed.add_field(name="القناة:", value=before.channel.mention, inline=True)
    embed.add_field(name="قبل:", value=before.content or "*فارغ*", inline=False)
    embed.add_field(name="بعد:", value=after.content or "*فارغ*", inline=False)

    await send_log_embed(before.guild, "edit_log_channel_id", embed)


@bot.event
async def on_member_join(member: discord.Member):
    embed = discord.Embed(
        title="📥 دخول عضو جديد",
        description=f"مرحباً بك {member.mention} في **{member.guild.name}**!",
        color=discord.Color.green(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="معرف العضو:", value=f"`{member.id}`", inline=True)
    embed.add_field(name="تاريخ إنشاء الحساب:", value=f"<t:{int(member.created_at.timestamp())}:R>", inline=True)

    await send_log_embed(member.guild, "member_log_channel_id", embed)


@bot.event
async def on_member_remove(member: discord.Member):
    embed = discord.Embed(
        title="📤 خروج عضو",
        description=f"غادر العضو {member.mention} السيرفر.",
        color=discord.Color.dark_grey(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="معرف العضو:", value=f"`{member.id}`", inline=True)

    await send_log_embed(member.guild, "member_log_channel_id", embed)


@bot.event
async def on_guild_channel_create(channel: discord.abc.GuildChannel):
    embed = discord.Embed(
        title="➕ إنشاء قناة جديدة",
        color=discord.Color.blue(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    embed.add_field(name="اسم القناة:", value=channel.name, inline=True)
    embed.add_field(name="النوع:", value=str(channel.type), inline=True)
    embed.add_field(name="المعرف:", value=f"`{channel.id}`", inline=False)

    await send_log_embed(channel.guild, "channel_log_channel_id", embed)


@bot.event
async def on_guild_channel_delete(channel: discord.abc.GuildChannel):
    embed = discord.Embed(
        title="➖ حذف قناة",
        color=discord.Color.dark_red(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    embed.add_field(name="اسم القناة:", value=channel.name, inline=True)
    embed.add_field(name="المعرف:", value=f"`{channel.id}`", inline=False)

    await send_log_embed(channel.guild, "channel_log_channel_id", embed)


# =========================================================
# AI LISTENER EVENT
# =========================================================

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        await bot.process_commands(message)
        return

    settings = get_guild_settings(message.guild.id)

    if settings["ai_enabled"] and message.channel.id == settings["ai_channel_id"]:
        system_prompt = (
            "أنت مساعد ذكاء اصطناعي رائع وخبير لسيرفر Roleplay في لعبة GTA V (Mystery Town). "
            "أجب بشكل وافي ومفيد وباللغة العربية مع لمسة احترافية."
        )

        async with message.channel.typing():
            reply = await ask_openai_chat(system_prompt, message.content)
            await message.reply(reply, mention_author=False)

    await bot.process_commands(message)


# =========================================================
# TICKET SYSTEM & VIEWS
# =========================================================

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="إغلاق التذكرة", style=discord.ButtonStyle.danger, custom_id="btn_close_ticket", emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        db = db_connect()
        cursor = db.cursor()
        cursor.execute("SELECT id, user_id FROM tickets WHERE channel_id = ? AND closed = 0", (interaction.channel.id,))
        row = cursor.fetchone()

        if not row:
            await interaction.response.send_message("❌ هذه القناة ليست تذكرة نشطة.", ephemeral=True)
            db.close()
            return

        ticket_id, owner_id = row
        cursor.execute("UPDATE tickets SET closed = 1 WHERE id = ?", (ticket_id,))
        db.commit()
        db.close()

        await interaction.response.send_message("🔒 جاري إغلاق التذكرة وأرشفة المحادثة...")
        await asyncio.sleep(3)
        await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")

    @discord.ui.button(label="استلام التذكرة", style=discord.ButtonStyle.success, custom_id="btn_claim_ticket", emoji="🖐️")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        db = db_connect()
        cursor = db.cursor()
        cursor.execute("SELECT id, claimed_by FROM tickets WHERE channel_id = ? AND closed = 0", (interaction.channel.id,))
        row = cursor.fetchone()

        if not row:
            await interaction.response.send_message("❌ هذه القناة ليست تذكرة نشطة.", ephemeral=True)
            db.close()
            return

        ticket_id, claimed_by = row
        if claimed_by != 0:
            await interaction.response.send_message(f"⚠️ التذكرة مستلمة بالفعل بواسطة <@{claimed_by}>.", ephemeral=True)
            db.close()
            return

        cursor.execute("UPDATE tickets SET claimed_by = ? WHERE id = ?", (interaction.user.id, ticket_id))
        db.commit()
        db.close()

        embed = discord.Embed(
            description=f"✅ تم استلام التذكرة بواسطة {interaction.user.mention}.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)


class TicketLaunchView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        placeholder="اختر القسم المناسب لفتح تذكرة...",
        custom_id="select_ticket_dept",
        options=[
            discord.SelectOption(label="الدعم الفني والشكاوى", value="support", description="مساعدة عامة أو تقديم شكوى", emoji="🛠️"),
            discord.SelectOption(label="وزارة العدل", value="justice", description="القضايا والمحاكمات والتوثيق", emoji="⚖️"),
            discord.SelectOption(label="الشرطة LSPD", value="police", description="البلاغات والخدمات العسكرية", emoji="🚔"),
            discord.SelectOption(label="الوزارة الصحية PHMC", value="health", description="التقارير والخدمات الطبية", emoji="🚑"),
        ]
    )
    async def select_dept(self, interaction: discord.Interaction, select: discord.ui.Select):
        dept = select.values[0]
        guild = interaction.guild

        # Create lock for race condition prevention
        if interaction.user.id not in TICKET_LOCKS:
            TICKET_LOCKS[interaction.user.id] = asyncio.Lock()

        async with TICKET_LOCKS[interaction.user.id]:
            db = db_connect()
            cursor = db.cursor()
            cursor.execute("SELECT id FROM tickets WHERE guild_id = ? AND user_id = ? AND closed = 0", (guild.id, interaction.user.id))
            if cursor.fetchone():
                await interaction.response.send_message("❌ لديك تذكرة مفتوحة بالفعل! يرجى إغلاقها قبل فتح جديدة.", ephemeral=True)
                db.close()
                return

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
            }

            channel_name = f"ticket-{dept}-{interaction.user.name}"
            category = discord.utils.get(guild.categories, name="TICKETS")
            
            ticket_chan = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                reason="فتح تذكرة جديدة"
            )

            cursor.execute(
                "INSERT INTO tickets (guild_id, user_id, channel_id, sector, created_at) VALUES (?, ?, ?, ?, ?)",
                (guild.id, interaction.user.id, ticket_chan.id, dept, now_utc())
            )
            db.commit()
            db.close()

            embed = discord.Embed(
                title=f"🎫 تذكرة جديدة - قسم {dept.upper()}",
                description=f"أهلاً بك {interaction.user.mention}، يرجى كتابة تفاصيل طلبك وسيتم الرد عليك من قبل الفريق المختص في أقرب وقت.",
                color=discord.Color.blue()
            )
            await ticket_chan.send(content=interaction.user.mention, embed=embed, view=TicketControlView())
            await interaction.response.send_message(f"✅ تم فتح تذكرتك بنجاح: {ticket_chan.mention}", ephemeral=True)
# =========================================================
# SLASH COMMANDS: ADMIN & LOG SETUP
# =========================================================

@bot.tree.command(name="setup_tickets", description="إرسال لوحة فتح التذاكر في القناة الحالية")
@app_commands.checks.has_permissions(administrator=True)
async def setup_tickets(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎫 مركز الدعم الفني والخدمات | Mystery Town",
        description=(
            "أهلاً بك في نظام التذاكر الخاص بالسيرفر.\n\n"
            "يرجى اختيار القسم المناسب لموضوعك من القائمة أدناه لفتح تذكرة وسيتم التعامل مع طلبك بسرعة."
        ),
        color=discord.Color.blue()
    )
    embed.set_footer(text="Mystery Town Roleplay • جميع الحقوق محفوظة")
    await interaction.channel.send(embed=embed, view=TicketLaunchView())
    await interaction.response.send_message("✅ تم إرسال لوحة التذاكر بنجاح.", ephemeral=True)


@bot.tree.command(name="set_log", description="تحديد قناة لسجل معين من سجلات البوت")
@app_commands.describe(
    log_type="نوع السجل المراد ضبطه",
    channel="القناة المخصصة لإرسال السجلات"
)
@app_commands.choices(log_type=[
    app_commands.Choice(name="سجل الأمان والحماية (Security Log)", value="security_log_channel_id"),
    app_commands.Choice(name="سجل حذف الرسائل (Delete Log)", value="delete_log_channel_id"),
    app_commands.Choice(name="سجل تعديل الرسائل (Edit Log)", value="edit_log_channel_id"),
    app_commands.Choice(name="سجل الأعضاء (Member Join/Leave Log)", value="member_log_channel_id"),
    app_commands.Choice(name="سجل الرقابة والإشراف (Mod Log)", value="mod_log_channel_id"),
    app_commands.Choice(name="سجل الرتب (Role Log)", value="role_log_channel_id"),
    app_commands.Choice(name="سجل القنوات (Channel Log)", value="channel_log_channel_id")
])
@app_commands.checks.has_permissions(administrator=True)
async def set_log(interaction: discord.Interaction, log_type: str, channel: discord.TextChannel):
    set_log_channel(interaction.guild_id, log_type, channel.id)
    await interaction.response.send_message(f"✅ تم ضبط قناة السجل لـ **{log_type}** على القناة: {channel.mention}", ephemeral=True)


@bot.tree.command(name="set_ai_channel", description="تفعيل أو تعطيل الذكاء الاصطناعي وتحديد القناة الخاصة به")
@app_commands.describe(enabled="تفعيل أو تعطيل الميزة", channel="القناة المخصصة للذكاء الاصطناعي")
@app_commands.checks.has_permissions(administrator=True)
async def set_ai_channel(interaction: discord.Interaction, enabled: bool, channel: discord.TextChannel):
    set_ai_settings(interaction.guild_id, enabled=enabled, channel_id=channel.id)
    status_str = "تفعيل" if enabled else "تعطيل"
    await interaction.response.send_message(f"✅ تم **{status_str}** الذكاء الاصطناعي وتحديد القناة: {channel.mention}", ephemeral=True)


# =========================================================
# SLASH COMMANDS: RULES SYSTEM
# =========================================================

@bot.tree.command(name="add_rule", description="إضافة قانون جديد إلى القوانين")
@app_commands.describe(rule_id="رقم القانون", name="عنوان القانون", content="محتوى التفاصيل")
@app_commands.checks.has_permissions(administrator=True)
async def add_rule(interaction: discord.Interaction, rule_id: int, name: str, content: str):
    db = db_connect()
    cursor = db.cursor()
    cursor.execute(
        """
        INSERT INTO rules (guild_id, rule_id, name, content, created_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(guild_id, rule_id) DO UPDATE SET name=excluded.name, content=excluded.content
        """,
        (interaction.guild_id, rule_id, name, content, now_utc())
    )
    db.commit()
    db.close()
    await interaction.response.send_message(f"✅ تم إضافة/تحديث القانون رقم **#{rule_id}** بنجاح.", ephemeral=True)


@bot.tree.command(name="show_rules", description="عرض جميع قوانين السيرفر المسجلة")
async def show_rules(interaction: discord.Interaction):
    db = db_connect()
    cursor = db.cursor()
    cursor.execute("SELECT rule_id, name, content FROM rules WHERE guild_id = ? ORDER BY rule_id ASC", (interaction.guild_id,))
    rows = cursor.fetchall()
    db.close()

    if not rows:
        await interaction.response.send_message("❌ لا توجد قوانين مسجلة في هذا السيرفر حالياً.", ephemeral=True)
        return

    embed = discord.Embed(
        title="📜 قوانين السيرفر الرسمية | Mystery Town",
        color=discord.Color.gold(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )

    for r_id, r_name, r_content in rows:
        embed.add_field(name=f"القانون #{r_id}: {r_name}", value=r_content, inline=False)

    await interaction.response.send_message(embed=embed)


# =========================================================
# SLASH COMMANDS: POLICE & CRIMINAL RECORDS
# =========================================================

@bot.tree.command(name="add_record", description="إضافة سابقة جنائية لمواطن (خاص بالشرطة)")
@app_commands.describe(citizen="المواطن المستهدف", crime="الجريمة المرتكبة", fine="الغرامة المالية", jail_time="مدة السجن")
async def add_record(interaction: discord.Interaction, citizen: discord.Member, crime: str, fine: int = 0, jail_time: str = "0"):
    db = db_connect()
    cursor = db.cursor()
    cursor.execute(
        """
        INSERT INTO criminal_records (guild_id, citizen_id, officer_id, crime, fine, jail_time, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (interaction.guild_id, citizen.id, interaction.user.id, crime, fine, jail_time, now_utc())
    )
    db.commit()
    db.close()

    embed = discord.Embed(
        title="🚨 تسجيل سابقة جنائية جديدة",
        color=discord.Color.dark_red(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    embed.add_field(name="المواطن:", value=citizen.mention, inline=True)
    embed.add_field(name="الضابط:", value=interaction.user.mention, inline=True)
    embed.add_field(name="الجريمة:", value=crime, inline=False)
    embed.add_field(name="الغرامة:", value=f"${fine:,}", inline=True)
    embed.add_field(name="مدة السجن:", value=jail_time, inline=True)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="check_records", description="الاستعلام عن السجلات الجنائية لمواطن")
@app_commands.describe(citizen="المواطن المراد البحث عنه")
async def check_records(interaction: discord.Interaction, citizen: discord.Member):
    db = db_connect()
    cursor = db.cursor()
    cursor.execute(
        "SELECT id, officer_id, crime, fine, jail_time, created_at FROM criminal_records WHERE guild_id = ? AND citizen_id = ? ORDER BY id DESC",
        (interaction.guild_id, citizen.id)
    )
    rows = cursor.fetchall()
    db.close()

    if not rows:
        await interaction.response.send_message(f"✅ المواطن {citizen.mention} لا يملك أي سوابق جنائية مسجلة.", ephemeral=True)
        return

    embed = discord.Embed(
        title=f"📋 السجل الجنائي للمواطن: {citizen.display_name}",
        color=discord.Color.orange()
    )

    for r_id, off_id, crime, fine, jail, created in rows[:10]:
        embed.add_field(
            name=f"قضية #{r_id} - {created[:10]}",
            value=f"**الجريمة:** {crime}\n**الغرامة:** ${fine:,}\n**السجن:** {jail}\n**المحرر:** <@{off_id}>",
            inline=False
        )

    await interaction.response.send_message(embed=embed)


# =========================================================
# SLASH COMMANDS: HEALTH & MEDICAL REPORTS
# =========================================================

@bot.tree.command(name="add_medical_report", description="إضافة تقرير طبي لمواطن (خاص بالصحة PHMC)")
@app_commands.describe(citizen="المواطن المرضي/المصاب", diagnosis="التشخيص الطبي", treatment="العلاج والوصفة")
async def add_medical_report(interaction: discord.Interaction, citizen: discord.Member, diagnosis: str, treatment: str):
    db = db_connect()
    cursor = db.cursor()
    cursor.execute(
        """
        INSERT INTO medical_reports (guild_id, citizen_id, medic_id, diagnosis, treatment, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (interaction.guild_id, citizen.id, interaction.user.id, diagnosis, treatment, now_utc())
    )
    db.commit()
    db.close()

    embed = discord.Embed(
        title="🚑 تقرير طبي جديد | PHMC",
        color=discord.Color.red(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    embed.add_field(name="المريض:", value=citizen.mention, inline=True)
    embed.add_field(name="الطبيب:", value=interaction.user.mention, inline=True)
    embed.add_field(name="التشخيص:", value=diagnosis, inline=False)
    embed.add_field(name="العلاج:", value=treatment, inline=False)

    await interaction.response.send_message(embed=embed)


# =========================================================
# SLASH COMMANDS: JUSTICE & DEEDS / WARRANTS
# =========================================================

@bot.tree.command(name="issue_warrant", description="إصدار مذكرة اعتقال/تفتيش قضائية (وزارة العدل)")
@app_commands.describe(citizen="المستهدف بالمذكرة", warrant_type="نوع المذكرة (اعتقال/تفتيش)", reason="السبب والمسوغ القانوني")
async def issue_warrant(interaction: discord.Interaction, citizen: discord.Member, warrant_type: str, reason: str):
    db = db_connect()
    cursor = db.cursor()
    cursor.execute(
        """
        INSERT INTO warrants (guild_id, citizen_id, officer_id, warrant_type, reason, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (interaction.guild_id, citizen.id, interaction.user.id, warrant_type, reason, now_utc())
    )
    db.commit()
    db.close()

    embed = discord.Embed(
        title="⚖️ مذكرة قضائية رسمية | Ministry of Justice",
        color=discord.Color.purple(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    embed.add_field(name="المستهدف:", value=citizen.mention, inline=True)
    embed.add_field(name="نوع المذكرة:", value=warrant_type, inline=True)
    embed.add_field(name="القاضي/المسؤول:", value=interaction.user.mention, inline=False)
    embed.add_field(name="الأسباب والمسوغات:", value=reason, inline=False)

    await interaction.response.send_message(embed=embed)


# =========================================================
# ERROR HANDLING
# =========================================================

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("❌ ليس لديك الصلاحيات الكافية لاستخدام هذا الأمر.", ephemeral=True)
    else:
        logging.error(f"Command Error: {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message("⚠️ حدث خطأ أثناء تنفيذ الأمر.", ephemeral=True)


# =========================================================
# KEEPALIVE SERVER (FLASK)
# =========================================================
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive and running!"

def run_flask():
    # تشغيل سيرفر Flask على المنفذ 8080 أو المنفذ المحدد من البيئة
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    """دالة تشغيل السيرفر في Thread منفصل لضمان عدم توقف البوت"""
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()


# =========================================================
# BOT RUNNER WITH KEEPALIVE
# =========================================================

if __name__ == "__main__":
    # 1. تشغيل سيرفر الإبقاء حياً (Flask)
    keep_alive()
    
    # 2. قراءة التوكن من متغيرات البيئة
    TOKEN = os.getenv("DISCORD_TOKEN")
    
    if not TOKEN:
        logging.error("❌ لم يتم العثور على رمز DISCORD_TOKEN في متغيرات البيئة!")
    else:
        try:
            bot.run(TOKEN)
        except Exception as e:
            logging.error(f"❌ حدث خطأ أثناء تشغيل البوت: {e}")
