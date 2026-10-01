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
# START
# =========================================================

if __name__ == "__main__":

    init_database()

    bot.run(TOKEN)
