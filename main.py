import os
import asyncio
import datetime
import logging
from collections import defaultdict
from threading import Thread
from flask import Flask
import discord
from discord import app_commands
from discord.ext import commands

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# ---------------------------------------------------------
# 1. خادم الويب (Keep Alive 24/7)
# ---------------------------------------------------------
web_app = Flask('')

@web_app.route('/')
def home():
    return "Bot Core & Security System is Online!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

# ---------------------------------------------------------
# 2. إعدادات البوت والقواعد
# ---------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.bans = True
intents.moderation = True

bot = commands.Bot(command_prefix="-", intents=intents)

# أسماء رتب القطاعات RP
ROLE_JUSTICE = "𝗠𝗧 | Justice"
ROLE_POLICE = "𝗠𝗧 | LSPD"
ROLE_SWAT = "𝗠𝗧 | S.W.A.T"
ROLE_HEALTH = "𝗠𝗧 | PHMC"

# رتب الحماية المصرح لها بالحظر (تم حذف MT | FOUNDERS)
WHITELIST_ROLES = [
    "#", 
    "MT | Owner ↔", 
    "MT | COowner ↔", 
    "MT | Ceo", 
    "Appy", 
    "Bot", 
    "bot"
]

SECURITY_CHANNEL_NAME = "📑┃حماية"

# السجلات الجنائية للبلاغات
criminal_records = {}

def is_whitelisted(user: discord.User | discord.Member, guild: discord.Guild) -> bool:
    """التحقق حصرياً من رتب الوايت لست المحددة فقط"""
    if not user or not guild:
        return False
    
    member = guild.get_member(user.id) if not isinstance(user, discord.Member) else user
    if not member:
        return False

    user_role_names = [role.name for role in member.roles]
    return any(w_role in user_role_names for w_role in WHITELIST_ROLES)

def check_role(user: discord.Member, role_name: str) -> bool:
    user_role_names = [role.name for role in user.roles]
    return role_name in user_role_names

async def get_security_channel(guild: discord.Guild):
    channel = discord.utils.get(guild.text_channels, name=SECURITY_CHANNEL_NAME)
    if not channel:
        try:
            channel = await guild.create_text_channel(SECURITY_CHANNEL_NAME)
            print(f"✅ تم إنشاء روم الحماية: {SECURITY_CHANNEL_NAME}")
        except Exception as e:
            print(f"❌ فشل إنشاء روم الحماية: {e}")
    return channel

# ---------------------------------------------------------
# 3. أحداث الحماية السريعة والتنبيهات
# ---------------------------------------------------------

@bot.event
async def on_member_ban(guild: discord.Guild, user: discord.User):
    sec_channel = await get_security_channel(guild)
    actor = None

    try:
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
            actor = entry.user
            break
    except Exception as e:
        print(f"❌ فشل قراءة سجلات التدقيق: {e}")

    if not actor:
        await asyncio.sleep(0.4)
        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
                actor = entry.user
                break
        except Exception:
            pass

    if actor:
        if actor.id == bot.user.id:
            return

        has_protection = is_whitelisted(actor, guild)

        # 1. إذا كان الفاعل يملك رتبة حماية
        if has_protection:
            if sec_channel:
                embed = discord.Embed(
                    title="ℹ️ [تنبيه حظر معتمد]",
                    description="تم إجراء حظر بواسطة شخص يمتلك رتبة حماية (لم يتم فك الباند).",
                    color=discord.Color.blue(),
                    timestamp=datetime.datetime.now(datetime.timezone.utc)
                )
                embed.add_field(name="المبند :", value=actor.mention, inline=False)
                embed.add_field(name="المحظور :", value=user.mention, inline=False)
                await sec_channel.send(embed=embed)
            return

        # 2. إذا كان الفاعل بدون رتبة حماية (تخريب)
        try:
            await guild.unban(user, reason="🛡️ حماية تلقائية: إلغاء حظر غير مصرح")
        except Exception as e:
            print(f"❌ فشل فك الحظر: {e}")

        try:
            await guild.ban(actor, reason="🛡️ حماية تلقائية: حظر بدون رتبة حماية")
        except Exception as e:
            print(f"❌ فشل حظر الفاعل: {e}")

        if sec_channel:
            embed = discord.Embed(
                title="🚨 [حماية فورية] إلغاء حظر وتبنيد الفاعل", 
                color=discord.Color.red(), 
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            embed.add_field(name="المبند :", value=actor.mention, inline=False)
            embed.add_field(name="تم الغاء الحظر من :", value=user.mention, inline=False)
            await sec_channel.send(embed=embed)

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    member = message.author
    if is_whitelisted(member, message.guild):
        await bot.process_commands(message)
        return

    sec_channel = await get_security_channel(message.guild)

    if ("@everyone" in message.content or "@here" in message.content) and not member.guild_permissions.administrator:
        try:
            await message.delete()
        except Exception:
            pass
        if sec_channel:
            embed = discord.Embed(title="⚠️ [منع المنشن] منشن العام بدون صلاحية", color=discord.Color.gold())
            embed.add_field(name="👤 العضو:", value=member.mention, inline=True)
            embed.add_field(name="📍 القناة:", value=message.channel.mention, inline=True)
            await sec_channel.send(embed=embed)
        return

    if "discord.gg/" in message.content or "http://" in message.content or "https://" in message.content:
        try:
            await message.delete()
        except Exception:
            pass
        if sec_channel:
            embed = discord.Embed(title="🔗 [حظر الروابط] مسح رابط خارجي مخالف", color=discord.Color.red())
            embed.add_field(name="👤 العضو:", value=member.mention, inline=True)
            embed.add_field(name="📝 النص:", value=message.content, inline=False)
            await sec_channel.send(embed=embed)
        return

    await bot.process_commands(message)

# ---------------------------------------------------------
# 4. واجهات التذاكر الموحدة (UI Elements)
# ---------------------------------------------------------
class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="إغلاق التذكرة 🔒", style=discord.ButtonStyle.red, custom_id="close_ticket_btn")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🔒 سيتم إغلاق التذكرة وحذف القناة خلال 5 ثوانٍ...")
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete()
        except Exception:
            pass

class TicketSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        placeholder="اختر القطاع أو الخدمة الحكومية...",
        custom_id="main_ticket_select",
        options=[
            discord.SelectOption(label="⚖️ ديوان وزارة العدل (DOJ)", description="رفع دعوى، توكيل محامي، صكوك", value=ROLE_JUSTICE),
            discord.SelectOption(label="🚨 بلاغ الشرطة والداخلية (LSPD)", description="تقديم بلاغ أمني أو شكوى", value=ROLE_POLICE),
            discord.SelectOption(label="⚡ طلب قوة السوات (S.W.A.T)", description="بلاغ عمليات خاصة وتدخل سريع", value=ROLE_SWAT),
            discord.SelectOption(label="🚑 طوارئ الإسعاف والصحة (PHMC)", description="طلب إسعاف أو فحص طبي", value=ROLE_HEALTH),
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        guild = interaction.guild
        category_name = f"📂 تذاكر قطاع - {select.values[0]}"
        category = discord.utils.get(guild.categories, name=category_name)
        
        if not category:
            try:
                category = await guild.create_category(category_name)
            except Exception:
                category = None

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        try:
            ticket_channel = await guild.create_text_channel(
                name=f"تذكرة-{interaction.user.name}",
                category=category,
                overwrites=overwrites
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ حدث خطأ أثناء إنشاء التذكرة: {e}", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"📋 تذكرة جديدة - {select.values[0]}",
            description=f"أهلاً بك {interaction.user.mention} 👋\nيرجى كتابة تفاصيل طلبك أو بلاغك وسيتم خدمتك في أقرب وقت.",
            color=discord.Color.gold(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        await ticket_channel.send(embed=embed, view=TicketCloseView())
        await interaction.response.send_message(f"✅ تم فتح تذكرتك بنجاح: {ticket_channel.mention}", ephemeral=True)

# ---------------------------------------------------------
# 5. أوامر Slash الكاملة للقطاعات RP
# ---------------------------------------------------------

@bot.event
async def on_ready():
    bot.add_view(TicketSelectView())
    bot.add_view(TicketCloseView())
    try:
        synced = await bot.tree.sync()
        print(f"✅ تم مزامنة {len(synced)} أمر Slash بنجاح!")
    except Exception as e:
        print(f"❌ خطأ في المزامنة: {e}")
    print(f"⚡ البوت يعمل بنجاح كـ: {bot.user.name}")

@bot.tree.command(name="ticket-panel", description="إرسال لوحة فتح التذاكر الموحدة")
async def ticket_panel(interaction: discord.Interaction, channel: discord.TextChannel = None):
    dest = channel or interaction.channel
    embed = discord.Embed(
        title="🏙️ مركز الخدمات الحكومية والقطاعات RP",
        description="مرحباً بكم في بوابة التذاكر الحكومية.\nاختر القطاع المطلوب من القائمة أدناه للتواصل مع المسؤولين.",
        color=discord.Color.blue()
    )
    await dest.send(embed=embed, view=TicketSelectView())
    await interaction.response.send_message("✅ تم إرسال البانل بنجاح!", ephemeral=True)

# --- أوامر وزارة العدل (DOJ) ---
@bot.tree.command(name="create-deed", description="[DOJ] إصدار صك ملكية جديد")
async def create_deed(interaction: discord.Interaction, owner: discord.Member, property_type: str, details: str):
    if not check_role(interaction.user, ROLE_JUSTICE):
        await interaction.response.send_message("❌ هذا الأمر مخصص لأعضاء وزارة العدل فقط!", ephemeral=True)
        return
    embed = discord.Embed(title="📜 صك ملكية رسمي", color=discord.Color.gold(), timestamp=datetime.datetime.now(datetime.timezone.utc))
    embed.add_field(name="المالك:", value=owner.mention, inline=True)
    embed.add_field(name="نوع العقار/الملكية:", value=property_type, inline=True)
    embed.add_field(name="التفاصيل:", value=details, inline=False)
    embed.set_footer(text=f"تم الإصدار بواسطة: {interaction.user.name}")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="issue-warrant", description="[DOJ] إصدار أمر إلقاء قبض أو تفتيش قضائي")
async def issue_warrant(interaction: discord.Interaction, target: discord.Member, reason: str, warrant_type: str):
    if not check_role(interaction.user, ROLE_JUSTICE):
        await interaction.response.send_message("❌ هذا الأمر مخصص للقضاة ووزارة العدل فقط!", ephemeral=True)
        return
    embed = discord.Embed(title=f"⚖️ أمر قضائي رسمي ({warrant_type})", color=discord.Color.dark_red(), timestamp=datetime.datetime.now(datetime.timezone.utc))
    embed.add_field(name="المطلوب:", value=target.mention, inline=True)
    embed.add_field(name="السبب:", value=reason, inline=False)
    embed.set_footer(text=f"القاضي المصدر: {interaction.user.name}")
    await interaction.response.send_message(embed=embed)

# --- أوامر الشرطة (LSPD) ---
@bot.tree.command(name="911-dispatch", description="[LSPD] إرسال نداء عمليات أمني")
async def dispatch_911(interaction: discord.Interaction, code: str, location: str, details: str):
    if not check_role(interaction.user, ROLE_POLICE):
        await interaction.response.send_message("❌ هذا الأمر مخصص لأعضاء LSPD فقط!", ephemeral=True)
        return
    embed = discord.Embed(title=f"🚨 بلاغ عمليات - {code}", color=discord.Color.blue(), timestamp=datetime.datetime.now(datetime.timezone.utc))
    embed.add_field(name="الموقع:", value=location, inline=True)
    embed.add_field(name="المنادي:", value=interaction.user.mention, inline=True)
    embed.add_field(name="التفاصيل:", value=details, inline=False)
    await interaction.response.send_message(content="||@everyone||", embed=embed)

@bot.tree.command(name="add-record", description="[LSPD] إضافة سابقة جنائية لمواطن")
async def add_record(interaction: discord.Interaction, citizen: discord.Member, crime: str, fine: int, jail_time: str):
    if not check_role(interaction.user, ROLE_POLICE):
        await interaction.response.send_message("❌ هذا الأمر مخصص للشرطة فقط!", ephemeral=True)
        return
    if citizen.id not in criminal_records:
        criminal_records[citizen.id] = []
    
    record_entry = {
        "officer": interaction.user.name,
        "crime": crime,
        "fine": fine,
        "jail_time": jail_time,
        "date": str(datetime.date.today())
    }
    criminal_records[citizen.id].append(record_entry)
    
    embed = discord.Embed(title="📁 تسجيل سابقة جنائية", color=discord.Color.dark_blue(), timestamp=datetime.datetime.now(datetime.timezone.utc))
    embed.add_field(name="المواطن:", value=citizen.mention, inline=True)
    embed.add_field(name="التهمة:", value=crime, inline=False)
    embed.add_field(name="الغرامة:", value=f"${fine}", inline=True)
    embed.add_field(name="مدة السجن:", value=jail_time, inline=True)
    embed.set_footer(text=f"الضابط المسؤول: {interaction.user.name}")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="view-records", description="[LSPD] الاستعلام عن السجل الجنائي لمواطن")
async def view_records(interaction: discord.Interaction, citizen: discord.Member):
    if not check_role(interaction.user, ROLE_POLICE):
        await interaction.response.send_message("❌ هذا الأمر مخصص لأعضاء LSPD فقط!", ephemeral=True)
        return
    user_recs = criminal_records.get(citizen.id, [])
    if not user_recs:
        await interaction.response.send_message(f"✅ المواطن {citizen.mention} سجل جنائي نظيف وخالٍ من الجرائم.", ephemeral=True)
        return
    
    embed = discord.Embed(title=f"📊 السجل الجنائي لـ {citizen.name}", color=discord.Color.orange())
    for idx, rec in enumerate(user_recs, 1):
        embed.add_field(
            name=f"قضية #{idx} - {rec['date']}",
            value=f"**التهمة:** {rec['crime']}\n**الغرامة:** ${rec['fine']}\n**السجن:** {rec['jail_time']}\n**الضابط:** {rec['officer']}",
            inline=False
        )
    await interaction.response.send_message(embed=embed)

# --- أوامر السوات (SWAT) ---
@bot.tree.command(name="swat-deploy", description="[SWAT] نداء إعلان حالة الطوارئ والتدخل السريع")
async def swat_deploy(interaction: discord.Interaction, zone: str, threat_level: str):
    if not check_role(interaction.user, ROLE_SWAT):
        await interaction.response.send_message("❌ هذا الأمر مخصص لقوات السوات فقط!", ephemeral=True)
        return
    embed = discord.Embed(title="⚡ نداء استنفرار وقوات التدخل السريع SWAT", color=discord.Color.dark_purple(), timestamp=datetime.datetime.now(datetime.timezone.utc))
    embed.add_field(name="منطقة العمليات:", value=zone, inline=True)
    embed.add_field(name="مستوى الخطر:", value=threat_level, inline=True)
    embed.add_field(name="التعليمات:", value="التوجه للموقع بالعتاد الكامل والاشتباك وفق قواعد الإطلاق.", inline=False)
    await interaction.response.send_message(content="||@everyone||", embed=embed)

# --- أوامر الصحة والإسعاف (PHMC) ---
@bot.tree.command(name="medical-report", description="[PHMC] إصدار تقرير طبي رسمي")
async def medical_report(interaction: discord.Interaction, patient: discord.Member, status: str, treatment: str):
    if not check_role(interaction.user, ROLE_HEALTH):
        await interaction.response.send_message("❌ هذا الأمر مخصص للقطاع الطبي فقط!", ephemeral=True)
        return
    embed = discord.Embed(title="🚑 تقرير طبي رسمي - مستشفى المركز", color=discord.Color.green(), timestamp=datetime.datetime.now(datetime.timezone.utc))
    embed.add_field(name="المريض:", value=patient.mention, inline=True)
    embed.add_field(name="الحالة التشخيصية:", value=status, inline=True)
    embed.add_field(name="العلاج أو الإجراء:", value=treatment, inline=False)
    embed.set_footer(text=f"الطبيب المعالج: {interaction.user.name}")
    await interaction.response.send_message(embed=embed)

# ---------------------------------------------------------
# 6. التشغيل الرئيسي
# ---------------------------------------------------------
if __name__ == "__main__":
    keep_alive()
    TOKEN = os.getenv("DISCORD_TOKEN")
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("❌ لم يتم العثور على DISCORD_TOKEN في متغيرات البيئة!")
