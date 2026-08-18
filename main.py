import os
import random
import asyncio
import discord
from discord.ext import commands

# إعدادات البوت والـ Intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="-", intents=intents)


# ==========================================
#              نظام التذاكر (TICKETS)
# ==========================================

class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="دعم فني", description="فتح تذكرة للدعم الفني", emoji="🛠️", value="tech"),
            discord.SelectOption(label="استفسار", description="فتح تذكرة للاستفسارات", emoji="❓", value="inquiry"),
            discord.SelectOption(label="شكوى", description="تقديم شكوى للإدارة", emoji="⚠️", value="complaint"),
            discord.SelectOption(label="رستارت", description="إعادة اختيار نوع التذكرة", emoji="🔄", value="restart"),
        ]
        super().__init__(placeholder="اختر قسم التذكرة المناسب...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        selection = self.values[0]

        if selection == "restart":
            await interaction.response.send_message("تم إعادة تعيين الاختيارات. يمكنك الاختيار مجدداً من القائمة أعلاه.", ephemeral=True)
            return

        category_name = {
            "tech": "دعم-فني",
            "inquiry": "استفسار",
            "complaint": "شكوى"
        }.get(selection, "تذكرة")

        guild = interaction.guild
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        channel_name = f"ticket-{selection}-{interaction.user.name}"
        ticket_channel = await guild.create_text_channel(channel_name, overwrites=overwrites)

        embed = discord.Embed(
            title=f"تذكرة {category_name}",
            description=f"أهلاً بك {interaction.user.mention}!\nتم فتح التذكرة بنجاح. يرجى كتابة تفاصيل طلبك وسيقوم فريق الدعم بالرد عليك قريباً.",
            color=discord.Color.green()
        )
        await ticket_channel.send(embed=embed)
        await interaction.response.send_message(f"تم إنشاء تذكرتك بنجاح: {ticket_channel.mention}", ephemeral=True)


class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())


@bot.command(name="تذاكر")
@commands.has_permissions(administrator=True)
async def setup_tickets(ctx):
    embed = discord.Embed(
        title="🎫 قسم التذاكر والدعم",
        description="أهلاً بكم، في حال تريد المساعدة لا تتردد!\nاختر القسم المناسب من القائمة بالأسفل لفتح تذكرة.",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed, view=TicketView())


# ==========================================
#              قائمة الألعاب
# ==========================================

@bot.command(name="العاب")
async def games_menu(ctx):
    embed = discord.Embed(title="🎮 قائمة الألعاب والفعاليات", color=discord.Color.gold())

    server_games = (
        "- روليت\n"
        "- xo\n"
        "- مافيا\n"
        "- كراسي\n"
        "- حجرة\n"
        "- نرد\n"
        "- عجلة\n"
        "- hotxo\n"
        "- غميضة\n"
        "- ريبيلكا\n"
        "- خمن\n"
        "- رسمة 🆕"  # تم إزالة النجمة ✨
    )

    solo_games = (
        "- زر\n"
        "- اسرع\n"
        "- فكك\n"
        "- ادمج\n"
        "- اعلام\n"
        "- اعكس\n"
        "- حرف\n"
        "- صحح\n"
        "- ترتيب\n"
        "- الوان\n"
        "- ايموجي\n"
        "- اكشف"
    )

    embed.add_field(name="**العاب السيرفر**", value=server_games, inline=False)
    embed.add_field(name="**العاب فردية**", value=solo_games, inline=False)
    await ctx.send(embed=embed)


# ==========================================
#            أوامر ألعاب السيرفر
# ==========================================

@bot.command(name="روليت")
async def roulette(ctx):
    res = random.choice(["🎉 مبروك فزت بالروليت!", "💥 للأسف تم إقصاؤك!", "⚡ نجوت هذه الجولة!"])
    await ctx.send(f"{ctx.author.mention} | {res}")

@bot.command(name="xo")
async def xo_game(ctx):
    await ctx.send(f"🎮 لعبة XO: أرسل من تحدي للبدء! (استخدم `-xo @user`)")

@bot.command(name="مافيا")
async def mafia_game(ctx):
    await ctx.send("🕵️‍♂️ تم بدء تسجيل لعبة المافيا! اكتب `انضمام` للوصول للحد الأدنى (4 لاعبين).")

@bot.command(name="كراسي")
async def chairs_game(ctx):
    await ctx.send("🪑 لعبة الكراسي الموسيقية: تجهزوا! اكتب `جلوس` فور ظهور الكرسي!")

@bot.command(name="حجرة")
async def rps_game(ctx):
    await ctx.send(f"{ctx.author.mention} اكتب: حجرة أو ورقة أو مقص!")

@bot.command(name="نرد")
async def dice(ctx):
    await ctx.send(f"🎲 النتيجة: **{random.randint(1, 6)}**")

@bot.command(name="عجلة")
async def wheel_game(ctx):
    items = ["جائزة 🎁", "حظ أوفر ❌", "نقاط مضاعفة 🌟", "عقاب 💀"]
    await ctx.send(f"🎡 دارت العجلة والنتيجة هي: **{random.choice(items)}**")

@bot.command(name="hotxo")
async def hotxo_game(ctx):
    await ctx.send("🔥 تم تشغيل لعبة HOT XO السريعة!")

@bot.command(name="غميضة")
async def hide_game(ctx):
    await ctx.send("🙈 بدأت لعبة الغميضة! اختر مكاناً للاختباء خلال 10 ثوانٍ.")

@bot.command(name="ريبيلكا")
async def replica_game(ctx):
    await ctx.send("📝 لعبة ريبيلكا: انسخ النص التالي بأسرع وقت!")

@bot.command(name="خمن")
async def guess_game(ctx):
    num = random.randint(1, 10)
    await ctx.send("🔢 خمن الرقم من 1 إلى 10!")

@bot.command(name="رسمة")
async def draw_game(ctx):
    await ctx.send("🎨 لعبة رسمة: خمن ماذا تمثل هذه الرسمة!")


# ==========================================
#            أوامر الألعاب الفردية
# ==========================================

@bot.command(name="زر")
async def button_game(ctx):
    await ctx.send("🔘 اضغط على الزر بأسرع ما يمكن!")

@bot.command(name="اسرع")
async def speed_game(ctx):
    words = ["سيرفر", "فعاليات", "ديسكورد", "برمجة"]
    word = random.choice(words)
    await ctx.send(f"⚡ أسرع شخص يكتب الكلمة التالية يفوز: **{word}**")

@bot.command(name="فكك")
async def disassemble_game(ctx):
    words = {"برمجة": "ب ر م ج ة", "ديسكورد": "د ي س ك و ر د", "فعالية": "ف ع ا ل ي ة"}
    word, ans = random.choice(list(words.items()))
    await ctx.send(f"🧩 فكك الكلمة التالية: **{word}**")

@bot.command(name="ادمج")
async def merge_game(ctx):
    await ctx.send("🧩 ادمج الحروف التالية لتكوين كلمة: **س ي ر ف ر**")

@bot.command(name="اعلام")
async def flags_game(ctx):
    flags = {"🇸🇦": "السعودية", "🇪🇬": "مصر", "🇦🇪": "الإمارات", "🇶🇦": "قطر"}
    flag, country = random.choice(list(flags.items()))
    await ctx.send(f"🏳️ ماهي دولة هذا العلم: {flag} ؟")

@bot.command(name="اعكس")
async def reverse_game(ctx):
    words = ["سعودية", "تفاح", "مدرسة"]
    w = random.choice(words)
    await ctx.send(f"🔄 اعكس الكلمة التالية: **{w}**")

@bot.command(name="حرف")
async def letter_game(ctx):
    letters = ["أ", "ب", "ت", "م", "ر"]
    await ctx.send(f"🔤 اذكر كلمة تبدأ بحرف: **{random.choice(letters)}**")

@bot.command(name="صحح")
async def correct_game(ctx):
    await ctx.send("✏️ صحح الكلمة التقديرية التالية: **دسكورد**")

@bot.command(name="ترتيب")
async def sort_game(ctx):
    await ctx.send("🔀 رتب الحروف التالية: **ر د ك و س ي**")

@bot.command(name="الوان")
async def colors_game(ctx):
    colors = ["🔴 أحمر", "🔵 أزرق", "🟢 أخضر", "🟡 أصفر"]
    await ctx.send(f"🎨 ما هو هذا اللون: {random.choice(colors)} ؟")

@bot.command(name="ايموجي")
async def emoji_game(ctx):
    await ctx.send("😀 خمن الايموجي المقصود!")

@bot.command(name="اكشف")
async def reveal_game(ctx):
    await ctx.send("🔍 اكشف الصورة المخفية!")


# ==========================================
#              تشغيل البوت
# ==========================================

TOKEN = os.getenv("BOT_TOKEN")

if __name__ == "__main__":
    bot.run(TOKEN)

import os

TOKEN = os.getenv("BOT_TOKEN")

if __name__ == "__main__":
    bot.run(TOKEN)
