import os
from threading import Thread
from flask import Flask

app = Flask('')


@app.route('/')
def home():
  return 'Bot is alive!'


def run():
  port = int(os.environ.get('PORT', 8080))
  app.run(host='0.0.0.0', port=port)


# تشغيل السيرفر الوهمي في الخلفية
Thread(target=run).start()

import os
import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import asyncio
from typing import Optional


# =========================================================
# CONFIG
# =========================================================

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError(
        "❌ DISCORD_TOKEN غير موجود في Environment Variables"
    )

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(
    command_prefix="-",
    intents=intents
)


# =========================================================
# DATABASE
# =========================================================

db = sqlite3.connect("mt_bot.db")
db.row_factory = sqlite3.Row

db.execute("""
CREATE TABLE IF NOT EXISTS ticket_setups (
    guild_id INTEGER NOT NULL,
    ticket_number INTEGER NOT NULL,
    category_id INTEGER NOT NULL,
    staff_role_id INTEGER NOT NULL,
    PRIMARY KEY (guild_id, ticket_number)
)
""")

db.execute("""
CREATE TABLE IF NOT EXISTS laws (
    guild_id INTEGER NOT NULL,
    law_number INTEGER NOT NULL,
    law_name TEXT NOT NULL,
    law_text TEXT NOT NULL,
    PRIMARY KEY (guild_id, law_number)
)
""")

db.commit()


# =========================================================
# HELPERS
# =========================================================

def get_ticket_setup(guild_id: int, number: int):
    return db.execute(
        """
        SELECT * FROM ticket_setups
        WHERE guild_id = ? AND ticket_number = ?
        """,
        (guild_id, number)
    ).fetchone()


def get_law(guild_id: int, number: int):
    return db.execute(
        """
        SELECT * FROM laws
        WHERE guild_id = ? AND law_number = ?
        """,
        (guild_id, number)
    ).fetchone()


def is_admin(interaction: discord.Interaction) -> bool:
    return (
        interaction.user.guild_permissions.administrator
        or interaction.user.guild_permissions.manage_guild
    )


async def deny(interaction: discord.Interaction):
    await interaction.response.send_message(
        "❌ هذا الأمر يحتاج صلاحية **إدارة السيرفر**.",
        ephemeral=True
    )


# =========================================================
# TICKET SYSTEM
# =========================================================

class TicketOpenView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="فتح تذكرة",
        emoji="🎫",
        style=discord.ButtonStyle.primary,
        custom_id="mt_ticket_open"
    )
    async def open_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        guild = interaction.guild

        if guild is None:
            return

        setups = db.execute(
            """
            SELECT * FROM ticket_setups
            WHERE guild_id = ?
            ORDER BY ticket_number ASC
            """,
            (guild.id,)
        ).fetchall()

        if not setups:
            await interaction.response.send_message(
                "❌ لم يتم تسطيب أي نوع من التذاكر.",
                ephemeral=True
            )
            return

        if len(setups) == 1:
            await create_ticket(
                interaction,
                setups[0]["ticket_number"]
            )
            return

        options = []

        for row in setups[:25]:
            options.append(
                discord.SelectOption(
                    label=f"{row['ticket_number']} - تذكرة",
                    value=str(row["ticket_number"]),
                    emoji="🎫"
                )
            )

        view = TicketTypeView(options)

        await interaction.response.send_message(
            "🎫 **اختر نوع التذكرة التي تريد فتحها:**",
            view=view,
            ephemeral=True
        )


class TicketTypeView(discord.ui.View):

    def __init__(self, options):
        super().__init__(timeout=120)

        select = discord.ui.Select(
            placeholder="اختر نوع التذكرة",
            options=options,
            custom_id="mt_ticket_type_select"
        )

        async def callback(interaction: discord.Interaction):

            number = int(select.values[0])

            await create_ticket(
                interaction,
                number
            )

        select.callback = callback
        self.add_item(select)


async def create_ticket(
    interaction: discord.Interaction,
    ticket_number: int
):

    guild = interaction.guild

    if guild is None:
        return

    setup = get_ticket_setup(
        guild.id,
        ticket_number
    )

    if not setup:
        await interaction.response.send_message(
            "❌ نوع التذكرة غير موجود.",
            ephemeral=True
        )
        return

    category = guild.get_channel(
        setup["category_id"]
    )

    role = guild.get_role(
        setup["staff_role_id"]
    )

    if not isinstance(category, discord.CategoryChannel):
        await interaction.response.send_message(
            "❌ الكاتيجوري المحددة للتذكرة غير موجودة.",
            ephemeral=True
        )
        return

    existing = discord.utils.get(
        category.channels,
        name=f"ticket-{interaction.user.id}"
    )

    if existing:
        await interaction.response.send_message(
            f"❌ لديك تذكرة مفتوحة بالفعل: {existing.mention}",
            ephemeral=True
        )
        return

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(
            view_channel=False
        ),

        interaction.user: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True
        ),

        guild.me: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            manage_channels=True,
            read_message_history=True
        )
    }

    if role:
        overwrites[role] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True
        )

    channel = await guild.create_text_channel(
        name=f"ticket-{interaction.user.id}",
        category=category,
        overwrites=overwrites,
        reason=f"Ticket #{ticket_number}"
    )

    embed = discord.Embed(
        title="🎫 تذكرة جديدة",
        description=(
            f"مرحبًا {interaction.user.mention}\n\n"
            "تم فتح تذكرتك بنجاح.\n"
            "سيقوم فريق الإدارة بالرد عليك قريبًا."
        ),
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="📁 نوع التذكرة",
        value=f"التذكرة رقم **{ticket_number}**",
        inline=False
    )

    embed.set_footer(
        text=f"فتحت بواسطة {interaction.user}"
    )

    await channel.send(
        content=(
            f"{interaction.user.mention}"
            + (f" {role.mention}" if role else "")
        ),
        embed=embed,
        view=TicketCloseView()
    )

    await interaction.response.send_message(
        f"✅ تم فتح التذكرة: {channel.mention}",
        ephemeral=True
    )


class TicketCloseView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

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

        if not (
            interaction.user.guild_permissions.manage_channels
            or interaction.user.guild_permissions.administrator
        ):
            await interaction.response.send_message(
                "❌ لا تملك صلاحية إغلاق التذكرة.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            "🔒 سيتم إغلاق التذكرة خلال 5 ثوانٍ.",
            ephemeral=False
        )

        await asyncio.sleep(5)

        try:
            await interaction.channel.delete(
                reason=f"Ticket closed by {interaction.user}"
            )
        except Exception:
            pass


# =========================================================
# /setup-ticket
# =========================================================

@bot.tree.command(
    name="setup-ticket",
    description="تسطيب نوع من أنواع التذاكر من 1 إلى 30"
)
@app_commands.describe(
    number="رقم التذكرة من 1 إلى 30",
    category="الكاتيجوري التي سيتم إنشاء التذاكر داخلها",
    staff_role="رتبة الدعم التي تستطيع رؤية التذاكر"
)
async def setup_ticket(
    interaction: discord.Interaction,
    number: app_commands.Range[int, 1, 30],
    category: discord.CategoryChannel,
    staff_role: discord.Role
):

    if not is_admin(interaction):
        await deny(interaction)
        return

    db.execute(
        """
        INSERT INTO ticket_setups
        (guild_id, ticket_number, category_id, staff_role_id)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(guild_id, ticket_number)
        DO UPDATE SET
            category_id = excluded.category_id,
            staff_role_id = excluded.staff_role_id
        """,
        (
            interaction.guild.id,
            number,
            category.id,
            staff_role.id
        )
    )

    db.commit()

    await interaction.response.send_message(
        "✅ **تم تسطيب التذكرة بنجاح**\n\n"
        f"🎫 رقم التذكرة: **{number}**\n"
        f"📁 الكاتيجوري: {category.mention}\n"
        f"👤 رتبة الدعم: {staff_role.mention}",
        ephemeral=True
    )


# =========================================================
# /ticket-panel
# =========================================================

@bot.tree.command(
    name="ticket-panel",
    description="إرسال بانل فتح التذاكر"
)
@app_commands.describe(
    channel="الروم الذي سيتم إرسال البانل فيه",
    title="عنوان البانل",
    description="وصف البانل"
)
async def ticket_panel(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    title: str = "🎫 نظام التذاكر",
    description: str = "اضغط على الزر بالأسفل لفتح تذكرة."
):

    if not is_admin(interaction):
        await deny(interaction)
        return

    setups = db.execute(
        """
        SELECT * FROM ticket_setups
        WHERE guild_id = ?
        ORDER BY ticket_number
        """,
        (interaction.guild.id,)
    ).fetchall()

    if not setups:
        await interaction.response.send_message(
            "❌ يجب تسطيب تذكرة واحدة على الأقل باستخدام `/setup-ticket`.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="🎫 فتح تذكرة",
        value="اضغط على الزر بالأسفل للبدء.",
        inline=False
    )

    embed.set_footer(
        text=f"{interaction.guild.name} • نظام التذاكر"
    )

    await channel.send(
        embed=embed,
        view=TicketOpenView()
    )

    await interaction.response.send_message(
        f"✅ تم إرسال بانل التذاكر في {channel.mention}",
        ephemeral=True
    )


# =========================================================
# LAWS SYSTEM
# =========================================================

@bot.tree.command(
    name="law",
    description="إنشاء أو تعديل قانون من 1 إلى 30"
)
@app_commands.describe(
    number="رقم القانون من 1 إلى 30",
    name="اسم القانون الذي سيظهر في المنيو",
    text="النص الذي سيظهر عند الضغط على القانون"
)
async def law(
    interaction: discord.Interaction,
    number: app_commands.Range[int, 1, 30],
    name: str,
    text: str
):

    if not is_admin(interaction):
        await deny(interaction)
        return

    db.execute(
        """
        INSERT INTO laws
        (guild_id, law_number, law_name, law_text)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(guild_id, law_number)
        DO UPDATE SET
            law_name = excluded.law_name,
            law_text = excluded.law_text
        """,
        (
            interaction.guild.id,
            number,
            name,
            text
        )
    )

    db.commit()

    await interaction.response.send_message(
        "✅ تم حفظ القانون.\n\n"
        f"🔢 الرقم: **{number}**\n"
        f"📌 الاسم: **{name}**\n"
        f"📖 النص:\n{text}",
        ephemeral=True
    )


# =========================================================
# LAW SELECT MENU
# =========================================================

class LawSelect(discord.ui.Select):

    def __init__(self, laws):

        options = []

        for row in laws:
            options.append(
                discord.SelectOption(
                    label=row["law_name"][:100],
                    description=f"القانون رقم {row['law_number']}",
                    value=str(row["law_number"]),
                    emoji="📜"
                )
            )

        super().__init__(
            placeholder="📜 اختر القانون",
            options=options,
            custom_id="mt_laws_select"
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        number = int(self.values[0])

        law_row = get_law(
            interaction.guild.id,
            number
        )

        if not law_row:
            await interaction.response.send_message(
                "❌ هذا القانون غير موجود.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"📜 {law_row['law_name']}",
            description=law_row["law_text"],
            color=discord.Color.blurple()
        )

        embed.set_footer(
            text=f"القانون رقم {number}"
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )


class LawsView(discord.ui.View):

    def __init__(self, laws):
        super().__init__(timeout=None)
        self.add_item(LawSelect(laws))


# =========================================================
# /send-laws
# =========================================================

@bot.tree.command(
    name="send-laws",
    description="إرسال منيو القوانين"
)
@app_commands.describe(
    channel="الروم الذي سيتم إرسال القوانين فيه",
    message="الرسالة التي ستظهر فوق المنيو",
    embed="هل تريد عرض الرسالة داخل Embed؟"
)
async def send_laws(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    message: str,
    embed: bool = True
):

    if not is_admin(interaction):
        await deny(interaction)
        return

    laws = db.execute(
        """
        SELECT * FROM laws
        WHERE guild_id = ?
        ORDER BY law_number
        """,
        (interaction.guild.id,)
    ).fetchall()

    if not laws:
        await interaction.response.send_message(
            "❌ لم تقم بإنشاء أي قانون حتى الآن.\n"
            "استخدم `/law` أولًا.",
            ephemeral=True
        )
        return

    first = laws[:15]
    second = laws[15:30]

    if embed:

        panel_embed = discord.Embed(
            title="📜 القوانين",
            description=message,
            color=discord.Color.blurple()
        )

        panel_embed.set_footer(
            text=f"{interaction.guild.name} • نظام القوانين"
        )

        await channel.send(
            embed=panel_embed
        )

    else:

        await channel.send(
            message
        )

    if first:

        view1 = LawsView(first)

        await channel.send(
            "📜 **القوانين 1 - 15**",
            view=view1
        )

    if second:

        view2 = LawsView(second)

        await channel.send(
            "📜 **القوانين 16 - 30**",
            view=view2
        )

    await interaction.response.send_message(
        f"✅ تم إرسال منيو القوانين في {channel.mention}",
        ephemeral=True
    )


# =========================================================
# /laws-list
# =========================================================

@bot.tree.command(
    name="laws-list",
    description="عرض القوانين التي تم إعدادها"
)
async def laws_list(
    interaction: discord.Interaction
):

    if not is_admin(interaction):
        await deny(interaction)
        return

    laws = db.execute(
        """
        SELECT * FROM laws
        WHERE guild_id = ?
        ORDER BY law_number
        """,
        (interaction.guild.id,)
    ).fetchall()

    if not laws:
        await interaction.response.send_message(
            "❌ لا توجد قوانين محفوظة.",
            ephemeral=True
        )
        return

    text = ""

    for row in laws:
        text += (
            f"**{row['law_number']}.** "
            f"{row['law_name']}\n"
        )

    embed = discord.Embed(
        title="📜 القوانين المحفوظة",
        description=text[:4000],
        color=discord.Color.blurple()
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# =========================================================
# /ticket-list
# =========================================================

@bot.tree.command(
    name="ticket-list",
    description="عرض أنواع التذاكر التي تم تسطيبها"
)
async def ticket_list(
    interaction: discord.Interaction
):

    if not is_admin(interaction):
        await deny(interaction)
        return

    setups = db.execute(
        """
        SELECT * FROM ticket_setups
        WHERE guild_id = ?
        ORDER BY ticket_number
        """,
        (interaction.guild.id,)
    ).fetchall()

    if not setups:
        await interaction.response.send_message(
            "❌ لا توجد تذاكر مسطبة.",
            ephemeral=True
        )
        return

    text = ""

    for row in setups:

        category = interaction.guild.get_channel(
            row["category_id"]
        )

        role = interaction.guild.get_role(
            row["staff_role_id"]
        )

        category_text = (
            category.mention
            if category
            else "غير موجودة"
        )

        role_text = (
            role.mention
            if role
            else "غير موجودة"
        )

        text += (
            f"🎫 **{row['ticket_number']}**\n"
            f"📁 {category_text}\n"
            f"👤 {role_text}\n\n"
        )

    embed = discord.Embed(
        title="🎫 أنواع التذاكر",
        description=text[:4000],
        color=discord.Color.blurple()
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# =========================================================
# READY
# =========================================================

@bot.event
async def on_ready():

    bot.add_view(TicketOpenView())
    bot.add_view(TicketCloseView())

    try:
        synced = await bot.tree.sync()

        print(
            f"Logged in as {bot.user}"
        )

        print(
            f"Synced {len(synced)} slash commands."
        )

    except Exception as e:
        print(
            f"Slash command sync error: {e}"
        )


# =========================================================
# RUN
# =========================================================

bot.run(TOKEN)
