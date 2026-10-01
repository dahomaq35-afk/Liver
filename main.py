import os
import sqlite3
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

# =========================================================
# CONFIG
# =========================================================

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError("❌ لم يتم العثور على DISCORD_TOKEN في Environment Variables")

DB_FILE = "ticket_bot.db"

intents = discord.Intents.default()
intents.guilds = True
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# =========================================================
# DATABASE
# =========================================================

def db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ticket_setups (
            guild_id INTEGER NOT NULL,
            ticket_number INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            staff_role_id INTEGER NOT NULL,
            PRIMARY KEY (guild_id, ticket_number)
        )
    """)
    conn.commit()
    return conn


# =========================================================
# HELPERS
# =========================================================

def get_setup(guild_id: int, ticket_number: int):
    conn = db()
    row = conn.execute(
        """
        SELECT category_id, staff_role_id
        FROM ticket_setups
        WHERE guild_id = ? AND ticket_number = ?
        """,
        (guild_id, ticket_number)
    ).fetchone()
    conn.close()
    return row


def save_setup(
    guild_id: int,
    ticket_number: int,
    category_id: int,
    staff_role_id: int
):
    conn = db()

    conn.execute(
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
            guild_id,
            ticket_number,
            category_id,
            staff_role_id
        )
    )

    conn.commit()
    conn.close()


# =========================================================
# TICKET SETUP MODAL
# =========================================================

class TicketSetupModal(discord.ui.Modal, title="إعداد التذكرة"):

    category_id = discord.ui.TextInput(
        label="معرف التصنيف Category ID",
        placeholder="مثال: 123456789012345678",
        required=True,
        max_length=30
    )

    staff_role_id = discord.ui.TextInput(
        label="معرف رتبة الدعم Staff Role ID",
        placeholder="مثال: 123456789012345678",
        required=True,
        max_length=30
    )

    def __init__(self, ticket_number: int):
        super().__init__()
        self.ticket_number = ticket_number

    async def on_submit(self, interaction: discord.Interaction):

        try:
            category_id = int(self.category_id.value)
            staff_role_id = int(self.staff_role_id.value)
        except ValueError:
            await interaction.response.send_message(
                "❌ تأكد أن معرف التصنيف والرتبة أرقام صحيحة.",
                ephemeral=True
            )
            return

        guild = interaction.guild

        category = guild.get_channel(category_id)
        role = guild.get_role(staff_role_id)

        if category is None:
            await interaction.response.send_message(
                "❌ لم أجد التصنيف بهذا الـ ID.",
                ephemeral=True
            )
            return

        if not isinstance(category, discord.CategoryChannel):
            await interaction.response.send_message(
                "❌ الـ ID الذي أدخلته ليس تصنيفًا.",
                ephemeral=True
            )
            return

        if role is None:
            await interaction.response.send_message(
                "❌ لم أجد الرتبة بهذا الـ ID.",
                ephemeral=True
            )
            return

        save_setup(
            guild.id,
            self.ticket_number,
            category.id,
            role.id
        )

        await interaction.response.send_message(
            f"✅ تم حفظ إعداد التذكرة رقم **{self.ticket_number}**.\n\n"
            f"📁 التصنيف: {category.mention}\n"
            f"🛡️ رتبة الدعم: {role.mention}",
            ephemeral=True
        )


# =========================================================
# TICKET NUMBER SELECT
# =========================================================

class TicketNumberSelect(discord.ui.Select):

    def __init__(self):
        options = []

        for i in range(1, 31):
            options.append(
                discord.SelectOption(
                    label=f"التذكرة رقم {i}",
                    value=str(i),
                    emoji="🎫"
                )
            )

        super().__init__(
            placeholder="اختر رقم التذكرة",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):

        ticket_number = int(self.values[0])

        await interaction.response.send_modal(
            TicketSetupModal(ticket_number)
        )


class TicketSetupView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(TicketNumberSelect())


# =========================================================
# TICKET PANEL MODAL
# =========================================================

class TicketPanelModal(discord.ui.Modal, title="إرسال بانل التذكرة"):

    title_text = discord.ui.TextInput(
        label="عنوان البانل",
        placeholder="مثال: فتح تذكرة",
        required=True,
        max_length=256
    )

    description = discord.ui.TextInput(
        label="وصف البانل",
        placeholder="اكتب الوصف الذي سيظهر في البانل",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=4000
    )

    image_url = discord.ui.TextInput(
        label="رابط الصورة (اختياري)",
        placeholder="https://...",
        required=False,
        max_length=500
    )

    footer = discord.ui.TextInput(
        label="النص السفلي (اختياري)",
        placeholder="مثال: MT Support",
        required=False,
        max_length=256
    )

    async def on_submit(self, interaction: discord.Interaction):

        embed = discord.Embed(
            title=self.title_text.value,
            description=self.description.value,
            color=discord.Color.blue()
        )

        if self.image_url.value.strip():
            embed.set_image(url=self.image_url.value.strip())

        if self.footer.value.strip():
            embed.set_footer(text=self.footer.value.strip())

        view = TicketOpenView()

        await interaction.channel.send(
            embed=embed,
            view=view
        )

        await interaction.response.send_message(
            "✅ تم إرسال بانل التذكرة.",
            ephemeral=True
        )


# =========================================================
# PANEL BUTTON
# =========================================================

class TicketPanelButton(discord.ui.Button):

    def __init__(self):
        super().__init__(
            label="بانل تذكرة",
            style=discord.ButtonStyle.primary,
            emoji="🎫"
        )

    async def callback(self, interaction: discord.Interaction):

        await interaction.response.send_modal(
            TicketPanelModal()
        )


class TicketPanelView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(TicketPanelButton())


# =========================================================
# OPEN TICKET
# =========================================================

class TicketTypeSelect(discord.ui.Select):

    def __init__(self, guild_id: int):
        self.guild_id = guild_id

        options = []

        for i in range(1, 31):

            setup = get_setup(guild_id, i)

            if setup:
                options.append(
                    discord.SelectOption(
                        label=f"التذكرة رقم {i}",
                        value=str(i),
                        emoji="🎫"
                    )
                )

        if not options:
            options.append(
                discord.SelectOption(
                    label="لا توجد تذاكر مفعلة",
                    value="none",
                    emoji="❌"
                )
            )

        super().__init__(
            placeholder="اختر نوع التذكرة",
            options=options,
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):

        if self.values[0] == "none":
            await interaction.response.send_message(
                "❌ لا توجد تذاكر مفعلة حاليًا.",
                ephemeral=True
            )
            return

        ticket_number = int(self.values[0])

        setup = get_setup(
            interaction.guild.id,
            ticket_number
        )

        if not setup:
            await interaction.response.send_message(
                "❌ إعداد التذكرة غير موجود.",
                ephemeral=True
            )
            return

        category_id, staff_role_id = setup

        category = interaction.guild.get_channel(category_id)
        staff_role = interaction.guild.get_role(staff_role_id)

        if category is None or staff_role is None:
            await interaction.response.send_message(
                "❌ إعداد التذكرة غير صحيح، راجع إعدادات التذكرة.",
                ephemeral=True
            )
            return

        existing = discord.utils.get(
            interaction.guild.text_channels,
            name=f"ticket-{interaction.user.id}"
        )

        if existing:
            await interaction.response.send_message(
                f"❌ لديك تذكرة مفتوحة بالفعل: {existing.mention}",
                ephemeral=True
            )
            return

        overwrites = {
            interaction.guild.default_role:
                discord.PermissionOverwrite(
                    view_channel=False
                ),

            interaction.user:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                ),

            staff_role:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                ),

            interaction.guild.me:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    manage_channels=True,
                    manage_messages=True
                )
        }

        channel = await guild_create_channel(
            guild=interaction.guild,
            category=category,
            name=f"ticket-{interaction.user.id}",
            overwrites=overwrites
        )

        embed = discord.Embed(
            title="🎫 تذكرة جديدة",
            description=(
                f"مرحبًا {interaction.user.mention}\n\n"
                "تم فتح تذكرتك بنجاح.\n"
                "يرجى الانتظار حتى يتولى فريق الدعم طلبك."
            ),
            color=discord.Color.blue()
        )

        close_view = CloseTicketView()

        await channel.send(
            content=f"{interaction.user.mention} {staff_role.mention}",
            embed=embed,
            view=close_view
        )

        await interaction.response.send_message(
            f"✅ تم إنشاء التذكرة: {channel.mention}",
            ephemeral=True
        )


async def guild_create_channel(
    guild,
    category,
    name,
    overwrites
):
    return await guild.create_text_channel(
        name=name,
        category=category,
        overwrites=overwrites
    )


class TicketOpenView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

        self.add_item(
            OpenTicketButton()
        )


class OpenTicketButton(discord.ui.Button):

    def __init__(self):
        super().__init__(
            label="فتح تذكرة",
            style=discord.ButtonStyle.primary,
            emoji="🎫",
            custom_id="mt_open_ticket"
        )

    async def callback(self, interaction: discord.Interaction):

        view = TicketTypeView(
            interaction.guild.id
        )

        await interaction.response.send_message(
            "🎫 **اختر نوع التذكرة من القائمة بالأسفل:**",
            view=view,
            ephemeral=True
        )


class TicketTypeView(discord.ui.View):

    def __init__(self, guild_id: int):
        super().__init__(timeout=120)
        self.add_item(
            TicketTypeSelect(guild_id)
        )


# =========================================================
# CLOSE TICKET
# =========================================================

class CloseTicketButton(discord.ui.Button):

    def __init__(self):
        super().__init__(
            label="إغلاق التذكرة",
            style=discord.ButtonStyle.danger,
            emoji="🔒",
            custom_id="mt_close_ticket"
        )

    async def callback(self, interaction: discord.Interaction):

        await interaction.response.send_message(
            "🔒 سيتم إغلاق التذكرة خلال 5 ثوانٍ."
        )

        await discord.utils.sleep_until(
            discord.utils.utcnow()
        )

        import asyncio
        await asyncio.sleep(5)

        try:
            await interaction.channel.delete(
                reason=f"Ticket closed by {interaction.user}"
            )
        except discord.Forbidden:
            pass


class CloseTicketView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(CloseTicketButton())


# =========================================================
# SLASH COMMANDS
# =========================================================

@bot.tree.command(
    name="ticket_setup",
    description="إعداد تذكرة من 1 إلى 30"
)
@app_commands.checks.has_permissions(administrator=True)
async def ticket_setup(
    interaction: discord.Interaction
):

    embed = discord.Embed(
        title="🎫 إعداد التذاكر",
        description=(
            "اختر رقم التذكرة التي تريد إعدادها.\n\n"
            "بعد الاختيار أدخل:\n"
            "📁 ID التصنيف\n"
            "🛡️ ID رتبة الدعم"
        ),
        color=discord.Color.blue()
    )

    await interaction.response.send_message(
        embed=embed,
        view=TicketSetupView(),
        ephemeral=True
    )


@bot.tree.command(
    name="ticket_panel",
    description="إرسال بانل فتح التذاكر"
)
@app_commands.checks.has_permissions(administrator=True)
async def ticket_panel(
    interaction: discord.Interaction
):

    embed = discord.Embed(
        title=interaction.guild.name,
        description=(
            "اضغط على الزر بالأسفل لإرسال بانل التذكرة."
        ),
        color=discord.Color.blue()
    )

    if interaction.guild.icon:
        embed.set_thumbnail(
            url=interaction.guild.icon.url
        )

    view = TicketPanelView()

    await interaction.response.send_message(
        embed=embed,
        view=view,
        ephemeral=True
    )


# =========================================================
# ERRORS
# =========================================================

@ticket_setup.error
async def ticket_setup_error(
    interaction: discord.Interaction,
    error
):

    if isinstance(
        error,
        app_commands.errors.MissingPermissions
    ):
        await interaction.response.send_message(
            "❌ هذا الأمر للإدارة فقط.",
            ephemeral=True
        )


@ticket_panel.error
async def ticket_panel_error(
    interaction: discord.Interaction,
    error
):

    if isinstance(
        error,
        app_commands.errors.MissingPermissions
    ):
        await interaction.response.send_message(
            "❌ هذا الأمر للإدارة فقط.",
            ephemeral=True
        )


# =========================================================
# BOT READY
# =========================================================

@bot.event
async def on_ready():

    db()

    try:
        synced = await bot.tree.sync()

        print(
            f"✅ Logged in as {bot.user}"
        )

        print(
            f"✅ Synced {len(synced)} slash commands"
        )

    except Exception as e:
        print(
            f"❌ Sync Error: {e}"
        )


# =========================================================
# RUN
# =========================================================

bot.run(TOKEN)
