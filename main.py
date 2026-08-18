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
#              لعبة الزر السريع
# ==========================================

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
        await interaction.response.send_message(f"✅ انضم {interaction.user.mention} إلى اللعبة!")

    @discord.ui.button(label="خروج ❌", style=discord.ButtonStyle.danger)
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user not in self.players:
            await interaction.response.send_message("أنت لست منضماً في اللعبة!", ephemeral=True)
            return
        self.players.remove(interaction.user)
        await interaction.response.send_message(f"🚪 خرج {interaction.user.mention} من اللعبة.")

    @discord.ui.button(label="بدء اللعبة 🚀", style=discord.ButtonStyle.primary)
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.host:
            await interaction.response.send_message("صاحب الأمر فقط هو من يستطيع بدء اللعبة!", ephemeral=True)
            return
        if len(self.players) < 1:
            await interaction.response.send_message("يجب أن ينضم لاعب واحد على الأقل!", ephemeral=True)
            return

        self.clear_items()
        await interaction.response.edit_message(content="⏳ **تجهزوا! الزر سيظهر في أي لحظة...**", view=self)

        await asyncio.sleep(random.randint(3, 7))

        click_view = ClickButtonView(self.players)
        await interaction.channel.send("🔴 **اضغط على الزر الآن بأسرع ما يمكن!!**", view=click_view)


class ClickButtonView(discord.ui.View):
    def __init__(self, allowed_players):
        super().__init__(timeout=15)
        self.allowed_players = allowed_players
        self.winner = None

    @discord.ui.button(label="اضغط هناااا!! ⚡", style=discord.ButtonStyle.danger)
    async def press(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user not in self.allowed_players:
            await interaction.response.send_message("أنت لم تكن منضماً في اللعبة!", ephemeral=True)
            return

        if self.winner is None:
            self.winner = interaction.user
            button.disabled = True
            button.label = f"الفائز: {self.winner.display_name}"
            await interaction.response.edit_message(view=self)
            await interaction.channel.send(f"🎉 **مبروووك! {self.winner.mention} ضغط على الزر أولاً وفاز باللعبة!**")


@bot.command(name="زر")
async def start_button_game(ctx):
    view = FastButtonGame(host=ctx.author)
    await ctx.send("🔘 **بدأت لعبة الزر السريع!**\nاضغط على **انضمام** للاشتراك، ثم اضغط **بدء اللعبة**.", view=view)

# ==========================================
#              لعبة المافيا
# ==========================================

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
        await interaction.response.edit_message(content=f"🕵️‍♂️ **تجميع لاعبين المافيا**\n\n**اللاعبين المنضمين ({len(self.players)}):**\n{names}")

    @discord.ui.button(label="خروج 🚪", style=discord.ButtonStyle.secondary)
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user not in self.players:
            await interaction.response.send_message("أنت غير منضم أساساً!", ephemeral=True)
            return
        self.players.remove(interaction.user)
        names = "\n".join([p.mention for p in self.players]) if self.players else "لا يوجد أحد"
        await interaction.response.edit_message(content=f"🕵️‍♂️ **تجميع لاعبين المافيا**\n\n**اللاعبين المنضمين ({len(self.players)}):**\n{names}")

    @discord.ui.button(label="بدء اللعبة 🎬", style=discord.ButtonStyle.danger)
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.host:
            await interaction.response.send_message("مُنشيء اللعبة فقط يمكنه البدء!", ephemeral=True)
            return
        if len(self.players) < 3:
            await interaction.response.send_message("تحتاج 3 لاعبين على الأقل لبدء المافيا!", ephemeral=True)
            return

        mafia_player = random.choice(self.players)
        self.clear_items()
        await interaction.response.edit_message(content="🎭 **بدأت لعبة المافيا! تم توزيع الأدوار في الخاص لكل لاعب.**", view=self)

        for p in self.players:
            try:
                if p == mafia_player:
                    await p.send("🤫 أنت هو **المافيا**! حاول ألا يكتشفك أحد.")
                else:
                    await p.send("️‍🗨️ أنت **مواطن بريء**. ابحث عن المافيا!")
            except:
                pass


@bot.command(name="مافيا")
async def mafia_cmd(ctx):
    view = MafiaLobby(host=ctx.author)
    await ctx.send(f"🕵️‍♂️ **تجميع لاعبين المافيا**\n\n**اللاعبين المنضمين (1):**\n{ctx.author.mention}", view=view)

# ==========================================
#              لعبة الروليت
# ==========================================

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
        await interaction.response.edit_message(content=f"🎰 تدور العجلة الآن... 🎯\n\n💥 **الطلقة أصابت {loser.mention}! لقد تم إقصاؤك من الروليت!**", view=self)


@bot.command(name="روليت")
async def roulette_cmd(ctx):
    view = RouletteLobby(host=ctx.author)
    await ctx.send(f"🎰 **لعبة الروليت الجماعية**\nاضغط انضمام للدخول، وعند التدوير سيتم طرد شخص عشوائياً!", view=view)


TOKEN = os.getenv("BOT_TOKEN")

if __name__ == "__main__":
    bot.run(TOKEN)

if __name__ == "__main__":
    bot.run(TOKEN)

import os

TOKEN = os.getenv("BOT_TOKEN")

if __name__ == "__main__":
    bot.run(TOKEN)
