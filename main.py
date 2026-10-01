import os
import re
import sqlite3
import asyncio
from threading import Thread

from flask import Flask

import discord
from discord import app_commands
from discord.ext import commands


# =========================================================
# CONFIG
# =========================================================

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing")

DB_FILE = "mt_ticket_system.db"
MAX_TICKETS = 25


# =========================================================
# FLASK - RENDER
# =========================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "MT Ticket System is Online!"


def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(
        host="0.0.0.0",
        port=port
    )


Thread(
    target=run_flask,
    daemon=True
).start()


# =========================================================
# DATABASE
# =========================================================

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
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


def save_ticket(
    guild_id,
    ticket_number,
    ticket_name,
    category_id,
    staff_role_id,
    log_channel_id
):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT OR REPLACE INTO ticket_setups (
            guild_id,
            ticket_number,
            ticket_name,
            category_id,
            staff_role_id,
            log_channel_id
        )
        VALUES (?, ?, ?, ?, ?, ?)
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


def get_ticket(guild_id, ticket_number):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM ticket_setups
        WHERE guild_id = ?
        AND ticket_number = ?
    """, (
        guild_id,
        ticket_number
    ))

    row = cur.fetchone()

    conn.close()

    return row


def get_all_tickets(guild_id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM ticket_setups
        WHERE guild_id = ?
        ORDER BY ticket_number ASC
    """, (
        guild_id,
    ))

    rows = cur.fetchall()

    conn.close()

    return rows


# =========================================================
# HELPERS
# =========================================================

def clean_channel_name(name):

    name = name.lower()

    name = re.sub(
        r"[^a-zA-Z0-9\u0600-\u06FF\s\-]",
        "",
        name
    )

    name = re.sub(
        r"\s+",
        "-",
        name
    )

    name = re.sub(
        r"-+",
        "-",
        name
    )

    name = name.strip("-")

    if not name:
        name = "ticket"

    return name[:70]


def find_open_ticket(guild, user_id):

    for channel in guild.text_channels:

        if not channel.topic:
            continue

        if f"ticket_owner:{user_id}" in channel.topic:
            return channel

    return None


# =========================================================
# BOT
# =========================================================

class MTBot(commands.Bot):

    async def setup_hook(self):

        init_database()

        self.add_view(
            TicketOpenPersistentView()
        )

        self.add_view(
            TicketClosePersistentView()
        )

        try:
            synced = await self.tree.sync()
            print(
                f"Synced {len(synced)} slash commands."
            )
        except Exception as e:
            print(
                "Slash sync error:",
                e
            )


intents = discord.Intents.default()
intents.guilds = True
intents.members = True

bot = MTBot(
    command_prefix="-",
    intents=intents
)


# =========================================================
# TICKET SETUP
# =========================================================

class TicketNumbersSelect(
    discord.ui.Select
):

    def __init__(self):

        options = []

        for number in range(
            1,
            MAX_TICKETS + 1
        ):

            options.append(
                discord.SelectOption(
                    label=f"تذكرة رقم {number}",
                    value=str(number),
                    emoji="🎫"
                )
            )

        super().__init__(
            placeholder="اختر أرقام التذاكر",
            min_values=1,
            max_values=MAX_TICKETS,
            options=options
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        numbers = sorted(
            int(x)
            for x in self.values
        )

        self.view.selected_numbers = numbers

        selected = "\n".join(
            f"🎫 رقم **{number}**"
            for number in numbers
        )

        await interaction.response.edit_message(
            content=(
                "## 🎫 إعداد التذاكر\n\n"
                "التذاكر المحددة:\n\n"
                f"{selected}\n\n"
                "اضغط **متابعة** للبدء."
            ),
            embed=None,
            view=self.view
        )


class StartTicketSetupButton(
    discord.ui.Button
):

    def __init__(self):

        super().__init__(
            label="متابعة",
            emoji="➡️",
            style=discord.ButtonStyle.primary
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        if not self.view.selected_numbers:

            await interaction.response.send_message(
                "❌ اختر تذكرة واحدة على الأقل.",
                ephemeral=True
            )
            return

        session = TicketSetupSession(
            interaction,
            self.view.selected_numbers
        )

        await show_ticket_name(
            interaction,
            session
        )


class CancelButton(
    discord.ui.Button
):

    def __init__(self):

        super().__init__(
            label="إلغاء",
            emoji="❌",
            style=discord.ButtonStyle.danger
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        await interaction.response.edit_message(
            content="❌ تم إلغاء الإعداد.",
            embed=None,
            view=None
        )


class TicketNumbersView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=600
        )

        self.selected_numbers = []

        self.add_item(
            TicketNumbersSelect()
        )

        self.add_item(
            StartTicketSetupButton()
        )

        self.add_item(
            CancelButton()
        )


class TicketSetupSession:

    def __init__(
        self,
        interaction,
        numbers
    ):

        self.interaction = interaction
        self.guild = interaction.guild
        self.numbers = numbers
        self.index = 0
        self.data = {}


# =========================================================
# TICKET NAME
# =========================================================

class TicketNameModal(
    discord.ui.Modal
):

    def __init__(
        self,
        session
    ):

        number = session.numbers[
            session.index
        ]

        super().__init__(
            title=f"اسم التذكرة رقم {number}"
        )

        self.session = session

        self.name_input = discord.ui.TextInput(
            label="اسم التذكرة",
            placeholder="مثال: الدعم الفني",
            required=True,
            max_length=80
        )

        self.add_item(
            self.name_input
        )

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        number = self.session.numbers[
            self.session.index
        ]

        self.session.data[number] = {
            "name": str(
                self.name_input.value
            ).strip()
        }

        await show_category(
            interaction,
            self.session
        )


async def show_ticket_name(
    interaction,
    session
):

    await interaction.response.send_modal(
        TicketNameModal(session)
    )


# =========================================================
# CATEGORY
# =========================================================

class CategorySelect(
    discord.ui.ChannelSelect
):

    def __init__(
        self,
        session
    ):

        self.session = session

        super().__init__(
            placeholder="اختر Category",
            channel_types=[
                discord.ChannelType.category
            ],
            min_values=1,
            max_values=1
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        number = self.session.numbers[
            self.session.index
        ]

        self.session.data[number][
            "category_id"
        ] = self.values[0].id

        await show_staff(
            interaction,
            self.session
        )


class CategoryView(
    discord.ui.View
):

    def __init__(
        self,
        session
    ):

        super().__init__(
            timeout=600
        )

        self.add_item(
            CategorySelect(session)
        )


async def show_category(
    interaction,
    session
):

    number = session.numbers[
        session.index
    ]

    data = session.data[number]

    embed = discord.Embed(
        title="📁 Category التذكرة",
        description=(
            f"**التذكرة:** رقم {number}\n"
            f"**الاسم:** {data['name']}\n\n"
            "اختر الـCategory التي سيتم "
            "إنشاء التذكرة بداخلها."
        ),
        color=discord.Color.blue()
    )

    await interaction.response.send_message(
        embed=embed,
        view=CategoryView(session),
        ephemeral=True
    )


# =========================================================
# STAFF ROLE
# =========================================================

class StaffRoleSelect(
    discord.ui.RoleSelect
):

    def __init__(
        self,
        session
    ):

        self.session = session

        super().__init__(
            placeholder="اختر Staff Role",
            min_values=1,
            max_values=1
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        number = self.session.numbers[
            self.session.index
        ]

        self.session.data[number][
            "staff_role_id"
        ] = self.values[0].id

        await show_log(
            interaction,
            self.session
        )


class StaffRoleView(
    discord.ui.View
):

    def __init__(
        self,
        session
    ):

        super().__init__(
            timeout=600
        )

        self.add_item(
            StaffRoleSelect(session)
        )


async def show_staff(
    interaction,
    session
):

    number = session.numbers[
        session.index
    ]

    data = session.data[number]

    embed = discord.Embed(
        title="👮 Staff Role",
        description=(
            f"**التذكرة:** رقم {number}\n"
            f"**الاسم:** {data['name']}\n\n"
            "اختر الرتبة التي سيكون لديها "
            "صلاحية مشاهدة التذكرة."
        ),
        color=discord.Color.blue()
    )

    await interaction.response.send_message(
        embed=embed,
        view=StaffRoleView(session),
        ephemeral=True
    )


# =========================================================
# LOG CHANNEL
# =========================================================

class LogChannelSelect(
    discord.ui.ChannelSelect
):

    def __init__(
        self,
        session
    ):

        self.session = session

        super().__init__(
            placeholder="اختر Log Channel",
            channel_types=[
                discord.ChannelType.text
            ],
            min_values=1,
            max_values=1
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        number = self.session.numbers[
            self.session.index
        ]

        self.session.data[number][
            "log_channel_id"
        ] = self.values[0].id

        await finish_ticket_setup(
            interaction,
            self.session
        )


class LogChannelView(
    discord.ui.View
):

    def __init__(
        self,
        session
    ):

        super().__init__(
            timeout=600
        )

        self.add_item(
            LogChannelSelect(session)
        )


async def show_log(
    interaction,
    session
):

    number = session.numbers[
        session.index
    ]

    data = session.data[number]

    embed = discord.Embed(
        title="📑 Log Channel",
        description=(
            f"**التذكرة:** رقم {number}\n"
            f"**الاسم:** {data['name']}\n\n"
            "اختر روم اللوق لفتح وإغلاق التذاكر."
        ),
        color=discord.Color.blue()
    )

    await interaction.response.send_message(
        embed=embed,
        view=LogChannelView(session),
        ephemeral=True
    )


async def finish_ticket_setup(
    interaction,
    session
):

    number = session.numbers[
        session.index
    ]

    data = session.data[number]

    save_ticket(
        interaction.guild.id,
        number,
        data["name"],
        data["category_id"],
        data["staff_role_id"],
        data["log_channel_id"]
    )

    session.index += 1

    if session.index < len(
        session.numbers
    ):

        next_number = session.numbers[
            session.index
        ]

        await interaction.response.send_message(
            (
                f"✅ تم حفظ التذكرة رقم **{number}**.\n\n"
                f"ننتقل الآن للتذكرة رقم "
                f"**{next_number}**."
            ),
            ephemeral=True
        )

        await asyncio.sleep(1)

        await show_ticket_name(
            interaction,
            session
        )

        return

    await interaction.response.send_message(
        (
            "## ✅ اكتمل إعداد التذاكر\n\n"
            + "\n".join(
                f"🎫 رقم **{n}** — "
                f"{session.data[n]['name']}"
                for n in session.numbers
            )
        ),
        ephemeral=True
    )


# =========================================================
# /ticket_setup
# =========================================================

@bot.tree.command(
    name="ticket_setup",
    description="إعداد أنواع التذاكر"
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
            "اختر أرقام التذاكر التي تريد إعدادها.\n\n"
            "يمكنك اختيار أكثر من رقم بنفس الوقت، "
            "مثال:\n\n"
            "🎫 رقم 2\n"
            "🎫 رقم 5\n"
            "🎫 رقم 7\n\n"
            "ثم سيتم إعداد كل تذكرة "
            "واحدة وراء الثانية."
        ),
        color=discord.Color.blue()
    )

    await interaction.response.send_message(
        embed=embed,
        view=TicketNumbersView(),
        ephemeral=True
    )


# =========================================================
# PANEL METHOD SELECT
# =========================================================

class PanelMethodSelect(
    discord.ui.Select
):

    def __init__(self):

        options = [
            discord.SelectOption(
                label="منيو",
                value="menu",
                description="فتح التذكرة عن طريق قائمة",
                emoji="📋"
            ),
            discord.SelectOption(
                label="أزرار",
                value="buttons",
                description="فتح التذكرة عن طريق أزرار",
                emoji="🔘"
            )
        ]

        super().__init__(
            placeholder="اختر طريقة فتح التذاكر",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        method = self.values[0]

        await interaction.response.send_modal(
            TicketPanelModal(method)
        )


class PanelMethodView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=300
        )

        self.add_item(
            PanelMethodSelect()
        )


# =========================================================
# PANEL MODAL
# =========================================================

class TicketPanelModal(
    discord.ui.Modal
):

    def __init__(
        self,
        method
    ):

        super().__init__(
            title="إعداد بانل التذاكر"
        )

        self.method = method

        self.embed_title = discord.ui.TextInput(
            label="عنوان الـ Embed",
            placeholder="نظام التذاكر",
            required=True,
            max_length=256
        )

        self.embed_description = discord.ui.TextInput(
            label="وصف الـ Embed",
            placeholder="اضغط على الزر أو اختر من المنيو لفتح تذكرة.",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=4000
        )

        self.embed_image = discord.ui.TextInput(
            label="رابط الصورة - اختياري",
            placeholder="https://...",
            required=False,
            max_length=1000
        )

        self.embed_footer = discord.ui.TextInput(
            label="Footer - اختياري",
            placeholder="MT Ticket System",
            required=False,
            max_length=2048
        )

        self.add_item(
            self.embed_title
        )

        self.add_item(
            self.embed_description
        )

        self.add_item(
            self.embed_image
        )

        self.add_item(
            self.embed_footer
        )

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        tickets = get_all_tickets(
            interaction.guild.id
        )

        if not tickets:

            await interaction.response.send_message(
                "❌ لم يتم إعداد أي تذكرة أولًا باستخدام `/ticket_setup`.",
                ephemeral=True
            )

            return

        embed = discord.Embed(
            title=str(
                self.embed_title.value
            ),
            description=str(
                self.embed_description.value
            ),
            color=discord.Color.blue()
        )

        image = str(
            self.embed_image.value
        ).strip()

        footer = str(
            self.embed_footer.value
        ).strip()

        if image:

            try:
                embed.set_image(
                    url=image
                )
            except Exception:
                pass

        if footer:

            embed.set_footer(
                text=footer
            )

        if self.method == "menu":

            view = TicketMenuPanelView(
                tickets
            )

        else:

            view = TicketButtonsPanelView(
                tickets
            )

        await interaction.channel.send(
            embed=embed,
            view=view
        )

        method_name = (
            "📋 منيو"
            if self.method == "menu"
            else "🔘 أزرار"
        )

        await interaction.response.send_message(
            f"✅ تم إرسال بانل التذاكر بطريقة **{method_name}**.",
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
    interaction: discord.Interaction
):

    guild = interaction.guild

    embed = discord.Embed(
        title=guild.name,
        description=(
            "اضغط على المنيو بالأسفل واختر "
            "طريقة فتح التذاكر."
        ),
        color=discord.Color.blue()
    )

    if guild.icon:

        embed.set_thumbnail(
            url=guild.icon.url
        )

    await interaction.response.send_message(
        embed=embed,
        view=PanelMethodView(),
        ephemeral=True
    )


# =========================================================
# MENU PANEL
# =========================================================

class TicketMenuSelect(
    discord.ui.Select
):

    def __init__(
        self,
        tickets
    ):

        options = []

        for ticket in tickets[:25]:

            options.append(
                discord.SelectOption(
                    label=ticket["ticket_name"][:100],
                    value=str(
                        ticket["ticket_number"]
                    ),
                    emoji="🎫",
                    description=(
                        f"فتح {ticket['ticket_name']}"
                    )[:100]
                )
            )

        super().__init__(
            placeholder="اختر نوع التذكرة",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="mt_ticket_menu"
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        number = int(
            self.values[0]
        )

        ticket = get_ticket(
            interaction.guild.id,
            number
        )

        if not ticket:

            await interaction.response.send_message(
                "❌ هذه التذكرة غير موجودة.",
                ephemeral=True
            )

            return

        await create_ticket(
            interaction,
            ticket
        )


class TicketMenuPanelView(
    discord.ui.View
):

    def __init__(
        self,
        tickets
    ):

        super().__init__(
            timeout=None
        )

        self.add_item(
            TicketMenuSelect(tickets)
        )


# =========================================================
# BUTTON PANEL
# =========================================================

class TicketOpenTypeButton(
    discord.ui.Button
):

    def __init__(
        self,
        ticket
    ):

        super().__init__(
            label=ticket["ticket_name"][:80],
            style=discord.ButtonStyle.primary,
            emoji="🎫",
            custom_id=(
                f"mt_ticket_button_"
                f"{ticket['ticket_number']}"
            )
        )

        self.ticket_number = ticket[
            "ticket_number"
        ]

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        ticket = get_ticket(
            interaction.guild.id,
            self.ticket_number
        )

        if not ticket:

            await interaction.response.send_message(
                "❌ هذه التذكرة غير موجودة.",
                ephemeral=True
            )

            return

        await create_ticket(
            interaction,
            ticket
        )


class TicketButtonsPanelView(
    discord.ui.View
):

    def __init__(
        self,
        tickets
    ):

        super().__init__(
            timeout=None
        )

        for ticket in tickets[:25]:

            self.add_item(
                TicketOpenTypeButton(
                    ticket
                )
            )


# =========================================================
# CREATE TICKET
# =========================================================

async def create_ticket(
    interaction,
    ticket
):

    guild = interaction.guild
    user = interaction.user

    existing = find_open_ticket(
        guild,
        user.id
    )

    if existing:

        await interaction.response.send_message(
            (
                "❌ لديك تذكرة مفتوحة بالفعل:\n"
                f"{existing.mention}"
            ),
            ephemeral=True
        )

        return

    category = guild.get_channel(
        ticket["category_id"]
    )

    staff_role = guild.get_role(
        ticket["staff_role_id"]
    )

    log_channel = guild.get_channel(
        ticket["log_channel_id"]
    )

    if not category:

        await interaction.response.send_message(
            "❌ الـCategory غير موجودة.",
            ephemeral=True
        )

        return

    if not staff_role:

        await interaction.response.send_message(
            "❌ Staff Role غير موجودة.",
            ephemeral=True
        )

        return

    channel_name = (
        f"{clean_channel_name(ticket['ticket_name'])}"
        f"-{clean_channel_name(user.name)}"
    )[:95]

    overwrites = {

        guild.default_role:
            discord.PermissionOverwrite(
                view_channel=False
            ),

        user:
            discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True
            ),

        staff_role:
            discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True
            ),

        guild.me:
            discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True,
                manage_messages=True
            )
    }

    try:

        channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            topic=(
                f"ticket_owner:{user.id}|"
                f"ticket_number:{ticket['ticket_number']}"
            ),
            overwrites=overwrites,
            reason="MT Ticket System"
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ البوت لا يملك صلاحية إنشاء الرومات.",
            ephemeral=True
        )

        return

    except Exception as e:

        print(
            "Create ticket error:",
            e
        )

        await interaction.response.send_message(
            "❌ حدث خطأ أثناء إنشاء التذكرة.",
            ephemeral=True
        )

        return

    embed = discord.Embed(
        title=f"🎫 {ticket['ticket_name']}",
        description=(
            f"مرحبًا {user.mention}\n\n"
            "تم فتح التذكرة بنجاح.\n"
            "يرجى كتابة طلبك وانتظار فريق الدعم."
        ),
        color=discord.Color.blue()
    )

    embed.add_field(
        name="👤 صاحب التذكرة",
        value=user.mention,
        inline=True
    )

    embed.add_field(
        name="🎫 رقم التذكرة",
        value=str(
            ticket["ticket_number"]
        ),
        inline=True
    )

    embed.set_footer(
        text="MT Ticket System"
    )

    await channel.send(
        content=(
            f"{user.mention} "
            f"{staff_role.mention}"
        ),
        embed=embed,
        view=TicketClosePersistentView()
    )

    await interaction.response.send_message(
        f"✅ تم فتح التذكرة: {channel.mention}",
        ephemeral=True
    )

    # =====================================================
    # OPEN LOG
    # =====================================================

    if log_channel:

        log_embed = discord.Embed(
            title="🎫 فتح تذكرة",
            color=discord.Color.green()
        )

        log_embed.add_field(
            name="👤 العضو",
            value=(
                f"{user.mention}\n"
                f"`{user.id}`"
            ),
            inline=False
        )

        log_embed.add_field(
            name="🎫 التذكرة",
            value=(
                f"{ticket['ticket_name']}\n"
                f"رقم {ticket['ticket_number']}"
            ),
            inline=True
        )

        log_embed.add_field(
            name="📁 الروم",
            value=channel.mention,
            inline=True
        )

        await log_channel.send(
            embed=log_embed
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

        channel = interaction.channel

        if not channel.topic:

            await interaction.response.send_message(
                "❌ هذا الروم ليس تذكرة.",
                ephemeral=True
            )

            return

        owner_match = re.search(
            r"ticket_owner:(\d+)",
            channel.topic
        )

        number_match = re.search(
            r"ticket_number:(\d+)",
            channel.topic
        )

        if not owner_match:

            await interaction.response.send_message(
                "❌ تعذر معرفة صاحب التذكرة.",
                ephemeral=True
            )

            return

        owner_id = int(
            owner_match.group(1)
        )

        number = (
            int(number_match.group(1))
            if number_match
            else 0
        )

        ticket = get_ticket(
            interaction.guild.id,
            number
        )

        await interaction.response.send_message(
            "🔒 سيتم إغلاق التذكرة خلال **5 ثوانٍ**."
        )

        await asyncio.sleep(5)

        if ticket:

            log_channel = interaction.guild.get_channel(
                ticket["log_channel_id"]
            )

            if log_channel:

                embed = discord.Embed(
                    title="🔒 إغلاق تذكرة",
                    color=discord.Color.red()
                )

                embed.add_field(
                    name="👤 صاحب التذكرة",
                    value=(
                        f"<@{owner_id}>\n"
                        f"`{owner_id}`"
                    ),
                    inline=False
                )

                embed.add_field(
                    name="🎫 نوع التذكرة",
                    value=(
                        f"{ticket['ticket_name']}\n"
                        f"رقم {number}"
                    ),
                    inline=True
                )

                embed.add_field(
                    name="🔒 أغلقها",
                    value=(
                        f"{interaction.user.mention}\n"
                        f"`{interaction.user.id}`"
                    ),
                    inline=True
                )

                await log_channel.send(
                    embed=embed
                )

        try:

            await channel.delete(
                reason="Ticket closed"
            )

        except Exception as e:

            print(
                "Delete ticket error:",
                e
            )


class TicketClosePersistentView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=None
        )

        self.add_item(
            CloseTicketButton()
        )


class TicketOpenPersistentView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=None
        )

        # هذه النسخة تستخدم Custom Button عام
        # للبانلات القديمة/المستقبلية.
        self.add_item(
            GenericOpenButton()
        )


class GenericOpenButton(
    discord.ui.Button
):

    def __init__(self):

        super().__init__(
            label="فتح تذكرة",
            style=discord.ButtonStyle.primary,
            emoji="🎫",
            custom_id="mt_generic_open_ticket"
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        tickets = get_all_tickets(
            interaction.guild.id
        )

        if not tickets:

            await interaction.response.send_message(
                "❌ لم يتم إعداد أي تذكرة.",
                ephemeral=True
            )

            return

        options = []

        for ticket in tickets[:25]:

            options.append(
                discord.SelectOption(
                    label=ticket["ticket_name"][:100],
                    value=str(
                        ticket["ticket_number"]
                    ),
                    emoji="🎫"
                )
            )

        await interaction.response.send_message(
            "🎫 اختر نوع التذكرة:",
            view=TicketMenuPanelView(tickets),
            ephemeral=True
        )


# =========================================================
# READY
# =========================================================

@bot.event
async def on_ready():

    print(
        f"Logged in as {bot.user} "
        f"({bot.user.id})"
    )

    print(
        f"Servers: {len(bot.guilds)}"
    )


# =========================================================
# ERROR HANDLERS
# =========================================================

@ticket_setup.error
async def ticket_setup_error(
    interaction,
    error
):

    if isinstance(
        error,
        app_commands.errors.MissingPermissions
    ):

        if not interaction.response.is_done():

            await interaction.response.send_message(
                "❌ هذا الأمر للإدارة فقط.",
                ephemeral=True
            )

        return

    print(
        "ticket_setup error:",
        error
    )


@ticket_panel.error
async def ticket_panel_error(
    interaction,
    error
):

    if isinstance(
        error,
        app_commands.errors.MissingPermissions
    ):

        if not interaction.response.is_done():

            await interaction.response.send_message(
                "❌ هذا الأمر للإدارة فقط.",
                ephemeral=True
            )

        return

    print(
        "ticket_panel error:",
        error
    )


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    init_database()

    bot.run(TOKEN)
