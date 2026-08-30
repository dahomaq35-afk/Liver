import os
import re
import asyncio
import logging
from threading import Thread
from datetime import datetime
from flask import Flask
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View, Select, Modal, TextInput
from google import genai

# ==========================================
# 1. إعداد السجلات والنظام
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(name)s: %(message)s'
)
logger = logging.getLogger("RoleplayBot")

# ==========================================
# 2. قائمة الرتب المستثناة والدوال المعالجة للزخارف
# ==========================================
EXEMPT_ROLES = {
    "#",
    "MT | Owner ↔",
    "MT | COowner ↔",
    "MT | Ceo",
    "MT | FOUNDERS",
    "Appy",
    "Bot",
    "bot"
}

def clean_text(text: str) -> str:
    """إزالة الزخارف والرموز الخاصة وتحويل الحروف إلى صغيرة لتسهيل المقارنة"""
    cleaned = re.sub(r'[^a-zA-Z0-9\u0600-\u06FF]', '', text)
    return cleaned.lower()

CLEANED_EXEMPT_ROLES = {clean_text(role) for role in EXEMPT_ROLES if clean_text(role)}

def is_exempt(member: discord.Member) -> bool:
    """فحص ما إذا كان العضو يملك إحدى الرتب المستثناة بغض النظر عن الزخارف أو الحروف"""
    if not isinstance(member, discord.Member):
        return False
    if member.guild_permissions.administrator:
        return True

    for role in member.roles:
        if role.name in EXEMPT_ROLES:
            return True
        if clean_text(role.name) in CLEANED_EXEMPT_ROLES:
            return True

    return False

# ==========================================
# 3. إعداد خادم Flask (Keep Alive 24/7)
# ==========================================
app = Flask(__name__)

@app.route('/')
def home():
    return "Roleplay & Security Master Bot is Active 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# ==========================================
# 4. إعداد Google Gemini API (المكتبة الحديثة)
# ==========================================
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_KEY:
    ai_client = genai.Client(api_key=GEMINI_KEY)
else:
    ai_client = None
    logger.warning("GEMINI_API_KEY environment variable is missing!")

# ==========================================
# 5. إعداد البوت والافتراضيات (تم تصحيح الـ Intents)
# ==========================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.bans = True
intents.moderation = True

bot = commands.Bot(command_prefix="!", intents=intents)

ai_enabled_channels = set()

# ==========================================
# 6. نظام سجلات الحماية לרوم (📑┃حماية)
# ==========================================
async def send_security_alert(guild: discord.Guild, title: str, description: str, color: discord.Color = discord.Color.red()):
    if not guild:
        return
    channel = discord.utils.get(guild.text_channels, name="📑┃حماية")
    if channel:
        embed = discord.Embed(title=title, description=description, color=color, timestamp=datetime.now())
        embed.set_footer(text="نظام الحماية والأمان السريع ⚡")
        try:
            await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Failed to send security log: {e}")

# ==========================================
# 7. نظام رادع الحظر التلقائي (Anti-Nuke / Anti-Ban)
# ==========================================
@bot.event
async def on_member_ban(guild: discord.Guild, user: discord.User):
    banner_user = None
    reason = "غير معروف"

    try:
        async for entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.ban):
            if entry.target.id == user.id:
                banner_user = entry.user
                reason = entry.reason or "لم يتم ذكر سبب"
                break

        if banner_user and banner_user.id != bot.user.id:
            banner_member = guild.get_member(banner_user.id)
            if banner_member and is_exempt(banner_member):
                await send_security_alert(
                    guild,
                    "ℹ️ تنبيه حظر معتمد (رتبة مستثناة)",
                    f"**المبند:** {banner_user.mention} (رتبة مستثناة من الحماية)\n"
                    f"**المحظور:** {user.mention} (`{user.id}`)\n"
                    f"**السبب:** {reason}",
                    discord.Color.blue()
                )
                return

            await guild.unban(user, reason="إلغاء حظر تلقائي بواسطة نظام الحماية")
            await guild.ban(banner_user, reason=f"تبنيد تلقائي: قام بالحظر بدون استثناء حماية ({user.name})")

            await send_security_alert(
                guild,
                "🚨 حماية عاجلة: حظر العضو وتبنيد الفاعل",
                f"**العضو المظلوم:** {user.mention} (`{user.id}`) -> **تم فك حظره تلقائياً**\n"
                f"**الفاعل:** {banner_user.mention} (`{banner_user.id}`) -> **تم تبنيده فوراً**\n"
                f"**السبب الأصلي:** {reason}",
                discord.Color.red()
            )

    except Exception as e:
        logger.error(f"Error in on_member_ban security handler: {e}")

# ==========================================
# 8. نظام كشف الحسابات والبوتات المخترقة
# ==========================================
SUSPICIOUS_PATTERNS = [
    r"discord\.gg/[a-zA-Z0-9]+",
    r"free nitro",
    r"steamcommunity\.com/gift",
    r"@everyone",
    r"@here",
    r"token",
    r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
]

class SecurityGuard:
    @staticmethod
    async def check_message(message: discord.Message) -> bool:
        if is_exempt(message.author):
            return True

        for pattern in SUSPICIOUS_PATTERNS:
            if re.search(pattern, message.content, re.IGNORECASE):
                try:
                    await message.delete()
                    await message.guild.ban(message.author, reason="حساب/بوت مخترق يقوم بنشر روابط وتهديدات أمنية")

                    await send_security_alert(
                        message.guild,
                        "🛑 كشف حساب/بوت مخترق وتبنيده فوراً",
                        f"**الحساب المخترق:** {message.author.mention} (`{message.author.id}`)\n"
                        f"**نوع الحساب:** {'بوت 🤖' if message.author.bot else 'حساب شخصي 👤'}\n"
                        f"**القناة:** {message.channel.mention}\n"
                        f"**المحتوى المرصود:**\n```{message.content}```",
                        discord.Color.dark_red()
                    )
                    return False
                except Exception as e:
                    logger.error(f"Failed to execute emergency security response: {e}")
                    return False
        return True

# ==========================================
# 9. نظام التذاكر (Tickets)
# ==========================================
class CloseTicketView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="إغلاق التذكرة 🔒", style=discord.ButtonStyle.red, custom_id="close_ticket_btn_v10")
    async def close_ticket(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("جاري إغلاق التذكرة...")
        await asyncio.sleep(2)
        try:
            await interaction.channel.delete()
        except Exception as e:
            logger.error(f"Error deleting channel: {e}")

    @discord.ui.button(label="استدعاء الإدارة 🔔", style=discord.ButtonStyle.secondary, custom_id="claim_ticket_btn_v10")
    async def claim_ticket(self, interaction: discord.Interaction, button: Button):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ هذا الخيار مخصص للإدارة فقط.", ephemeral=True)
            return
        await interaction.response.send_message(f"🔔 قام الإداري {interaction.user.mention} بالاستجابة لتذكرتك.")

class TicketDropdown(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="الدعم الفني العامة", description="المشاكل والطلبات العامة بالسيرفر", emoji="🛠️", value="support"),
            discord.SelectOption(label="بلاغات الشرطة (LSPD)", description="تقديم شكوى أو بلاغ جنائي", emoji="👮", value="police"),
            discord.SelectOption(label="القوات الخاصة (SWAT)", description="بلاغات السطو والحالات الحرجية", emoji="🚨", value="swat"),
            discord.SelectOption(label="وزارة العدل والمحاكم", description="تقديم قضية أو استئناف حكم قضائي", emoji="⚖️", value="justice"),
            discord.SelectOption(label="القطاع الصحي والإسعاف", description="التقارير الطبية وإشعارات الإسعاف", emoji="🚑", value="health"),
            discord.SelectOption(label="إدارة عصابات ومنظمات", description="تراخيص وشؤون العصابات والأنشطة", emoji="🏴‍☠️", value="gangs"),
            discord.SelectOption(label="طلب استرجاع ممتلكات", description="استرجاع المركبات والأغراض مفقودة", emoji="📦", value="restore")
        ]
        super().__init__(placeholder="اختر القسم المطلوب لفتح تذكرة...", min_values=1, max_values=1, options=options, custom_id="ticket_select_dropdown_v10")

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        val = self.values[0]

        cat_names = {
            "support": "تذاكر الدعم العام",
            "police": "تذاكر الشرطة LSPD",
            "swat": "تذاكر القوات الخاصة",
            "justice": "تذاكر وزارة العدل",
            "health": "تذاكر القطاع الصحي",
            "gangs": "تذاكر المنظمات والعصابات",
            "restore": "تذاكر الاسترجاع"
        }

        category_name = cat_names.get(val, "التذاكر العامة")
        category = discord.utils.get(guild.categories, name=category_name)
        if not category:
            category = await guild.create_category(category_name)

        ticket_channel = await guild.create_text_channel(
            name=f"t-{interaction.user.name}",
            category=category,
            overwrites={
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
        )

        embed = discord.Embed(
            title=f"📋 تذكرة جديدة - {category_name}",
            description=f"مرحباً بك {interaction.user.mention}!\nيرجى كتابة كافة التفاصيل والأدلة المتاحة، وسيقوم الفريق المختص بمتابعة طلبك.",
            color=discord.Color.green()
        )
        await ticket_channel.send(embed=embed, view=CloseTicketView())
        await interaction.response.send_message(f"✅ تم إنشاء التذكرة بنجاح: {ticket_channel.mention}", ephemeral=True)

class TicketLauncher(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketDropdown())

# ==========================================
# 10. باقي القطاعات
# ==========================================
class CourtCaseModal(Modal, title="رفع دعوى قضائية لدى المحكمة العليا"):
    plaintiff = TextInput(label="اسم المدعي (أنت)", placeholder="اسم الشخصية بالكامل...", required=True)
    defendant = TextInput(label="اسم المدعى عليه", placeholder="اسم الشخص أو الجهة المشتكى عليها...", required=True)
    charge = TextInput(label="التهمة الموجهة", placeholder="اختلاس، اعتداء، مخالفت أنظمة...", required=True)
    details = TextInput(label="تفاصيل الدعوى والوقائع", style=discord.TextStyle.paragraph, placeholder="اشرح الوقائع والأحداث...", required=True)
    evidence = TextInput(label="الأدلة والبراهين", style=discord.TextStyle.paragraph, placeholder="روابط الصور أو مقاطع الفيديو...", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(title="⚖️ لائحة دعوى قضائية جديدة", color=discord.Color.gold())
        embed.add_field(name="المدعي:", value=self.plaintiff.value, inline=True)
        embed.add_field(name="المدعى عليه:", value=self.defendant.value, inline=True)
        embed.add_field(name="التهمة:", value=self.charge.value, inline=True)
        embed.add_field(name="تفاصيل الدعوى:", value=self.details.value, inline=False)
        embed.add_field(name="الأدلة والبراهين:", value=self.evidence.value, inline=False)
        embed.set_footer(text="وزارة العدل - ديوان التقاضي الإلكتروني")
        await interaction.response.send_message("✅ تم قيد الدعوى القضائية بنجاح وتحويلها لرئيس ديوان المظالم.", embed=embed)

class JusticeView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="رفع قضية جديدة ⚖️", style=discord.ButtonStyle.primary, custom_id="justice_court_case_btn_v10")
    async def open_modal(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(CourtCaseModal())

class PoliceReportModal(Modal, title="بلاغ أمني - مركز العمليات الموحد"):
    caller = TextInput(label="اسم المبلّغ", placeholder="اسمك الكامل ورقم الهاتف...", required=True)
    location = TextInput(label="موقع الحادثة", placeholder="المنطقة، الشارع أو الإحداثيات...", required=True)
    suspect = TextInput(label="أوصاف المشتبه به / المركبة", placeholder="الملامح، رقم اللوحة...", required=False)
    details = TextInput(label="تفاصيل البلاغ الجنائي", style=discord.TextStyle.paragraph, placeholder="اشرح ما حدث بالتفصيل...", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🚨 بلاغ أمني عاجل - عمليات الشرطة", color=discord.Color.blue())
        embed.add_field(name="المبلغ:", value=self.caller.value, inline=True)
        embed.add_field(name="الموقع:", value=self.location.value, inline=True)
        embed.add_field(name="المشتبه به:", value=self.suspect.value or "غير معروف", inline=True)
        embed.add_field(name="تفاصيل البلاغ:", value=self.details.value, inline=False)
        await interaction.response.send_message("🚨 تم توجيه البلاغ لأقرب دورية أمنية متواجدة بالموقع!", embed=embed)

class PoliceView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="تقديم بلاغ أمني 🚨", style=discord.ButtonStyle.danger, custom_id="police_report_btn_v10")
    async def open_modal(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(PoliceReportModal())

class SWATReportModal(Modal, title="نداء طوارئ - القوات الخاصة SWAT"):
    officer_name = TextInput(label="الرتبة والاسم", placeholder="الرتبة واسم الضابط...", required=True)
    code = TextInput(label="نوع الشفرة الأمنية", placeholder="Code 3 / Code 99...", required=True)
    location = TextInput(label="موقع الاشتباك / السطو", placeholder="الموقع بالتفصيل...", required=True)
    situation = TextInput(label="تقييم الوضع والمخاطر", style=discord.TextStyle.paragraph, placeholder="عدد المعتدين، الأسلحة...", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(title="⚡ نداء استغاثة عالي الخطورة - SWAT", color=discord.Color.dark_purple())
        embed.add_field(name="الضابط الطالب:", value=self.officer_name.value, inline=True)
        embed.add_field(name="الشفرة:", value=self.code.value, inline=True)
        embed.add_field(name="الموقع:", value=self.location.value, inline=True)
        embed.add_field(name="تقييم المخاطر:", value=self.situation.value, inline=False)
        await interaction.response.send_message("⚡ تم استنفار وحدات SWAT وتوجيه المدرعات للموقع!", embed=embed)

class SWATView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="طلب دعم القوات الخاصة ⚡", style=discord.ButtonStyle.secondary, custom_id="swat_call_btn_v10")
    async def open_modal(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(SWATReportModal())

class HealthRequestModal(Modal, title="نداء إسعاف وطوارئ طبية"):
    patient = TextInput(label="اسم المصاب / المريض", placeholder="اسم الشخصية...", required=True)
    location = TextInput(label="الموقع الدقيق", placeholder="اسم الحي أو الإحداثية...", required=True)
    injury_type = TextInput(label="نوع الإصابة", placeholder="طلق ناري، حادث...", required=True)
    condition = TextInput(label="وصف حالة المصاب الحالية", style=discord.TextStyle.paragraph, placeholder="هل التنفس منتظم؟", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🚑 بلاغ إسعاف وطوارئ طبية", color=discord.Color.red())
        embed.add_field(name="المصاب:", value=self.patient.value, inline=True)
        embed.add_field(name="الموقع:", value=self.location.value, inline=True)
        embed.add_field(name="نوع الإصابة:", value=self.injury_type.value, inline=True)
        embed.add_field(name="وصف الحالة:", value=self.condition.value, inline=False)
        await interaction.response.send_message("🚑 تم تحويل الطلب لغرفة الطوارئ والمسعفون في الطريق!", embed=embed)

class HealthView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="طلب إسعاف عاجل 🚑", style=discord.ButtonStyle.success, custom_id="health_request_btn_v10")
    async def open_modal(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(HealthRequestModal())

class ChannelSelectView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        channel_types=[discord.ChannelType.text],
        placeholder="اختر القنوات المفعلة للذكاء الاصطناعي...",
        min_values=1,
        max_values=5,
        custom_id="ai_channel_select_v10"
    )
    async def select_channels(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        global ai_enabled_channels
        ai_enabled_channels = {ch.id for ch in select.values}
        ch_mentions = ", ".join([ch.mention for ch in select.values])
        await interaction.response.send_message(f"✅ تم تخصيص الرد التلقائي للذكاء الاصطناعي في القنوات: {ch_mentions}", ephemeral=True)

# ==========================================
# 11. أوامر السلاش المحدثة
# ==========================================
@bot.tree.command(name="ai_security", description="فحص حالة الحماية والذكاء الاصطناعي للسيرفر")
async def ai_security(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    roles_list = "\n".join([f"• `{role}`" for role in EXEMPT_ROLES])
    
    embed = discord.Embed(
        title="🛡️ حالة الحماية السريعة والذكاء الاصطناعي",
        description="نظام الحماية المتقدم يعمل بالسرعة القصوى ومربوط بروم **`📑┃حماية`**.",
        color=discord.Color.green()
    )
    embed.add_field(name="الذكاء الاصطناعي:", value="مُفعل بنجاح (`gemini-2.5-flash`)", inline=True)
    embed.add_field(name="نظام فك الحظر وتبنيد الفاعل:", value="مُفعل تلقائياً", inline=True)
    embed.add_field(name="تجاهل الزخارف بالحماية:", value="مُفعل (Normalizer Active)", inline=True)
    embed.add_field(name="الرتب المستثناة من الحماية (Whitelist):", value=roles_list, inline=False)
    
    await interaction.followup.send(embed=embed, ephemeral=True)

# ==========================================
# 12. الأحداث والأوامر الرئيسية
# ==========================================
@bot.event
async def on_ready():
    logger.info(f"✅ تم تشغيل البوت بنجاح كـ: {bot.user.name} (ID: {bot.user.id})")

    try:
        synced = await bot.tree.sync()
        logger.info(f"✅ تم مزامنة {len(synced)} أمر سلاش بنجاح.")
    except Exception as e:
        logger.error(f"Failed to sync slash commands: {e}")

    bot.add_view(TicketLauncher())
    bot.add_view(CloseTicketView())
    bot.add_view(JusticeView())
    bot.add_view(PoliceView())
    bot.add_view(SWATView())
    bot.add_view(HealthView())
    bot.add_view(ChannelSelectView())

    await bot.change_presence(activity=discord.Game(name="إدارة سيرفر الرول بلي والحماية 🛡️"))

# --- أوامر التجهيز الإدارية ---
@bot.command(name="setup_tickets")
@commands.has_permissions(administrator=True)
async def setup_tickets(ctx):
    embed = discord.Embed(title="🎫 مركز الدعم الفني والخدمات العامة", description="اختر القسم المطلوب من القائمة بالأسفل.", color=discord.Color.blue())
    await ctx.send(embed=embed, view=TicketLauncher())

@bot.command(name="setup_justice")
@commands.has_permissions(administrator=True)
async def setup_justice(ctx):
    embed = discord.Embed(title="⚖️ ديوان وزارة العدل والمحاكم العليا", description="تقديم الدعاوى القضائية والبلاغات القانونية.", color=discord.Color.gold())
    await ctx.send(embed=embed, view=JusticeView())

@bot.command(name="setup_police")
@commands.has_permissions(administrator=True)
async def setup_police(ctx):
    embed = discord.Embed(title="🚔 القيادة العامة لشرطة LSPD", description="إرسال بلاغ أمني مباشر لغرفة العمليات.", color=discord.Color.dark_blue())
    await ctx.send(embed=embed, view=PoliceView())

@bot.command(name="setup_swat")
@commands.has_permissions(administrator=True)
async def setup_swat(ctx):
    embed = discord.Embed(title="⚡ وحدة التدخل السريع والقوات الخاصة SWAT", description="طلب الدعم التكتيكي للحالات الحرجية.", color=discord.Color.dark_purple())
    await ctx.send(embed=embed, view=SWATView())

@bot.command(name="setup_health")
@commands.has_permissions(administrator=True)
async def setup_health(ctx):
    embed = discord.Embed(title="🚑 الهيئة العامة للخدمات الطبية والطب الطارئ", description="طلب الإسعاف الطارئ للحوادث والإصابات.", color=discord.Color.red())
    await ctx.send(embed=embed, view=HealthView())

@bot.command(name="setup_ai")
@commands.has_permissions(administrator=True)
async def setup_ai(ctx):
    embed = discord.Embed(title="🤖 لوحة تحكم قنوات الذكاء الاصطناعي", description="اختر القنوات المسموح للذكاء الاصطناعي بالرد التلقائي فيها.", color=discord.Color.purple())
    await ctx.send(embed=embed, view=ChannelSelectView())

# --- أمر الذكاء الاصطناعي ---
@bot.command(name="ai")
async def chat_ai(ctx, *, prompt: str):
    if not ai_client:
        await ctx.send("❌ مفتاح Gemini API غير معرف.")
        return

    async with ctx.typing():
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                lambda: ai_client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt
                )
            )
            answer = response.text

            if len(answer) <= 2000:
                await ctx.send(answer)
            else:
                for i in range(0, len(answer), 1900):
                    await ctx.send(answer[i:i + 1900])
        except Exception as e:
            await ctx.send(f"⚠️ حدث خطأ:\n```{str(e)}```")

# --- معالجة الرسائل والمنشنات ---
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot and message.author.id == bot.user.id:
        return

    is_safe = await SecurityGuard.check_message(message)
    if not is_safe:
        return

    if bot.user.mentioned_in(message) and not message.mention_everyone:
        if ai_enabled_channels and message.channel.id not in ai_enabled_channels:
            await message.reply("⚠️ التفاعل مع الذكاء الاصطناعي محدد بقنوات معينة فقط.")
            return

        content = message.content.replace(f'<@{bot.user.id}>', '').strip()
        if content and ai_client:
            async with message.channel.typing():
                try:
                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(
                        None, 
                        lambda: ai_client.models.generate_content(
                            model='gemini-2.5-flash',
                            contents=content
                        )
                    )
                    answer = response.text

                    if len(answer) <= 2000:
                        await message.reply(answer)
                    else:
                        for i in range(0, len(answer), 1900):
                            await message.channel.send(answer[i:i + 1900])
                except Exception as e:
                    await message.reply(f"⚠️ حدث خطأ أثناء الاتصال بالذكاء الاصطناعي:\n```{str(e)}```")
                return

    await bot.process_commands(message)

# ==========================================
# 13. التشغيل
# ==========================================
if __name__ == "__main__":
    keep_alive()

    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
    if DISCORD_TOKEN:
        bot.run(DISCORD_TOKEN)
    else:
        logger.error("ERROR: DISCORD_TOKEN environment variable is missing!")
