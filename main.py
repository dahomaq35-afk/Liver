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
    return "Bot is alive 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# ---------------------------------------------------------
# 2. إعداد البوت والدوال الأساسية
# ---------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.moderation = True

bot = commands.Bot(command_prefix="-", intents=intents)

# 🏷️ أسماء رتب القطاعات الحكومية
ROLE_JUSTICE = "𝗠𝗧 | Justice"
ROLE_POLICE = "𝗠𝗧 | LSPD"
ROLE_SWAT = "𝗠𝗧 | S.W.A.T"
ROLE_HEALTH = "𝗠𝗧 | PHMC"

# 🛡️ رتب القائمة البيضاء (الاستثناء من الحماية)
WHITELIST_ROLES = ["#", "MT | Owner", "MT | COowner", "MT | Ceo", "MT | Founders", "bot", "Bot"]

# 📂 اسم روم الحماية والبلاغات
SECURITY_CHANNEL_NAME = "📑┃حماية"

# قواعد البيانات المؤقتة ومسجل الرسائل
criminal_records = {}
user_message_logs = defaultdict(list)

# دالة التحقق من الاستثناء
def is_whitelisted(user: discord.Member) -> bool:
    if not isinstance(user, discord.Member):
        return False
    if user.id == user.guild.owner_id:
        return True
    
    user_role_names = [role.name for role in user.roles]
    return any(w_role in user_role_names for w_role in WHITELIST_ROLES)

# دالة التحقق من رتبة القطاع
def check_role(user: discord.Member, role_name: str) -> bool:
    user_role_names = [role.name for role in user.roles]
    return role_name in user_role_names

# دالة جلب/إنشاء روم الحماية
async def get_security_channel(guild: discord.Guild):
    channel = discord.utils.get(guild.text_channels, name=SECURITY_CHANNEL_NAME)
    if not channel:
        try:
            channel = await guild.create_text_channel(SECURITY_CHANNEL_NAME)
        except Exception:
            pass
    return channel

# ---------------------------------------------------------
# 3. أحداث الحماية المعدلة (Anti-Ban, Anti-Bot, Anti-Spam)
# ---------------------------------------------------------

# 🚨 حماية من حظر/طرد الأعضاء (معدلة ومضمونة)
@bot.event
async def on_member_ban(guild: discord.Guild, user: discord.User):
    sec_channel = await get_security_channel(guild)
    await asyncio.sleep(1)  # انتظار ثانية لضمان تسجيل الحدث في السجلات

    actor = None
    try:
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
            if entry.target.id == user.id:
                actor = entry.user
                break
    except Exception as e:
        print(f"❌ خطأ في قراءة الـ Audit Log: {e}")

    if actor and isinstance(actor, discord.Member):
        # إذا كان الفاعل مصرحاً له (في القائمة البيضاء أو المالك)، يتجاهل الأمر
        if is_whitelisted(actor):
            return

        # 1. تبنيد الشخص المخالف
        try:
            await guild.ban(actor, reason="🛡️ حماية: حظر عضو بدون تصريح")
        except Exception as e:
            print(f"❌ فشل حظر المخالف: {e}")

        # 2. فك الحظر عن العضو المظلوم
        try:
            await guild.unban(user, reason="🛡️ حماية: إلغاء الحظر التلقائي")
        except Exception as e:
            print(f"❌ فشل فك حظر العضو: {e}")

        # 3. إرسال الإشعار لروم الحماية
        if sec_channel:
            embed = discord.Embed(
                title="🚨 [تنبيه أمني] محاولة حظر تخريبية", 
                color=discord.Color.red(), 
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            embed.add_field(name="👤 المخالف (تم تبنيده):", value=f"{actor.mention} (`{actor.id}`)", inline=False)
            embed.add_field(name="👤 العضو (تم فك حظره):", value=f"{user.mention} (`{user.id}`)", inline=False)
            await sec_channel.send(embed=embed)

# 🤖 / 👤 فحص الحسابات والبوتات عند الدخول
@bot.event
async def on_member_join(member: discord.Member):
    sec_channel = await get_security_channel(member.guild)
    
    # 1. فحص البوتات
    if member.bot:
        await asyncio.sleep(1)
        async for entry in member.guild.audit_logs(limit=1, action=discord.AuditLogAction.bot_add):
            actor = entry.user
            if actor and isinstance(actor, discord.Member) and not is_whitelisted(actor):
                try:
                    await member.ban(reason="🛡️ حماية: بوت غير مصرح به")
                    await actor.ban(reason="🛡️ حماية: إدخال بوت مشبوه")
                except Exception:
                    pass
                
                if sec_channel:
                    embed = discord.Embed(title="🛡️ [حماية البوتات] طرد وتدعيم بوت", color=discord.Color.dark_red(), timestamp=datetime.datetime.now(datetime.timezone.utc))
                    embed.add_field(name="🤖 البوت (تم تبنيده):", value=member.mention, inline=False)
                    embed.add_field(name="👤 المسؤول (تم تبنيده):", value=actor.mention, inline=False)
                    await sec_channel.send(embed=embed)
                return

    # 2. فحص الحسابات المشبوهة
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    account_age = (now_utc - member.created_at).days
    forbidden_keywords = ["hacked", "hack", "اختراق", "تفجير", "تخريب"]
    has_forbidden_name = any(kw in member.display_name.lower() for kw in forbidden_keywords)

    if account_age < 1 or has_forbidden_name:
        try:
            await member.ban(reason="🛡️ حماية: حساب مخترق/مشبوه")
            if sec_channel:
                embed = discord.Embed(title="🚨 [حماية الحسابات] تبنيد حساب مشبوه", color=discord.Color.orange(), timestamp=datetime.datetime.now(datetime.timezone.utc))
                embed.add_field(name="👤 الحساب (تم تبنيده):", value=f"{member.mention} ({member.id})", inline=False)
                embed.add_field(name="📝 السبب:", value=f"عمر الحساب ({account_age} يوم) أو الاسم مخالف", inline=False)
                await sec_channel.send(embed=embed)
        except Exception:
            pass

# 💬 حماية الشات، الروابط، السبام، والمنشن
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    member = message.author
    if is_whitelisted(member):
        await bot.process_commands(message)
        return

    sec_channel = await get_security_channel(message.guild)

    # 1. منع @everyone و @here
    if ("@everyone" in message.content or "@here" in message.content) and not member.guild_permissions.administrator:
        await message.delete()
        if sec_channel:
            embed = discord.Embed(title="⚠️ [منع المنشن] منشن العام بدون صلاحية", color=discord.Color.gold())
            embed.add_field(name="👤 العضو:", value=member.mention, inline=True)
            embed.add_field(name="📍 القناة:", value=message.channel.mention, inline=True)
            await sec_channel.send(embed=embed)
        return

    # 2. منع الروابط
    if "discord.gg/" in message.content or "http://" in message.content or "https://" in message.content:
        await message.delete()
        if sec_channel:
            embed = discord.Embed(title="🔗 [حظر الروابط] مسح رابط مخالف", color=discord.Color.red())
            embed.add_field(name="👤 العضو:", value=member.mention, inline=True)
            embed.add_field(name="📝 النص:", value=message.content, inline=False)
            await sec_channel.send(embed=embed)
        return

    # 3. نظام الإسبام (5 رسائل خلال ثانيتين)
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
                embed.add_field(name="⏱️ السبب والمدة:", value="5 رسائل في ثانيتين (دقيقتين ميوت)", inline=True)
                await sec_channel.send(embed=embed)
        except Exception:
            pass

    await bot.process_commands(message)

# ---------------------------------------------------------
# 4. نظام التذاكر
# ---------------------------------------------------------
class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="إغلاق التذكرة 🔒", style=discord.ButtonStyle.red, custom_id="close_ticket_btn")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("سيتم إغلاق التذكرة ومسح القناة خلال 5 ثوانٍ...")
        await asyncio.sleep(5)
        await interaction.channel.delete()

class TicketSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        placeholder="اختر القطاع أو الخدمة المطلوب التواصل معها...",
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

# ---------------------------------------------------------
# 5. الأحداث والمزامنة
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
    print(f"⚖️ البوت جاهز ويعمل باسم: {bot.user.name}")

# ---------------------------------------------------------
# 6. أوامر القطاعات (Justice, LSPD, SWAT, PHMC)
# ---------------------------------------------------------
@bot.tree.command(name="create-deed", description="[Justice] تسجيل صك ملكية أو عقد رسمي بين طرفين")
@app_commands.describe(owner="صاحب الملكية", property_type="نوع العقار/السيارة", details="تفاصيل الصك", target_channel="القناة (اختياري)")
async def create_deed(interaction: discord.Interaction, owner: discord.Member, property_type: str, details: str, target_channel: discord.TextChannel = None):
    if not check_role(interaction.user, ROLE_JUSTICE):
        return await interaction.response.send_message(f"❌ هذا الأمر مخصص لرتبة **{ROLE_JUSTICE}** فقط!", ephemeral=True)

    dest = target_channel or interaction.channel
    embed = discord.Embed(title="📜 صك ملكية رسمي", color=discord.Color.gold(), timestamp=datetime.datetime.now(datetime.timezone.utc))
    embed.add_field(name="👤 المالـك:", value=owner.mention, inline=True)
    embed.add_field(name="🏠 نوع الملكية:", value=property_type, inline=True)
    embed.add_field(name="📝 تفاصيل الصك:", value=details, inline=False)
    embed.add_field(name="⚖️ توثيق القاضي:", value=interaction.user.mention, inline=True)
    await dest.send(embed=embed)
    await interaction.response.send_message(f"✅ تم إرسال الصك إلى {dest.mention}", ephemeral=True)

@bot.tree.command(name="set-trial", description="[Justice] تحديد موعد جلسة محاكمة وتنبيه المتهم")
@app_commands.describe(target="المتهم", date_time="تاريخ ووقت الجلسة", room="القاعة/الروم", target_channel="القناة (اختياري)")
async def set_trial(interaction: discord.Interaction, target: discord.Member, date_time: str, room: discord.TextChannel, target_channel: discord.TextChannel = None):
    if not check_role(interaction.user, ROLE_JUSTICE):
        return await interaction.response.send_message(f"❌ هذا الأمر مخصص لرتبة **{ROLE_JUSTICE}** فقط!", ephemeral=True)

    dest = target_channel or interaction.channel
    embed = discord.Embed(title="⚖️ استدعاء وجلسة محاكمة رسمية", color=discord.Color.dark_red(), timestamp=datetime.datetime.now(datetime.timezone.utc))
    embed.add_field(name="👤 المتهم المستدعى:", value=target.mention, inline=True)
    embed.add_field(name="📅 الموعد:", value=date_time, inline=True)
    embed.add_field(name="📍 القاعة:", value=room.mention, inline=False)
    embed.add_field(name="👨‍⚖️ الناظر في القضية:", value=interaction.user.mention, inline=True)
    await dest.send(content=target.mention, embed=embed)
    await interaction.response.send_message(f"✅ تم إرسال طلب المحاكمة إلى {dest.mention}", ephemeral=True)

@bot.tree.command(name="add-charge", description="[Justice] تسجيل تهمة في السجل الجنائي")
@app_commands.describe(target="المتهم", charge="نص التهمة", target_channel="القناة (اختياري)")
async def add_charge(interaction: discord.Interaction, target: discord.Member, charge: str, target_channel: discord.TextChannel = None):
    if not check_role(interaction.user, ROLE_JUSTICE):
        return await interaction.response.send_message(f"❌ هذا الأمر مخصص لرتبة **{ROLE_JUSTICE}** فقط!", ephemeral=True)

    uid = target.id
    if uid not in criminal_records:
        criminal_records[uid] = []
    
    date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    criminal_records[uid].append({"charge": charge, "officer": interaction.user.display_name, "date": date_str})

    dest = target_channel or interaction.channel
    embed = discord.Embed(title="📂 إدانة وتهمة مسجلة", color=discord.Color.red(), timestamp=datetime.datetime.now(datetime.timezone.utc))
    embed.add_field(name="👤 المتهم:", value=target.mention, inline=True)
    embed.add_field(name="⚖️ التهمة:", value=f"**{charge}**", inline=False)
    embed.add_field(name="🛡️ القاضي/المسجل:", value=interaction.user.mention, inline=True)
    await dest.send(embed=embed)
    await interaction.response.send_message(f"✅ تم تسجيل التهمة في {dest.mention}", ephemeral=True)

@bot.tree.command(name="911-dispatch", description="[LSPD] إرسال توجيه وتعميم لغرفة العمليات")
@app_commands.describe(location="موقع الحادث", details="تفاصيل البلاغ", target_channel="القناة (اختياري)")
async def dispatch_911(interaction: discord.Interaction, location: str, details: str, target_channel: discord.TextChannel = None):
    if not check_role(interaction.user, ROLE_POLICE):
        return await interaction.response.send_message(f"❌ هذا الأمر مخصص لرتبة **{ROLE_POLICE}** فقط!", ephemeral=True)

    dest = target_channel or interaction.channel
    embed = discord.Embed(title="🚨 بلاغ وتوجيه عمليات 911", color=discord.Color.blue(), timestamp=datetime.datetime.now(datetime.timezone.utc))
    embed.add_field(name="📍 الموقع:", value=location, inline=True)
    embed.add_field(name="📝 التفاصيل:", value=details, inline=False)
    embed.add_field(name="👮 الضابط المبلغ:", value=interaction.user.mention, inline=True)
    await dest.send(embed=embed)
    await interaction.response.send_message(f"✅ تم إرسال البلاغ إلى {dest.mention}", ephemeral=True)

@bot.tree.command(name="log-inspection", description="[LSPD] تسجيل مصادرة وأغراض مقبوضات أثناء التفتيش")
@app_commands.describe(target="الشخص المفتش", items="المضبوطات", target_channel="القناة (اختياري)")
async def log_inspection(interaction: discord.Interaction, target: discord.Member, items: str, target_channel: discord.TextChannel = None):
    if not check_role(interaction.user, ROLE_POLICE):
        return await interaction.response.send_message(f"❌ هذا الأمر مخصص لرتبة **{ROLE_POLICE}** فقط!", ephemeral=True)

    dest = target_channel or interaction.channel
    embed = discord.Embed(title="🔍 محضر تفتيش ومصادرة", color=discord.Color.orange(), timestamp=datetime.datetime.now(datetime.timezone.utc))
    embed.add_field(name="👤 الخاضع للتفتيش:", value=target.mention, inline=True)
    embed.add_field(name="📦 المضبوطات والممنوعات:", value=items, inline=False)
    embed.add_field(name="👮 القائم بالتفتيش:", value=interaction.user.mention, inline=True)
    await dest.send(embed=embed)
    await interaction.response.send_message(f"✅ تم تسجيل المحضر في {dest.mention}", ephemeral=True)

@bot.tree.command(name="code-red", description="[SWAT] إعلان حالة استنفار طارئة SWAT Code Red")
@app_commands.describe(reason="سبب الاستنفار والموقع", target_channel="القناة (اختياري)")
async def code_red(interaction: discord.Interaction, reason: str, target_channel: discord.TextChannel = None):
    if not check_role(interaction.user, ROLE_SWAT):
        return await interaction.response.send_message(f"❌ هذا الأمر مخصص لرتبة **{ROLE_SWAT}** فقط!", ephemeral=True)

    dest = target_channel or interaction.channel
    embed = discord.Embed(title="⚡ [CODE RED] إعلان استنفار وتدخل سريع", color=discord.Color.dark_red(), timestamp=datetime.datetime.now(datetime.timezone.utc))
    embed.add_field(name="🚨 السبب والموقع:", value=f"**{reason}**", inline=False)
    embed.add_field(name="🛡️ قائد العمليات:", value=interaction.user.mention, inline=True)
    await dest.send(content="@everyone ⚡ حالة استنفار سوات!", embed=embed)
    await interaction.response.send_message(f"✅ تم إعلان الاستنفار في {dest.mention}", ephemeral=True)

@bot.tree.command(name="raid-plan", description="[SWAT] تجهيز وإرسال خطة مداهمة تكتيكية")
@app_commands.describe(target_location="الموقع المستهدف", voice_channel="روم الصوت المخصص", target_channel="القناة (اختياري)")
async def raid_plan(interaction: discord.Interaction, target_location: str, voice_channel: discord.VoiceChannel, target_channel: discord.TextChannel = None):
    if not check_role(interaction.user, ROLE_SWAT):
        return await interaction.response.send_message(f"❌ هذا الأمر مخصص لرتبة **{ROLE_SWAT}** فقط!", ephemeral=True)

    dest = target_channel or interaction.channel
    embed = discord.Embed(title="🎯 خطة تكتيكية ومداهمة", color=discord.Color.purple(), timestamp=datetime.datetime.now(datetime.timezone.utc))
    embed.add_field(name="📍 الهدف والموقع:", value=target_location, inline=True)
    embed.add_field(name="🔊 الروم الصوت التكتيكي:", value=voice_channel.mention, inline=True)
    embed.add_field(name="👮 المشرف:", value=interaction.user.mention, inline=False)
    await dest.send(embed=embed)
    await interaction.response.send_message(f"✅ تم إرسال الخطة إلى {dest.mention}", ephemeral=True)

@bot.tree.command(name="medical-triage", description="[PHMC] تسجيل نتيجة الفحص والفرز الطبي للمصاب")
@app_commands.describe(patient="المصاب", status="الحالة (حرجة / مستقرة)", blood_type="فصيلة الدم", target_channel="القناة (اختياري)")
async def medical_triage(interaction: discord.Interaction, patient: discord.Member, status: str, blood_type: str = "غير محدد", target_channel: discord.TextChannel = None):
    if not check_role(interaction.user, ROLE_HEALTH):
        return await interaction.response.send_message(f"❌ هذا الأمر مخصص لرتبة **{ROLE_HEALTH}** فقط!", ephemeral=True)

    dest = target_channel or interaction.channel
    embed = discord.Embed(title="🚑 تقرير فرز ومعاينة طبية", color=discord.Color.teal(), timestamp=datetime.datetime.now(datetime.timezone.utc))
    embed.add_field(name="👤 المريض:", value=patient.mention, inline=True)
    embed.add_field(name="🩺 حالة المريض:", value=f"**{status}**", inline=True)
    embed.add_field(name="🩸 فصيلة الدم:", value=blood_type, inline=True)
    embed.add_field(name="👨‍⚕️ المسعف/الطبيب:", value=interaction.user.mention, inline=False)
    await dest.send(embed=embed)
    await interaction.response.send_message(f"✅ تم إرسال التقرير إلى {dest.mention}", ephemeral=True)

@bot.tree.command(name="check-charges", description="[الجميع] عرض سجل التهم الجنائية للاعب")
@app_commands.describe(target="اللاعب المراد فحص سجله")
async def check_charges(interaction: discord.Interaction, target: discord.Member):
    uid = target.id
    records = criminal_records.get(uid, [])

    if not records:
        embed = discord.Embed(title="🔍 السجل الجنائي", description=f"السجل الجنائي للاعب {target.mention} **نظيف وخالٍ من السوابق**.", color=discord.Color.green())
        return await interaction.response.send_message(embed=embed)

    embed = discord.Embed(title=f"📜 السجل الجنائي: {target.display_name}", color=discord.Color.orange())
    for i, item in enumerate(records, 1):
        embed.add_field(name=f"قضية #{i}", value=f"> **التهمة:** {item['charge']}\n> **المسجل:** {item['officer']}\n> **التاريخ:** {item['date']}", inline=False)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ticket-panel", description="إرسال لوحة فتح التذاكر الموحدة")
@app_commands.describe(channel="القناة لفتح اللوحة بها")
async def ticket_panel(interaction: discord.Interaction, channel: discord.TextChannel = None):
    dest = channel or interaction.channel
    embed = discord.Embed(
        title="🏙️ مركز الخدمات الحكومية والقطاعات RP",
        description="مرحباً بكم في بوابة التذاكر الحكومية.\nاختر القطاع المطلوب للتواصل مع المسؤولين.",
        color=discord.Color.blue()
    )
    await dest.send(embed=embed, view=TicketSelectView())
    await interaction.response.send_message("✅ تم إرسال البانل بنجاح!", ephemeral=True)

# ---------------------------------------------------------
# 7. التشغيل
# ---------------------------------------------------------
if __name__ == "__main__":
    keep_alive()
    TOKEN = os.getenv("DISCORD_TOKEN")
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("❌ لم يتم العثور على DISCORD_TOKEN!")
