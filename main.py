import os
import asyncio
import datetime
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
    return "Bot is alive 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# ---------------------------------------------------------
# 2. إعداد البوت والـ Intents
# ---------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="-", intents=intents)

ALLOWED_USERS = [
    000000000000000000,  # 👈 ID المصرح لهم بالأوامر الإدارية
]

criminal_records = {}

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
        placeholder="اختر نوع المعاملة العدلية...",
        custom_id="justice_ticket_select",
        options=[
            discord.SelectOption(label="رفع دعوى قضائية", description="لتقديم شكوى أو قضية رسمية", emoji="⚖️"),
            discord.SelectOption(label="طلب محامي دفاع", description="طلب توكيل محامي معتمد", emoji="📜"),
            discord.SelectOption(label="استفسار أو توثيق", description="للتوثيق والصكوك والاستفسارات", emoji="📋"),
            discord.SelectOption(label="رد اعتبار / تبرئة", description="لتقديم طلب مسح سوابق وتهم", emoji="✨"),
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        guild = interaction.guild
        category_name = "📂 تذاكر وزارة العدل"
        category = discord.utils.get(guild.categories, name=category_name)
        
        if not category:
            category = await guild.create_category(category_name)

        ticket_channel = await guild.create_text_channel(
            name=f"قضية-{interaction.user.name}",
            category=category,
            overwrites={
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
        )

        embed = discord.Embed(
            title=f"⚖️ معاملة: {select.values[0]}",
            description=f"مرحباً بك {interaction.user.mention} في ديوان وزارة العدل 👋\n\nيرجى كتابة كافة التفاصيل والأدلة الخاصة بطلبك وسيقوم القاضي/المكلف بالمتابعة معك.",
            color=discord.Color.gold(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.set_footer(text="وزارة العدل - لإغلاق التذكرة اضغط على الزر أدناه")

        await ticket_channel.send(embed=embed, view=TicketCloseView())
        await interaction.response.send_message(f"✅ تم فتح تذكرتك بنجاح: {ticket_channel.mention}", ephemeral=True)

# ---------------------------------------------------------
# 4. الأحداث والمزامنة الفورية لكل السيرفرات
# ---------------------------------------------------------
@bot.event
async def on_ready():
    bot.add_view(TicketSelectView())
    bot.add_view(TicketCloseView())
    try:
        synced = await bot.tree.sync()
        print(f"✅ تم مزامنة {len(synced)} أمر Slash على مستوى العالم بنجاح!")
    except Exception as e:
        print(f"❌ خطأ في المزامنة: {e}")
    print(f"⚖️ البوت شغال باسم: {bot.user.name}")

# مزامنة فورية عند دخول أي سيرفر جديد
@bot.event
async def on_guild_join(guild):
    try:
        await bot.tree.sync(guild=guild)
        print(f"✅ تم مزامنة الأوامر فوراً في سيرفر: {guild.name}")
    except Exception as e:
        print(f"❌ تعذر المزامنة في السيرفر الجديد: {e}")

# ---------------------------------------------------------
# 5. الأوامر (ticket-panel / ticket-setup)
# ---------------------------------------------------------
@bot.tree.command(name="ticket-panel", description="لارسال بانل فتح التذاكر")
@app_commands.describe(channel="اختر القناة المراد إرسال البانل فيها (اختياري)")
async def ticket_panel(interaction: discord.Interaction, channel: discord.TextChannel = None):
    target_channel = channel or interaction.channel

    embed = discord.Embed(
        title="⚖️ مركز الخدمة العدلية وتلقي القضايا",
        description="أهلاً بكم في بوابة وزارة العدل.\nيرجى اختيار نوع المعاملة أو القضية المراد فتحها من القائمة المنسدلة أسفله للتواصل مع الهيئة القضائية.",
        color=discord.Color.dark_gold()
    )
    embed.set_footer(text="وزارة العدل - نظام التذاكر")

    try:
        await target_channel.send(embed=embed, view=TicketSelectView())
        await interaction.response.send_message(f"✅ تم إرسال بانل فتح التذاكر بنجاح في {target_channel.mention}", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ فشل إرسال البانل! تأكد أن البوت يمتلك صلاحية Send Messages و Embed Links في القناة.\nالخطأ: {e}", ephemeral=True)

@bot.tree.command(name="ticket-setup", description="لتسطيب نظام التذاكر")
async def ticket_setup(interaction: discord.Interaction):
    guild = interaction.guild
    category_name = "📂 تذاكر وزارة العدل"
    category = discord.utils.get(guild.categories, name=category_name)

    if not category:
        await guild.create_category(category_name)
        status_msg = "✅ تم تسطيب وتجهيز الفئة المخصصة لتذاكر وزارة العدل بنجاح!"
    else:
        status_msg = "ℹ️ نظام التذاكر مسطب ومجهز مسبقاً في السيرفر!"

    embed = discord.Embed(
        title="⚙️ إعداد نظام التذاكر",
        description=f"{status_msg}\nيمكنك الان استخدام أمر `/ticket-panel` لإرسال البانل بأي روم.",
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ---------------------------------------------------------
# 6. الأوامر الإدارية الأخرى
# ---------------------------------------------------------
@bot.tree.command(name="send-embed", description="إرسال رسالة منسقة من البوت إلى روم محدد")
@app_commands.describe(channel="اختر القناة المراد إرسال الرسالة فيها", message="اكتب نص الرسالة التي تريد إرسالها", title="عنوان الرسالة (اختياري)", color="اختر لون الإمبد")
@app_commands.choices(color=[
    app_commands.Choice(name="🔴 أحمر (رسمي / طارئ)", value="red"),
    app_commands.Choice(name="🟢 أخضر (موافقة / إعلان)", value="green"),
    app_commands.Choice(name="🔵 أزرق (تنبيه / معلومات)", value="blue"),
    app_commands.Choice(name="🟡 ذهبي (توجيه / قرارات)", value="gold")
])
async def send_embed(interaction: discord.Interaction, channel: discord.TextChannel, message: str, color: app_commands.Choice[str], title: str = None):
    if interaction.user.id not in ALLOWED_USERS:
        return await interaction.response.send_message("❌ عذراً، هذا الأمر مخصص لأعضاء محددين فقط!", ephemeral=True)

    color_map = {"red": discord.Color.red(), "green": discord.Color.green(), "blue": discord.Color.blue(), "gold": discord.Color.gold()}
    embed = discord.Embed(
        title=title if title else "⚖️ بيان صادر عن وزارة العدل",
        description=message,
        color=color_map.get(color.value, discord.Color.blue()),
        timestamp=datetime.datetime.utcnow()
    )
    embed.set_footer(text=f"صادر بواسطة: {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
    await channel.send(embed=embed)
    await interaction.response.send_message(f"✅ تم إرسال الرسالة بنجاح في القناة {channel.mention}", ephemeral=True)

@bot.tree.command(name="add-charge", description="تسجيل تهمة جديدة في السجل الجنائي للاعب")
@app_commands.describe(target="منشن اللاعب المراد تسجيل التهمة عليه", charge="اختر التهمة الموجهة للاعب")
@app_commands.choices(charge=[
    app_commands.Choice(name="⚖️ التمرد وعصيان الأوامر العدلية", value="التمرد وعصيان الأوامر العدلية"),
    app_commands.Choice(name="📜 تقديم وثائق أو شهادة تزوير", value="تقديم وثائق أو شهادة تزوير"),
    app_commands.Choice(name="🚨 التعطيل والاعتداء على جلسة محاكمة", value="التعطيل والاعتداء على جلسة محاكمة"),
    app_commands.Choice(name="💼 الهروب من تنفيذ الحكم القضائي", value="الهروب من تنفيذ الحكم القضائي"),
    app_commands.Choice(name="🔍 إهانة الهيئة القضائية أو المحامي", value="إهانة الهيئة القضائية أو المحامي")
])
async def add_charge(interaction: discord.Interaction, target: discord.Member, charge: app_commands.Choice[str]):
    if interaction.user.id not in ALLOWED_USERS:
        return await interaction.response.send_message("❌ هذا الأمر مخصص لأعضاء محددين فقط!", ephemeral=True)

    user_id = target.id
    if user_id not in criminal_records:
        criminal_records[user_id] = []
        
    date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    criminal_records[user_id].append({"charge": charge.value, "officer": interaction.user.display_name, "date": date_str})

    embed = discord.Embed(title="📂 تم تسجيل تهمة جديدة", color=discord.Color.red(), timestamp=datetime.datetime.utcnow())
    embed.add_field(name="👤 المتهم", value=target.mention, inline=True)
    embed.add_field(name="⚖️ التهمة المسجلة", value=f"**{charge.value}**", inline=False)
    embed.add_field(name="🛡️ المسجل بواسطة", value=interaction.user.mention, inline=True)
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.set_footer(text="وزارة العدل - نظام السجلات الجنائية")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="check-charges", description="عرض سجل التهم والسوابق الجنائية للاعب")
@app_commands.describe(target="اختر اللاعب لرؤية سجله الجنائي")
async def check_charges(interaction: discord.Interaction, target: discord.Member):
    user_id = target.id
    records = criminal_records.get(user_id, [])

    if not records:
        embed = discord.Embed(title="🔍 السجل الجنائي", description=f"السجل الجنائي للاعب {target.mention} **نظيف** ولا توجد أي تهم مسجلة بحقه.", color=discord.Color.green())
        embed.set_thumbnail(url=target.display_avatar.url)
        return await interaction.response.send_message(embed=embed)

    embed = discord.Embed(title=f"📜 السجل الجنائي للاعب: {target.display_name}", description=f"إجمالي عدد التهم المسجلة: **{len(records)}**", color=discord.Color.orange())
    embed.set_thumbnail(url=target.display_avatar.url)
    for i, item in enumerate(records, 1):
        embed.add_field(name=f"التهمة رقم #{i}", value=f"> **التهمة:** {item['charge']}\n> **بواسطة:** {item['officer']}\n> **التاريخ:** {item['date']}", inline=False)

    embed.set_footer(text="وزارة العدل - نظام السجلات الجنائية")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="remove-charges", description="مسح كافة التهم والسوابق الجنائية عن لاعب (تبرئة)")
@app_commands.describe(target="منشن اللاعب المراد مسح التهم عنه")
async def remove_charges(interaction: discord.Interaction, target: discord.Member):
    if interaction.user.id not in ALLOWED_USERS:
        return await interaction.response.send_message("❌ هذا الأمر مخصص لأعضاء محددين فقط!", ephemeral=True)

    user_id = target.id
    if user_id not in criminal_records or len(criminal_records[user_id]) == 0:
        return await interaction.response.send_message(f"⚠️ اللاعب {target.mention} لا يمتلك أي تهم مسجلة!", ephemeral=True)

    criminal_records[user_id] = []
    embed = discord.Embed(title="✨ تم رد الاعتبار والتبرئة", description=f"تم مسح جميع التهم بحق {target.mention} بنجاح.", color=discord.Color.green(), timestamp=datetime.datetime.utcnow())
    embed.add_field(name="🛡️ المسؤول عن التبرئة", value=interaction.user.mention, inline=True)
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.set_footer(text="وزارة العدل - نظام رد الاعتبار والتبرئة")
    await interaction.response.send_message(embed=embed)

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
