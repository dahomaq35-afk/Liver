import os
import re
import asyncio
import logging
from threading import Thread
from datetime import datetime
from flask import Flask
import discord
from discord.ext import commands, tasks
from discord.ui import Button, View, Select, Modal, TextInput
import google.generativeai as genai

# ==========================================
# 1. إعداد السجلات والنظام (Logging System)
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(name)s: %(message)s'
)
logger = logging.getLogger("RoleplayBot")

# ==========================================
# 2. إعداد خادم Flask لإبقاء البوت حياً (Keep Alive 24/7)
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
# 3. إعداد Google Gemini API (الذكاء الاصطناعي)
# ==========================================
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    # استخدام النموذج المعتمد والمستقر تفادياً لخطأ 404
    ai_model = genai.GenerativeModel('gemini-2.5-flash')
else:
    ai_model = None
    logger.warning("GEMINI_API_KEY environment variable is missing!")

# ==========================================
# 4. إعداد البوت والافتراضيات (Bot Setup)
# ==========================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.bans = True
intents.moderation = True

bot = commands.Bot(command_prefix="!", intents=intents)

# متغيرات النظام العامة
ai_enabled_channels = set()
bot_ai_active = True
user_message_count = {}
user_last_message_time = {}

# ==========================================
# 5. نظام إرسال التحديثات وسجلات الحماية (Security Logging)
# ==========================================
async def send_security_log(guild: discord.Guild, title: str, description: str, color: discord.Color = discord.Color.red()):
    """دالة تبحث عن روم 📑┃حماية وترسل فيه التحديثات والبلاغات"""
    if not guild:
        return
    channel = discord.utils.get(guild.text_channels, name="📑┃حماية")
    if channel:
        embed = discord.Embed(title=title, description=description, color=color, timestamp=datetime.now())
        embed.set_footer(text="نظام مراقبة الحماية والتحديثات")
        try:
            await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Failed to send security log: {e}")

# ==========================================
# 6. نظام الحماية والأمان المتقدم (Security Guard System)
# ==========================================
SPAM_PATTERNS = [
    r"discord\.gg/[a-zA-Z0-9]+",
    r"discord\.com/invite/[a-zA-Z0-9]+",
    r"free nitro",
    r"steamcommunity\.com/gift",
    r"https?://[^\s]+"
]

class SecurityGuard:
    @staticmethod
    async def check_message(message: discord.Message) -> bool:
        if message.author.bot or message.author.guild_permissions.administrator:
            return True

        # فحص الروابط والإعلانات
        for pattern in SPAM_PATTERNS:
            if re.search(pattern, message.content, re.IGNORECASE):
                try:
                    await message.delete()
                    await message.channel.send(
                        f"⚠️ {message.author.mention} يُمنع نشر الروابط والإعلانات داخل السيرفر!",
                        delete_after=5
                    )
                    # إرسال التنبيه لروم 📑┃حماية
                    await send_security_log(
                        message.guild,
                        "🚨 تنبيه أمني - إعلان / رابط مخالف",
                        f"**العضو المخالف:** {message.author.mention} (`{message.author.id}`)\n"
                        f"**القناة:** {message.channel.mention}\n"
                        f"**المحتوى:**\n```{message.content}```",
                        discord.Color.red()
                    )
                    return False
                except Exception as e:
                    logger.error(f"Failed to delete spam message: {e}")
                    return False

        # فحص التكرار السريع (Anti-Spam)
        user_id = message.author.id
        current_time = datetime.now().timestamp()
        
        last_time = user_last_message_time.get(user_id, 0)
        count = user_message_count.get(user_id, 0)

        if current_time - last_time < 2:
            count += 1
        else:
            count = 1

        user_last_message_time[user_id] = current_time
        user_message_count[user_id] = count

        if count >= 5:
            try:
                await message.delete()
                await message.channel.send(
                    f"🚫 {message.author.mention} تم إيقاف رسائلك مؤقتاً بسبب السبام السريع.",
                    delete_after=5
                )
                # إرسال التنبيه لروم 📑┃حماية
                await send_security_log(
                    message.guild,
                    "⚠️ تنبيه أمني - تكرار رسائل (Spam)",
                    f"**العضو:** {message.author.mention} (`{message.author.id}`)\n"
                    f"**القناة:** {message.channel.mention}\n"
                    f"**الإجراء:** تم إرسال رسائل متكررة في وقت قصير وتم حظر الرسالة.",
                    discord.Color.orange()
                )
                return False
            except Exception as e:
                logger.error(f"Anti-spam error: {e}")
                return False

        return True

# ==========================================
# 7. نظام التذاكر والدعم الفني (Ticket Management System)
# ==========================================
class CloseTicketView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="إغلاق التذكرة 🔒", style=discord.ButtonStyle.red, custom_id="close_ticket_btn_v5")
    async def close_ticket(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("جاري إغلاق التذكرة وحفظ الأرشيف خلال 5 ثوانٍ...")
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete()
        except Exception as e:
            logger.error(f"Error deleting channel: {e}")

    @discord.ui.button(label="استدعاء الإدارة 🔔", style=discord.ButtonStyle.secondary, custom_id="claim_ticket_btn_v5")
    async def claim_ticket(self, interaction: discord.Interaction, button: Button):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ هذا الخيار مخصص للإدارة فقط.", ephemeral=True)
            return
        await interaction.response.send_message(f"🔔 قام الإداري {interaction.user.mention} بالاستجابة لتذكرتك وسيتابع معك الآن.")

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
        super().__init__(placeholder="اختر القسم المطلوب لفتح تذكرة...", min_values=1, max_values=1, options=options, custom_id="ticket_select_dropdown_v5")

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
            description=f"مرحباً بك {interaction.user.mention}!\nيرجى كتابة كافة التفاصيل والأدلة المتاحة، وسيقوم الفريق المختص بمتابعة طلبك في أقرب وقت.",
            color=discord.Color.green()
        )
        embed.set_footer(text="نظام خدمة المواطنين والتذاكر الإلكتروني")
        await ticket_channel.send(embed=embed, view=CloseTicketView())
        await interaction.response.send_message(f"✅ تم إنشاء التذكرة بنجاح: {ticket_channel.mention}", ephemeral=True)

class TicketLauncher(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketDropdown())

# ==========================================
# 8. نظام وزارة العدل (Ministry of Justice System)
# ==========================================
class CourtCaseModal(Modal, title="رفع دعوى قضائية لدى المحكمة العليا"):
    plaintiff = TextInput(label="اسم المدعي (أنت)", placeholder="اسم الشخصية بالكامل...", required=True)
    defendant = TextInput(label="اسم المدعى عليه", placeholder="اسم الشخص أو الجهة المشتكى عليها...", required=True)
    charge = TextInput(label="التهمة الموجهة", placeholder="اختلاس، اعتداء، مخالفت أنظمة...", required=True)
    details = TextInput(label="تفاصيل الدعوى والوقائع", style=discord.TextStyle.paragraph, placeholder="اشرح الوقائع والأحداث والتواريخ...", required=True)
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

    @discord.ui.button(label="رفع قضية جديدة ⚖️", style=discord.ButtonStyle.primary, custom_id="justice_court_case_btn_v5")
    async def open_modal(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(CourtCaseModal())

# ==========================================
# 9. نظام الشرطة والأمن (Police Department - LSPD)
# ==========================================
class PoliceReportModal(Modal, title="بلاغ أمني - مركز العمليات الموحد"):
    caller = TextInput(label="اسم المبلّغ", placeholder="اسمك الكامل ورقم الهاتف...", required=True)
    location = TextInput(label="موقع الحادثة", placeholder="المنطقة، الشارع أو الإحداثيات...", required=True)
    suspect = TextInput(label="أوصاف المشتبه به / المركبة", placeholder="الملامح، رقم اللوحة، نوع المركبة...", required=False)
    details = TextInput(label="تفاصيل البلاغ الجنائي", style=discord.TextStyle.paragraph, placeholder="اشرح ما حدث بالتفصيل...", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🚨 بلاغ أمني عاجل - عمليات الشرطة", color=discord.Color.blue())
        embed.add_field(name="المبلغ:", value=self.caller.value, inline=True)
        embed.add_field(name="الموقع:", value=self.location.value, inline=True)
        embed.add_field(name="المشتبه به:", value=self.suspect.value or "غير معروف", inline=True)
        embed.add_field(name="تفاصيل البلاغ:", value=self.details.value, inline=False)
        embed.set_footer(text="مديرية الأمن العام - قسم البلاغات الجنائية")
        await interaction.response.send_message("🚨 تم توجيه البلاغ لأقرب دورية أمنية متواجدة بالموقع!", embed=embed)

class PoliceView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="تقديم بلاغ أمني 🚨", style=discord.ButtonStyle.danger, custom_id="police_report_btn_v5")
    async def open_modal(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(PoliceReportModal())

# ==========================================
# 10. نظام القوات الخاصة (SWAT Special Unit)
# ==========================================
class SWATReportModal(Modal, title="نداء طوارئ - القوات الخاصة SWAT"):
    officer_name = TextInput(label="الرتبة والاسم", placeholder="الرتبة واسم الضابط...", required=True)
    code = TextInput(label="نوع الشفرة الأمنية", placeholder="Code 3 / Code 99...", required=True)
    location = TextInput(label="موقع الاشتباك / السطو", placeholder="الموقع بالتفصيل...", required=True)
    situation = TextInput(label="تقييم الوضع والمخاطر", style=discord.TextStyle.paragraph, placeholder="عدد المعتدين، الأسلحة المستخدمة...", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(title="⚡ نداء استغاثة عالي الخطورة - SWAT", color=discord.Color.dark_purple())
        embed.add_field(name="الضابط الطالب:", value=self.officer_name.value, inline=True)
        embed.add_field(name="الشفرة:", value=self.code.value, inline=True)
        embed.add_field(name="الموقع:", value=self.location.value, inline=True)
        embed.add_field(name="تقييم المخاطر:", value=self.situation.value, inline=False)
        embed.set_footer(text="وحدة التدخل السريع والقوات الخاصة")
        await interaction.response.send_message("⚡ تم استنفار وحدات SWAT وتوجيه المدرعات للموقع!", embed=embed)

class SWATView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="طلب دعم القوات الخاصة ⚡", style=discord.ButtonStyle.secondary, custom_id="swat_call_btn_v5")
    async def open_modal(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(SWATReportModal())

# ==========================================
# 11. نظام الخدمات الصحية الإسعاف (Healthcare System)
# ==========================================
class HealthRequestModal(Modal, title="نداء إسعاف وطوارئ طبية"):
    patient = TextInput(label="اسم المصاب / المريض", placeholder="اسم الشخصية...", required=True)
    location = TextInput(label="الموقع الدقيق", placeholder="اسم الحي أو الإحداثية...", required=True)
    injury_type = TextInput(label="نوع الإصابة", placeholder="طلق ناري، حادث مروري، إغماء...", required=True)
    condition = TextInput(label="وصف حالة المصاب الحالية", style=discord.TextStyle.paragraph, placeholder="هل التنفس منتظم؟ هل يوجد نزيف؟", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🚑 بلاغ إسعاف وطوارئ طبية", color=discord.Color.red())
        embed.add_field(name="المصاب:", value=self.patient.value, inline=True)
        embed.add_field(name="الموقع:", value=self.location.value, inline=True)
        embed.add_field(name="نوع الإصابة:", value=self.injury_type.value, inline=True)
        embed.add_field(name="وصف الحالة:", value=self.condition.value, inline=False)
        embed.set_footer(text="الهيئة العامة للخدمات الطبية والطب الطارئ")
        await interaction.response.send_message("🚑 تم تحويل الطلب لغرفة الطوارئ والمسعفون في الطريق!", embed=embed)

class HealthView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="طلب إسعاف عاجل 🚑", style=discord.ButtonStyle.success, custom_id="health_request_btn_v5")
    async def open_modal(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(HealthRequestModal())

# ==========================================
# 12. نظام إدارة التحكم بالذكاء الاصطناعي (AI Config)
# ==========================================
class ChannelSelectView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        channel_types=[discord.ChannelType.text],
        placeholder="اختر القنوات المفعلة للذكاء الاصطناعي...",
        min_values=1,
        max_values=5,
        custom_id="ai_channel_select_v5"
    )
    async def select_channels(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        global ai_enabled_channels
        ai_enabled_channels = {ch.id for ch in select.values}
        ch_mentions = ", ".join([ch.mention for ch in select.values])
        await interaction.response.send_message(f"✅ تم تخصيص الرد التلقائي للذكاء الاصطناعي في القنوات: {ch_mentions}", ephemeral=True)

# ==========================================
# 13. الأحداث والأوامر الرئيسية (Events & Commands)
# ==========================================
@bot.event
async def on_ready():
    logger.info(f"✅ تم تشغيل البوت بنجاح كـ: {bot.user.name} (ID: {bot.user.id})")

    # تسجيل الواجهات لضمان استمرار عمل كافة الأزرار حتى بعد إيقاف وتحديث البوت
    bot.add_view(TicketLauncher())
    bot.add_view(CloseTicketView())
    bot.add_view(JusticeView())
    bot.add_view(PoliceView())
    bot.add_view(SWATView())
    bot.add_view(HealthView())
    bot.add_view(ChannelSelectView())

    await bot.change_presence(activity=discord.Game(name="إدارة سيرفر الرول بلي والحماية 🛡️"))

    # إرسال إشعار التحديث والتشغيل تلقائياً إلى روم 📑┃حماية
    for guild in bot.guilds:
        await send_security_log(
            guild,
            "✅ تم إعادة تشغيل النظام وتحديث البوت",
            "تم تحديث كود البوت بنجاح وإعادة تفعيل جميع القطاعات، نموذج الذكاء الاصطناعي، ونظام الحماية المتقدم.",
            discord.Color.green()
        )

# --- أوامر التجهيز الإدارية ---
@bot.command(name="setup_tickets")
@commands.has_permissions(administrator=True)
async def setup_tickets(ctx):
    """إنشاء لوحة التذاكر"""
    embed = discord.Embed(
        title="🎫 مركز الدعم الفني والخدمات العامة",
        description="يرجى اختيار القسم المطلوب من القائمة المنسدلة بالأسفل للتواصل مع الفريق المختص.",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed, view=TicketLauncher())

@bot.command(name="setup_justice")
@commands.has_permissions(administrator=True)
async def setup_justice(ctx):
    """إنشاء لوحة وزارة العدل"""
    embed = discord.Embed(
        title="⚖️ ديوان وزارة العدل والمحاكم العليا",
        description="يمكنك تقديم الدعاوى القضائية والبلاغات القانونية عبر الضغط على الزر أدناه.",
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed, view=JusticeView())

@bot.command(name="setup_police")
@commands.has_permissions(administrator=True)
async def setup_police(ctx):
    """إنشاء لوحة عمليات الشرطة"""
    embed = discord.Embed(
        title="🚔 القيادة العامة لشرطة LSPD",
        description="اضغط على الزر بالأسفل لإرسال بلاغ أمني مباشر لغرفة العمليات.",
        color=discord.Color.dark_blue()
    )
    await ctx.send(embed=embed, view=PoliceView())

@bot.command(name="setup_swat")
@commands.has_permissions(administrator=True)
async def setup_swat(ctx):
    """إنشاء لوحة القوات الخاصة"""
    embed = discord.Embed(
        title="⚡ وحدة التدخل السريع والقوات الخاصة SWAT",
        description="مخصص للضباط لطلب الدعم التكتيكي في الحالات عالية الخطورة.",
        color=discord.Color.dark_purple()
    )
    await ctx.send(embed=embed, view=SWATView())

@bot.command(name="setup_health")
@commands.has_permissions(administrator=True)
async def setup_health(ctx):
    """إنشاء لوحة الصحة والإسعاف"""
    embed = discord.Embed(
        title="🚑 الهيئة العامة للخدمات الطبية والطب الطارئ",
        description="اضغط على الزر بالأسفل لطلب الإسعاف الطارئ في الحوادث والإصابات.",
        color=discord.Color.red()
    )
    await ctx.send(embed=embed, view=HealthView())

@bot.command(name="setup_ai")
@commands.has_permissions(administrator=True)
async def setup_ai(ctx):
    """تخصيص قنوات الذكاء الاصطناعي"""
    embed = discord.Embed(
        title="🤖 لوحة تحكم قنوات الذكاء الاصطناعي",
        description="اختر القنوات المسموح للذكاء الاصطناعي بالرد التلقائي فيها.",
        color=discord.Color.purple()
    )
    await ctx.send(embed=embed, view=ChannelSelectView())

# --- أمر الذكاء الاصطناعي اليدوي ---
@bot.command(name="ai")
async def chat_ai(ctx, *, prompt: str):
    """التحدث المباشر مع الذكاء الاصطناعي"""
    if not ai_model:
        await ctx.send("❌ مفتاح Gemini API غير معرف في متغيرات البيئة.")
        return

    async with ctx.typing():
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: ai_model.generate_content(prompt))
            answer = response.text

            if len(answer) <= 2000:
                await ctx.send(answer)
            else:
                for i in range(0, len(answer), 1900):
                    await ctx.send(answer[i:i + 1900])
        except Exception as e:
            await ctx.send(f"⚠️ حدث خطأ أثناء معالجة النص:\n```{str(e)}```")

# --- معالجة الرسائل والمنشنات الحماية ---
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # تشغيل نظام الفحص والأمان أولاً
    is_safe = await SecurityGuard.check_message(message)
    if not is_safe:
        return

    # الرد التلقائي عند الإشارة للبوت (Mention)
    if bot.user.mentioned_in(message) and not message.mention_everyone:
        if ai_enabled_channels and message.channel.id not in ai_enabled_channels:
            await message.reply("⚠️ التفاعل مع الذكاء الاصطناعي محدد بقنوات معينة فقط.")
            return

        content = message.content.replace(f'<@{bot.user.id}>', '').strip()
        if content and ai_model:
            async with message.channel.typing():
                try:
                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(None, lambda: ai_model.generate_content(content))
                    answer = response.text

                    if len(answer) <= 2000:
                        await message.reply(answer)
                    else:
                        for i in range(0, len(answer), 1900):
                            await message.channel.send(answer[i:i + 1900])
                except Exception as e:
                    await message.reply(f"⚠️ حدث خطأ أثناء الاتصال بنموذج الذكاء الاصطناعي:\n```{str(e)}```")
                return

    await bot.process_commands(message)

# ==========================================
# 14. التشغيل الرئيسي للمشروع (Execution)
# ==========================================
if __name__ == "__main__":
    keep_alive()

    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
    if DISCORD_TOKEN:
        bot.run(DISCORD_TOKEN)
    else:
        logger.error("ERROR: DISCORD_TOKEN environment variable is missing!")
