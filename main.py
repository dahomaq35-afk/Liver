import discord
from discord.ext import commands
from discord.ui import Select, View, Button
import asyncio

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ==========================================
# ⚙️ الإعدادات المخصصة
# ==========================================
GAME_CHANNEL_NAME = "👾-ألعاب-liver"       # اسم الروم المخصص لأوامر الألعاب
TICKET_CATEGORY_NAME = "👑-تذاكر-VIP-LIVER"  # التصنيف الذي ستفتح تحته التذاكر
STAFF_ROLE_NAME = "الدعم الفني"            # اسم رتبة الدعم الفني

# ==========================================
# 🛑 لوحة التحكم المتقدمة داخل التذكرة المفتوحة
# ==========================================
class AdvancedTicketControlView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="استلام التذكرة (Claim)", style=discord.ButtonStyle.success, emoji="👑", custom_id="claim_ticket")
    async def claim_ticket(self, interaction: discord.Interaction, button: Button):
        staff_role = discord.utils.get(interaction.guild.roles, name=STAFF_ROLE_NAME)
        if staff_role not in interaction.user.roles and not interaction.user.guild_permissions.administrator:
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

    @discord.ui.button(label="إغلاق التذكرة", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_vip_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: Button):
        embed = discord.Embed(
            title="✨ نظام الإغلاق الـ VVvVIP",
            description="```yaml\nسيتم أرشفة وحذف هذه التذكرة الفاخرة خلال 5 ثوانٍ...\n```",
            color=discord.Color.gold()
        )
        await interaction.response.send_message(embed=embed)
        await asyncio.sleep(5)
        await interaction.channel.delete()

# ==========================================
# 👑 القائمة المنسدلة الفاخرة لفتح التذاكر (VVvVIP)
# ==========================================
class VipTicketSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="👑 التذكرة الملكية الـ VIP",
                description="لطلب الخدمات الخاصة، الرتب الـ VIP، والخدمات الحصرية",
                emoji="💎",
                value="royal_vip"
            ),
            discord.SelectOption(
                label="🏆 قسم البطولات والسكريمات",
                description="التسجيل في بطولات فورتنايت وقراند والمنافسات الكبرى",
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
                description="لأي مشاكل تقنية أو مساعدة خاصة بالألعاب والسيرفر",
                emoji="⚙️",
                value="general_tech"
            )
        ]
        super().__init__(
            placeholder="─── ⚡ اضغط هنا لاختيار نوع التذكرة الـ VIP ⚡ ───",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="vip_ticket_dropdown"
        )

    async def callback(self, interaction: discord.Interaction):
        ticket_type = self.values[0]
        guild = interaction.guild
        user = interaction.user

        category = discord.utils.get(guild.categories, name=TICKET_CATEGORY_NAME)
        if not category:
            category = await guild.create_category(TICKET_CATEGORY_NAME)

        channel_name = f"vip-{ticket_type}-{user.name.lower()}"
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
            title="✨ VIP TICKET SYSTEM | LIVER GAMING ✨",
            description=(
                f"أهلاً بك يا {user.mention} في **قصر الدعم الـ VIP** الخاص بـ **Liver**!\n\n"
                f"```fix\nنوع التذكرة: [{ticket_type.upper()}]\nحالة الطلب: قيد المعالجة الأولية\n```\n"
                f"📌 **يرجى كتابة جميع التفاصيل الخاصة بطلبك هنا وسيتم استلام التذكرة فوراً من قبل طاقم الدعم.**"
            ),
            color=discord.Color.from_rgb(255, 215, 0)
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(
            name="⚡ مميزات خيارات التحكم بالأسفل:",
            value="• 👑 **Claim:** لاستلام التذكرة من قبل الإداري.\n• 🔔 **Ping:** لنداء طاقم الدعم حالة التأخر.\n• 🔒 **Close:** لإغلاق وأرشفة التذكرة.",
            inline=False
        )
        embed.set_footer(text="Liver Elite Support • VIP Experience", icon_url=bot.user.display_avatar.url if bot.user.avatar else None)

        await channel.send(content=f"{user.mention} | مرحباً بك!", embed=embed, view=AdvancedTicketControlView())
        await interaction.response.send_message(f"👑 **تم إنشاء تذكرتك الملكية بنجاح:** {channel.mention}", ephemeral=True)

class VipTicketMainView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(VipTicketSelect())

# ==========================================
# 🕹️ نظام الألعاب (نفس أسلوب Fizbo)
# ==========================================
class GamesDropdown(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="فورتنايت (Fortnite)", description="بطولات، سكريمات، وإعدادات المابات", emoji="🔫", value="fortnite"),
            discord.SelectOption(label="قراند الحياة الواقعية (GTA V RP)", description="سيرفرات الرول بلاي والكتائب", emoji="🚗", value="gta"),
            discord.SelectOption(label="ألعاب المحاكاة (Simulators)", description="Supermarket & Gas Station Sim", emoji="🏪", value="sims"),
            discord.SelectOption(label="روبلوكس (Roblox)", description="سيرفرات خاصة وفعاليات مجتمعية", emoji="🧱", value="roblox"),
            discord.SelectOption(label="ألعاب تفاعلية (Mini-Games)", description="تخمين، ألغاز، وتحديات سريعة", emoji="🎲", value="minigames")
        ]
        super().__init__(placeholder="اختر لعبة لرؤية التفاصيل والفعاليات...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        choice = self.values[0]
        if choice == "fortnite":
            embed = discord.Embed(title="🎯 قسم فورتنايت | Liver Gaming", description="• **البطولات:** سكريمات أسبوعية مع جوائز متجددة.\n• **الفعاليات:** مابات Custom وتحديات بناء.", color=discord.Color.blue())
        elif choice == "gta":
            embed = discord.Embed(title="🎭 قسم GTA V RP | Liver Gaming", description="• **السيرفرات:** سيناريوهات رول بلاي احترافية.\n• **الفصائل:** انضمام للعصابات والكتائب.", color=discord.Color.red())
        elif choice == "sims":
            embed = discord.Embed(title="🛒 ألعاب المحاكاة | Liver Gaming", description="• **Supermarket & Gas Station:** تحديات المتجر وبناء المحطات.", color=discord.Color.gold())
        elif choice == "roblox":
            embed = discord.Embed(title="🧱 قسم روبلوكس | Liver Gaming", description="• **سيرفرات خاصة:** رومات VIP ومسابقات هدايا.", color=discord.Color.purple())
        elif choice == "minigames":
            embed = discord.Embed(title="🎲 الألعاب التفاعلية السريعة", description="• **أسئلة وألغاز (Trivia):** اختبر معلوماتك واجمع النقاط.", color=discord.Color.green())

        await interaction.response.send_message(embed=embed, ephemeral=True)

class GamesView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(GamesDropdown())

def is_game_channel():
    async def predicate(ctx):
        if ctx.channel.name != GAME_CHANNEL_NAME:
            msg = await ctx.send(f"⚠️ هذه الأوامر تعمل فقط داخل الروم المخصص: #{GAME_CHANNEL_NAME}")
            await asyncio.sleep(5)
            await ctx.message.delete()
            await msg.delete()
            return False
        return True
    return commands.check(predicate)

# ==========================================
# 🤖 أحداث وأوامر البوت
# ==========================================
@bot.event
async def on_ready():
    print(f'تم تشغيل البوت بنجاح باسم: {bot.user.name}')
    await bot.change_presence(activity=discord.Game(name="Liver VIP | !العاب"))

@bot.command(name="العاب")
@is_game_channel()
async def show_games(ctx):
    embed = discord.Embed(
        title="✨ مركز ألعاب Liver Gaming ✨",
        description="استعرض الألعاب والخدمات التفاعلية المتاحة بالسيرفر من القائمة أسفله.",
        color=discord.Color.dark_theme()
    )
    embed.add_field(
        name="🎮 الألعاب المدعومة حالياً:",
        value="• 🔫 **Fortnite**\n• 🚗 **GTA V RP**\n• 🏪 **Supermarket & Sims**\n• 🧱 **Roblox**\n• 🎲 **Mini-Games**",
        inline=False
    )
    embed.set_thumbnail(url=bot.user.display_avatar.url if bot.user.avatar else None)
    embed.set_footer(text="Liver Bot - Fizbo Style Games")
    await ctx.send(embed=embed, view=GamesView())

@bot.command(name="تذاكر")
@commands.has_permissions(administrator=True)
async def setup_tickets(ctx):
    await ctx.message.delete()
    
    embed = discord.Embed(
        title="👑 LIVER VVvVVVvVvvVIp SUPPORT CENTER 👑",
        description=(
            "**أهلاً بك في نظام التذاكر الملكي الفاخر لـ Liver Gaming**\n\n"
            "```ansi\n\u001b[1;33m[VIP System]: يتيح لك هذا النظام التواصل المباشر والسريع مع طاقم الدعم والمدراء.\u001b[0m\n```\n"
            "👇 **اختر القسم المناسب من القائمة المنسدلة أسفله لفتح تذكرتك الملكية:**"
        ),
        color=discord.Color.from_rgb(255, 215, 0)
    )
    
    embed.add_field(
        name="💎 الأقسام المتاحة للتواصل:",
        value=(
            "• 👑 **التذكرة الملكية الـ VIP:** للخدمات والتسهيلات الخاصة.\n"
            "• 🏆 **قسم البطولات:** السكريمات ومنافسات الجوائز.\n"
            "• 🏎️ **سيرفرات GTA V:** سيناريوهات قراند الحياة الواقعية.\n"
            "• ⚙️ **الدعم التقني:** استفسارات ومشاكل الألعاب."
        ),
        inline=False
    )
    
    embed.set_thumbnail(url=bot.user.display_avatar.url if bot.user.avatar else None)
    embed.set_footer(text="Liver VIP System • خدمة مخصصة لأفضل تجربة ألعاب", icon_url=bot.user.display_avatar.url if bot.user.avatar else None)

    await ctx.send(embed=embed, view=VipTicketMainView())

# ضع توكن البوت الخاص بك هنا
bot.run('MTUzODgzNzI4Mjk3NzQ4ODkwNg.GNmbmm.mcn4EpaTLWxHL11Ssg3UM4bfoRvMShcE6lhKXk')
