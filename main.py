import os
import sqlite3
import threading
import asyncio

from flask import Flask

import discord
from discord import app_commands
from discord.ext import commands


# =========================================================
# CONFIG
# =========================================================

TOKEN = os.getenv("DISCORD_TOKEN")
DB_FILE = "ticket_bot.db"

MAX_TICKETS = 25

if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN is missing from Environment Variables"
    )


# =========================================================
# FLASK - RENDER
# =========================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "MT Ticket Bot is Online!"


def run_flask():
    port = int(os.environ.get("PORT", 8080))

    app.run(
        host="0.0.0.0",
        port=port,
        use_reloader=False
    )


def keep_alive():
    thread = threading.Thread(
        target=run_flask,
        daemon=True
    )
    thread.start()


# =========================================================
# DATABASE
# =========================================================

def get_db():
    conn = sqlite3.connect(DB_FILE)

    conn.execute(
        "PRAGMA busy_timeout = 5000"
    )

    return conn


def init_database():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS ticket_setups (
            guild_id INTEGER NOT NULL,
            ticket_number INTEGER NOT NULL,
            ticket_name TEXT NOT NULL,
            category_id INTEGER NOT NULL,
            staff_role_id INTEGER NOT NULL,
            log_channel_id INTEGER NOT NULL,
            PRIMARY KEY (guild_id, ticket_number)
        )
    """)

    conn.commit()
    conn.close()


def save_ticket_setup(
    guild_id,
    ticket_number,
    ticket_name,
    category_id,
    staff_role_id,
    log_channel_id
):
    conn = get_db()

    conn.execute("""
        INSERT INTO ticket_setups (
            guild_id,
            ticket_number,
            ticket_name,
            category_id,
            staff_role_id,
            log_channel_id
        )
        VALUES (?, ?, ?, ?, ?, ?)

        ON CONFLICT(guild_id, ticket_number)
        DO UPDATE SET
            ticket_name = excluded.ticket_name,
            category_id = excluded.category_id,
            staff_role_id = excluded.staff_role_id,
            log_channel_id = excluded.log_channel_id
    """, (
        guild_id,
        ticket_number,
        ticket_name,
        category_id,
        staff_role_id,
        log_channel_id
    ))

    conn.commit()
    conn.close()


def get_ticket_setup(
    guild_id,
    ticket_number
):
    conn = get_db()

    row = conn.execute("""
        SELECT
            ticket_number,
            ticket_name,
            category_id,
            staff_role_id,
            log_channel_id

        FROM ticket_setups

        WHERE
            guild_id = ?
            AND ticket_number = ?
    """, (
        guild_id,
        ticket_number
    )).fetchone()

    conn.close()

    return row


def get_all_ticket_setups(guild_id):
    conn = get_db()

    rows = conn.execute("""
        SELECT
            ticket_number,
            ticket_name,
            category_id,
            staff_role_id,
            log_channel_id

        FROM ticket_setups

        WHERE guild_id = ?

        ORDER BY ticket_number ASC
    """, (
        guild_id,
    )).fetchall()

    conn.close()

    return rows


# =========================================================
# BOT
# =========================================================

intents = discord.Intents.default()

intents.guilds = True
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# =========================================================
# HELPER
# =========================================================

async def get_channel_safe(
    channel_id
):
    try:
        return await bot.fetch_channel(
            channel_id
        )
    except Exception:
        return None


async def send_log(
    guild,
    log_channel_id,
    embed
):
    channel = guild.get_channel(
        log_channel_id
    )

    if channel is None:
        channel = await get_channel_safe(
            log_channel_id
        )

    if channel is None:
        return

    try:
        await channel.send(
            embed=embed
        )
    except Exception as error:
        print(
            f"Log error: {repr(error)}"
        )


# =========================================================
# TICKET NAME MODAL
# =========================================================

class TicketNameModal(
    discord.ui.Modal
):

    def __init__(
        self,
        ticket_number
    ):
        super().__init__(
            title=f"إعداد التذكرة {ticket_number}"
        )

        self.ticket_number = ticket_number

        self.ticket_name = discord.ui.TextInput(
            label="اسم التذكرة",
            placeholder="مثال: دعم فني",
            required=True,
            min_length=1,
            max_length=80
        )

        self.add_item(
            self.ticket_name
        )

    async def on_submit(
        self,
        interaction
    ):

        name = self.ticket_name.value.strip()

        await interaction.response.send_message(
            embed=discord.Embed(
                title="⚙️ إعداد التذكرة",
                description=(
                    f"🎫 **رقم التذكرة:** "
                    f"`{self.ticket_number}`\n\n"
                    f"📝 **اسم التذكرة:** "
                    f"`{name}`\n\n"
                    "اختر الآن من القوائم بالأسفل:\n"
                    "📁 التصنيف\n"
                    "🛡️ رتبة الستاف\n"
                    "📋 روم اللوق"
                ),
                color=discord.Color.blue()
            ),
            view=TicketConfigurationView(
                self.ticket_number,
                name
            ),
            ephemeral=True
        )


# =========================================================
# CATEGORY SELECT
# =========================================================

class CategorySelect(
    discord.ui.ChannelSelect
):

    def __init__(
        self
    ):
        super().__init__(
            placeholder="📁 اختر تصنيف التذاكر",
            channel_types=[
                discord.ChannelType.category
            ],
            min_values=1,
            max_values=1
        )


# =========================================================
# ROLE SELECT
# =========================================================

class StaffRoleSelect(
    discord.ui.RoleSelect
):

    def __init__(
        self
    ):
        super().__init__(
            placeholder="🛡️ اختر رتبة الستاف",
            min_values=1,
            max_values=1
        )


# =========================================================
# LOG CHANNEL SELECT
# =========================================================

class LogChannelSelect(
    discord.ui.ChannelSelect
):

    def __init__(
        self
    ):
        super().__init__(
            placeholder="📋 اختر روم اللوق",
            channel_types=[
                discord.ChannelType.text
            ],
            min_values=1,
            max_values=1
        )


# =========================================================
# SAVE TICKET BUTTON
# =========================================================

class SaveTicketButton(
    discord.ui.Button
):

    def __init__(
        self
    ):
        super().__init__(
            label="حفظ إعداد التذكرة",
            style=discord.ButtonStyle.success,
            emoji="💾"
        )

    async def callback(
        self,
        interaction
    ):

        view = self.view

        if not view.category:
            await interaction.response.send_message(
                "❌ اختر تصنيف التذكرة أولًا.",
                ephemeral=True
            )
            return

        if not view.staff_role:
            await interaction.response.send_message(
                "❌ اختر رتبة الستاف أولًا.",
                ephemeral=True
            )
            return

        if not view.log_channel:
            await interaction.response.send_message(
                "❌ اختر روم اللوق أولًا.",
                ephemeral=True
            )
            return

        save_ticket_setup(
            interaction.guild.id,
            view.ticket_number,
            view.ticket_name,
            view.category.id,
            view.staff_role.id,
            view.log_channel.id
        )

        embed = discord.Embed(
            title="✅ تم حفظ التذكرة",
            color=discord.Color.green()
        )

        embed.add_field(
            name="🎫 رقم التذكرة",
            value=str(view.ticket_number),
            inline=True
        )

        embed.add_field(
            name="📝 الاسم",
            value=view.ticket_name,
            inline=True
        )

        embed.add_field(
            name="📁 التصنيف",
            value=view.category.mention,
            inline=True
        )

        embed.add_field(
            name="🛡️ الستاف",
            value=view.staff_role.mention,
            inline=True
        )

        embed.add_field(
            name="📋 اللوق",
            value=view.log_channel.mention,
            inline=True
        )

        await interaction.response.edit_message(
            embed=embed,
            view=None
        )


# =========================================================
# CONFIGURATION VIEW
# =========================================================

class TicketConfigurationView(
    discord.ui.View
):

    def __init__(
        self,
        ticket_number,
        ticket_name
    ):
        super().__init__(
            timeout=300
        )

        self.ticket_number = ticket_number
        self.ticket_name = ticket_name

        self.category = None
        self.staff_role = None
        self.log_channel = None

        self.category_select = CategorySelect()
        self.staff_select = StaffRoleSelect()
        self.log_select = LogChannelSelect()

        self.add_item(
            self.category_select
        )

        self.add_item(
            self.staff_select
        )

        self.add_item(
            self.log_select
        )

        self.add_item(
            SaveTicketButton()
        )

    async def interaction_check(
        self,
        interaction
    ):

        return True


# =========================================================
# SELECT CALLBACKS
# =========================================================

async def category_callback(
    interaction
):

    view = interaction.message.components


# =========================================================
# PATCH SELECT CALLBACKS
# =========================================================

old_category_init = CategorySelect.__init__


def category_init(self):
    old_category_init(self)

    async def callback(interaction):
        self.view.category = self.values[0]

        await interaction.response.send_message(
            f"✅ تم اختيار التصنيف: "
            f"{self.values[0].mention}",
            ephemeral=True
        )

    self.callback = callback


CategorySelect.__init__ = category_init


old_role_init = StaffRoleSelect.__init__


def role_init(self):
    old_role_init(self)

    async def callback(interaction):
        self.view.staff_role = self.values[0]

        await interaction.response.send_message(
            f"✅ تم اختيار الرتبة: "
            f"{self.values[0].mention}",
            ephemeral=True
        )

    self.callback = callback


StaffRoleSelect.__init__ = role_init


old_log_init = LogChannelSelect.__init__


def log_init(self):
    old_log_init(self)

    async def callback(interaction):
        self.view.log_channel = self.values[0]

        await interaction.response.send_message(
            f"✅ تم اختيار اللوق: "
            f"{self.values[0].mention}",
            ephemeral=True
        )

    self.callback = callback


LogChannelSelect.__init__ = log_init


# =========================================================
# TICKET NUMBER SELECT
# =========================================================

class TicketNumberSelect(
    discord.ui.Select
):

    def __init__(
        self
    ):

        options = []

        for number in range(
            1,
            MAX_TICKETS + 1
        ):

            options.append(
                discord.SelectOption(
                    label=f"التذكرة رقم {number}",
                    value=str(number),
                    emoji="🎫"
                )
            )

        super().__init__(
            placeholder="🎫 اختر رقم التذكرة",
            options=options,
            min_values=1,
            max_values=1
        )

    async def callback(
        self,
        interaction
    ):

        number = int(
            self.values[0]
        )

        await interaction.response.send_modal(
            TicketNameModal(number)
        )


class TicketSetupView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=300
        )

        self.add_item(
            TicketNumberSelect()
        )


# =========================================================
# PANEL MODAL
# =========================================================

class TicketPanelModal(
    discord.ui.Modal
):

    def __init__(
        self
    ):

        super().__init__(
            title="إرسال بانل التذكرة"
        )

        self.title_input = discord.ui.TextInput(
            label="عنوان الإمبد",
            placeholder="مثال: تذاكر الدعم",
            required=True,
            max_length=256
        )

        self.description_input = discord.ui.TextInput(
            label="وصف الإمبد",
            placeholder="اكتب وصف بانل التذاكر",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=4000
        )

        self.image_input = discord.ui.TextInput(
            label="رابط الصورة - اختياري",
            placeholder="https://...",
            required=False,
            max_length=500
        )

        self.footer_input = discord.ui.TextInput(
            label="النص السفلي - اختياري",
            placeholder="MT Ticket System",
            required=False,
            max_length=256
        )

        self.add_item(
            self.title_input
        )

        self.add_item(
            self.description_input
        )

        self.add_item(
            self.image_input
        )

        self.add_item(
            self.footer_input
        )

    async def on_submit(
        self,
        interaction
    ):

        embed = discord.Embed(
            title=self.title_input.value,
            description=self.description_input.value,
            color=discord.Color.blue()
        )

        if self.image_input.value.strip():

            embed.set_image(
                url=self.image_input.value.strip()
            )

        if self.footer_input.value.strip():

            embed.set_footer(
                text=self.footer_input.value.strip()
            )

        if interaction.guild.icon:

            embed.set_thumbnail(
                url=interaction.guild.icon.url
            )

        await interaction.channel.send(
            embed=embed,
            view=TicketOpenView()
        )

        await interaction.response.send_message(
            "✅ تم إرسال بانل التذكرة.",
            ephemeral=True
        )


# =========================================================
# PANEL BUTTON
# =========================================================

class TicketPanelButton(
    discord.ui.Button
):

    def __init__(self):

        super().__init__(
            label="بانل تذكرة",
            style=discord.ButtonStyle.primary,
            emoji="🎫"
        )

    async def callback(
        self,
        interaction
    ):

        await interaction.response.send_modal(
            TicketPanelModal()
        )


class TicketPanelView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=300
        )

        self.add_item(
            TicketPanelButton()
        )


# =========================================================
# OPEN TICKET BUTTON
# =========================================================

class OpenTicketButton(
    discord.ui.Button
):

    def __init__(
        self
    ):

        super().__init__(
            label="فتح تذكرة",
            style=discord.ButtonStyle.primary,
            emoji="🎫",
            custom_id="mt_open_ticket"
        )

    async def callback(
        self,
        interaction
    ):

        setups = get_all_ticket_setups(
            interaction.guild.id
        )

        if not setups:

            await interaction.response.send_message(
                "❌ لا توجد تذاكر مفعلة حاليًا.\n"
                "استخدم `/ticket_setup` أولًا.",
                ephemeral=True
            )

            return

        await interaction.response.send_message(
            "🎫 **اختر نوع التذكرة:**",
            view=TicketTypeView(
                interaction.guild.id
            ),
            ephemeral=True
        )


class TicketOpenView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=None
        )

        self.add_item(
            OpenTicketButton()
        )


# =========================================================
# TICKET TYPE SELECT
# =========================================================

class TicketTypeSelect(
    discord.ui.Select
):

    def __init__(
        self,
        guild_id
    ):

        setups = get_all_ticket_setups(
            guild_id
        )

        options = []

        for (
            number,
            name,
            category_id,
            staff_role_id,
            log_channel_id
        ) in setups:

            options.append(
                discord.SelectOption(
                    label=name[:100],
                    description=(
                        f"التذكرة رقم {number}"
                    ),
                    value=str(number),
                    emoji="🎫"
                )
            )

        if not options:

            options.append(
                discord.SelectOption(
                    label="لا توجد تذاكر",
                    value="none",
                    emoji="❌"
                )
            )

        super().__init__(
            placeholder="🎫 اختر نوع التذكرة",
            options=options,
            min_values=1,
            max_values=1
        )

    async def callback(
        self,
        interaction
    ):

        value = self.values[0]

        if value == "none":

            await interaction.response.send_message(
                "❌ لا توجد تذاكر مفعلة.",
                ephemeral=True
            )

            return

        ticket_number = int(value)

        setup = get_ticket_setup(
            interaction.guild.id,
            ticket_number
        )

        if setup is None:

            await interaction.response.send_message(
                "❌ إعداد التذكرة غير موجود.",
                ephemeral=True
            )

            return

        (
            number,
            ticket_name,
            category_id,
            staff_role_id,
            log_channel_id
        ) = setup

        category = interaction.guild.get_channel(
            category_id
        )

        role = interaction.guild.get_role(
            staff_role_id
        )

        log_channel = interaction.guild.get_channel(
            log_channel_id
        )

        if category is None:

            category = await get_channel_safe(
                category_id
            )

        if role is None:

            try:
                role = await interaction.guild.fetch_role(
                    staff_role_id
                )
            except Exception:
                role = None

        if category is None:

            await interaction.response.send_message(
                "❌ التصنيف غير موجود.",
                ephemeral=True
            )

            return

        if role is None:

            await interaction.response.send_message(
                "❌ رتبة الستاف غير موجودة.",
                ephemeral=True
            )

            return

        # =============================================
        # CHECK EXISTING TICKET
        # =============================================

        for channel in interaction.guild.text_channels:

            if channel.topic == (
                f"ticket_owner:{interaction.user.id}"
            ):

                await interaction.response.send_message(
                    f"❌ لديك تذكرة مفتوحة بالفعل: "
                    f"{channel.mention}",
                    ephemeral=True
                )

                return

        # =============================================
        # PERMISSIONS
        # =============================================

        overwrites = {

            interaction.guild.default_role:
                discord.PermissionOverwrite(
                    view_channel=False
                ),

            interaction.user:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True,
                    embed_links=True
                ),

            role:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True,
                    embed_links=True
                ),

            interaction.guild.me:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    manage_channels=True,
                    manage_messages=True,
                    read_message_history=True
                )
        }

        # =============================================
        # CHANNEL NAME
        # =============================================

        safe_name = (
            ticket_name
            .lower()
            .replace(" ", "-")
            .replace("/", "-")
            .replace("\\", "-")
        )

        safe_name = "".join(
            char
            for char in safe_name
            if char.isalnum() or char == "-"
        )

        safe_name = safe_name[:40]

        channel_name = (
            f"{safe_name}-{interaction.user.name.lower()}"
        )

        channel_name = "".join(
            char
            for char in channel_name
            if char.isalnum() or char == "-"
        )[:95]

        # =============================================
        # CREATE CHANNEL
        # =============================================

        try:

            channel = await interaction.guild.create_text_channel(
                name=channel_name,
                category=category,
                topic=(
                    f"ticket_owner:{interaction.user.id}"
                    f"|ticket_number:{ticket_number}"
                ),
                overwrites=overwrites,
                reason="MT Ticket System"
            )

        except Exception as error:

            print(
                f"Create ticket error: {repr(error)}"
            )

            await interaction.response.send_message(
                "❌ لم أستطع إنشاء التذكرة. "
                "تأكد أن البوت يملك Manage Channels.",
                ephemeral=True
            )

            return

        # =============================================
        # TICKET EMBED
        # =============================================

        embed = discord.Embed(
            title=f"🎫 {ticket_name}",
            description=(
                f"مرحبًا {interaction.user.mention}\n\n"
                "تم فتح تذكرتك بنجاح.\n"
                "يرجى كتابة طلبك وسيقوم فريق الدعم بمساعدتك."
            ),
            color=discord.Color.blue()
        )

        embed.add_field(
            name="👤 صاحب التذكرة",
            value=interaction.user.mention,
            inline=True
        )

        embed.add_field(
            name="🎫 النوع",
            value=ticket_name,
            inline=True
        )

        embed.add_field(
            name="🔢 الرقم",
            value=str(ticket_number),
            inline=True
        )

        embed.set_footer(
            text="MT Ticket System"
        )

        await channel.send(
            content=(
                f"{interaction.user.mention} "
                f"{role.mention}"
            ),
            embed=embed,
            view=CloseTicketView()
        )

        # =============================================
        # LOG
        # =============================================

        log_embed = discord.Embed(
            title="🎫 فتح تذكرة",
            color=discord.Color.green()
        )

        log_embed.add_field(
            name="👤 العضو",
            value=(
                f"{interaction.user.mention}\n"
                f"`{interaction.user.id}`"
            ),
            inline=False
        )

        log_embed.add_field(
            name="🎫 نوع التذكرة",
            value=ticket_name,
            inline=True
        )

        log_embed.add_field(
            name="🔢 الرقم",
            value=str(ticket_number),
            inline=True
        )

        log_embed.add_field(
            name="📁 التذكرة",
            value=channel.mention,
            inline=False
        )

        log_embed.set_footer(
            text="MT Ticket Logs"
        )

        await send_log(
            interaction.guild,
            log_channel_id,
            log_embed
        )

        await interaction.response.send_message(
            f"✅ تم إنشاء التذكرة: {channel.mention}",
            ephemeral=True
        )


class TicketTypeView(
    discord.ui.View
):

    def __init__(
        self,
        guild_id
    ):

        super().__init__(
            timeout=120
        )

        self.add_item(
            TicketTypeSelect(guild_id)
        )


# =========================================================
# CLOSE TICKET
# =========================================================

class CloseTicketButton(
    discord.ui.Button
):

    def __init__(self):

        super().__init__(
            label="إغلاق التذكرة",
            style=discord.ButtonStyle.danger,
            emoji="🔒",
            custom_id="mt_close_ticket"
        )

    async def callback(
        self,
        interaction
    ):

        channel = interaction.channel

        owner_id = None
        ticket_number = None

        if channel.topic:

            for part in channel.topic.split("|"):

                if part.startswith(
                    "ticket_owner:"
                ):

                    try:
                        owner_id = int(
                            part.split(":")[1]
                        )
                    except Exception:
                        pass

                if part.startswith(
                    "ticket_number:"
                ):

                    try:
                        ticket_number = int(
                            part.split(":")[1]
                        )
                    except Exception:
                        pass

        log_channel_id = None

        if ticket_number is not None:

            setup = get_ticket_setup(
                interaction.guild.id,
                ticket_number
            )

            if setup:

                log_channel_id = setup[4]

        await interaction.response.send_message(
            "🔒 سيتم إغلاق التذكرة خلال **5 ثوانٍ**."
        )

        # =============================================
        # CLOSE LOG
        # =============================================

        log_embed = discord.Embed(
            title="🔒 إغلاق تذكرة",
            color=discord.Color.red()
        )

        log_embed.add_field(
            name="👤 أغلق التذكرة",
            value=(
                f"{interaction.user.mention}\n"
                f"`{interaction.user.id}`"
            ),
            inline=False
        )

        if owner_id:

            owner = interaction.guild.get_member(
                owner_id
            )

            if owner:

                owner_text = owner.mention

            else:

                owner_text = f"`{owner_id}`"

            log_embed.add_field(
                name="👤 صاحب التذكرة",
                value=owner_text,
                inline=False
            )

        log_embed.add_field(
            name="📁 الروم",
            value=channel.name,
            inline=True
        )

        if ticket_number:

            log_embed.add_field(
                name="🔢 رقم التذكرة",
                value=str(ticket_number),
                inline=True
            )

        log_embed.set_footer(
            text="MT Ticket Logs"
        )

        if log_channel_id:

            await send_log(
                interaction.guild,
                log_channel_id,
                log_embed
            )

        await asyncio.sleep(5)

        try:

            await channel.delete(
                reason=(
                    f"Ticket closed by "
                    f"{interaction.user}"
                )
            )

        except discord.Forbidden:

            pass

        except Exception as error:

            print(
                f"Delete ticket error: {repr(error)}"
            )


class CloseTicketView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=None
        )

        self.add_item(
            CloseTicketButton()
        )


# =========================================================
# /ticket_setup
# =========================================================

@bot.tree.command(
    name="ticket_setup",
    description="إعداد تذاكر السيرفر"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def ticket_setup(
    interaction
):

    embed = discord.Embed(
        title="⚙️ إعداد التذاكر",
        description=(
            "اختر رقم التذكرة التي تريد إعدادها.\n\n"
            "بعد اختيار الرقم سيطلب منك اسم التذكرة، "
            "ثم تختار التصنيف والرتبة وروم اللوق من القوائم.\n\n"
            "🎫 الحد الأقصى: **25 تذكرة**"
        ),
        color=discord.Color.blue()
    )

    if interaction.guild.icon:

        embed.set_thumbnail(
            url=interaction.guild.icon.url
        )

    await interaction.response.send_message(
        embed=embed,
        view=TicketSetupView(),
        ephemeral=True
    )


# =========================================================
# /ticket_panel
# =========================================================

@bot.tree.command(
    name="ticket_panel",
    description="إرسال بانل فتح التذاكر"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def ticket_panel(
    interaction
):

    embed = discord.Embed(
        title=interaction.guild.name,
        description=(
            "اضغط على الزر بالأسفل "
            "لإعداد بانل التذكرة وإرساله."
        ),
        color=discord.Color.blue()
    )

    if interaction.guild.icon:

        embed.set_thumbnail(
            url=interaction.guild.icon.url
        )

    await interaction.response.send_message(
        embed=embed,
        view=TicketPanelView(),
        ephemeral=True
    )


# =========================================================
# ERRORS
# =========================================================

@ticket_setup.error
async def ticket_setup_error(
    interaction,
    error
):

    print(
        f"ticket_setup error: {repr(error)}"
    )

    if isinstance(
        error,
        app_commands.errors.MissingPermissions
    ):

        message = "❌ هذا الأمر للإدارة فقط."

    else:

        message = (
            "❌ حدث خطأ أثناء إعداد التذاكر.\n"
            "راجع Console في Render."
        )

    try:

        if interaction.response.is_done():

            await interaction.followup.send(
                message,
                ephemeral=True
            )

        else:

            await interaction.response.send_message(
                message,
                ephemeral=True
            )

    except Exception:
        pass


@ticket_panel.error
async def ticket_panel_error(
    interaction,
    error
):

    print(
        f"ticket_panel error: {repr(error)}"
    )

    if isinstance(
        error,
        app_commands.errors.MissingPermissions
    ):

        message = "❌ هذا الأمر للإدارة فقط."

    else:

        message = (
            "❌ حدث خطأ أثناء إرسال بانل التذاكر."
        )

    try:

        if interaction.response.is_done():

            await interaction.followup.send(
                message,
                ephemeral=True
            )

        else:

            await interaction.response.send_message(
                message,
                ephemeral=True
            )

    except Exception:
        pass


# =========================================================
# READY
# =========================================================

@bot.event
async def on_ready():

    print(
        f"✅ Logged in as {bot.user}"
    )

    try:

        synced = await bot.tree.sync()

        print(
            f"✅ Slash commands synced: {len(synced)}"
        )

    except Exception as error:

        print(
            f"❌ Sync error: {repr(error)}"
        )


# =========================================================
# START
# =========================================================

init_database()

keep_alive()

bot.run(TOKEN)
