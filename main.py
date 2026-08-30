import os
import asyncio
import datetime
from collections import defaultdict
from threading import Thread
from flask import Flask
import discord
from discord import app_commands
from discord.ext import commands

# ---------------------------------------------------------
# 1. خادم الويب (Keep Alive 24/7)
# ---------------------------------------------------------
web_app = Flask('')

@web_app.route('/')
def home():
    return "Roleplay & Security Bot is active 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

# ---------------------------------------------------------
# 2. إعداد البوت والقوائم
# ---------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.bans = True
intents.moderation = True

bot = commands.Bot(command_prefix="-", intents=intents)

# 🏷️ أسماء رتب القطاعات الحكومية
ROLE_JUSTICE = "𝗠𝗧 | Justice"
ROLE_POLICE = "𝗠𝗧 | LSPD"
ROLE_SWAT = "𝗠𝗧 | S.W.A.T"
ROLE_HEALTH = "𝗠𝗧 | PHMC"

# 🛡️ أسماء الرتب المستثناة من الحماية (Whitelist)
WHITELIST_ROLES = [
    "#", 
    "MT | Owner ↔", 
    "MT | COowner ↔", 
    "MT | Ceo", 
    "MT | FOUNDERS", 
    "Appy", 
    "Bot", 
    "bot"
]

# 🆔 أرقام الـ IDs للرتب (اختياري - ضعه مستقبلاً إن أردت)
WHITELIST_ROLE_IDS = []

# 🆔 أرقام البوتات الموثوقة المستثناة من الحظر
ALLOWED_BOT_IDS = []

SECURITY_CHANNEL_NAME = "📑┃حماية"

criminal_records = {}
user_message_logs = defaultdict(list)

def is_whitelisted(user: discord.User | discord.Member, guild: discord.Guild = None) -> bool:
    """التحقق الحقيقي والدقيق من استثناء العضو (مالك، أدمن، أو رتبة مستثناة)"""
    if not user:
        return False
    
    member = user
    if guild and not isinstance(user, discord.Member):
        member = guild.get_member(user.id)

    if guild and member and member.id == guild.owner_id:
        return True

    if isinstance(member, discord.Member) and member.guild_permissions.administrator:
        return True

    if isinstance(member, discord.Member):
        user_role_ids = [role.id for role in member.roles]
        if any(r_id in user_role_ids for r_id in WHITELIST_ROLE_IDS):
            return True

        user_role_names = [role.name for role in member.roles]
        if any(w_role in user_role_names for w_role in WHITELIST_ROLES):
            return True

    return False

def check_role(user: discord.Member, role_name: str) -> bool:
    user_role_names = [role.name for role in user.roles]
    return role_name in user_role_names

async def get_security_channel(guild: discord.Guild):
    channel = discord.utils.get(guild.text_channels, name=SECURITY_CHANNEL_NAME)
    if not channel:
        try:
            channel = await guild.create_text_channel(SECURITY_CHANNEL_NAME)
        except Exception:
            pass
    return channel

# ---------------------------------------------------------
# 3. أحداث الحماية الأمنية المتقدمة (Anti-Nuke / Anti-Spam)
# ---------------------------------------------------------

@bot.event
async def on_member_ban(guild: discord.Guild, user: discord.User):
    await asyncio.sleep(0.3)
    sec_channel = await get_security_channel(guild)
    actor = None

    try:
        async for entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.ban):
            if entry.target and entry.target.id == user.id:
                actor = entry.user
                break
    except Exception:
        pass

    if not actor:
        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
                actor = entry.user
        except Exception:
            pass

    if actor and actor.id != bot.user.id:
        if is_whitelisted(actor, guild):
            if sec_channel:
                embed = discord.Embed(
                    title="ℹ️ تنبيه: حظر معتمد",
                    description=f"**المبند:** {actor.mention}\n**المحظور:** {user.mention}",
                    color=discord.Color.blue(),
                    timestamp=datetime.datetime.now(datetime.timezone.utc)
                )
                await sec_channel.send(embed=embed)
            return

        try:
            await guild.unban(user, reason="🛡️ حماية: فك حظر تلقائي")
        except Exception:
            pass

        try:
            await guild.ban(actor, reason="🛡️ حماية: محاولة تخريب وحظر بدون صلاحية")
        except Exception:
            pass

        if sec_channel:
            embed = discord.Embed(
                title="🚨 [حماية فورية] كشف تخريب وتبنيد الفاعل", 
                color=discord.Color.red(), 
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            embed.add_field(name="👤 المخالف (تم تبنيده فوراً):", value=f"{actor.mention} (`{actor.id}`)", inline=False)
            embed.add_field(name="👤 العضو (تم فك حظره):", value=f"{user.mention} (`{user.id}`)", inline=False)
            await sec_channel.send(embed=embed)

@bot.event
async def on_member_join(member: discord.Member):
    sec_channel = await get_security_channel(member.guild)
    
    if member.bot:
        if member.id in ALLOWED_BOT_IDS:
            return

        await asyncio.sleep(0.3)
        actor = None
        try:
            async for entry in member.guild.audit_logs(limit=1, action=discord.AuditLogAction.bot_add):
                actor = entry.user
        except Exception:
            pass

        if actor and actor.id != bot.user.id:
            if not is_whitelisted(actor, member.guild):
                try:
                    await member.ban(reason="🛡️ حماية: دخول بوت غير مصرح")
                    await member.guild.ban(actor, reason="🛡️ حماية: إدخال بوت مشبوه")
                except Exception:
                    pass
                
                if sec_channel:
                    embed = discord.Embed(title="🛡️ [حماية البوتات] طرد وتبنيد", color=discord.Color.dark_red(), timestamp=datetime.datetime.now(datetime.timezone.utc))
                    embed.add_field(name="🤖 البوت:", value=member.mention, inline=False)
                    embed.add_field(name="👤 المسؤول:", value=actor.mention, inline=False)
                    await sec_channel.send(embed=embed)
                return

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    account_age = (now_utc - member.created_at).days
    forbidden_keywords = ["hacked", "hack", "اختراق", "تفجير", "تخريب"]
    has_forbidden_name = any(kw in member.display_name.lower() for kw in forbidden_keywords)

    if account_age < 1 or has_forbidden_name:
        try:
            await member.ban(reason="🛡️ حماية: حساب وهمي أو مشبوه")
            if sec_channel:
                embed = discord.Embed(title="🚨 [حماية الحسابات] تبنيد حساب مشبوه", color=discord.Color.orange(), timestamp=datetime.datetime.now(datetime.timezone.utc))
                embed.add_field(name="👤 الحساب:", value=f"{member.mention} (`{member.id}`)", inline=False)
                embed.add_field(name="📝 السبب:", value=f"عمر الحساب ({account_age} يوم) أو الاسم مخالف", inline=False)
                await sec_channel.send(embed=embed)
        except Exception:
            pass

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

    now_time = datetime.datetime.now(datetime.timezone.utc)
    user_id = member.id
    user_message_logs[user_id].append(now_time)

    user_message_logs[user_id] = [
        t for t in user_message_logs[user_id]
        if (now_time - t).total_seconds() <= 2
    ]

    if len(user_message_logs[user_id]) >= 5:
        user_message_logs[user_id].clear()
        timeout_until = now_time + datetime.timedelta(minutes=2)
        try:
            await member.timeout(timeout_until, reason="🛡️ إسبام: إرسال 5 رسائل خلال ثانيتين")
            await message.channel.send(f"🔇 تم إعطاء {member.mention} ميوت لمدة دقيقتين بسبب الإسبام.", delete_after=5)
            
            def is_user_msg(m): return m.author.id == user_id
            await message.channel.purge(limit=5, check=is_user_msg)

            if sec_channel:
                embed = discord.Embed(title="🔇 [ميوت سبام] تايم آوت تلقائي", color=discord.Color.blue())
                embed.add_field(name="👤 العضو:", value=member.mention, inline=True)
                embed.add_field(name="⏱️ السبب:", value="إرسال رسائل متكررة بسرعة عالية", inline=True)
                await sec_channel.send(embed=embed)
        except Exception:
            pass

    await bot.process_commands(message)

# ---------------------------------------------------------
# 4. نظام التذاكر والقطاعات والأزرار
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
# 5. تشغيل البوت وتسجيل الأوامر
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

@bot.tree.command(name="set-trial", description="[DOJ] تحديد موعد محاكمة جديدة")
async def set_trial(interaction: discord.Interaction, defendant: discord.Member, judge: discord.Member, date_time: str, location: str):
    if not check_role(interaction.user, ROLE_JUSTICE):
        await interaction.response.send_message("❌ هذا الأمر مخصص لأعضاء وزارة العدل فقط!", ephemeral=True)
        return
    embed = discord.Embed(title="⚖️ إشعار موعد محاكمة", color=discord.Color.dark_purple(), timestamp=datetime.datetime.now(datetime.timezone.utc))
    embed.add_field(name="المتهم:", value=defendant.mention, inline=True)
    embed.add_field(name="القاضي المكلف:", value=judge.mention, inline=True)
    embed.add_field(name="الموعد:", value=date_time, inline=False)
    embed.add_field(name="المكان:", value=location, inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="add-charge", description="[DOJ] تسجيل تهمة في السجل الجنائي")
async def add_charge(interaction: discord.Interaction, target: discord.Member, charge: str, fine: int = 0):
    if not check_role(interaction.user, ROLE_JUSTICE):
        await interaction.response.send_message("❌ هذا الأمر مخصص لأعضاء وزارة العدل فقط!", ephemeral=True)
        return
    if target.id not in criminal_records:
        criminal_records[target.id] = []
    criminal_records[target.id].append({"charge": charge, "fine": fine, "date": datetime.date.today().strftime("%Y-%m-%d")})
    embed = discord.Embed(title="🚨 تسجيل سابقة جنائية", color=discord.Color.red())
    embed.add_field(name="المتهم:", value=target.mention, inline=True)
    embed.add_field(name="التهمة:", value=charge, inline=True)
    embed.add_field(name="الغرامة:", value=f"${fine:,}", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="check-charges", description="[DOJ] عرض السجل الجنائي لعضو")
async def check_charges(interaction: discord.Interaction, target: discord.Member):
    records = criminal_records.get(target.id, [])
    if not records:
        await interaction.response.send_message(f"✅ السجل الجنائي لـ {target.mention} نظيف تماماً.", ephemeral=True)
        return
    embed = discord.Embed(title=f"📁 السجل الجنائي لـ {target.display_name}", color=discord.Color.dark_red())
    for idx, rec in enumerate(records, 1):
        embed.add_field(name=f"سابقة #{idx} ({rec['date']})", value=f"التهمة: {rec['charge']}\nالغرامة: ${rec['fine']:,}", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

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

@bot.tree.command(name="log-inspection", description="[LSPD] محضر تفتيش شخص أو مركبة")
async def log_inspection(interaction: discord.Interaction, suspect: discord.Member, items_found: str, status: str):
    if not check_role(interaction.user, ROLE_POLICE):
        await interaction.response.send_message("❌ هذا الأمر مخصص لأعضاء LSPD فقط!", ephemeral=True)
        return
    embed = discord.Embed(title="🔍 محضر تفتيش أمني", color=discord.Color.dark_blue())
    embed.add_field(name="المشتبه به:", value=suspect.mention, inline=True)
    embed.add_field(name="المضبوطات:", value=items_found, inline=False)
    embed.add_field(name="الإجراء المتخذ:", value=status, inline=False)
    embed.set_footer(text=f"الضابط المسؤول: {interaction.user.name}")
    await interaction.response.send_message(embed=embed)

# --- أوامر السوات (S.W.A.T) ---
@bot.tree.command(name="code-red", description="[SWAT] إعلان حالة الاستنفار القصوى")
async def code_red(interaction: discord.Interaction, zone: str, reason: str):
    if not check_role(interaction.user, ROLE_SWAT):
        await interaction.response.send_message("❌ هذا الأمر مخصص لقوات S.W.A.T فقط!", ephemeral=True)
        return
    embed = discord.Embed(title="⚠️ إعلان حالة استنفار حمراء (CODE RED)", color=discord.Color.dark_red(), timestamp=datetime.datetime.now(datetime.timezone.utc))
    embed.add_field(name="المنطقة المحظورة:", value=zone, inline=True)
    embed.add_field(name="السبب:", value=reason, inline=False)
    embed.add_field(name="تعليمات:", value="يُمنع اقتراب المدنيين، سيتم التعامل المباشر بالقوة القاتلة.", inline=False)
    await interaction.response.send_message(content="||@everyone||", embed=embed)

@bot.tree.command(name="raid-plan", description="[SWAT] اصدار خطة مداهمة أمنية")
async def raid_plan(interaction: discord.Interaction, target_location: str, team_leader: discord.Member, entry_point: str):
    if not check_role(interaction.user, ROLE_SWAT):
        await interaction.response.send_message("❌ هذا الأمر مخصص لقوات S.W.A.T فقط!", ephemeral=True)
        return
    embed = discord.Embed(title="⚔️ أمر مداهمة ومعالجة أمنية", color=discord.Color.red())
    embed.add_field(name="الموقع المستهدف:", value=target_location, inline=True)
    embed.add_field(name="قائد الميدان:", value=team_leader.mention, inline=True)
    embed.add_field(name="نقطة الاقتحام:", value=entry_point, inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# --- أوامر الصحة (PHMC) ---
@bot.tree.command(name="medical-triage", description="[PHMC] إصدار تقرير طبي وفحص")
async def medical_triage(interaction: discord.Interaction, patient: discord.Member, condition: str, treatment: str):
    if not check_role(interaction.user, ROLE_HEALTH):
        await interaction.response.send_message("❌ هذا الأمر مخصص لطاقم PHMC فقط!", ephemeral=True)
        return
    embed = discord.Embed(title="🏥 تقرير حالة طبية", color=discord.Color.green(), timestamp=datetime.datetime.now(datetime.timezone.utc))
    embed.add_field(name="المريض:", value=patient.mention, inline=True)
    embed.add_field(name="التشخيص:", value=condition, inline=True)
    embed.add_field(name="العلاج الموصوف:", value=treatment, inline=False)
    embed.set_footer(text=f"الطبيب المعالج: {interaction.user.name}")
    await interaction.response.send_message(embed=embed)

# ---------------------------------------------------------
# 6. التشغيل النهائي
# ---------------------------------------------------------
if __name__ == "__main__":
    keep_alive()
    TOKEN = os.getenv("DISCORD_TOKEN")
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("❌ لم يتم العثور على DISCORD_TOKEN في متغيرات البيئة!")
