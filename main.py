import os
import random
import asyncio
import discord
from discord.ext import commands

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
        description="أهلاً بكم في حال تريد المساعدة لاتتردد!\nاختر القسم المناسب من القائمة بالأسفل لفتح تذكرة.",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed, view=TicketView())


# ==========================================
#              قائمة الألعاب (-العاب)
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
        "- رسمة 🆕"
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
#              ألعاب السيرفر (تفاعلية)
# ==========================================

# 1. روليت
class RouletteLobby(discord.ui.View):
    def __init__(self, host):
        super().__init__(timeout=60)
        self.host = host
        self.players = [host]

    @discord.ui.button(label="انضمام 🎰", style=discord.ButtonStyle.primary)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user in self.players:
            await interaction.response.send_message("أنت منضم بالفعل!", ephemeral=True)
            return
        self.players.append(interaction.user)
        await interaction.response.send_message(f"✅ انضم {interaction.user.mention} للروليت!")

    @discord.ui.button(label="تدوير العجلة 💥", style=discord.ButtonStyle.danger)
    async def spin(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.host:
            await interaction.response.send_message("صاحب الروليت فقط من يستطيع التدوير!", ephemeral=True)
            return
        loser = random.choice(self.players)
        self.clear_items()
        await interaction.response.edit_message(content=f"🎰 تدور العجلة... 🎯\n💥 **الطلقة أصابت {loser.mention}! تم إقصاؤك!**", view=self)

@bot.command(name="روليت")
async def roulette_cmd(ctx):
    await ctx.send("🎰 **لعبة الروليت الجماعية**\nاضغط انضمام ثم تدوير العجلة!", view=RouletteLobby(ctx.author))

# 2. XO
@bot.command(name="xo")
async def xo_game(ctx, opponent: discord.User = None):
    if not opponent:
        await ctx.send("❌ يرجى منشن الشخص الذي تريد تحديه! مثال: `-xo @user` ")
        return
    await ctx.send(f"🎮 **بدأت لعبة XO بين {ctx.author.mention} و {opponent.mention}!**\n(اكتب مكان الرمز: 1 إلى 9)")

# 3. مافيا
class MafiaLobby(discord.ui.View):
    def __init__(self, host):
        super().__init__(timeout=120)
        self.host = host
        self.players = [host]

    @discord.ui.button(label="انضمام 🕵️‍♂️", style=discord.ButtonStyle.success)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user in self.players:
            await interaction.response.send_message("أنت منضم بالفعل!", ephemeral=True)
            return
        self.players.append(interaction.user)
        names = "\n".join([p.mention for p in self.players])
        await interaction.response.edit_message(content=f"🕵️‍♂️ **تجميع لاعبين المافيا**\n\n**المنضمين ({len(self.players)}):**\n{names}")

    @discord.ui.button(label="بدء اللعبة 🎬", style=discord.ButtonStyle.danger)
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.host:
            await interaction.response.send_message("مُنشيء اللعبة فقط يمكنه البدء!", ephemeral=True)
            return
        if len(self.players) < 3:
            await interaction.response.send_message("تحتاج 3 لاعبين على الأقل!", ephemeral=True)
            return
        mafia = random.choice(self.players)
        self.clear_items()
        await interaction.response.edit_message(content="🎭 **بدأت لعبة المافيا! تم إرسال الأدوار في الخاص.**", view=self)
        for p in self.players:
            try:
                await p.send("🤫 أنت **المافيا**!" if p == mafia else "🕵️ أنت **مواطن بريء**.")
            except: pass

@bot.command(name="مافيا")
async def mafia_cmd(ctx):
    await ctx.send(f"🕵️‍♂️ **تجميع لاعبين المافيا**\n\n**المنضمين (1):**\n{ctx.author.mention}", view=MafiaLobby(ctx.author))

# 4. كراسي
class ChairsView(discord.ui.View):
    def __init__(self, players):
        super().__init__(timeout=30)
        self.players = players
        self.seated = []

    @discord.ui.button(label="جلوس 🪑", style=discord.ButtonStyle.green)
    async def sit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user not in self.players:
            await interaction.response.send_message("أنت لست مشاركاً!", ephemeral=True)
            return
        if interaction.user in self.seated:
            await interaction.response.send_message("جلسَت بالفعل!", ephemeral=True)
            return
        self.seated.append(interaction.user)
        await interaction.response.send_message(f"🪑 جلس {interaction.user.mention} بسرعة!")

@bot.command(name="كراسي")
async def chairs_game(ctx):
    msg = await ctx.send("🪑 **تجهزوا للعب الكراسي...**")
    await asyncio.sleep(random.randint(3, 6))
    await msg.edit(content="🪑 **ظهر الكرسي!! اضغط بسرعة!**", view=ChairsView([ctx.author]))

# 5. حجرة
class RPSView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=30)

    @discord.ui.button(label="حجرة 🪨", style=discord.ButtonStyle.secondary)
    async def rock(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.play(interaction, "حجرة")

    @discord.ui.button(label="ورقة 📄", style=discord.ButtonStyle.primary)
    async def paper(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.play(interaction, "ورقة")

    @discord.ui.button(label="مقص ✂️", style=discord.ButtonStyle.danger)
    async def scissors(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.play(interaction, "مقص")

    async def play(self, interaction, user_choice):
        bot_choice = random.choice(["حجرة", "ورقة", "مقص"])
        if user_choice == bot_choice:
            res = "تعادل! 🤝"
        elif (user_choice == "حجرة" and bot_choice == "مقص") or (user_choice == "ورقة" and bot_choice == "حجرة") or (user_choice == "مقص" and bot_choice == "ورقة"):
            res = "فزت أنت! 🎉"
        else:
            res = "فاز البوت! 🤖"
        await interaction.response.send_message(f"اخترت: **{user_choice}** | اختار البوت: **{bot_choice}**\nالنتيجة: **{res}**", ephemeral=True)

@bot.command(name="حجرة")
async def rps_cmd(ctx):
    await ctx.send("🪨📄✂️ **اختر حركتك:**", view=RPSView())

# 6. نرد
@bot.command(name="نرد")
async def dice_cmd(ctx):
    await ctx.send(f"🎲 {ctx.author.mention} رميت النرد وحصلت على: **{random.randint(1, 6)}**")

# 7. عجلة
@bot.command(name="عجلة")
async def wheel_cmd(ctx):
    prizes = ["جائزة كبرى 🎁", "حظ أوفر ❌", "نقاط 🌟", "عقاب 💀"]
    await ctx.send(f"🎡 دارت العجلة والنتيجة: **{random.choice(prizes)}**")

# 8. hotxo
@bot.command(name="hotxo")
async def hotxo_cmd(ctx):
    await ctx.send("🔥 **بدأت لعبة HOT XO السريعة!** (اكتب خانتك بسرعة قبل الانتهاء)")

# 9. غميضة
@bot.command(name="غميضة")
async def hide_cmd(ctx):
    places = ["خلف الباب 🚪", "تحت الطاولة 📑", "في الخزانة 🗄️"]
    await ctx.send(f"🙈 اخترت الاختباء: **{random.choice(places)}**!")

# 10. ريبيلكا
@bot.command(name="ريبيلكا")
async def replica_cmd(ctx):
    words = ["سيرفر الفعاليات", "ديسكورد بوت", "برمجة ألعاب"]
    w = random.choice(words)
    await ctx.send(f"📝 **انسخ الكلام بأسرع وقت:**\n`{w}`")

# 11. خمن
@bot.command(name="خمن")
async def guess_cmd(ctx):
    await ctx.send(f"🔢 {ctx.author.mention} خمن رقم من 1 إلى 10 في الشات!")

# 12. رسمة
@bot.command(name="رسمة")
async def draw_cmd(ctx):
    await ctx.send("🎨 **لعبة رسمة:** خمن ما هي الرسمة القادمة!")


# ==========================================
#              الألعاب الفردية (تفاعلية)
# ==========================================

# 1. زر
class FastButtonGame(discord.ui.View):
    def __init__(self, host):
        super().__init__(timeout=60)
        self.host = host
        self.players = []

    @discord.ui.button(label="انضمام 🎮", style=discord.ButtonStyle.green)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user in self.players:
            await interaction.response.send_message("أنت منضم بالفعل!", ephemeral=True)
            return
        self.players.append(interaction.user)
        await interaction.response.send_message(f"✅ انضم {interaction.user.mention}!")

    @discord.ui.button(label="بدء اللعبة 🚀", style=discord.ButtonStyle.primary)
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.host:
            await interaction.response.send_message("صاحب اللعبة فقط يبدأ!", ephemeral=True)
            return
        self.clear_items()
        await interaction.response.edit_message(content="⏳ **تجهزوا...**", view=self)
        await asyncio.sleep(random.randint(2, 5))
        click_view = ClickButtonView(self.players)
        await interaction.channel.send("🔴 **اضغط الآن بأسرع ما يمكن!!**", view=click_view)

class ClickButtonView(discord.ui.View):
    def __init__(self, allowed_players):
        super().__init__(timeout=15)
        self.allowed_players = allowed_players
        self.winner = None

    @discord.ui.button(label="اضغط هناااا!! ⚡", style=discord.ButtonStyle.danger)
    async def press(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.winner is None:
            self.winner = interaction.user
            button.disabled = True
            button.label = f"الفائز: {self.winner.display_name}"
            await interaction.response.edit_message(view=self)
            await interaction.channel.send(f"🎉 **مبروك {self.winner.mention} فاز بالزر السريع!**")

@bot.command(name="زر")
async def button_cmd(ctx):
    await ctx.send("🔘 **لعبة الزر السريع!**", view=FastButtonGame(ctx.author))

# 2. اسرع
@bot.command(name="اسرع")
async def speed_cmd(ctx):
    words = ["سعودية", "فعاليات", "تحديات", "سيرفرات"]
    w = random.choice(words)
    await ctx.send(f"⚡ **أسرع شخص يكتب الكلمة التالية يفوز:**\n`{w}`")

# 3. فكك
@bot.command(name="فكك")
async def disassemble_cmd(ctx):
    words = {"مدرسة": "م د ر س ة", "ديسكورد": "د ي س ك و ر د", "رياض": "ر ي ا ض"}
    word, ans = random.choice(list(words.items()))
    await ctx.send(f"🧩 **فكك الكلمة التالية:**\n`{word}`")

# 4. ادمج
@bot.command(name="ادمج")
async def merge_cmd(ctx):
    words = {"س ي ر ف ر": "سيرفر", "ب و ت": "بوت", "ع ل م": "علم"}
    word, ans = random.choice(list(words.items()))
    await ctx.send(f"🧩 **ادمج الحروف التالية:**\n`{word}`")

# 5. اعلام
@bot.command(name="اعلام")
async def flags_cmd(ctx):
    flags = {"🇸🇦": "السعودية", "🇪🇬": "مصر", "🇦🇪": "الامارات", "🇶🇦": "قطر"}
    flag, name = random.choice(list(flags.items()))
    await ctx.send(f"🏳️ **ماهي دولة هذا العلم:** {flag} ؟")

# 6. اعكس
@bot.command(name="اعكس")
async def reverse_cmd(ctx):
    words = ["تفاح", "مدرسة", "شمس"]
    w = random.choice(words)
    await ctx.send(f"🔄 **اعكس الكلمة التالية:**\n`{w}`")

# 7. حرف
@bot.command(name="حرف")
async def letter_cmd(ctx):
    letters = ["أ", "ب", "ت", "م", "ر", "س"]
    await ctx.send(f"🔤 **اذكر كلمة تبدأ بحرف:** **{random.choice(letters)}**")

# 8. صحح
@bot.command(name="صحح")
async def correct_cmd(ctx):
    await ctx.send("✏️ **صحح الكلمة التالية:** `دسكورد`")

# 9. ترتيب
@bot.command(name="ترتيب")
async def sort_cmd(ctx):
    await ctx.send("🔀 **رتب الحروف التالية لتكوين كلمة:** `ر د ك و س ي`")

# 10. الوان
@bot.command(name="الوان")
async def colors_cmd(ctx):
    colors = ["🔴 أحمر", "🔵 أزرق", "🟢 أخضر", "🟡 أصفر"]
    await ctx.send(f"🎨 **ما هو هذا اللون:** {random.choice(colors)} ؟")

# 11. ايموجي
@bot.command(name="ايموجي")
async def emoji_cmd(ctx):
    emojis = ["⚽ (كرة قدم)", "🍕 (بيتزا)", "🚗 (سيارة)"]
    await ctx.send(f"😀 **خمن الايموجي المقصود:** {random.choice(emojis)}")

# 12. اكشف
@bot.command(name="اكشف")
async def reveal_cmd(ctx):
    await ctx.send("🔍 **اكشف الكلمة أو الصورة المخفية!**")


TOKEN = os.getenv("BOT_TOKEN")

if __name__ == "__main__":
    bot.run(TOKEN)


if __name__ == "__main__":
    bot.run(TOKEN)

if __name__ == "__main__":
    bot.run(TOKEN)

import os

TOKEN = os.getenv("BOT_TOKEN")

if __name__ == "__main__":
    bot.run(TOKEN)
