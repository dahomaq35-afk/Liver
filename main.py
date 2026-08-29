import os
import asyncio
import datetime
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
# 2. إعداد البوت وأسماء الرتب المعتمدة
# ---------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="-", intents=intents)

# 🏷️ أسماء الرتب المصرح لها لكل قطاع
ROLE_JUSTICE = "عدل"
ROLE_POLICE = "شرطة"
ROLE_SWAT = "سوات"
ROLE_HEALTH = "صحة"

# قواعد البيانات المؤقتة
criminal_records = {}

# دالة التحقق من الرتبة فقط (بدون استثناء للأدمن/الأونر)
def check_role(user: discord.Member, role_name: str) -> bool:
    return any(role.name == role_name for role in user.roles)

# ---------------------------------------------------------
# 3. مكونات التذاكر (Interactive UI)
# ---------------------------------------------------------
class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="إغلاق التذكرة 🔒", style=discord.ButtonStyle.red, custom_id="close_justice_ticket")
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
            discord.SelectOption(label="⚖️ ديوان وزارة العدل", description="رفع دعوى، توكيل محامي، صكوك", value="عدل"),
            discord.SelectOption(label="🚨 بلاغ للشرطة والأمن", description="تقديم بلاغ أمني أو شكوى", value="شرطة"),
            discord.SelectOption(label="⚡ طلب قوة السوات SWAT", description="بلاغ عمليات خاصة وتدخل سريع", value="سوات"),
            discord.SelectOption(label="🚑 طوارئ الإسعاف والصحة", description="طلب إسعاف أو فحص طبي", value="صحة"),
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        guild = interaction.guild
        category_name = f"📂 تذاكر قطاع - {select.values[0]}"
        category = discord.utils.get(guild.categories, name=category_name)
        
        if not category:
            category = await guild.create_category(category_name)

        ticket_channel = await guild.create_text_channel(
            name=f"تذكرة-{select.values[0]}-{interaction.user.name}",
            category=category,
            overwrites={
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
        )

        embed = discord.Embed(
            title=f"📋 تذكرة جديدة - {select.values[0]}",
            description=f"أهلاً بك {interaction.user.mention} 👋\nيرجى كتابة كافة التفاصيل والبلاغ وسيقوم المختص بالرد عليك.",
            color=discord.Color.gold(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.set_footer(text="نظام التذاكر الموحد - لإغلاق التذكرة اضغط الزر أدناه")

        await ticket_channel.send(embed=embed, view=TicketCloseView())
        await interaction.response.send_message(f"✅ تم فتح تذكرتك بنجاح: {ticket_channel.mention}", ephemeral=True)

# ---------------------------------------------------------
# 4. الأحداث والمزامنة
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
    print(f"⚖️ البوت شغال بنجاح باسم: {bot.user.name}")

# ---------------------------------------------------------
# 5. أوامر وزارة العدل (تتطلب رتبة: عدل فقط)
# ---------------------------------------------------------
@bot.tree.command(name="create-deed", description="[عدل] تسجيل صك ملكية أو عقد رسمي بين طرفين")
@app_commands.describe(owner="صاحب الملكية", property_type="نوع العقار/السيارة", details="تفاصيل الصك")
async def create_deed(interaction: discord.Interaction, owner: discord.Member, property_type: str, details: str):
    if not check_role(interaction.user, ROLE_JUSTICE):
        return await interaction.response.send_message(f"❌ هذا الأمر مخصص لمن يحمل رتبة **{ROLE_JUSTICE}** فقط!", ephemeral=True)

    embed = discord.Embed(title="📜 صك ملكية رسمي", color=discord.Color.gold(), timestamp=datetime.datetime.utcnow())
    embed.add_field(name="👤 المالـك:", value=owner.mention, inline=True)
    embed.add_field(name="🏠 نوع العقار/الملكية:", value=property_type, inline=True)
    embed.add_field(name="📝 تفاصيل الصك:", value=details, inline=False)
    embed.add_field(name="⚖️ توثيق القاضي:", value=interaction.user.mention, inline=True)
    embed.set_footer(text="وزارة العدل - ديوان الصكوك والعقود")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="set-trial", description="[عدل] تحديد موعد جلسة محاكمة وتنبيه المتهم")
@app_commands.describe(target="المتهم", date_time="تاريخ ووقت الجلسة", room="اسم القاعة/الروم")
async def set_trial(interaction: discord.Interaction, target: discord.Member, date_time: str, room: discord.TextChannel):
    if not check_role(interaction.user, ROLE_JUSTICE):
        return await interaction.response.send_message(f"❌ هذا الأمر مخصص لمن يحمل رتبة **{ROLE_JUSTICE}** فقط!", ephemeral=True)

    embed = discord.Embed(title="⚖️ استدعاء وجلسة محاكمة رسمية", color=discord.Color.dark_red(), timestamp=datetime.datetime.utcnow())
    embed.add_field(name="👤 المتهم المستدعى:", value=target.mention, inline=True)
    embed.add_field(name="📅 الموعد:", value=date_time, inline=True)
    embed.add_field(name="📍 القاعة:", value=room.mention, inline=False)
    embed.add_field(name="👨‍⚖️ الناظر في القضية:", value=interaction.user.mention, inline=True)
    embed.set_footer(text="وزارة العدل - نظام الاستدعاءات القضائية")
    await interaction.response.send_message(content=target.mention, embed=embed)

@bot.tree.command(name="add-charge", description="[عدل] تسجيل تهمة في السجل الجنائي")
@app_commands.describe(target="المتهم", charge="نص التهمة الموجهة")
async def add_charge(interaction: discord.Interaction, target: discord.Member, charge: str):
    if not check_role(interaction.user, ROLE_JUSTICE):
        return await interaction.response.send_message(f"❌ هذا الأمر مخصص لمن يحمل رتبة **{ROLE_JUSTICE}** فقط!", ephemeral=True)

    user_id = target.id
    if user_id not in criminal_records:
        criminal_records[user_id] = []
    
    date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    criminal_records[user_id].append({"charge": charge, "officer": interaction.user.display_name, "date": date_str})

    embed = discord.Embed(title="📂 إدانة وتهمة مسجلة", color=discord.Color.red(), timestamp=datetime.datetime.utcnow())
    embed.add_field(name="👤 المتهم:", value=target.mention, inline=True)
    embed.add_field(name="⚖️ التهمة:", value=f"**{charge}**", inline=False)
    embed.add_field(name="🛡️ القاضي/المسجل:", value=interaction.user.mention, inline=True)
    await interaction.response.send_message(embed=embed)

# ---------------------------------------------------------
# 6. أوامر الشرطة والأمن (تتطلب رتبة: شرطة فقط)
# ---------------------------------------------------------
@bot.tree.command(name="911-dispatch", description="[شرطة] إرسال توجيه وتعميم لغرفة العمليات")
@app_commands.describe(location="موقع الحادث", details="تفاصيل البلاغ والتعميم")
async def dispatch_911(interaction: discord.Interaction, location: str, details: str):
    if not check_role(interaction.user, ROLE_POLICE):
        return await interaction.response.send_message(f"❌ هذا الأمر مخصص لمن يحمل رتبة **{ROLE_POLICE}** فقط!", ephemeral=True)

    embed = discord.Embed(title="🚨 بلاغ وتوجيه عمليات 911", color=discord.Color.blue(), timestamp=datetime.datetime.utcnow())
    embed.add_field(name="📍 الموقع:", value=location, inline=True)
    embed.add_field(name="📝 التفاصيل:", value=details, inline=False)
    embed.add_field(name="👮 الضابط المبلغ:", value=interaction.user.mention, inline=True)
    embed.set_footer(text="الأمن العام - غرفة العمليات المركزية")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="log-inspection", description="[شرطة] تسجيل مصادرة وأغراض مقبوضات أثناء التفتيش")
@app_commands.describe(target="الشخص المفتش", items="الأغراض والمصادرات")
async def log_inspection(interaction: discord.Interaction, target: discord.Member, items: str):
    if not check_role(interaction.user, ROLE_POLICE):
        return await interaction.response.send_message(f"❌ هذا الأمر مخصص لمن يحمل رتبة **{ROLE_POLICE}** فقط!", ephemeral=True)

    embed = discord.Embed(title="🔍 محضر تفتيش ومصادرة", color=discord.Color.orange(), timestamp=datetime.datetime.utcnow())
    embed.add_field(name="👤 الخاضع للتفتيش:", value=target.mention, inline=True)
    embed.add_field(name="📦 المضبوطات والممنوعات:", value=items, inline=False)
    embed.add_field(name="👮 القائم بالتفتيش:", value=interaction.user.mention, inline=True)
    await interaction.response.send_message(embed=embed)

# ---------------------------------------------------------
# 7. أوامر قوات السوات SWAT (تتطلب رتبة: سوات فقط)
# ---------------------------------------------------------
@bot.tree.command(name="code-red", description="[سوات] إعلان حالة استنفار طارئة كبرى SWAT Code Red")
@app_commands.describe(reason="سبب الاستنفار والموقع")
async def code_red(interaction: discord.Interaction, reason: str):
    if not check_role(interaction.user, ROLE_SWAT):
        return await interaction.response.send_message(f"❌ هذا الأمر مخصص لمن يحمل رتبة **{ROLE_SWAT}** فقط!", ephemeral=True)

    embed = discord.Embed(title="⚡ [CODE RED] إعلان استنفار وتدخل سريع", color=discord.Color.dark_red(), timestamp=datetime.datetime.utcnow())
    embed.add_field(name="🚨 السبب والموقع:", value=f"**{reason}**", inline=False)
    embed.add_field(name="🛡️ قائد العمليات:", value=interaction.user.mention, inline=True)
    embed.set_footer(text="قوات التدخل السريع SWAT - حالة تأهب كبرى")
    await interaction.response.send_message(content="@everyone ⚡ حالة استنفار سوات!", embed=embed)

@bot.tree.command(name="raid-plan", description="[سوات] تجهيز وإرسال خطة مداهمة تكتيكية")
@app_commands.describe(target_location="الموقع المستهدف", voice_channel="روم الصوت المخصص للعملية")
async def raid_plan(interaction: discord.Interaction, target_location: str, voice_channel: discord.VoiceChannel):
    if not check_role(interaction.user, ROLE_SWAT):
        return await interaction.response.send_message(f"❌ هذا الأمر مخصص لمن يحمل رتبة **{ROLE_SWAT}** فقط!", ephemeral=True)

    embed = discord.Embed(title="🎯 خطة تكتيكية ومداهمة", color=discord.Color.purple(), timestamp=datetime.datetime.utcnow())
    embed.add_field(name="📍 الهدف والموقع:", value=target_location, inline=True)
    embed.add_field(name="🔊 الروم التكتيكي الصوتي:", value=voice_channel.mention, inline=True)
    embed.add_field(name="👮 المشرف:", value=interaction.user.mention, inline=False)
    await interaction.response.send_message(embed=embed)

# ---------------------------------------------------------
# 8. أوامر وزارة الصحة (تتطلب رتبة: صحة فقط)
# ---------------------------------------------------------
@bot.tree.command(name="medical-triage", description="[صحة] تسجيل نتيجة الفحص والفرز الطبي للمصاب")
@app_commands.describe(patient="المصاب", status="حالة المصاب (حرجة / مستقرة)", blood_type="فصيلة الدم (اختياري)")
async def medical_triage(interaction: discord.Interaction, patient: discord.Member, status: str, blood_type: str = "غير محدد"):
    if not check_role(interaction.user, ROLE_HEALTH):
        return await interaction.response.send_message(f"❌ هذا الأمر مخصص لمن يحمل رتبة **{ROLE_HEALTH}** فقط!", ephemeral=True)

    embed = discord.Embed(title="🚑 تقرير فرز ومعاينة طبية", color=discord.Color.teal(), timestamp=datetime.datetime.utcnow())
    embed.add_field(name="👤 المريض:", value=patient.mention, inline=True)
    embed.add_field(name="🩺 حالة المريض:", value=f"**{status}**", inline=True)
    embed.add_field(name="🩸 فصيلة الدم:", value=blood_type, inline=True)
    embed.add_field(name="👨‍⚕️ المسعف/الطبيب:", value=interaction.user.mention, inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="check-charges", description="[الجميع] عرض سجل التهم الجنائية للاعب")
@app_commands.describe(target="اللاعب المراد فحص سجله")
async def check_charges(interaction: discord.Interaction, target: discord.Member):
    user_id = target.id
    records = criminal_records.get(user_id, [])

    if not records:
        embed = discord.Embed(title="🔍 السجل الجنائي", description=f"السجل الجنائي للاعب {target.mention} **نظيف وخالٍ من السوابق**.", color=discord.Color.green())
        return await interaction.response.send_message(embed=embed)

    embed = discord.Embed(title=f"📜 السجل الجنائي: {target.display_name}", color=discord.Color.orange())
    for i, item in enumerate(records, 1):
        embed.add_field(name=f"قضية #{i}", value=f"> **التهمة:** {item['charge']}\n> **المسجل:** {item['officer']}\n> **التاريخ:** {item['date']}", inline=False)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ticket-panel", description="إرسال لوحة فتح التذاكر الموحدة")
@app_commands.describe(channel="القناة (اختياري)")
async def ticket_panel(interaction: discord.Interaction, channel: discord.TextChannel = None):
    target_channel = channel or interaction.channel
    embed = discord.Embed(
        title="🏙️ مركز الخدمات الحكومية والقطاعات RP",
        description="مرحباً بكم في بوابة التذاكر الحكومية.\nاختر القطاع المطلوب للتواصل مع المسؤولين.",
        color=discord.Color.blue()
    )
    await target_channel.send(embed=embed, view=TicketSelectView())
    await interaction.response.send_message("✅ تم إرسال البانل بنجاح!", ephemeral=True)

# ---------------------------------------------------------
# 9. التشغيل
# ---------------------------------------------------------
if __name__ == "__main__":
    keep_alive()
    TOKEN = os.getenv("DISCORD_TOKEN")
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("❌ لم يتم العثور على DISCORD_TOKEN!")
