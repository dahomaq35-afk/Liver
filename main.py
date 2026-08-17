import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Select, View, Button
import asyncio
import random
import os

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # مزامنة أوامر السلاش (/) مع الديسكورد لكي تظهر قائمة الأوامر عند كتابة /
        await self.tree.sync()
        print("تمت مزامنة أوامر السلاش (/) بنجاح!")

bot = MyBot()

# ==========================================
# ⚙️ الإعدادات المخصصة
# ==========================================
TICKET_CATEGORY_NAME = "👑-تذاكر-الدعم"  # التصنيف الذي ستفتح تحته التذاكر
STAFF_ROLE_NAME = "الدعم الفني"         # اسم رتبة الدعم الفني

# ==========================================
# 🛑 لوحة التحكم المتقدمة داخل التذكرة المفتوحة
# ==========================================
class TicketControlView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="استلام التذكرة (Claim)", style=discord.ButtonStyle.success, emoji="👑", custom_id="claim_ticket")
    async def claim_ticket(self, interaction: discord.Interaction, button: Button):
        staff_role = discord.utils.get(interaction.guild.roles, name=STAFF_ROLE_NAME)
        if staff_role and staff_role not in interaction.user.roles and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ هذا الخيار مخصص لطاقم الإدارة والدعم الفني فقط.", ephemeral=True)
            return
        
        embed = discord.Embed(
            description=f"👑 **تم استلام هذه التذكرة بواسطة:** {interaction.user.mention}\nسيكون معك لمساعدتك حتى إغلاق التذكرة.",
            color=discord.Color.gold()
        )
        button.disabled = True
        button.label = f"مستلمة بواسطة {interaction.user.display_name}"
        await interaction.message.edit(view=self)
        await interaction.response.send_message(embed=embed)

    @discord.ui.button(label="استدعاء الدعم (Ping)", style=discord.ButtonStyle.primary, emoji="🔔", custom_id="ping_staff")
    async def ping_staff(self, interaction: discord.Interaction, button: Button):
        staff_role = discord.utils.get(interaction.guild.roles, name=STAFF_ROLE_NAME)
        role_mention = staff_role.mention if staff_role else "@الدعم الفني"
        await interaction.response.send_message(f"🔔 {role_mention} | قام {interaction.user.mention} بطلب مساعدة عاجلة داخل التذكرة!")

    @discord.ui.button(label="إغلاق التذكرة", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: Button):
        embed = discord.Embed(
            title="🔒 نظام الإغلاق",
            description="```yaml\nسيتم حذف وأرشفة هذه التذكرة خلال 5 ثوانٍ...\n```",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)
        await asyncio.sleep(5)
        await interaction.channel.delete()

# ==========================================
# 👑 القائمة المنسدلة لفتح التذاكر
# ==========================================
class TicketSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="👑 التذكرة الملكية VIP",
                description="لطلب الخدمات الخاصة والرتب الحصرية",
                emoji="💎",
                value="royal_vip"
            ),
            discord.SelectOption(
                label="🏆 البطولات والمنافسات",
                description="التسجيل في بطولات فورتنايت وقراند والمنافسات",
                emoji="🥇",
                value="tournaments"
            ),
            discord.SelectOption(
                label="🏎️ سيرفرات ورول بلاي GTA V",
                description="استفسارات سيناريوهات الرول بلاي والعصابات",
                emoji="🏎️",
                value="gta_rp"
            ),
            discord.SelectOption(
                label="🛠️ الدعم الفني العام والاستفسارات",
                description="لأي مشاكل تقنية أو مساعدة خاصة بالسيرفر",
                emoji="⚙️",
                value="general_tech"
            )
        ]
        super().__init__(
            placeholder="─── ⚡ اضغط هنا لاختيار نوع التذكرة ⚡ ───",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_dropdown"
        )

    async def callback(self, interaction: discord.Interaction):
        ticket_type = self.values[0]
        guild = interaction.guild
        user = interaction.user

        category = discord.utils.get(guild.categories, name=TICKET_CATEGORY_NAME)
        if not category:
            category = await guild.create_category(TICKET_CATEGORY_NAME)

        channel_name = f"ticket-{ticket_type}-{user.name.lower()}"
        existing_channel = discord.utils.get(category.channels, name=channel_name)
        if existing_channel:
            await interaction.response.send_message(f"⚠️ **لديك تذكرة مفتوحة بالفعل لهذا القسم:** {existing_channel.mention}", ephemeral=True)
            return

        staff_role = discord.utils.get(guild.roles, name=STAFF_ROLE_NAME)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites)

        embed = discord.Embed(
            title="✨ TICKET SUPPORT SYSTEM ✨",
            description=(
                f"أهلاً بك يا {user.mention} في مركز الدعم الفني!\n\n"
                f"```fix\nنوع التذكرة: [{ticket_type.upper()}]\nحالة الطلب: قيد الانتظار\n```\n"
                f"📌 **يرجى كتابة تفاصيل استفسارك أو طلبك هنا وسيقوم فريق الدعم بالرد عليك فوراً.**"
            ),
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text="Elite Support System")

        await channel.send(content=f"{user.mention} | مرحباً بك!", embed=embed, view=TicketControlView())
        await interaction.response.send_message(f"👑 **تم إنشاء تذكرتك بنجاح:** {channel.mention}", ephemeral=True)

class TicketMainView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

# ==========================================
# 🎮 لعبة حجر ورقة مقص (RPS) بالأزرار
# ==========================================
class RPSView(View):
    def __init__(self, author):
        super().__init__(timeout=30)
        self.author = author

    @discord.ui.button(label="حجر 🪨", style=discord.ButtonStyle.primary)
    async def rock(self, interaction: discord.Interaction, button: Button):
        await self.play(interaction, "حجر")

    @discord.ui.button(label="ورقة 📄", style=discord.ButtonStyle.success)
    async def paper(self, interaction: discord.Interaction, button: Button):
        await self.play(interaction, "ورقة")

    @discord.ui.button(label="مقص ✂️", style=discord.ButtonStyle.danger)
    async def scissors(self, interaction: discord.Interaction, button: Button):
        await self.play(interaction, "مقص")

    async def play(self, interaction: discord.Interaction, user_choice: str):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ هذه اللعبة ليست لك!", ephemeral=True)
            return

        bot_choice = random.choice(["حجر", "ورقة", "مقص"])
        
        if user_choice == bot_choice:
            result = "تعادل! 🤝"
        elif (user_choice == "حجر" and bot_choice == "مقص") or \
             (user_choice == "ورقة" and bot_choice == "حجر") or \
             (user_choice == "مقص" and bot_choice == "ورقة"):
            result = "فزت على البوت! 🎉"
        else:
            result = "خسرت، البوت فاز عليك! 🤖"

        embed = discord.Embed(title="🎮 نتائج لعبة حجر ورقة مقص", color=discord.Color.purple())
        embed.add_field(name="اختيارك", value=user_choice, inline=True)
        embed.add_field(name="اختيار البوت", value=bot_choice, inline=True)
        embed.add_field(name="النتيجة", value=f"**{result}**", inline=False)

        await interaction.response.edit_message(embed=embed, view=None)

# ==========================================
# 🤖 أحداث وأوامر السلاش (/) والبوت
# ==========================================
@bot.event
async def on_ready():
    print(f'تم تشغيل البوت بنجاح باسم: {bot.user.name}')
    await bot.change_presence(activity=discord.Game(name="اكتب / لرؤية جميع الألعاب والأوامر!"))

# 1. أمر السلاش قائمة الألعاب
@bot.tree.command(name="games", description="عرض جميع الألعاب التفاعلية المتاحة في البوت")
async def slash_games(interaction: discord.Interaction):
    embed = discord.Embed(
        title="✨ مركز ألعاب البوت التفاعلي ✨",
        description="استمتع بالألعاب التالية عبر كتابة الأوامر أو استخدام الأزرار في أي روم!",
        color=discord.Color.dark_theme()
    )
    embed.add_field(name="🎲 الألعاب التفاعلية المتاحة:", value=(
        "• `/rps` - لعبة حجر ورقة مقص بالضغط على الأزرار 🪨📄✂️\name"
        "• `/guess` - لعبة تخمين الرقم السري من 1 إلى 10 🔢\name"
        "• `/trivia` - لعبة أسئلة وألغاز عامة واختبار معلومات 🧠\name"
        "• `/roll` - لعبة رمي النرد والحظ 🎲"
    ), inline=False)
    embed.set_footer(text="يمكنك استخدام الأوامر في أي روم بالسيرفر!")
    await interaction.response.send_message(embed=embed)

# 2. أمر حجر ورقة مقص
@bot.tree.command(name="rps", description="لعبة حجر ورقة مقص تفاعلية بالأزرار")
async def slash_rps(interaction: discord.Interaction):
    embed = discord.Embed(title="🎮 لعبة حجر ورقة مقص", description="اختر إما حجر أو ورقة أو مقص من الأزرار بالأسفل:", color=discord.Color.blue())
    view = RPSView(interaction.user)
    await interaction.response.send_message(embed=embed, view=view)

# 3. أمر تخمين الرقم
@bot.tree.command(name="guess", description="لعبة تخمين رقم سري بين 1 و 10")
async def slash_guess(interaction: discord.Interaction):
    secret_number = random.randint(1, 10)
    await interaction.response.send_message(f"🎲 **{interaction.user.mention} لقد اخترت رقماً سرّياً بين 1 و 10!**\nاكتب رقمك الآن في الروم (لديك 15 ثانية):")

    def check(m):
        return m.author == interaction.user and m.channel == interaction.channel and m.content.isdigit()

    try:
        msg = await bot.wait_for('message', check=check, timeout=15.0)
        guess = int(msg.content)
        if guess == secret_number:
            await interaction.followup.send(f"🎉 **كفووو! إجابة صحيحة!** الرقم هو `{secret_number}`.")
        else:
            await interaction.followup.send(f"❌ **إجابة خاطئة!** الرقم الصحيح كان `{secret_number}`.")
    except asyncio.TimeoutError:
        await interaction.followup.send(f"⏰ **انتهى الوقت!** الرقم الصحيح كان `{secret_number}`.")

# 4. أمر أسئلة وألغاز (Trivia)
QUESTIONS = [
    {"q": "ما هي عاصمة المملكة العربية السعودية؟", "a": "الرياض"},
    {"q": "كم عدد أضلاع المثلث؟", "a": "3"},
    {"q": "ما هو أكبر كوكب في المجموعة الشمسية؟", "a": "المشتري"},
    {"q": "ما هو الحيوان الملقب بسفينة الصحراء؟", "a": "الجمل"}
]

@bot.tree.command(name="trivia", description="لعبة أسئلة وألغاز عامة واختبار المعلومات")
async def slash_trivia(interaction: discord.Interaction):
    item = random.choice(QUESTIONS)
    await interaction.response.send_message(f"🧠 **سؤال:** {item['q']}\n*(أجب باللغة العربية خلال 15 ثانية)*")

    def check(m):
        return m.channel == interaction.channel and not m.author.bot

    try:
        msg = await bot.wait_for('message', check=check, timeout=15.0)
        if msg.content.strip() == item['a']:
            await interaction.followup.send(f"🎉 **إجابة صحيحة يا {msg.author.mention}!** الإجابة هي `{item['a']}`.")
        else:
            await interaction.followup.send(f"❌ **إجابة خاطئة!** الإجابة الصحيحة هي `{item['a']}`.")
    except asyncio.TimeoutError:
        await interaction.followup.send(f"⏰ **انتهى الوقت!** الإجابة الصحيحة هي `{item['a']}`.")

# 5. أمر رمي النرد
@bot.tree.command(name="roll", description="رمي نرد عشوائي من 1 إلى 6")
async def slash_roll(interaction: discord.Interaction):
    dice = random.randint(1, 6)
    await interaction.response.send_message(f"🎲 **{interaction.user.mention} رمى النرد وحصل على الرقم:** `{dice}`")

# 6. أمر إنشاء لوحة التذاكر (للمشرفين)
@bot.tree.command(name="tickets_setup", description="إرسال لوحة فتح التذاكر (للإدارة فقط)")
@app_commands.checks.has_permissions(administrator=True)
async def slash_setup_tickets(interaction: discord.Interaction):
    embed = discord.Embed(
        title="👑 LIVER SUPPORT & TICKETS CENTER 👑",
        description=(
            "**أهلاً بك في نظام التذاكر الملكي**\n\n"
            "👇 **اختر القسم المناسب من القائمة المنسدلة أسفله لفتح تذكرتك:**"
        ),
        color=discord.Color.gold()
    )
    embed.add_field(
        name="💎 الأقسام المتاحة للتواصل:",
        value=(
            "• 👑 **التذكرة الملكية VIP:** للخدمات والتسهيلات الخاصة.\n"
            "• 🏆 **قسم البطولات:** السكريمات ومنافسات الجوائز.\n"
            "• 🏎️ **سيرفرات GTA V:** سيناريوهات قراند الحياة الواقعية.\n"
            "• ⚙️ **الدعم التقني:** استفسارات ومشاكل الألعاب."
        ),
        inline=False
    )
    embed.set_footer(text="VIP Elite Support System")
    await interaction.response.send_message(embed=embed, view=TicketMainView())

# تشغيل البوت عبر توكن Render الآمن
bot.run(os.getenv('DISCORD_TOKEN'))

# ضع توكن البوت الخاص بك هنا
bot.run('MTUzODgzNzI4Mjk3NzQ4ODkwNg.GNmbmm.mcn4EpaTLWxHL11Ssg3UM4bfoRvMShcE6lhKXk')
