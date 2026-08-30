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
# 1. خادم الويب (Keep Alive)
# ---------------------------------------------------------
web_app = Flask('')

@web_app.route('/')
def home():
    return "Bot is active!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# ---------------------------------------------------------
# 2. إعداد البوت الصارم والسريع
# ---------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.moderation = True

bot = commands.Bot(command_prefix="-", intents=intents)

ROLE_JUSTICE = "𝗠𝗧 | Justice"
ROLE_POLICE = "𝗠𝗧 | LSPD"
ROLE_SWAT = "𝗠𝗧 | S.W.A.T"
ROLE_HEALTH = "𝗠𝗧 | PHMC"

WHITELIST_ROLES = ["#", "MT | Owner", "MT | COowner", "MT | Ceo", "MT | Founders", "bot", "Bot"]
SECURITY_CHANNEL_NAME = "📑┃حماية"

criminal_records = {}
user_message_logs = defaultdict(list)

def is_whitelisted(user: discord.Member) -> bool:
    if not isinstance(user, discord.Member):
        return False
    if user.id == user.guild.owner_id:
        return True
    user_role_names = [role.name for role in user.roles]
    return any(w_role in user_role_names for w_role in WHITELIST_ROLES)

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
# 3. أحداث الحماية الفائقة (سرعة 0.1s)
# ---------------------------------------------------------

@bot.event
async def on_member_ban(guild: discord.Guild, user: discord.User):
    # تنفيذ فوري بدون تأخير طويل (0.1 ثانية)
    await asyncio.sleep(0.1)
    
    sec_channel = await get_security_channel(guild)
    actor = None

    try:
        async for entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.ban):
            if entry.target and entry.target.id == user.id:
                actor = entry.user
                break
    except Exception as e:
        print(f"Audit Log Error: {e}")

    # إذا لم نجد الفاعل من السجل، نأخذ آخر شخص قام بالبند
    if not actor:
        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
                actor = entry.user
        except Exception:
            pass

    if actor:
        # تحويل الفاعل إلى Member للتحقق من الرتب
        actor_member = guild.get_member(actor.id)
        
        # إذا كان الفاعل مصرحاً له أو صاحب السيرفر، لا تفعل شيئاً
        if actor_member and is_whitelisted(actor_member):
            return

        # 1. تبنيد الفاعل المخالف فوراً (0.1s)
        try:
            await guild.ban(actor, reason="🛡️ حماية سرعة 0.1s: حظر عضو بدون تصريح")
        except Exception as e:
            print(f"Failed to ban actor: {e}")

        # 2. فك الحظر عن المظلوم فوراً (0.1s)
        try:
            await guild.unban(user, reason="🛡️ حماية سرعة 0.1s: فك حظر تلقائي")
        except Exception as e:
            print(f"Failed to unban target: {e}")

        # 3. إرسال الإشعار لروم الحماية فوراً
        if sec_channel:
            embed = discord.Embed(
                title="🚨 [حماية فورية 0.1s] محاولة حظر تخريبية", 
                color=discord.Color.red(), 
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            embed.add_field(name="👤 المخالف (تم تبنيده):", value=f"{actor.mention} (`{actor.id}`)", inline=False)
            embed.add_field(name="👤 العضو (تم فك حظره):", value=f"{user.mention} (`{user.id}`)", inline=False)
            await sec_channel.send(embed=embed)

@bot.event
async def on_member_join(member: discord.Member):
    sec_channel = await get_security_channel(member.guild)
    
    # 1. فحص البوتات المضافة بسرعة 0.1 ثانية
    if member.bot:
        await asyncio.sleep(0.1)
        actor = None
        try:
            async for entry in member.guild.audit_logs(limit=1, action=discord.AuditLogAction.bot_add):
                actor = entry.user
        except Exception:
            pass

        if actor:
            actor_member = member.guild.get_member(actor.id)
            if actor_member and not is_whitelisted(actor_member):
                try:
                    await member.ban(reason="🛡️ حماية: دخول بوت غير مصرح")
                    await actor.ban(reason="🛡️ حماية: إدخال بوت مشبوه")
                except Exception:
                    pass
                
                if sec_channel:
                    embed = discord.Embed(title="🛡️ [حماية البوتات] طرد وتدعيم فورية", color=discord.Color.dark_red(), timestamp=datetime.datetime.now(datetime.timezone.utc))
                    embed.add_field(name="🤖 البوت (تبنيد):", value=member.mention, inline=False)
                    embed.add_field(name="👤 المسؤول (تبنيد):", value=actor.mention, inline=False)
                    await sec_channel.send(embed=embed)
                return

    # 2. فحص الحسابات المشبوهة
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    account_age = (now_utc - member.created_at).days
    forbidden_keywords = ["hacked", "hack", "اختراق", "تفجير", "تخريب"]
    has_forbidden_name = any(kw in member.display_name.lower() for kw in forbidden_keywords)

    if account_age < 1 or has_forbidden_name:
        try:
            await member.ban(reason="🛡️ حماية: حساب مخترق/جديد جداً")
            if sec_channel:
                embed = discord.Embed(title="🚨 [حماية الحسابات] تبنيد حساب مشبوه", color=discord.Color.orange(), timestamp=datetime.datetime.now(datetime.timezone.utc))
                embed.add_field(name="👤 الحساب (تبنيد):", value=f"{member.mention} ({member.id})", inline=False)
                embed.add_field(name="📝 السبب:", value=f"عمر الحساب ({account_age} يوم) أو الاسم مخالف", inline=False)
                await sec_channel.send(embed=embed)
        except Exception:
            pass

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    member = message.author
    if is_whitelisted(member):
        await bot.process_commands(message)
        return

    sec_channel = await get_security_channel(message.guild)

    # 1. منع @everyone و @here فوراً
    if ("@everyone" in message.content or "@here" in message.content) and not member.guild_permissions.administrator:
        await message.delete()
        if sec_channel:
            embed = discord.Embed(title="⚠️ [منع المنشن] منشن العام بدون صلاحية", color=discord.Color.gold())
            embed.add_field(name="👤 العضو:", value=member.mention, inline=True)
            embed.add_field(name="📍 القناة:", value=message.channel.mention, inline=True)
            await sec_channel.send(embed=embed)
        return

    # 2. منع الروابط فوراً
    if "discord.gg/" in message.content or "http://" in message.content or "https://" in message.content:
        await message.delete()
        if sec_channel:
            embed = discord.Embed(title="🔗 [حظر الروابط] مسح رابط مخالف", color=discord.Color.red())
            embed.add_field(name="👤 العضو:", value=member.mention, inline=True)
            embed.add_field(name="📝 النص:", value=message.content, inline=False)
            await sec_channel.send(embed=embed)
        return

    # 3. سبام (5 رسائل في ثانيتين)
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
            await member.timeout(timeout_until, reason="🛡️ إسبام: 5 رسائل خلال ثانيتين")
            await message.channel.send(f"🔇 تم إعطاء {member.mention} ميوت لمدة دقيقتين بسبب الإسبام.", delete_after=5)
            
            def is_user_msg(m): return m.author.id == user_id
            await message.channel.purge(limit=5, check=is_user_msg)

            if sec_channel:
                embed = discord.Embed(title="🔇 [ميوت سبام] تايم آوت تلقائي", color=discord.Color.blue())
                embed.add_field(name="👤 العضو:", value=member.mention, inline=True)
                embed.add_field(name="⏱️ السبب:", value="5 رسائل في ثانيتين", inline=True)
                await sec_channel.send(embed=embed)
        except Exception:
            pass

    await bot.process_commands(message)

# ---------------------------------------------------------
# 4. التذاكر والأوامر (كما هي دون تغيير)
# ---------------------------------------------------------
class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="إغلاق التذكرة 🔒", style=discord.ButtonStyle.red, custom_id="close_ticket_btn")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("سيتم إغلاق التذكرة خلال 5 ثوانٍ...")
        await asyncio.sleep(5)
        await interaction.channel.delete()

class TicketSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        placeholder="اختر القطاع أو الخدمة...",
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
            category = await guild.create_category(category_name)

        ticket_channel = await guild.create_text_channel(
            name=f"تذكرة-{interaction.user.name}",
            category=category,
            overwrites={
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
        )

        embed = discord.Embed(
            title=f"📋 تذكرة جديدة - {select.values[0]}",
            description=f"أهلاً بك {interaction.user.mention} 👋\nيرجى كتابة التفاصيل وسيقوم المختص بالرد عليك.",
            color=discord.Color.gold(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        await ticket_channel.send(embed=embed, view=TicketCloseView())
        await interaction.response.send_message(f"✅ تم فتح تذكرتك بنجاح: {ticket_channel.mention}", ephemeral=True)

@bot.event
async def on_ready():
    bot.add_view(TicketSelectView())
    bot.add_view(TicketCloseView())
    try:
        synced = await bot.tree.sync()
        print(f"✅ تم مزامنة {len(synced)} أمر Slash!")
    except Exception as e:
        print(f"❌ خطأ في المزامنة: {e}")
    print(f"⚡ البوت يعمل بجميع وظائف الحماية السريعة (0.1s): {bot.user.name}")

# --- باقي الأوامر ---
@bot.tree.command(name="ticket-panel", description="إرسال لوحة فتح التذاكر الموحدة")
async def ticket_panel(interaction: discord.Interaction, channel: discord.TextChannel = None):
    dest = channel or interaction.channel
    embed = discord.Embed(
        title="🏙️ مركز الخدمات الحكومية والقطاعات RP",
        description="مرحباً بكم في بوابة التذاكر الحكومية.\nاختر القطاع المطلوب للتواصل مع المسؤولين.",
        color=discord.Color.blue()
    )
    await dest.send(embed=embed, view=TicketSelectView())
    await interaction.response.send_message("✅ تم إرسال البانل بنجاح!", ephemeral=True)

if __name__ == "__main__":
    keep_alive()
    TOKEN = os.getenv("DISCORD_TOKEN")
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("❌ لم يتم العثور على DISCORD_TOKEN!")
