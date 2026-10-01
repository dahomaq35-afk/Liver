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

if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN غير موجود في Environment Variables"
    )


# =========================================================
# FLASK / RENDER
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
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def init_database():

    conn = get_db()

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
    conn.close()


def save_ticket_setup(
    guild_id: int,
    ticket_number: int,
    category_id: int,
    staff_role_id: int
):

    conn = get_db()

    conn.execute(
        """
        INSERT INTO ticket_setups
        (
            guild_id,
            ticket_number,
            category_id,
            staff_role_id
        )
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


def get_ticket_setup(
    guild_id: int,
    ticket_number: int
):

    conn = get_db()

    row = conn.execute(
        """
        SELECT category_id, staff_role_id
        FROM ticket_setups
        WHERE guild_id = ?
        AND ticket_number = ?
        """,
        (
            guild_id,
            ticket_number
        )
    ).fetchone()

    conn.close()

    return row


def get_all_ticket_setups(
    guild_id: int
):

    conn = get_db()

    rows = conn.execute(
        """
        SELECT ticket_number, category_id, staff_role_id
        FROM ticket_setups
        WHERE guild_id = ?
        ORDER BY ticket_number ASC
        """,
        (guild_id,)
    ).fetchall()

    conn.close()

    return rows


# =========================================================
# DISCORD BOT
# =========================================================

intents = discord.Intents.default()
intents.guilds = True
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# =========================================================
# GET CHANNEL / ROLE
# =========================================================

async def fetch_category(
    guild: discord.Guild,
    category_id: int
):

    channel = guild.get_channel(category_id)

    if channel is not None:
        return channel

    try:
        channel = await bot.fetch_channel(category_id)
        return channel
    except Exception:
        return None


async def fetch_role(
    guild: discord.Guild,
    role_id: int
):

    role = guild.get_role(role_id)

    if role is not None:
        return role

    try:
        return await guild.fetch_role(role_id)
    except Exception:
        return None


# =========================================================
# TICKET SETUP MODAL
# =========================================================

class TicketSetupModal(discord.ui.Modal):

    def __init__(
        self,
        ticket_number: int
    ):

        super().__init__(
            title=f"إعداد التذكرة {ticket_number}"
        )

        self.ticket_number = ticket_number

        self.category_input = discord.ui.TextInput(
            label="ID التصنيف",
            placeholder="ضع ID التصنيف هنا",
            required=True,
            min_length=1,
            max_length=30
        )

        self.role_input = discord.ui.TextInput(
            label="ID رتبة الدعم",
            placeholder="ضع ID الرتبة هنا",
            required=True,
            min_length=1,
            max_length=30
        )

        self.add_item(self.category_input)
        self.add_item(self.role_input)


    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        try:
            category_id = int(
                self.category_input.value.strip()
            )

            role_id = int(
                self.role_input.value.strip()
            )

        except ValueError:

            await interaction.response.send_message(
                "❌ الـ ID يجب أن يكون رقمًا فقط.",
                ephemeral=True
            )

            return


        category = await fetch_category(
            interaction.guild,
            category_id
        )

        if category is None:

            await interaction.response.send_message(
                "❌ لم أجد التصنيف بهذا الـ ID.\n"
                "تأكد أن الـ ID صحيح وأن البوت موجود في السيرفر.",
                ephemeral=True
            )

            return


        if not isinstance(
            category,
            discord.CategoryChannel
        ):

            await interaction.response.send_message(
                "❌ الـ ID الذي وضعته ليس تصنيفًا.",
                ephemeral=True
            )

            return


        role = await fetch_role(
            interaction.guild,
            role_id
        )

        if role is None:

            await interaction.response.send_message(
                "❌ لم أجد الرتبة بهذا الـ ID.\n"
                "تأكد أن الـ ID صحيح وأن الرتبة موجودة في السيرفر.",
                ephemeral=True
            )

            return


        save_ticket_setup(
            interaction.guild.id,
            self.ticket_number,
            category.id,
            role.id
        )


        await interaction.response.send_message(
            "✅ **تم حفظ إعداد التذكرة بنجاح**\n\n"
            f"🎫 رقم التذكرة: **{self.ticket_number}**\n"
            f"📁 التصنيف: {category.mention}\n"
            f"🛡️ رتبة الدعم: {role.mention}",
            ephemeral=True
        )


# =========================================================
# TICKET NUMBER MENU
# =========================================================

class TicketNumberSelect(
    discord.ui.Select
):

    def __init__(self):

        options = []

        for number in range(1, 31):

            options.append(
                discord.SelectOption(
                    label=f"التذكرة رقم {number}",
                    value=str(number),
                    emoji="🎫"
                )
            )

        super().__init__(
            placeholder="اختر رقم التذكرة",
            options=options,
            min_values=1,
            max_values=1
        )


    async def callback(
        self,
        interaction: discord.Interaction
    ):

        number = int(self.values[0])

        await interaction.response.send_modal(
            TicketSetupModal(number)
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

    def __init__(self):

        super().__init__(
            title="إرسال بانل التذكرة"
        )

        self.embed_title = discord.ui.TextInput(
            label="عنوان الإمبد",
            placeholder="مثال: تذاكر الدعم",
            required=True,
            max_length=256
        )

        self.embed_description = discord.ui.TextInput(
            label="وصف الإمبد",
            placeholder="اكتب وصف بانل التذاكر",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=4000
        )

        self.image = discord.ui.TextInput(
            label="رابط الصورة - اختياري",
            placeholder="https://...",
            required=False,
            max_length=500
        )

        self.footer = discord.ui.TextInput(
            label="النص السفلي - اختياري",
            placeholder="MT Ticket System",
            required=False,
            max_length=256
        )

        self.add_item(self.embed_title)
        self.add_item(self.embed_description)
        self.add_item(self.image)
        self.add_item(self.footer)


    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        embed = discord.Embed(
            title=self.embed_title.value,
            description=self.embed_description.value,
            color=discord.Color.blue()
        )


        if self.image.value.strip():

            embed.set_image(
                url=self.image.value.strip()
            )


        if self.footer.value.strip():

            embed.set_footer(
                text=self.footer.value.strip()
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
        interaction: discord.Interaction
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

    def __init__(self):

        super().__init__(
            label="فتح تذكرة",
            style=discord.ButtonStyle.primary,
            emoji="🎫",
            custom_id="mt_open_ticket"
        )


    async def callback(
        self,
        interaction: discord.Interaction
    ):

        setups = get_all_ticket_setups(
            interaction.guild.id
        )


        if not setups:

            await interaction.response.send_message(
                "❌ لا توجد تذاكر مفعلة حاليًا.\n"
                "استخدم `/ticket_setup` أولًا لإعداد التذاكر.",
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
# TICKET TYPE MENU
# =========================================================

class TicketTypeSelect(
    discord.ui.Select
):

    def __init__(
        self,
        guild_id: int
    ):

        self.guild_id = guild_id

        setups = get_all_ticket_setups(
            guild_id
        )

        options = []


        for ticket_number, category_id, role_id in setups:

            options.append(
                discord.SelectOption(
                    label=f"التذكرة رقم {ticket_number}",
                    description="اضغط لفتح هذه التذكرة",
                    value=str(ticket_number),
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


    async def callback(
        self,
        interaction: discord.Interaction
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


        category_id, role_id = setup


        category = await fetch_category(
            interaction.guild,
            category_id
        )

        role = await fetch_role(
            interaction.guild,
            role_id
        )


        if category is None:

            await interaction.response.send_message(
                "❌ التصنيف المرتبط بهذه التذكرة غير موجود.",
                ephemeral=True
            )

            return


        if not isinstance(
            category,
            discord.CategoryChannel
        ):

            await interaction.response.send_message(
                "❌ التصنيف المرتبط بهذه التذكرة غير صالح.",
                ephemeral=True
            )

            return


        if role is None:

            await interaction.response.send_message(
                "❌ رتبة الدعم المرتبطة بهذه التذكرة غير موجودة.",
                ephemeral=True
            )

            return


        # منع فتح تذكرتين لنفس الشخص
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

            role:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                ),

            interaction.guild.me:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    manage_channels=True,
                    manage_messages=True
                )
        }


        safe_name = (
            interaction.user.name
            .lower()
            .replace(" ", "-")
        )

        safe_name = safe_name[:20]


        channel = await interaction.guild.create_text_channel(
            name=f"ticket-{safe_name}",
            category=category,
            topic=f"ticket_owner:{interaction.user.id}",
            overwrites=overwrites,
            reason="MT Ticket System"
        )


        embed = discord.Embed(
            title="🎫 تذكرة جديدة",
            description=(
                f"مرحبًا {interaction.user.mention}\n\n"
                "تم فتح تذكرتك بنجاح.\n"
                "اكتب طلبك هنا وسيقوم فريق الدعم بمساعدتك."
            ),
            color=discord.Color.blue()
        )


        embed.add_field(
            name="نوع التذكرة",
            value=f"رقم {ticket_number}",
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


        await interaction.response.send_message(
            f"✅ تم إنشاء التذكرة: {channel.mention}",
            ephemeral=True
        )


class TicketTypeView(
    discord.ui.View
):

    def __init__(
        self,
        guild_id: int
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
        interaction: discord.Interaction
    ):

        await interaction.response.send_message(
            "🔒 سيتم إغلاق التذكرة خلال **5 ثوانٍ**."
        )


        await asyncio.sleep(5)


        try:

            await interaction.channel.delete(
                reason=(
                    f"Ticket closed by "
                    f"{interaction.user}"
                )
            )

        except discord.Forbidden:

            pass


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
# SLASH COMMAND: SETUP
# =========================================================

@bot.tree.command(
    name="ticket_setup",
    description="إعداد تذكرة من 1 إلى 30"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def ticket_setup(
    interaction: discord.Interaction
):

    embed = discord.Embed(
        title="🎫 إعداد التذاكر",
        description=(
            "اختر رقم التذكرة التي تريد إعدادها.\n\n"
            "بعد الاختيار سيظهر لك نموذج لإدخال:\n"
            "📁 ID التصنيف\n"
            "🛡️ ID رتبة الدعم\n\n"
            "يمكنك إعداد حتى **30 تذكرة**."
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
# SLASH COMMAND: PANEL
# =========================================================

@bot.tree.command(
    name="ticket_panel",
    description="إرسال بانل فتح التذاكر"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def ticket_panel(
    interaction: discord.Interaction
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

    else:

        print(
            f"ticket_setup error: {error}"
        )

        if not interaction.response.is_done():

            await interaction.response.send_message(
                "❌ حدث خطأ أثناء إعداد التذكرة.",
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

    else:

        print(
            f"ticket_panel error: {error}"
        )

        if not interaction.response.is_done():

            await interaction.response.send_message(
                "❌ حدث خطأ أثناء إرسال البانل.",
                ephemeral=True
            )


# =========================================================
# READY
# =========================================================

@bot.event
async def on_ready():

    init_database()


    # الأزرار الدائمة
    bot.add_view(
        TicketOpenView()
    )

    bot.add_view(
        CloseTicketView()
    )


    try:

        synced = await bot.tree.sync()

        print(
            "===================================="
        )

        print(
            f"✅ Bot: {bot.user}"
        )

        print(
            f"✅ Commands synced: {len(synced)}"
        )

        print(
            "✅ Flask is running"
        )

        print(
            "===================================="
        )

    except Exception as error:

        print(
            f"❌ Sync Error: {error}"
        )


# =========================================================
# START
# =========================================================

init_database()

keep_alive()

bot.run(TOKEN)
