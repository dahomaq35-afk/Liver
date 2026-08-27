import os
import random
import asyncio
import datetime
from flask import Flask
from threading import Thread
import discord
from discord.ext import commands

# ---------------------------------------------------------
# 1. إعدادات السيرفر البسيط (Keep Alive) لمنصة Render
# ---------------------------------------------------------
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive and running 24/7!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# ---------------------------------------------------------
# 2. إعداد الـ Intents وقائمة الحماية
# ---------------------------------------------------------
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.members = True
intents.audit_logs = True

bot = commands.Bot(command_prefix="-", intents=intents)

# قائمة أيديات المصرح لهم فقط بإضافة بوتات (استبدل الأصفار بأيديات المشرفين)
ALLOWED_USERS = [
    1410703717539254373,  # ID حسابك الأساسي
    716867342398914602,  # ID المشرف الأول
    1498036019881054500,  # ID المشرف الثاني
    1490406877782343843,  # ID المشرف الثالث
    1148059857241518101,  # ID المشرف الرابع
       # ID المشرف الخامس
]

# ---------------------------------------------------------
# 3. حدث الحماية التلقائية من البوتات (Anti-Bot Guard)
# ---------------------------------------------------------
@bot.event
async def on_member_join(member: discord.Member):
    if member.bot:
        guild = member.guild
        
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.bot_add):
            inviter = entry.user

            if inviter.id not in ALLOWED_USERS and inviter.id != guild.owner_id:
                try:
                    await member.ban(reason="حماية تلقائية: بوت غير مصرح به من الإدارة.")
                except Exception as e:
                    print(f"❌ تعذر حظر البوت {member.name}: {e}")

                if isinstance(inviter, discord.Member):
                    try:
                        await inviter.edit(roles=[], reason="حماية تلقائية: محاولة إضافة بوت مشبوه.")
                    except discord.Forbidden:
                        print(f"❌ لم يتم سحب رتب {inviter.name} بسبب نقص الصلاحيات.")

                print(f"🚨 [حماية] تم حظر البوت المشبوه {member.name} وسحب رتب العضو {inviter.name}")
                return

# ---------------------------------------------------------
# 4. نظام التذاكر الكامل (Ticket System)
# ---------------------------------------------------------
class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="إغلاق التذكرة 🔒", style=discord.ButtonStyle.red, custom_id="close_ticket")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("سيتم إغلاق التذكرة ومسح القناة خلال 5 ثوانٍ...")
        await asyncio.sleep(5)
        await interaction.channel.delete()

class TicketSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        placeholder="اختر قسم التذكرة...",
        custom_id="ticket_select",
        options=[
            discord.SelectOption(label="دعم فني", description="للمساعدة التقنية والحلول البرمجية", emoji="🛠️"),
            discord.SelectOption(label="استفسار عام", description="لأي سؤال متعلق بالسيرفر والأدوار", emoji="❓"),
            discord.SelectOption(label="بلاغ / شكوى", description="للإبلاغ عن مخالفة أو تقديم شكوى", emoji="🚨"),
            discord.SelectOption(label="طلب شراء / شحن", description="للخدمات المدفوعة والاشتراكات", emoji="💳"),
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        guild = interaction.guild
        category_name = "🎫 التذاكر"
        category = discord.utils.get(guild.categories, name=category_name)
        
        if not category:
            category = await guild.create_category(category_name)

        ticket_channel = await guild.create_text_channel(
            name=f"ticket-{interaction.user.name}",
            category=category,
            overwrites={
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
        )

        embed = discord.Embed(
            title=f"تذكرة قسم: {select.values[0]}",
            description=f"مرحباً بك {interaction.user.mention} 👋\n\nيرجى كتابة تفاصيل طلبك أو المشكلة بالتفصيل وسيقوم فريق الدعم بالرد عليك في أقرب وقت.",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.set_footer(text="لإغلاق التذكرة اضغط على الزر أدناه")

        await ticket_channel.send(embed=embed, view=TicketCloseView())
        await interaction.response.send_message(f"تم إنشاء تذكرتك بنجاح: {ticket_channel.mention}", ephemeral=True)

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_ticket(ctx):
    await ctx.message.delete()
    embed = discord.Embed(
        title="🎫 مركز الدعم والخدمات",
        description="أهلاً بك! يرجى اختيار القسم المناسب لطلبك من القائمة المنسدلة أسفله لفتح تذكرة خاصة.",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed, view=TicketSelectView())

# ---------------------------------------------------------
# 5. نظام الألعاب والفعاليات (Mini-Games System)
# ---------------------------------------------------------
@bot.command()
async def rps(ctx, choice: str = None):
    options = ["حجر", "ورقة", "مقص"]
    if not choice or choice not in options:
        return await ctx.send("يرجى اختيار أحد الخيارات: `حجر` ، `ورقة` ، `مقص`\nمثال: `-rps حجر`")

    bot_choice = random.choice(options)
    if choice == bot_choice:
        result = "تعادل! 🤝"
    elif (choice == "حجر" and bot_choice == "مقص") or \
         (choice == "ورقة" and bot_choice == "حجر") or \
         (choice == "مقص" and bot_choice == "ورقة"):
        result = "كفو! فزت أنت 🎉"
    else:
        result = "فاز البوت! 🤖"

    embed = discord.Embed(title="🎮 لعبة حجر ورقة مقص", color=discord.Color.gold())
    embed.add_field(name="اختيارك", value=choice, inline=True)
    embed.add_field(name="اختيار البوت", value=bot_choice, inline=True)
    embed.add_field(name="النتيجة", value=result, inline=False)
    await ctx.send(embed=embed)

@bot.command()
async def guess(ctx):
    secret_number = random.randint(1, 10)
    await ctx.send("🎲 اخترت رقماً بين **1 و 10**، معك 15 ثانية لتخمين الرقم!")

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content.isdigit()

    try:
        msg = await bot.wait_for('message', check=check, timeout=15.0)
        if int(msg.content) == secret_number:
            await ctx.send(f"🎉 إجابة صحيحة يا {ctx.author.mention}! الرقم كان **{secret_number}**.")
        else:
            await ctx.send(f"❌ إجابة خاطئة! الرقم الصحيح كان **{secret_number}**.")
    except asyncio.TimeoutError:
        await ctx.send(f"⏰ انتهى الوقت! الرقم الصحيح كان **{secret_number}**.")

@bot.command()
async def roulette(ctx):
    outcomes = [
        "🎉 فزت بـ 500 نقطة!",
        "💥 خصرت! الحظ لم يكن بجانبك.",
        "👑 حصلت على لقب أسطورة اليوم!",
        "💀 تم إقصاؤك من الجولة!",
        "🪙 فزت بـ 1000 قطعة ذهبية!"
    ]
    result = random.choice(outcomes)
    await ctx.send(f"🎰 **عجلة الحظ تدور...**\nنتيجة {ctx.author.mention}: {result}")

@bot.command()
async def math(ctx):
    num1 = random.randint(10, 99)
    num2 = random.randint(1, 9)
    operator = random.choice(['+', '-', '*'])
    
    if operator == '+': answer = num1 + num2
    elif operator == '-': answer = num1 - num2
    else: answer = num1 * num2

    await ctx.send(f"⚡ **أسرع شخص يحسب المسألة التالي:**\n> `{num1} {operator} {num2}`")

    def check(m):
        return m.channel == ctx.channel and m.content.strip() == str(answer)

    try:
        msg = await bot.wait_for('message', check=check, timeout=12.0)
        await ctx.send(f"🏆 مبروك {msg.author.mention}! إجابتك صحيحة (`{answer}`).")
    except asyncio.TimeoutError:
        await ctx.send(f"⏰ انتهى الوقت دون إجابة! الناتج الصحيح كان: `{answer}`")

# ---------------------------------------------------------
# 6. الأحداث والتشغيل
# ---------------------------------------------------------
@bot.event
async def on_ready():
    bot.add_view(TicketSelectView())
    bot.add_view(TicketCloseView())
    print(f"✅ تم تسجيل الدخول باسم: {bot.user.name} ({bot.user.id})")
    print("🛡️ نظام الحماية والتذاكر والألعاب المكتملة تعمل بنجاح!")

if __name__ == "__main__":
    keep_alive()
    TOKEN = os.getenv("DISCORD_TOKEN")
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("❌ لم يتم العثور على DISCORD_TOKEN في المتغيرات البيئية!")
