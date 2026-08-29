import os
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

bot = commands.Bot(command_prefix="-", intents=intents)

# قاعدة بيانات مؤقتة لتخزين سجلات التهم
criminal_records = {}

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"✅ تم مزامنة {len(synced)} أمر slash لوزارة العدل بنجاح!")
    except Exception as e:
        print(f"❌ خطأ في مزامنة الأوامر: {e}")
    print(f"⚖️ بوت وزارة العدل يعمل بنجاح باسم: {bot.user.name}")

# ---------------------------------------------------------
# 2. أمر تسجيل تهمة على لاعب (/add-charge)
# ---------------------------------------------------------
@bot.tree.command(name="add-charge", description="تسجيل تهمة جديدة في السجل الجنائي للاعب")
@app_commands.describe(
    target="منشن اللاعب المراد تسجيل التهمة عليه",
    charge="اختر التهمة الموجهة للاعب"
)
@app_commands.choices(charge=[
    app_commands.Choice(name="⚖️ التمرد وعصيان الأوامر العدلية", value="التمرد وعصيان الأوامر العدلية"),
    app_commands.Choice(name="📜 تقديم وثائق أو شهادة تزوير", value="تقديم وثائق أو شهادة تزوير"),
    app_commands.Choice(name="🚨 التعطيل والاعتداء على جلسة محاكمة", value="التعطيل والاعتداء على جلسة محاكمة"),
    app_commands.Choice(name="💼 الهروب من تنفيذ الحكم القضائي", value="الهروب من تنفيذ الحكم القضائي"),
    app_commands.Choice(name="🔍 إهانة الهيئة القضائية أو المحامي", value="إهانة الهيئة القضائية أو المحامي")
])
@app_commands.checks.has_permissions(administrator=True)
async def add_charge(interaction: discord.Interaction, target: discord.Member, charge: app_commands.Choice[str]):
    user_id = target.id
    
    if user_id not in criminal_records:
        criminal_records[user_id] = []
        
    date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    criminal_records[user_id].append({
        "charge": charge.value,
        "officer": interaction.user.display_name,
        "date": date_str
    })

    embed = discord.Embed(
        title="📂 تم تسجيل تهمة جديدة",
        color=discord.Color.red(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.add_field(name="👤 المتهم", value=target.mention, inline=True)
    embed.add_field(name="⚖️ التهمة المسجلة", value=f"**{charge.value}**", inline=False)
    embed.add_field(name="🛡️ المسجل بواسطة", value=interaction.user.mention, inline=True)
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.set_footer(text="وزارة العدل - نظام السجلات الجنائية")

    await interaction.response.send_message(embed=embed)

# ---------------------------------------------------------
# 3. أمر الاستعلام عن سوابق لاعب (/check-charges)
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
# 4. أمر مسح وتبرئة التهم من اللاعب (/remove-charges)
# ---------------------------------------------------------
@bot.tree.command(name="remove-charges", description="مسح كافة التهم والسوابق الجنائية عن لاعب (تبرئة)")
@app_commands.describe(target="منشن اللاعب المراد مسح التهم عنه")
@app_commands.checks.has_permissions(administrator=True)
async def remove_charges(interaction: discord.Interaction, target: discord.Member):
    user_id = target.id
    
    # التأكد ما إذا كان اللاعب يمتلك تهم مسبقة أم لا
    if user_id not in criminal_records or len(criminal_records[user_id]) == 0:
        embed = discord.Embed(
            title="⚠️ تنبيه",
            description=f"اللاعب {target.mention} لا يمتلك أي تهم مسجلة بالفعل حتى يتم مسحها!",
            color=discord.Color.gold()
        )
        return await interaction.response.send_message(embed=embed, ephemeral=True)

    # تفريغ قائمة التهم الخاص باللاعب
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

# معالجة الخطأ عند عدم وجود صلاحيات للأوامر
@add_charge.error
@remove_charges.error
async def permissions_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("❌ لا تملك صلاحيات إدارة لاستخدام هذا الأمر!", ephemeral=True)

# ---------------------------------------------------------
# 5. قراءة التوكن والتشغيل تلقائياً من المتغيرات البيئية
# ---------------------------------------------------------
if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("❌ لم يتم العثور على DISCORD_TOKEN في المتغيرات البيئية (Environment Variables)!")
