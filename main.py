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


@app.route("/health")
def health():
    return "OK"


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

    # -----------------------------------------------------
    # TICKET SETUPS
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # OPEN TICKETS
    # -----------------------------------------------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS open_tickets (
            channel_id INTEGER PRIMARY KEY,
            guild_id INTEGER NOT NULL,
            owner_id INTEGER NOT NULL,
            ticket_number INTEGER NOT NULL,
            claimer_id INTEGER
        )
    """)

    # -----------------------------------------------------
    # PANEL CONFIGS
    # -----------------------------------------------------

    cur.execute("""
        CREATE TABLE IF NOT EXISTS panel_configs (
            panel_id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            image_url TEXT,
            footer TEXT,
            ticket_message TEXT NOT NULL,
            method TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


# =========================================================
# TICKET DATABASE
# =========================================================

def save_ticket(
    guild_id,
    ticket_number,
    ticket_name,
    category_id,
    staff_role_id,
    log_channel_id
):

    conn = get_db()

    conn.execute("""
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


def get_ticket(
    guild_id,
    ticket_number
):

    conn = get_db()

    row = conn.execute("""
        SELECT *
        FROM ticket_setups
        WHERE guild_id = ?
        AND ticket_number = ?
    """, (
        guild_id,
        ticket_number
    )).fetchone()

    conn.close()

    return row


def get_all_tickets(
    guild_id
):

    conn = get_db()

    rows = conn.execute("""
        SELECT *
        FROM ticket_setups
        WHERE guild_id = ?
        ORDER BY ticket_number ASC
    """, (
        guild_id,
    )).fetchall()

    conn.close()

    return rows


# =========================================================
# OPEN TICKET DATABASE
# =========================================================

def save_open_ticket(
    channel_id,
    guild_id,
    owner_id,
    ticket_number
):

    conn = get_db()

    conn.execute("""
        INSERT OR REPLACE INTO open_tickets (
            channel_id,
            guild_id,
            owner_id,
            ticket_number,
            claimer_id
        )
        VALUES (?, ?, ?, ?, NULL)
    """, (
        channel_id,
        guild_id,
        owner_id,
        ticket_number
    ))

    conn.commit()
    conn.close()


def get_open_ticket(
    channel_id
):

    conn = get_db()

    row = conn.execute("""
        SELECT *
        FROM open_tickets
        WHERE channel_id = ?
    """, (
        channel_id,
    )).fetchone()

    conn.close()

    return row


def set_ticket_claimer(
    channel_id,
    claimer_id
):

    conn = get_db()

    conn.execute("""
        UPDATE open_tickets
        SET claimer_id = ?
        WHERE channel_id = ?
    """, (
        claimer_id,
        channel_id
    ))

    conn.commit()
    conn.close()


def delete_open_ticket(
    channel_id
):

    conn = get_db()

    conn.execute("""
        DELETE FROM open_tickets
        WHERE channel_id = ?
    """, (
        channel_id,
    ))

    conn.commit()
    conn.close()


def find_open_ticket(
    guild,
    user_id
):

    conn = get_db()

    row = conn.execute("""
        SELECT *
        FROM open_tickets
        WHERE guild_id = ?
        AND owner_id = ?
        LIMIT 1
    """, (
        guild.id,
        user_id
    )).fetchone()

    conn.close()

    if not row:
        return None

    return guild.get_channel(
        row["channel_id"]
    )


# =========================================================
# PANEL DATABASE
# =========================================================

def save_panel(
    guild_id,
    title,
    description,
    image_url,
    footer,
    ticket_message,
    method
):

    conn = get_db()

    cur = conn.cursor()

    cur.execute("""
        INSERT INTO panel_configs (
            guild_id,
            title,
            description,
            image_url,
            footer,
            ticket_message,
            method
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        guild_id,
        title,
        description,
        image_url,
        footer,
        ticket_message,
        method
    ))

    panel_id = cur.lastrowid

    conn.commit()
    conn.close()

    return panel_id


def get_panel(
    panel_id
):

    conn = get_db()

    row = conn.execute("""
        SELECT *
        FROM panel_configs
        WHERE panel_id = ?
    """, (
        panel_id,
    )).fetchone()

    conn.close()

    return row


def get_all_panels():

    conn = get_db()

    rows = conn.execute("""
        SELECT *
        FROM panel_configs
    """).fetchall()

    conn.close()

    return rows


# =========================================================
# HELPERS
# =========================================================

def clean_channel_name(
    name
):

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


def valid_image_url(
    url
):

    if not url:
        return True

    return (
        url.startswith("https://")
        or
        url.startswith("http://")
    )


def is_admin(
    member
):

    return (
        isinstance(member, discord.Member)
        and member.guild_permissions.administrator
    )


# =========================================================
# BOT
# =========================================================

class MTBot(
    commands.Bot
):

    async def setup_hook(
        self
    ):

        init_database()

        # -------------------------------------------------
        # Persistent ticket controls
        # -------------------------------------------------

        self.add_view(
            TicketControlsView()
        )

        # -------------------------------------------------
        # Restore saved panels
        # -------------------------------------------------

        panels = get_all_panels()

        for panel in panels:

            tickets = get_all_tickets(
                panel["guild_id"]
            )

            if not tickets:
                continue

            if panel["method"] == "menu":

                self.add_view(
                    TicketMenuPanelView(
                        tickets,
                        panel["panel_id"]
                    )
                )

            else:

                self.add_view(
                    TicketButtonsPanelView(
                        tickets,
                        panel["panel_id"]
                    )
                )

        # -------------------------------------------------
        # Sync commands
        # -------------------------------------------------

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
        interaction
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

    def __init__(
        self
    ):

        super().__init__(
            label="متابعة",
            emoji="➡️",
            style=discord.ButtonStyle.primary
        )

    async def callback(
        self,
        interaction
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

    def __init__(
        self
    ):

        super().__init__(
            label="إلغاء",
            emoji="❌",
            style=discord.ButtonStyle.danger
        )

    async def callback(
        self,
        interaction
    ):

        await interaction.response.edit_message(
            content="❌ تم إلغاء الإعداد.",
            embed=None,
            view=None
        )


class TicketNumbersView(
    discord.ui.View
):

    def __init__(
        self
    ):

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
        interaction
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
        interaction
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
        interaction
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
        interaction
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
                f"ننتقل الآن للتذكرة رقم **{next_number}**."
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
    interaction
):

    embed = discord.Embed(
        title="🎫 إعداد التذاكر",
        description=(
            "اختر أرقام التذاكر التي تريد إعدادها.\n\n"
            "يمكنك اختيار أكثر من رقم بنفس الوقت."
        ),
        color=discord.Color.blue()
    )

    await interaction.response.send_message(
        embed=embed,
        view=TicketNumbersView(),
        ephemeral=True
    )


# =========================================================
# PANEL METHOD
# =========================================================

class PanelMethodSelect(
    discord.ui.Select
):

    def __init__(
        self
    ):

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
        interaction
    ):

        method = self.values[0]

        await interaction.response.send_modal(
            TicketPanelModal(method)
        )


class PanelMethodView(
    discord.ui.View
):

    def __init__(
        self
    ):

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

        self.ticket_message = discord.ui.TextInput(
            label="الكلام داخل التكت",
            placeholder="اكتب الكلام الذي يظهر عند فتح التذكرة...",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=2000
        )

        self.add_item(self.embed_title)
        self.add_item(self.embed_description)
        self.add_item(self.embed_image)
        self.add_item(self.embed_footer)
        self.add_item(self.ticket_message)

    async def on_submit(
        self,
        interaction
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

        image = str(
            self.embed_image.value
        ).strip()

        if image and not valid_image_url(image):

            await interaction.response.send_message(
                "❌ رابط الصورة غير صحيح. يجب أن يبدأ بـ `https://` أو `http://`.",
                ephemeral=True
            )

            return

        panel_id = save_panel(
            guild_id=interaction.guild.id,
            title=str(self.embed_title.value),
            description=str(self.embed_description.value),
            image_url=image,
            footer=str(self.embed_footer.value).strip(),
            ticket_message=(
                str(self.ticket_message.value).strip()
                or
                "مرحبًا {user}، تم فتح التذكرة بنجاح.\n"
                "يرجى كتابة طلبك وانتظار فريق الدعم."
            ),
            method=self.method
        )

        embed = discord.Embed(
            title=str(self.embed_title.value),
            description=str(self.embed_description.value),
            color=discord.Color.blue()
        )

        # -------------------------------------------------
        # الصورة الصغيرة على اليمين
        # -------------------------------------------------

        if image:

            embed.set_thumbnail(
                url=image
            )

        footer = str(
            self.embed_footer.value
        ).strip()

        if footer:

            embed.set_footer(
                text=footer
            )

        if interaction.guild.icon:

            embed.set_author(
                name=interaction.guild.name,
                icon_url=interaction.guild.icon.url
            )

        else:

            embed.set_author(
                name=interaction.guild.name
            )

        embed.add_field(
            name="طريقة فتح التذكرة",
            value=(
                "📋 اختر نوع التذكرة من القائمة بالأسفل."
                if self.method == "menu"
                else
                "🔘 اضغط على الزر الخاص بنوع التذكرة."
            ),
            inline=False
        )

        if self.method == "menu":

            view = TicketMenuPanelView(
                tickets,
                panel_id
            )

        else:

            view = TicketButtonsPanelView(
                tickets,
                panel_id
            )

        await interaction.channel.send(
            embed=embed,
            view=view
        )

        method_name = (
            "📋 منيو"
            if self.method == "menu"
            else
            "🔘 أزرار"
        )

        await interaction.response.send_message(
            (
                "✅ تم إرسال بانل التذاكر.\n"
                f"طريقة الفتح: **{method_name}**\n"
                "🖼️ الصورة تم وضعها بشكل صغير على اليمين."
            ),
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
# TICKET MENU PANEL
# =========================================================

class TicketMenuSelect(
    discord.ui.Select
):

    def __init__(
        self,
        tickets,
        panel_id
    ):

        self.panel_id = panel_id

        options = []

        for ticket in tickets[:25]:

            options.append(
                discord.SelectOption(
                    label=ticket["ticket_name"][:100],
                    value=str(ticket["ticket_number"]),
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
            custom_id=f"mt_ticket_menu_{panel_id}"
        )

    async def callback(
        self,
        interaction
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

        panel = get_panel(
            self.panel_id
        )

        await create_ticket(
            interaction,
            ticket,
            panel
        )


class TicketMenuPanelView(
    discord.ui.View
):

    def __init__(
        self,
        tickets,
        panel_id
    ):

        super().__init__(
            timeout=None
        )

        self.add_item(
            TicketMenuSelect(
                tickets,
                panel_id
            )
        )


# =========================================================
# TICKET BUTTON PANEL
# =========================================================

class TicketOpenTypeButton(
    discord.ui.Button
):

    def __init__(
        self,
        ticket,
        panel_id
    ):

        self.ticket_number = ticket[
            "ticket_number"
        ]

        self.panel_id = panel_id

        super().__init__(
            label=ticket["ticket_name"][:80],
            style=discord.ButtonStyle.primary,
            emoji="🎫",
            custom_id=(
                f"mt_ticket_button_"
                f"{panel_id}_"
                f"{self.ticket_number}"
            )
        )

    async def callback(
        self,
        interaction
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

        panel = get_panel(
            self.panel_id
        )

        await create_ticket(
            interaction,
            ticket,
            panel
        )


class TicketButtonsPanelView(
    discord.ui.View
):

    def __init__(
        self,
        tickets,
        panel_id
    ):

        super().__init__(
            timeout=None
        )

        for ticket in tickets[:25]:

            self.add_item(
                TicketOpenTypeButton(
                    ticket,
                    panel_id
                )
            )


# =========================================================
# CREATE TICKET
# =========================================================

async def create_ticket(
    interaction,
    ticket,
    panel
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
                manage_channels=True,
                manage_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True
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

    save_open_ticket(
        channel.id,
        guild.id,
        user.id,
        ticket["ticket_number"]
    )

    ticket_embed = discord.Embed(
        title=f"🎫 {ticket['ticket_name']}",
        color=discord.Color.blue()
    )

    ticket_message = (
        panel["ticket_message"]
        if panel
        else
        "مرحبًا {user}، تم فتح التذكرة بنجاح.\n"
        "يرجى كتابة طلبك وانتظار فريق الدعم."
    )

    ticket_message = ticket_message.replace(
        "{user}",
        user.mention
    )

    ticket_message = ticket_message.replace(
        "{support}",
        staff_role.mention
    )

    ticket_embed.description = ticket_message

    ticket_embed.add_field(
        name="👤 صاحب التذكرة",
        value=user.mention,
        inline=True
    )

    ticket_embed.add_field(
        name="🎫 رقم التذكرة",
        value=str(ticket["ticket_number"]),
        inline=True
    )

    ticket_embed.add_field(
        name="🟢 المستلم",
        value="لم يتم الاستلام بعد",
        inline=False
    )

    ticket_embed.set_footer(
        text="MT Ticket System"
    )

    await channel.send(
        content=(
            f"{user.mention} "
            f"{staff_role.mention}"
        ),
        embed=ticket_embed,
        view=TicketControlsView()
    )

    await interaction.response.send_message(
        f"✅ تم فتح التذكرة: {channel.mention}",
        ephemeral=True
    )

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
# CLAIM TICKET
# =========================================================

class ClaimTicketButton(
    discord.ui.Button
):

    def __init__(
        self
    ):

        super().__init__(
            label="استلام",
            style=discord.ButtonStyle.success,
            emoji="🟢",
            custom_id="mt_claim_ticket"
        )

    async def callback(
        self,
        interaction
    ):

        channel = interaction.channel

        data = get_open_ticket(
            channel.id
        )

        if not data:

            await interaction.response.send_message(
                "❌ هذا الروم ليس تذكرة مفتوحة.",
                ephemeral=True
            )

            return

        if interaction.user.id == data["owner_id"]:

            await interaction.response.send_message(
                "❌ صاحب التذكرة لا يستطيع استلام التذكرة.",
                ephemeral=True
            )

            return

        ticket = get_ticket(
            interaction.guild.id,
            data["ticket_number"]
        )

        if not ticket:

            await interaction.response.send_message(
                "❌ إعداد التذكرة غير موجود.",
                ephemeral=True
            )

            return

        staff_role = interaction.guild.get_role(
            ticket["staff_role_id"]
        )

        if not staff_role:

            await interaction.response.send_message(
                "❌ رتبة الدعم غير موجودة.",
                ephemeral=True
            )

            return

        if (
            staff_role not in interaction.user.roles
            and
            not interaction.user.guild_permissions.administrator
        ):

            await interaction.response.send_message(
                "❌ لا تملك صلاحية استلام هذه التذكرة.",
                ephemeral=True
            )

            return

        if data["claimer_id"]:

            claimer = interaction.guild.get_member(
                data["claimer_id"]
            )

            mention = (
                claimer.mention
                if claimer
                else
                f"<@{data['claimer_id']}>"
            )

            await interaction.response.send_message(
                f"❌ التذكرة مستلمة بالفعل من {mention}.",
                ephemeral=True
            )

            return

        set_ticket_claimer(
            channel.id,
            interaction.user.id
        )

        await interaction.response.send_message(
            (
                f"🟢 تم استلام التذكرة بواسطة "
                f"{interaction.user.mention}."
            )
        )

        async for message in channel.history(
            limit=20
        ):

            if (
                message.author == interaction.client.user
                and
                message.embeds
            ):

                embed = message.embeds[0]

                new_embed = discord.Embed.from_dict(
                    embed.to_dict()
                )

                for index, field in enumerate(
                    new_embed.fields
                ):

                    if field.name == "🟢 المستلم":

                        new_embed.set_field_at(
                            index,
                            name="🟢 المستلم",
                            value=interaction.user.mention,
                            inline=False
                        )

                await message.edit(
                    embed=new_embed,
                    view=TicketControlsView(
                        claimed=True
                    )
                )

                break

        log_channel = interaction.guild.get_channel(
            ticket["log_channel_id"]
        )

        if log_channel:

            log_embed = discord.Embed(
                title="🟢 استلام تذكرة",
                color=discord.Color.green()
            )

            log_embed.add_field(
                name="🎫 التذكرة",
                value=channel.mention,
                inline=False
            )

            log_embed.add_field(
                name="👤 صاحب التذكرة",
                value=f"<@{data['owner_id']}>",
                inline=True
            )

            log_embed.add_field(
                name="🟢 المستلم",
                value=interaction.user.mention,
                inline=True
            )

            await log_channel.send(
                embed=log_embed
            )


# =========================================================
# REMIND OWNER
# =========================================================

class RemindOwnerButton(
    discord.ui.Button
):

    def __init__(
        self
    ):

        super().__init__(
            label="تذكير صاحب التذكرة",
            style=discord.ButtonStyle.secondary,
            emoji="🔔",
            custom_id="mt_remind_owner"
        )

    async def callback(
        self,
        interaction
    ):

        channel = interaction.channel

        data = get_open_ticket(
            channel.id
        )

        if not data:

            await interaction.response.send_message(
                "❌ هذه ليست تذكرة مفتوحة.",
                ephemeral=True
            )

            return

        if not data["claimer_id"]:

            await interaction.response.send_message(
                "❌ لا يمكن التذكير قبل استلام التذكرة.",
                ephemeral=True
            )

            return

        ticket = get_ticket(
            interaction.guild.id,
            data["ticket_number"]
        )

        if not ticket:

            await interaction.response.send_message(
                "❌ إعداد التذكرة غير موجود.",
                ephemeral=True
            )

            return

        staff_role = interaction.guild.get_role(
            ticket["staff_role_id"]
        )

        if not staff_role:

            await interaction.response.send_message(
                "❌ رتبة الدعم غير موجودة.",
                ephemeral=True
            )

            return

        if (
            staff_role not in interaction.user.roles
            and
            not interaction.user.guild_permissions.administrator
        ):

            await interaction.response.send_message(
                "❌ لا تملك صلاحية تذكير صاحب التذكرة.",
                ephemeral=True
            )

            return

        owner = interaction.guild.get_member(
            data["owner_id"]
        )

        if owner:

            await channel.send(
                content=(
                    f"🔔 {owner.mention}\n"
                    "يرجى الرد على التذكرة، "
                    "فريق الدعم بانتظار ردك."
                )
            )

        else:

            await channel.send(
                content=(
                    f"🔔 <@{data['owner_id']}>\n"
                    "يرجى الرد على التذكرة."
                )
            )

        await interaction.response.send_message(
            "✅ تم تذكير صاحب التذكرة.",
            ephemeral=True
        )

        log_channel = interaction.guild.get_channel(
            ticket["log_channel_id"]
        )

        if log_channel:

            log_embed = discord.Embed(
                title="🔔 تذكير صاحب التذكرة",
                color=discord.Color.orange()
            )

            log_embed.add_field(
                name="🎫 التذكرة",
                value=channel.mention,
                inline=True
            )

            log_embed.add_field(
                name="👤 صاحب التذكرة",
                value=f"<@{data['owner_id']}>",
                inline=True
            )

            log_embed.add_field(
                name="🔔 بواسطة",
                value=interaction.user.mention,
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

    def __init__(
        self
    ):

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

        data = get_open_ticket(
            channel.id
        )

        if not data:

            await interaction.response.send_message(
                "❌ هذا الروم ليس تذكرة.",
                ephemeral=True
            )

            return

        ticket = get_ticket(
            interaction.guild.id,
            data["ticket_number"]
        )

        if not ticket:

            await interaction.response.send_message(
                "❌ إعداد التذكرة غير موجود.",
                ephemeral=True
            )

            return

        staff_role = interaction.guild.get_role(
            ticket["staff_role_id"]
        )

        if not staff_role:

            await interaction.response.send_message(
                "❌ رتبة المسؤول غير موجودة.",
                ephemeral=True
            )

            return

        # -------------------------------------------------
        # صلاحيات الإغلاق
        #
        # 1 - مستلم التذكرة
        # 2 - المسؤول / Staff Role
        # 3 - الرتب الأعلى من Staff Role
        # -------------------------------------------------

        is_claimer = (
    data["claimer_id"] is not None
    and
    interaction.user.id == data["claimer_id"]
)

        is_admin = (
            interaction.user.guild_permissions.administrator
        )

        is_staff_or_higher = (
            interaction.user.top_role >= staff_role
            and
            interaction.user.top_role != interaction.guild.default_role
        )

        if not (
            is_claimer
            or
            is_admin
            or
            is_staff_or_higher
        ):

            await interaction.response.send_message(
                (
                    "❌ لا تملك صلاحية إغلاق هذه التذكرة.\n\n"
                    "المسموح لهم بالإغلاق:\n"
                    "🟢 مستلم التذكرة\n"
                    "🛡️ المسؤول\n"
                    "⬆️ الرتب الأعلى من المسؤول"
                ),
                ephemeral=True
            )

            return

        await interaction.response.send_message(
            "🔒 سيتم إغلاق التذكرة خلال **5 ثوانٍ**."
        )

        await asyncio.sleep(5)

        # -------------------------------------------------
        # LOG
        # -------------------------------------------------

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
                    f"<@{data['owner_id']}>\n"
                    f"`{data['owner_id']}`"
                ),
                inline=False
            )

            embed.add_field(
                name="🎫 نوع التذكرة",
                value=(
                    f"{ticket['ticket_name']}\n"
                    f"رقم {data['ticket_number']}"
                ),
                inline=True
            )

            embed.add_field(
                name="🟢 المستلم",
                value=(
                    f"<@{data['claimer_id']}>"
                    if data["claimer_id"]
                    else
                    "لم يتم الاستلام"
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

        delete_open_ticket(
            channel.id
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


# =========================================================
# TICKET CONTROLS VIEW
# =========================================================

class TicketControlsView(
    discord.ui.View
):

    def __init__(
        self,
        claimed=False
    ):

        super().__init__(
            timeout=None
        )

        claim_button = ClaimTicketButton()

        if claimed:

            claim_button.disabled = True
            claim_button.label = "تم الاستلام"

        self.add_item(
            claim_button
        )

        self.add_item(
            RemindOwnerButton()
        )

        self.add_item(
            CloseTicketButton()
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
# APPLICATION SYSTEM
# =========================================================

APPLICATION_DB = "mt_ticket_system.db"


def app_db():
    conn = sqlite3.connect(APPLICATION_DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_application_database():
    conn = app_db()
    cur = conn.cursor()

    # إعدادات نظام التقديم
    cur.execute("""
        CREATE TABLE IF NOT EXISTS application_settings (
            guild_id INTEGER PRIMARY KEY,
            review_channel_id INTEGER,
            reviewer_role_id INTEGER,
            instructions TEXT,
            accept_message TEXT,
            reject_message TEXT,
            panel_title TEXT,
            panel_description TEXT,
            panel_image TEXT
        )
    """)

    # رتب القبول
    cur.execute("""
        CREATE TABLE IF NOT EXISTS application_roles (
            guild_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,
            PRIMARY KEY (guild_id, role_id)
        )
    """)

    # أسئلة التقديم
    cur.execute("""
        CREATE TABLE IF NOT EXISTS application_questions (
            guild_id INTEGER NOT NULL,
            question_number INTEGER NOT NULL,
            question TEXT NOT NULL,
            PRIMARY KEY (guild_id, question_number)
        )
    """)

    # التقديمات
    cur.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            application_id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            answers TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            review_message_id INTEGER,
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


init_application_database()


# =========================================================
# APPLICATION SETTINGS
# =========================================================

def save_application_settings(
    guild_id,
    review_channel_id=None,
    reviewer_role_id=None,
    instructions=None,
    accept_message=None,
    reject_message=None,
    panel_title=None,
    panel_description=None,
    panel_image=None
):

    conn = app_db()

    old = conn.execute("""
        SELECT *
        FROM application_settings
        WHERE guild_id = ?
    """, (guild_id,)).fetchone()

    if old:

        review_channel_id = (
            review_channel_id
            if review_channel_id is not None
            else old["review_channel_id"]
        )

        reviewer_role_id = (
            reviewer_role_id
            if reviewer_role_id is not None
            else old["reviewer_role_id"]
        )

        instructions = (
            instructions
            if instructions is not None
            else old["instructions"]
        )

        accept_message = (
            accept_message
            if accept_message is not None
            else old["accept_message"]
        )

        reject_message = (
            reject_message
            if reject_message is not None
            else old["reject_message"]
        )

        panel_title = (
            panel_title
            if panel_title is not None
            else old["panel_title"]
        )

        panel_description = (
            panel_description
            if panel_description is not None
            else old["panel_description"]
        )

        panel_image = (
            panel_image
            if panel_image is not None
            else old["panel_image"]
        )

    conn.execute("""
        INSERT OR REPLACE INTO application_settings (
            guild_id,
            review_channel_id,
            reviewer_role_id,
            instructions,
            accept_message,
            reject_message,
            panel_title,
            panel_description,
            panel_image
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        guild_id,
        review_channel_id,
        reviewer_role_id,
        instructions,
        accept_message,
        reject_message,
        panel_title,
        panel_description,
        panel_image
    ))

    conn.commit()
    conn.close()


def get_application_settings(guild_id):

    conn = app_db()

    row = conn.execute("""
        SELECT *
        FROM application_settings
        WHERE guild_id = ?
    """, (guild_id,)).fetchone()

    conn.close()

    return row


# =========================================================
# APPLICATION ROLES
# =========================================================

def add_application_role(guild_id, role_id):

    conn = app_db()

    conn.execute("""
        INSERT OR IGNORE INTO application_roles (
            guild_id,
            role_id
        )
        VALUES (?, ?)
    """, (
        guild_id,
        role_id
    ))

    conn.commit()
    conn.close()


def remove_application_role(guild_id, role_id):

    conn = app_db()

    conn.execute("""
        DELETE FROM application_roles
        WHERE guild_id = ?
        AND role_id = ?
    """, (
        guild_id,
        role_id
    ))

    conn.commit()
    conn.close()


def get_application_roles(guild_id):

    conn = app_db()

    rows = conn.execute("""
        SELECT role_id
        FROM application_roles
        WHERE guild_id = ?
    """, (guild_id,)).fetchall()

    conn.close()

    return [row["role_id"] for row in rows]


# =========================================================
# APPLICATION QUESTIONS
# =========================================================

def save_application_question(
    guild_id,
    number,
    question
):

    conn = app_db()

    conn.execute("""
        INSERT OR REPLACE INTO application_questions (
            guild_id,
            question_number,
            question
        )
        VALUES (?, ?, ?)
    """, (
        guild_id,
        number,
        question
    ))

    conn.commit()
    conn.close()


def get_application_questions(guild_id):

    conn = app_db()

    rows = conn.execute("""
        SELECT *
        FROM application_questions
        WHERE guild_id = ?
        ORDER BY question_number ASC
    """, (guild_id,)).fetchall()

    conn.close()

    return rows


# =========================================================
# APPLICATION DATABASE
# =========================================================

def create_application(
    guild_id,
    user_id,
    answers
):

    conn = app_db()

    cur = conn.cursor()

    cur.execute("""
        INSERT INTO applications (
            guild_id,
            user_id,
            answers,
            status,
            created_at
        )
        VALUES (?, ?, ?, 'pending', ?)
    """, (
        guild_id,
        user_id,
        answers,
        str(asyncio.get_event_loop().time())
    ))

    application_id = cur.lastrowid

    conn.commit()
    conn.close()

    return application_id


def get_application(application_id):

    conn = app_db()

    row = conn.execute("""
        SELECT *
        FROM applications
        WHERE application_id = ?
    """, (application_id,)).fetchone()

    conn.close()

    return row


def set_application_status(
    application_id,
    status,
    message_id=None
):

    conn = app_db()

    if message_id is not None:

        conn.execute("""
            UPDATE applications
            SET status = ?,
                review_message_id = ?
            WHERE application_id = ?
        """, (
            status,
            message_id,
            application_id
        ))

    else:

        conn.execute("""
            UPDATE applications
            SET status = ?
            WHERE application_id = ?
        """, (
            status,
            application_id
        ))

    conn.commit()
    conn.close()


# =========================================================
# APPLICATION SETUP SELECTS
# =========================================================

class ApplicationReviewChannelSelect(
    discord.ui.ChannelSelect
):

    def __init__(self):

        super().__init__(
            placeholder="اختر روم استقبال التقديمات",
            channel_types=[
                discord.ChannelType.text
            ],
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction):

        save_application_settings(
            interaction.guild.id,
            review_channel_id=self.values[0].id
        )

        await interaction.response.send_message(
            f"✅ تم تحديد روم التقديمات: {self.values[0].mention}",
            ephemeral=True
        )


class ApplicationReviewChannelView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(timeout=300)

        self.add_item(
            ApplicationReviewChannelSelect()
        )


@bot.tree.command(
    name="تقديم_روم",
    description="تحديد روم استقبال التقديمات"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def application_channel(
    interaction
):

    embed = discord.Embed(
        title="📥 روم التقديمات",
        description=(
            "اختر الروم الذي سيتم إرسال التقديمات إليه."
        ),
        color=discord.Color.blue()
    )

    await interaction.response.send_message(
        embed=embed,
        view=ApplicationReviewChannelView(),
        ephemeral=True
    )


# =========================================================
# REVIEW ROLE
# =========================================================

class ApplicationReviewerRoleSelect(
    discord.ui.RoleSelect
):

    def __init__(self):

        super().__init__(
            placeholder="اختر رتبة مراجعة التقديمات",
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction):

        save_application_settings(
            interaction.guild.id,
            reviewer_role_id=self.values[0].id
        )

        await interaction.response.send_message(
            f"✅ تم تحديد رتبة المراجعة: {self.values[0].mention}",
            ephemeral=True
        )


class ApplicationReviewerRoleView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(timeout=300)

        self.add_item(
            ApplicationReviewerRoleSelect()
        )


@bot.tree.command(
    name="تقديم_مراجعين",
    description="تحديد رتبة الأشخاص المسموح لهم بقبول ورفض التقديمات"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def application_reviewer_role(
    interaction
):

    await interaction.response.send_message(
        "👮 اختر رتبة مراجعة التقديمات:",
        view=ApplicationReviewerRoleView(),
        ephemeral=True
    )


# =========================================================
# ACCEPT ROLES
# =========================================================

class ApplicationAcceptRolesSelect(
    discord.ui.RoleSelect
):

    def __init__(self):

        super().__init__(
            placeholder="اختر الرتب التي تعطى عند القبول",
            min_values=1,
            max_values=10
        )

    async def callback(self, interaction):

        conn = app_db()

        conn.execute("""
            DELETE FROM application_roles
            WHERE guild_id = ?
        """, (interaction.guild.id,))

        for role in self.values:

            conn.execute("""
                INSERT OR IGNORE INTO application_roles (
                    guild_id,
                    role_id
                )
                VALUES (?, ?)
            """, (
                interaction.guild.id,
                role.id
            ))

        conn.commit()
        conn.close()

        roles_text = "\n".join(
            f"• {role.mention}"
            for role in self.values
        )

        await interaction.response.send_message(
            (
                "✅ تم تحديد رتب القبول:\n\n"
                f"{roles_text}"
            ),
            ephemeral=True
        )


class ApplicationAcceptRolesView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(timeout=300)

        self.add_item(
            ApplicationAcceptRolesSelect()
        )


@bot.tree.command(
    name="تقديم_رتب",
    description="تحديد الرتب التي يحصل عليها المقبول"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def application_roles(
    interaction
):

    await interaction.response.send_message(
        (
            "🏷️ اختر الرتب التي تريد إعطاءها للمتقدم "
            "عند القبول.\n\n"
            "يمكن اختيار أكثر من رتبة."
        ),
        view=ApplicationAcceptRolesView(),
        ephemeral=True
    )


# =========================================================
# APPLICATION MESSAGES
# =========================================================

class ApplicationMessagesModal(
    discord.ui.Modal
):

    def __init__(self):

        super().__init__(
            title="رسائل نظام التقديم"
        )

        self.instructions = discord.ui.TextInput(
            label="رسالة التعليمات",
            placeholder="اكتب التعليمات التي تظهر للمتقدم قبل التقديم...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=4000
        )

        self.accept = discord.ui.TextInput(
            label="رسالة القبول",
            placeholder="اكتب رسالة القبول التي تصل للمتقدم خاص...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=4000
        )

        self.reject = discord.ui.TextInput(
            label="رسالة الرفض",
            placeholder="اكتب رسالة الرفض التي تصل للمتقدم خاص...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=4000
        )

        self.add_item(self.instructions)
        self.add_item(self.accept)
        self.add_item(self.reject)

    async def on_submit(self, interaction):

        save_application_settings(
            interaction.guild.id,
            instructions=str(
                self.instructions.value
            ),
            accept_message=str(
                self.accept.value
            ),
            reject_message=str(
                self.reject.value
            )
        )

        await interaction.response.send_message(
            "✅ تم حفظ رسائل التعليمات والقبول والرفض.",
            ephemeral=True
        )


@bot.tree.command(
    name="تقديم_رسائل",
    description="تحديد رسائل التعليمات والقبول والرفض"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def application_messages(
    interaction
):

    await interaction.response.send_modal(
        ApplicationMessagesModal()
    )


# =========================================================
# APPLICATION QUESTIONS
# =========================================================

class ApplicationQuestionModal(
    discord.ui.Modal
):

    def __init__(
        self,
        number
    ):

        super().__init__(
            title=f"إضافة سؤال رقم {number}"
        )

        self.number = number

        self.question = discord.ui.TextInput(
            label="السؤال",
            placeholder="اكتب سؤال التقديم...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=1000
        )

        self.add_item(
            self.question
        )

    async def on_submit(self, interaction):

        save_application_question(
            interaction.guild.id,
            self.number,
            str(self.question.value)
        )

        await interaction.response.send_message(
            (
                f"✅ تم حفظ السؤال رقم **{self.number}**.\n\n"
                f"**السؤال:** {self.question.value}"
            ),
            ephemeral=True
        )


class ApplicationQuestionNumberSelect(
    discord.ui.Select
):

    def __init__(self):

        options = []

        for number in range(1, 11):

            options.append(
                discord.SelectOption(
                    label=f"السؤال {number}",
                    value=str(number),
                    emoji="📝"
                )
            )

        super().__init__(
            placeholder="اختر رقم السؤال",
            options=options,
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction):

        number = int(
            self.values[0]
        )

        await interaction.response.send_modal(
            ApplicationQuestionModal(number)
        )


class ApplicationQuestionView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(timeout=300)

        self.add_item(
            ApplicationQuestionNumberSelect()
        )


@bot.tree.command(
    name="تقديم_سؤال",
    description="إضافة أو تعديل سؤال في التقديم"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def application_question(
    interaction
):

    await interaction.response.send_message(
        (
            "📝 اختر رقم السؤال الذي تريد إضافته "
            "أو تعديله."
        ),
        view=ApplicationQuestionView(),
        ephemeral=True
    )


# =========================================================
# APPLICATION PANEL
# =========================================================

class ApplicationPanelModal(
    discord.ui.Modal
):

    def __init__(self):

        super().__init__(
            title="إعداد بانل التقديم"
        )

        self.title_input = discord.ui.TextInput(
            label="عنوان البانل",
            placeholder="التقديم على الإدارة",
            required=True,
            max_length=256
        )

        self.description = discord.ui.TextInput(
            label="وصف البانل",
            placeholder="اضغط على الزر بالأسفل للتقديم.",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=4000
        )

        self.image = discord.ui.TextInput(
            label="رابط الصورة - اختياري",
            placeholder="https://...",
            required=False,
            max_length=1000
        )

        self.add_item(self.title_input)
        self.add_item(self.description)
        self.add_item(self.image)

    async def on_submit(self, interaction):

        image = str(
            self.image.value
        ).strip()

        if image and not valid_image_url(image):

            await interaction.response.send_message(
                "❌ رابط الصورة غير صحيح.",
                ephemeral=True
            )

            return

        save_application_settings(
            interaction.guild.id,
            panel_title=str(
                self.title_input.value
            ),
            panel_description=str(
                self.description.value
            ),
            panel_image=image
        )

        embed = discord.Embed(
            title=str(
                self.title_input.value
            ),
            description=str(
                self.description.value
            ),
            color=discord.Color.blue()
        )

        if interaction.guild.icon:

            embed.set_author(
                name=interaction.guild.name,
                icon_url=interaction.guild.icon.url
            )

        else:

            embed.set_author(
                name=interaction.guild.name
            )

        if image:

            embed.set_thumbnail(
                url=image
            )

        await interaction.channel.send(
            embed=embed,
            view=ApplicationPanelView()
        )

        await interaction.response.send_message(
            "✅ تم إرسال بانل التقديم.",
            ephemeral=True
        )


@bot.tree.command(
    name="تقديم_بانل",
    description="إرسال بانل التقديم"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def application_panel(
    interaction
):

    await interaction.response.send_modal(
        ApplicationPanelModal()
    )


# =========================================================
# APPLICATION START BUTTON
# =========================================================

class StartApplicationButton(
    discord.ui.Button
):

    def __init__(self):

        super().__init__(
            label="تقديم",
            emoji="📝",
            style=discord.ButtonStyle.primary,
            custom_id="mt_application_start"
        )

    async def callback(self, interaction):

        settings = get_application_settings(
            interaction.guild.id
        )

        if not settings:

            await interaction.response.send_message(
                "❌ لم يتم إعداد نظام التقديم.",
                ephemeral=True
            )

            return

        if not settings["review_channel_id"]:

            await interaction.response.send_message(
                "❌ لم يتم تحديد روم استقبال التقديمات.",
                ephemeral=True
            )

            return

        questions = get_application_questions(
            interaction.guild.id
        )

        if not questions:

            await interaction.response.send_message(
                "❌ لم يتم إضافة أسئلة للتقديم.",
                ephemeral=True
            )

            return

        instructions = settings["instructions"]

        if instructions:

            embed = discord.Embed(
                title="📋 تعليمات التقديم",
                description=instructions,
                color=discord.Color.blue()
            )

            view = ApplicationConfirmView()

            await interaction.response.send_message(
                embed=embed,
                view=view,
                ephemeral=True
            )

            return

        await show_application_modal(
            interaction
        )


class ApplicationPanelView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=None
        )

        self.add_item(
            StartApplicationButton()
        )


# =========================================================
# CONFIRM APPLICATION
# =========================================================

class ApplicationConfirmButton(
    discord.ui.Button
):

    def __init__(self):

        super().__init__(
            label="بدء التقديم",
            emoji="📝",
            style=discord.ButtonStyle.success
        )

    async def callback(self, interaction):

        await show_application_modal(
            interaction
        )


class ApplicationCancelButton(
    discord.ui.Button
):

    def __init__(self):

        super().__init__(
            label="إلغاء",
            emoji="❌",
            style=discord.ButtonStyle.danger
        )

    async def callback(self, interaction):

        await interaction.response.edit_message(
            content="❌ تم إلغاء التقديم.",
            embed=None,
            view=None
        )


class ApplicationConfirmView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=300
        )

        self.add_item(
            ApplicationConfirmButton()
        )

        self.add_item(
            ApplicationCancelButton()
        )


# =========================================================
# APPLICATION FORM
# =========================================================

async def show_application_modal(
    interaction
):

    questions = get_application_questions(
        interaction.guild.id
    )

    if not questions:

        await interaction.response.send_message(
            "❌ لا توجد أسئلة للتقديم.",
            ephemeral=True
        )

        return

    # Discord Modal يسمح بخمسة عناصر فقط.
    # لذلك نقسم الأسئلة على صفحات إذا زادت عن 5.

    first_questions = questions[:5]

    await interaction.response.send_modal(
        ApplicationFormModal(
            first_questions,
            0
        )
    )


class ApplicationFormModal(
    discord.ui.Modal
):

    def __init__(
        self,
        questions,
        page
    ):

        super().__init__(
            title=f"تقديم - صفحة {page + 1}"
        )

        self.questions = questions
        self.page = page

        self.inputs = []

        for question in questions:

            text = discord.ui.TextInput(
                label=(
                    f"{question['question_number']}. "
                    f"{question['question']}"
                )[:45],
                style=discord.TextStyle.paragraph,
                required=True,
                max_length=1000
            )

            self.inputs.append(text)

            self.add_item(text)

    async def on_submit(self, interaction):

        all_questions = get_application_questions(
            interaction.guild.id
        )

        answers = {}

        for index, question in enumerate(
            self.questions
        ):

            answers[
                str(question["question_number"])
            ] = str(
                self.inputs[index].value
            )

        # إذا فيه أسئلة أكثر من 5
        next_questions = all_questions[
            (self.page + 1) * 5:
            (self.page + 2) * 5
        ]

        if next_questions:

            await interaction.response.send_modal(
                ApplicationFormNextModal(
                    all_questions,
                    answers,
                    self.page + 1
                )
            )

            return

        await finish_application(
            interaction,
            answers
        )


class ApplicationFormNextModal(
    discord.ui.Modal
):

    def __init__(
        self,
        all_questions,
        previous_answers,
        page
    ):

        super().__init__(
            title=f"تقديم - صفحة {page + 1}"
        )

        self.all_questions = all_questions
        self.previous_answers = previous_answers
        self.page = page

        self.questions = all_questions[
            page * 5:
            (page + 1) * 5
        ]

        self.inputs = []

        for question in self.questions:

            text = discord.ui.TextInput(
                label=(
                    f"{question['question_number']}. "
                    f"{question['question']}"
                )[:45],
                style=discord.TextStyle.paragraph,
                required=True,
                max_length=1000
            )

            self.inputs.append(text)

            self.add_item(text)

    async def on_submit(self, interaction):

        answers = dict(
            self.previous_answers
        )

        for index, question in enumerate(
            self.questions
        ):

            answers[
                str(question["question_number"])
            ] = str(
                self.inputs[index].value
            )

        next_questions = self.all_questions[
            (self.page + 1) * 5:
            (self.page + 2) * 5
        ]

        if next_questions:

            await interaction.response.send_modal(
                ApplicationFormNextModal(
                    self.all_questions,
                    answers,
                    self.page + 1
                )
            )

            return

        await finish_application(
            interaction,
            answers
        )


# =========================================================
# FINISH APPLICATION
# =========================================================

async def finish_application(
    interaction,
    answers
):

    settings = get_application_settings(
        interaction.guild.id
    )

    review_channel = interaction.guild.get_channel(
        settings["review_channel_id"]
    )

    if not review_channel:

        await interaction.response.send_message(
            "❌ روم استقبال التقديمات غير موجود.",
            ephemeral=True
        )

        return

    application_id = create_application(
        interaction.guild.id,
        interaction.user.id,
        str(answers)
    )

    embed = discord.Embed(
        title="📥 تقديم جديد",
        color=discord.Color.blue()
    )

    embed.set_author(
        name=interaction.user,
        icon_url=interaction.user.display_avatar.url
    )

    embed.add_field(
        name="👤 المتقدم",
        value=(
            f"{interaction.user.mention}\n"
            f"`{interaction.user.id}`"
        ),
        inline=False
    )

    for question in get_application_questions(
        interaction.guild.id
    ):

        answer = answers.get(
            str(question["question_number"]),
            "—"
        )

        embed.add_field(
            name=(
                f"📝 {question['question_number']}. "
                f"{question['question']}"
            )[:256],
            value=answer[:1024],
            inline=False
        )

    embed.set_footer(
        text=f"Application ID: {application_id}"
    )

    message = await review_channel.send(
        content=(
            f"📥 **تقديم جديد**\n"
            f"المتقدم: {interaction.user.mention}"
        ),
        embed=embed,
        view=ApplicationReviewView(
            application_id
        )
    )

    set_application_status(
        application_id,
        "pending",
        message.id
    )

    await interaction.response.send_message(
        (
            "✅ تم إرسال تقديمك بنجاح.\n"
            "انتظر مراجعة الإدارة."
        ),
        ephemeral=True
    )


# =========================================================
# ACCEPT / REJECT BUTTONS
# =========================================================

def can_review_application(
    interaction
):

    settings = get_application_settings(
        interaction.guild.id
    )

    if not settings:
        return False

    if interaction.user.guild_permissions.administrator:
        return True

    role_id = settings["reviewer_role_id"]

    if not role_id:
        return False

    role = interaction.guild.get_role(
        role_id
    )

    if not role:
        return False

    return role in interaction.user.roles


class AcceptApplicationButton(
    discord.ui.Button
):

    def __init__(
        self,
        application_id
    ):

        self.application_id = application_id

        super().__init__(
            label="قبول",
            emoji="🟢",
            style=discord.ButtonStyle.success,
            custom_id=(
                f"mt_application_accept_"
                f"{application_id}"
            )
        )

    async def callback(self, interaction):

        if not can_review_application(
            interaction
        ):

            await interaction.response.send_message(
                "❌ لا تملك صلاحية قبول التقديمات.",
                ephemeral=True
            )

            return

        application = get_application(
            self.application_id
        )

        if not application:

            await interaction.response.send_message(
                "❌ التقديم غير موجود.",
                ephemeral=True
            )

            return

        if application["status"] != "pending":

            await interaction.response.send_message(
                (
                    "❌ تمت معالجة هذا التقديم مسبقًا.\n"
                    f"الحالة: **{application['status']}**"
                ),
                ephemeral=True
            )

            return

        member = interaction.guild.get_member(
            application["user_id"]
        )

        if not member:

            await interaction.response.send_message(
                "❌ المتقدم غير موجود في السيرفر.",
                ephemeral=True
            )

            return

        role_ids = get_application_roles(
            interaction.guild.id
        )

        added_roles = []

        for role_id in role_ids:

            role = interaction.guild.get_role(
                role_id
            )

            if not role:
                continue

            try:

                await member.add_roles(
                    role,
                    reason="Application accepted"
                )

                added_roles.append(
                    role.mention
                )

            except discord.Forbidden:

                print(
                    f"Cannot add role {role_id}"
                )

        settings = get_application_settings(
            interaction.guild.id
        )

        message_text = (
            settings["accept_message"]
            or
            "مبروك! تم قبول تقديمك."
        )

        message_text = message_text.replace(
            "{user}",
            member.mention
        )

        message_text = message_text.replace(
            "{server}",
            interaction.guild.name
        )

        try:

            await member.send(
                message_text
            )

            dm_status = "📩 تم إرسال رسالة القبول في الخاص."

        except discord.Forbidden:

            dm_status = "⚠️ تعذر إرسال رسالة القبول في الخاص."

        set_application_status(
            self.application_id,
            "accepted"
        )

        await interaction.response.edit_message(
            content=(
                f"🟢 **تم قبول التقديم**\n"
                f"المتقدم: {member.mention}\n"
                f"بواسطة: {interaction.user.mention}\n\n"
                f"{dm_status}"
            ),
            embed=interaction.message.embeds[0]
            if interaction.message.embeds
            else None,
            view=None
        )


class RejectApplicationButton(
    discord.ui.Button
):

    def __init__(
        self,
        application_id
    ):

        self.application_id = application_id

        super().__init__(
            label="رفض",
            emoji="🔴",
            style=discord.ButtonStyle.danger,
            custom_id=(
                f"mt_application_reject_"
                f"{application_id}"
            )
        )

    async def callback(self, interaction):

        if not can_review_application(
            interaction
        ):

            await interaction.response.send_message(
                "❌ لا تملك صلاحية رفض التقديمات.",
                ephemeral=True
            )

            return

        application = get_application(
            self.application_id
        )

        if not application:

            await interaction.response.send_message(
                "❌ التقديم غير موجود.",
                ephemeral=True
            )

            return

        if application["status"] != "pending":

            await interaction.response.send_message(
                (
                    "❌ تمت معالجة هذا التقديم مسبقًا.\n"
                    f"الحالة: **{application['status']}**"
                ),
                ephemeral=True
            )

            return

        member = interaction.guild.get_member(
            application["user_id"]
        )

        if not member:

            await interaction.response.send_message(
                "❌ المتقدم غير موجود في السيرفر.",
                ephemeral=True
            )

            return

        settings = get_application_settings(
            interaction.guild.id
        )

        message_text = (
            settings["reject_message"]
            or
            "نعتذر، لم يتم قبول تقديمك."
        )

        message_text = message_text.replace(
            "{user}",
            member.mention
        )

        message_text = message_text.replace(
            "{server}",
            interaction.guild.name
        )

        try:

            await member.send(
                message_text
            )

            dm_status = "📩 تم إرسال رسالة الرفض في الخاص."

        except discord.Forbidden:

            dm_status = "⚠️ تعذر إرسال رسالة الرفض في الخاص."

        set_application_status(
            self.application_id,
            "rejected"
        )

        await interaction.response.edit_message(
            content=(
                f"🔴 **تم رفض التقديم**\n"
                f"المتقدم: {member.mention}\n"
                f"بواسطة: {interaction.user.mention}\n\n"
                f"{dm_status}"
            ),
            embed=interaction.message.embeds[0]
            if interaction.message.embeds
            else None,
            view=None
        )


class ApplicationReviewView(
    discord.ui.View
):

    def __init__(
        self,
        application_id
    ):

        super().__init__(
            timeout=None
        )

        self.add_item(
            AcceptApplicationButton(
                application_id
            )
        )

        self.add_item(
            RejectApplicationButton(
                application_id
            )
        )


# =========================================================
# APPLICATION STATUS
# =========================================================

@bot.tree.command(
    name="تقديم_الحالة",
    description="عرض إعدادات نظام التقديم"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def application_status(
    interaction
):

    settings = get_application_settings(
        interaction.guild.id
    )

    if not settings:

        await interaction.response.send_message(
            "❌ لم يتم إعداد نظام التقديم.",
            ephemeral=True
        )

        return

    review_channel = (
        interaction.guild.get_channel(
            settings["review_channel_id"]
        )
        if settings["review_channel_id"]
        else None
    )

    reviewer_role = (
        interaction.guild.get_role(
            settings["reviewer_role_id"]
        )
        if settings["reviewer_role_id"]
        else None
    )

    roles = get_application_roles(
        interaction.guild.id
    )

    role_text = "\n".join(
        f"• <@&{role_id}>"
        for role_id in roles
    ) or "لا توجد رتب"

    questions = get_application_questions(
        interaction.guild.id
    )

    embed = discord.Embed(
        title="⚙️ إعدادات نظام التقديم",
        color=discord.Color.blue()
    )

    embed.add_field(
        name="📥 روم التقديمات",
        value=(
            review_channel.mention
            if review_channel
            else
            "غير محدد"
        ),
        inline=False
    )

    embed.add_field(
        name="👮 رتبة المراجعة",
        value=(
            reviewer_role.mention
            if reviewer_role
            else
            "غير محددة"
        ),
        inline=False
    )

    embed.add_field(
        name="🏷️ رتب القبول",
        value=role_text,
        inline=False
    )

    embed.add_field(
        name="📝 عدد الأسئلة",
        value=str(len(questions)),
        inline=False
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# =========================================================
# CLEAR APPLICATION QUESTIONS
# =========================================================

@bot.tree.command(
    name="تقديم_مسح_الاسئلة",
    description="مسح جميع أسئلة التقديم"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def application_clear_questions(
    interaction
):

    conn = app_db()

    conn.execute("""
        DELETE FROM application_questions
        WHERE guild_id = ?
    """, (
        interaction.guild.id,
    ))

    conn.commit()
    conn.close()

    await interaction.response.send_message(
        "🗑️ تم مسح جميع أسئلة التقديم.",
        ephemeral=True
    )


# =========================================================
# APPLICATION ERROR HANDLERS
# =========================================================

@application_channel.error
async def application_channel_error(
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
        "application_channel error:",
        error
    )


@application_reviewer_role.error
async def application_reviewer_role_error(
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
        "application_reviewer_role error:",
        error
    )


@application_roles.error
async def application_roles_error(
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
        "application_roles error:",
        error
    )


@application_messages.error
async def application_messages_error(
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
        "application_messages error:",
        error
    )


@application_question.error
async def application_question_error(
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
        "application_question error:",
        error
    )


@application_panel.error
async def application_panel_error(
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
        "application_panel error:",
        error
    )


@application_status.error
async def application_status_error(
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
        "application_status error:",
        error
    )


@application_clear_questions.error
async def application_clear_questions_error(
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
        "application_clear_questions error:",
        error
    )


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    init_database()

    bot.run(TOKEN)
