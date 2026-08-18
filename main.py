import discord
from discord.ext import commands
from discord import app_commands, ui

# إعدادات البوت والـ Intents
intents = discord.Intents.default()
intents.message_content = True

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='-', intents=intents)

    async def setup_hook(self):
        # مزامنة الأوامر التي تبدأ بـ /
        await self.tree.sync()

bot = MyBot()

# --- نظام التذاكر (Tickets System) ---

class TicketMenu(ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="الدعم الفني", description="فتح تذكرة للدعم الفني", emoji="🛠️"),
            discord.SelectOption(label="استفسار", description="فتح تذكرة للاستفسارات", emoji="❓"),
            discord.SelectOption(label="شكوى", description="فتح تذكرة للشكاوى", emoji="⚠️"),
            discord.SelectOption(label="رستارت تكت", description="إعادة ضبط اختيار تذكرة أخرى", emoji="🔄"),
        ]
        super().__init__(placeholder="Menu اختر نوع التذكرة من الـ", min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        choice = self.values[0]
        
        if choice == "رستارت تكت":
            await interaction.response.send_message("تم إعادة ضبط الاختيار، يمكنك الاختيار مرة أخرى.", ephemeral=True)
            return

        # إنشاء روم التذكرة
        guild = interaction.guild
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        channel_name = f"ticket-{choice}-{interaction.user.name}"
        channel = await guild.create_text_channel(name=channel_name, overwrites=overwrites)
        
        await interaction.response.send_message(f"تم إنشاء تذكرتك بنجاح: {channel.mention}", ephemeral=True)
        await channel.send(f"أهلاً بك {interaction.user.mention} في قسم **{choice}**. يرجى كتابة تفاصيل طلبك وسيقوم الفريق بالرد عليك قريباً.")

class TicketView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketMenu())

# أمر تشغيل نظام التذاكر عبر السلاش /
@bot.tree.command(name="setup_tickets", description="تشغيل ورسالة نظام التذاكر")
async def setup_tickets(interaction: discord.Interaction):
    embed = discord.Embed(
        title="نظام التذاكر",
        description="أهلاً وسهلاً فيكم في بوت **LIevr**\n\nفي حال تريد فتح تذكرة 👇",
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed, view=TicketView())


# --- نظام الألعاب (Games System) ---

# قائمة الألعاب المطابقة للصورة تماماً
GAMES_LIST = """
**العاب السيرفر**

- روليت
- xo
- مافيا
- كراسي
- حجرة
- نرد
- عجلة
- hotxo
- غميضة
- ريبلكا
- خمن
- رسمة 🆕


**العاب فردية**

- زر
- اسرع
- فكك
- ادمج
- اعلام
- اعكس
- حرف
- صحح
- ترتيب
- الوان
- ايموجي
- اكشف
"""

# أمر عرض قائمة الألعاب بادئة (-)
@bot.command(name="العاب")
async def games_list(ctx):
    await ctx.send(GAMES_LIST)

# أمثلة لبدء لعبة معينة ببادئة (-)
@bot.command(name="روليت")
async def start_roulette(ctx):
    await ctx.send("🎲 بدأت لعبة **الروليت**!")

@bot.command(name="زر")
async def start_button_game(ctx):
    await ctx.send("🔘 بدأت لعبة **زر**!")

# يمكنك إضافة باقي الألعاب بنفس الطريقة أعلاه

# ضع التوكن الخاص بك بين التنصيص مباشرة
bot.run("MTUzODgzNzI4Mjk3NzQ4ODkwNg.GHZCHi.RExw0dT7LJMxZqV78j31ImKZKZE7mSO7E7S9h8") 
