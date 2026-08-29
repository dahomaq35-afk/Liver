import os
import asyncio
import datetime
import discord
from discord import app_commands
from discord.ext import commands

# ---------------------------------------------------------
# 1. إعداد الـ Intents وشجرة الأوامر
# ---------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="-", intents=intents)

# قائمة الـ 5 أيديات المصرح لهم بالأوامر الإدارية الأخرى (المحكمة والرسائل)
ALLOWED_USERS = [
    1410703717539254373,  # 👈 ID الشخص الأول
    1490406877782343843,  # 👈 ID الشخص الثاني
    1498036019881054500,  # 👈 ID الشخص الثالث
    000000000000000000,  # 👈 ID الشخص الرابع
    000000000000000000   # 👈 ID الشخص الخامس
]

# قاعدة بيانات مؤقتة لتخزين سجلات التهم
criminal_records = {}

# ---------------------------------------------------------
# 2. مكونات نظام التذاكر (Interactive UI Component)
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
# 3. أحداث البوت والمزامنة
# ---------------------------------------------------------
@bot.event
async def on_ready():
    bot.add_view(TicketSelectView())
    bot.add_view(TicketCloseView())
    try:
        synced = await bot.tree.sync()
        print(f"✅ تم مزامنة {len(synced)} أمر slash لوزارة العدل بنجاح!")
    except Exception as e:
        print(f"❌ خطأ في مزامنة الأوامر: {e}")
    print(f"⚖️ بوت وزارة العدل يعمل بنجاح باسم: {bot.user.name}")

# ---------------------------------------------------------
# 4. أوامر التذاكر (بدون حماية الأيديات - متاحة للجميع)
# ---------------------------------------------------------

# أمر إرسال بانل التذاكر
@bot.tree.command(name="ticket-panel", description="لارسال بانل فتح التذاكر")
@app_commands.describe(channel="اختر القناة المراد إرسال بانل التذاكر فيها")
async def ticket_panel(interaction: discord.Interaction, channel: discord.TextChannel):
    embed = discord.Embed(
        title="⚖️ مركز الخدمة العدلية وتلقي القضايا",
        description="أهلاً بكم في بوابة وزارة العدل.\nيرجى اختيار نوع المعاملة أو القضية المراد فتحها من القائمة المنسدلة أسفله للتواصل مع الهيئة القضائية.",
        color=discord.Color.dark_gold()
    )
    embed.set_footer(text="وزارة العدل - نظام التذاكر")

    await channel.send(embed=embed, view=TicketSelectView())
    await interaction.response.send_message(f"✅ تم إرسال بانل فتح التذاكر بنجاح في {channel.mention}", ephemeral=True)


# أمر تسطيب نظام التذاكر
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
# 5. أمر إرسال رسالة منسقة (/send-embed)
# ---------------------------------------------------------
@bot.tree.command(name="send-embed", description="إرسال رسالة منسقة من البوت إلى روم محدد")
@app_commands.describe(
    channel="اختر القناة المراد إرسال الرسالة فيها",
    message="اكتب نص الرسالة التي تريد إرسالها",
    title="عنوان الرسالة (اختياري)",
    color="اختر لون الإمبد"
)
@app_commands.choices(color=[
    app_commands.Choice(name="🔴 أحمر (رسمي / طارئ)", value="red"),
    app_commands.Choice(name="🟢 أخضر (موافقة / إعلان)", value="green"),
    app_commands.Choice(name="🔵 أزرق (تنبيه / معلومات)", value="blue"),
    app_commands.Choice(name="🟡 ذهبي (توجيه / قرارات)", value="gold")
])
async def send_embed(
    interaction: discord.Interaction, 
    channel: discord.TextChannel, 
    message: str, 
    color: app_commands.Choice[str],
    title: str = None
):
    if interaction.user.id not in ALLOWED_USERS:
        return await interaction.response.send_message("❌ عذراً، هذا الأمر مخصص لأعضاء محددين فقط!", ephemeral=True)

    color_map = {
        "red": discord.Color.red(),
        "green": discord.Color.green(),
        "blue": discord.Color.blue(),
        "gold": discord.Color.gold()
    }

    embed = discord.Embed(
        title=title if title else "⚖️ بيان صادر عن وزارة العدل",
        description=message,
        color=color_map.get(color.value, discord.Color.blue()),
        timestamp=datetime.datetime.utcnow()
    )
    embed.set_footer(text=f"صادر بواسطة: {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)

    try:
        await channel.send(embed=embed)
        await interaction.response.send_message(f"✅ تم إرسال الرسالة بنجاح في القناة {channel.mention}", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ تعذر إرسال الرسالة: {e}", ephemeral=True)

# ---------------------------------------------------------
# 6. أمر تسجيل تهمة على لاعب (/add-charge)
# ---------------------------------------------------------
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
    criminal_records[user_id].append({
        "charge": charge.value,
        "officer": interaction.user.display_name,
        "date": date_str
    })

    embed = discord.Embed(title="📂 تم تسجيل تهمة جديدة", color=discord.Color.red(), timestamp=datetime.datetime.utcnow())
    embed.add_field(name="👤 المتهم", value=target.mention, inline=True)
    embed.add_field(name="⚖️ التهمة المسجلة", value=f"**{charge.value}**", inline=False)
    embed.add_field(name="🛡️ المسجل بواسطة", value=interaction.user.mention, inline=True)
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.set_footer(text="وزارة العدل - نظام السجلات الجنائية")

    await interaction.response.send_message(embed=embed)

# ---------------------------------------------------------
# 7. أمر الاستعلام عن سوابق لاعب (/check-charges)
# ---------------------------------------------------------
@bot.tree.command(name="check-charges", description="عرض سجل التهم والسوابق الجنائية للاعب")
@app_commands.describe(target="اختر اللاعب لرؤية سجله الجنائي")
async def check_charges(interaction: discord.Interaction, target: discord.Member):
    user_id = target.id
    records = criminal_records.get(user_id, [])

    if not records:
        embed = discord.Embed(
            title="🔍 السجل الجنائي",
            description=f"السجل الجنائي للاعب {target.mention} **نظيف** ولا توجد أي تهم مسجلة بحقه.",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        return await interaction.response.send_message(embed=embed)

    embed = discord.Embed(
        title=f"📜 السجل الجنائي للاعب: {target.display_name}",
        description=f"إجمالي عدد التهم المسجلة: **{len(records)}**",
        color=discord.Color.orange()
    )
    embed.set_thumbnail(url=target.display_avatar.url)

    for i, item in enumerate(records, 1):
        embed.add_field(
            name=f"التهمة رقم #{i}",
            value=f"> **التهمة:** {item['charge']}\n> **بواسطة:** {item['officer']}\n> **التاريخ:** {item['date']}",
            inline=False
        )

    embed.set_footer(text="وزارة العدل - نظام السجلات الجنائية")
    await interaction.response.send_message(embed=embed)

# ---------------------------------------------------------
# 8. أمر مسح وتبرئة التهم (/remove-charges)
# ---------------------------------------------------------
@bot.tree.command(name="remove-charges", description="مسح كافة التهم والسوابق الجنائية عن لاعب (تبرئة)")
@app_commands.describe(target="منشن اللاعب المراد مسح التهم عنه")
async def remove_charges(interaction: discord.Interaction, target: discord.Member):
    if interaction.user.id not in ALLOWED_USERS:
        return await interaction.response.send_message("❌ هذا الأمر مخصص لأعضاء محددين فقط!", ephemeral=True)

    user_id = target.id
    if user_id not in criminal_records or len(criminal_records[user_id]) == 0:
        embed = discord.Embed(
            title="⚠️ تنبيه",
            description=f"اللاعب {target.mention} لا يمتلك أي تهم مسجلة بالفعل!",
            color=discord.Color.gold()
        )
        return await interaction.response.send_message(embed=embed, ephemeral=True)

    criminal_records[user_id] = []

    embed = discord.Embed(
        title="✨ تم رد الاعتبار والتبرئة",
        description=f"تم مسح جميع التهم والسوابق الجنائية المسجلة بحق اللاعب {target.mention} بنجاح.",
        color=discord.Color.green(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.add_field(name="🛡️ المسؤول عن التبرئة", value=interaction.user.mention, inline=True)
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.set_footer(text="وزارة العدل - نظام رد الاعتبار والتبرئة")

    await interaction.response.send_message(embed=embed)

# ---------------------------------------------------------
# 9. التشغيل التلقائي عبر المتغيرات البيئية
# ---------------------------------------------------------
if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("❌ لم يتم العثور على DISCORD_TOKEN في المتغيرات البيئية!")
