# ==============================================================================
#                               BOT CONFIGURATION
# ==============================================================================
import os
import random
import asyncio
import discord
from discord.ext import commands
from flask import Flask
from threading import Thread

# --- إعداد سيرفر Flask للتشغيل 24/7 على منصة Render ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- إعداد الصلاحيات والبوت ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="-", intents=intents)

# قاموس لتتبع الألعاب النشطة داخل كل روم
active_games = {}

# ==============================================================================
#                            EVENT HANDLERS & READY
# ==============================================================================

@bot.event
async def on_ready():
    print("==========================================")
    print(f"Logged in as: {bot.user.name} - {bot.user.id}")
    print("Bot is fully active and ready for games!")
    print("==========================================")
    
    # تسجيل الواجهات الدائمة حتى تعمل التذاكر حتى لو أعيد تشغيل البوت
    bot.add_view(TicketView())
    bot.add_view(TicketControlView())
    
    await bot.change_presence(
        activity=discord.Game(name="-العاب | -تذاكر")
    )

# ==============================================================================
#                             1. TICKETS SYSTEM (معدّل ومضمون)
# ==============================================================================

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # جعل الواجهة دائمة

    @discord.ui.button(label="إغلاق التذكرة 🔒", style=discord.ButtonStyle.danger, custom_id="close_ticket_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("سيتم إغلاق التذكرة وحذف القناة خلال 5 ثوانٍ...")
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete()
        except discord.Forbidden:
            await interaction.followup.send("❌ البوت لا يملك صلاحية حذف هذه القناة!", ephemeral=True)


class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="دعم فني",
                description="اضغط هنا لفتح تذكرة خاصة بالدعم الفني والمساعدة",
                emoji="🛠️",
                value="tech"
            ),
            discord.SelectOption(
                label="استفسار",
                description="اضغط هنا للتقديم على استفسار عام",
                emoji="❓",
                value="inquiry"
            ),
            discord.SelectOption(
                label="شكوى",
                description="اضغط هنا لرفع شكوى للإدارة",
                emoji="⚠️",
                value="complaint"
            ),
            discord.SelectOption(
                label="رستارت",
                description="إعادة تعيين القائمة واختيار خيار آخر",
                emoji="🔄",
                value="restart"
            ),
        ]
        super().__init__(
            placeholder="اختر قسم التذكرة المناسب من هنا...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_select_menu"
        )

    async def callback(self, interaction: discord.Interaction):
        selection = self.values[0]

        if selection == "restart":
            await interaction.response.send_message(
                "تم إعادة تعيين الاختيارات. يمكنك الاختيار مجدداً من القائمة.",
                ephemeral=True
            )
            return

        category_name = {
            "tech": "دعم-فني",
            "inquiry": "استفسار",
            "complaint": "شكوى"
        }.get(selection, "تذكرة")

        guild = interaction.guild

        # صلاحيات القناة
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }

        channel_name = f"ticket-{selection}-{interaction.user.name}"
        
        try:
            ticket_channel = await guild.create_text_channel(name=channel_name, overwrites=overwrites)
        except discord.Forbidden:
            await interaction.response.send_message("❌ البوت لا يملك صلاحية إنشاء قنوات (Manage Channels)!", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"🎫 تذكرة جديدة: {category_name}",
            description=(
                f"أهلاً بك {interaction.user.mention}!\n\n"
                f"تم فتح التذكرة بنجاح. يرجى كتابة تفاصيل طلبك أو مشكلتك هنا وسيقوم فريق الدعم بالرد عليك في أقرب وقت.\n\n"
                f"للإغلاق اضغط على الزر أدناه."
            ),
            color=discord.Color.green()
        )

        await ticket_channel.send(embed=embed, view=TicketControlView())
        await interaction.response.send_message(
            f"✅ تم إنشاء تذكرتك بنجاح! اذهب إلى: {ticket_channel.mention}",
            ephemeral=True
        )


class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # جعل القائمة المنسدلة دائمة
        self.add_item(TicketSelect())


@bot.command(name="تذاكر")
@commands.has_permissions(administrator=True)
async def setup_tickets_cmd(ctx):
    embed = discord.Embed(
        title="🎫 قسم التذاكر والدعم الفني",
        description=(
            "أهلاً بكم في سيرفرنا!\n"
            "في حال كنت بحاجة إلى مساعدة، أو لديك استفسار أو شكوى، لا تتردد في فتح تذكرة.\n\n"
            "👇 **اختر القسم المناسب من القائمة المنسدلة بالأسفل:**"
        ),
        color=discord.Color.blue()
    )
    embed.set_footer(text="نظام التذاكر التفاعلي")
    await ctx.send(embed=embed, view=TicketView())

# ==============================================================================
#                             2. MAIN GAMES MENU (-العاب)
# ==============================================================================

@bot.command(name="العاب")
async def games_menu_cmd(ctx):
    embed = discord.Embed(
        title="🎮 قائمة الألعاب والفعاليات",
        description="اختر اللعبة وابدأ اللعب مباشرة باستخدام الأمر المناسب!",
        color=discord.Color.gold()
    )

    server_games_list = (
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

    solo_games_list = (
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

    embed.add_field(name="**العاب السيرفر**", value=server_games_list, inline=False)
    embed.add_field(name="**العاب فردية**", value=solo_games_list, inline=False)
    embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
    embed.set_footer(text="استمتع باللعب مع أصدقائك!")

    await ctx.send(embed=embed)

# ==============================================================================
#                             3. SERVER GAMES
# ==============================================================================

# --- 1. لعبة الروليت ---
class RouletteLobbyView(discord.ui.View):
    def __init__(self, host):
        super().__init__(timeout=60)
        self.host = host
        self.players = [host]

    @discord.ui.button(label="انضمام 🎰", style=discord.ButtonStyle.primary)
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user in self.players:
            await interaction.response.send_message("أنت منضم بالفعل للعبة!", ephemeral=True)
            return
        self.players.append(interaction.user)
        await interaction.response.send_message(f"✅ انضم {interaction.user.mention} للعبة الروليت!")

    @discord.ui.button(label="تدوير العجلة 💥", style=discord.ButtonStyle.danger)
    async def spin_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.host:
            await interaction.response.send_message("صاحب اللعبة فقط هو من يستطيع التدوير!", ephemeral=True)
            return
        if len(self.players) < 1:
            await interaction.response.send_message("لا يوجد لاعبين!", ephemeral=True)
            return
        
        loser = random.choice(self.players)
        self.clear_items()
        await interaction.response.edit_message(
            content=f"🎰 تدور العجلة الآن... 🎯\n\n💥 **الطلقة أصابت {loser.mention}! تم إقصاؤك من اللعبة!**",
            view=self
        )

@bot.command(name="روليت")
async def roulette_game_cmd(ctx):
    embed = discord.Embed(
        title="🎰 لعبة الروليت الجماعية",
        description="اضغط على **انضمام** للمشاركة، ثم يضغط صاحب اللعبة على **تدوير العجلة**!",
        color=discord.Color.red()
    )
    await ctx.send(embed=embed, view=RouletteLobbyView(ctx.author))


# --- 2. لعبة XO ---
class XOButton(discord.ui.Button):
    def __init__(self, x: int, y: int):
        super().__init__(style=discord.ButtonStyle.secondary, label=" ", row=y)
        self.x = x
        self.y = y

    async def callback(self, interaction: discord.Interaction):
        view: XOBoardView = self.view
        if interaction.user != view.current_player:
            await interaction.response.send_message("ليس دورك الآن!", ephemeral=True)
            return

        if view.board[self.y][self.x] != 0:
            await interaction.response.send_message("هذه الخانة محجوزة بالفعل!", ephemeral=True)
            return

        view.board[self.y][self.x] = view.current_mark
        self.label = "X" if view.current_mark == 1 else "O"
        self.style = discord.ButtonStyle.danger if view.current_mark == 1 else discord.ButtonStyle.success
        self.disabled = True

        if view.check_winner():
            for child in view.children:
                child.disabled = True
            await interaction.response.edit_message(
                content=f"🎉 **مبروك! الفائز هو {view.current_player.mention}!**",
                view=view
            )
            return

        if view.check_draw():
            await interaction.response.edit_message(content="🤝 **تعادل! انتهت اللعبة.**", view=view)
            return

        view.switch_turn()
        await interaction.response.edit_message(
            content=f"🎮 **لعبة XO**\nالدور الآن على: {view.current_player.mention} ({'X' if view.current_mark == 1 else 'O'})",
            view=view
        )

class XOBoardView(discord.ui.View):
    def __init__(self, player1, player2):
        super().__init__(timeout=120)
        self.p1 = player1
        self.p2 = player2
        self.current_player = player1
        self.current_mark = 1
        self.board = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]

        for y in range(3):
            for x in range(3):
                self.add_item(XOButton(x, y))

    def switch_turn(self):
        if self.current_player == self.p1:
            self.current_player = self.p2
            self.current_mark = 2
        else:
            self.current_player = self.p1
            self.current_mark = 1

    def check_winner(self):
        b = self.board
        for i in range(3):
            if b[i][0] == b[i][1] == b[i][2] != 0: return True
            if b[0][i] == b[1][i] == b[2][i] != 0: return True
        if b[0][0] == b[1][1] == b[2][2] != 0: return True
        if b[0][2] == b[1][1] == b[2][0] != 0: return True
        return False

    def check_draw(self):
        for row in self.board:
            if 0 in row: return False
        return True

@bot.command(name="xo")
async def xo_game_cmd(ctx, opponent: discord.User = None):
    if not opponent or opponent.bot or opponent == ctx.author:
        await ctx.send("❌ يرجى منشن شخص آخر لتحديه! مثال: `-xo @user` ")
        return
    
    view = XOBoardView(ctx.author, opponent)
    await ctx.send(
        f"🎮 **بدأت لعبة XO بين {ctx.author.mention} و {opponent.mention}!**\nالدور الأول لـ: {ctx.author.mention} (X)",
        view=view
    )


# --- 3. لعبة المافيا ---
class MafiaLobbyView(discord.ui.View):
    def __init__(self, host):
        super().__init__(timeout=120)
        self.host = host
        self.players = [host]

    @discord.ui.button(label="انضمام 🕵️‍♂️", style=discord.ButtonStyle.success)
    async def join_mafia(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user in self.players:
            await interaction.response.send_message("أنت منضم بالفعل!", ephemeral=True)
            return
        self.players.append(interaction.user)
        player_list = "\n".join([f"- {p.mention}" for p in self.players])
        await interaction.response.edit_message(
            content=f"🕵️‍♂️ **تجميع لاعبين المافيا**\n\n**اللاعبين المنضمين ({len(self.players)}):**\n{player_list}",
            view=self
        )

    @discord.ui.button(label="بدء اللعبة 🎬", style=discord.ButtonStyle.danger)
    async def start_mafia(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.host:
            await interaction.response.send_message("صاحب اللعبة فقط هو من يستطيع البدء!", ephemeral=True)
            return
        if len(self.players) < 3:
            await interaction.response.send_message("تحتاج إلى 3 لاعبين على الأقل للبدء!", ephemeral=True)
            return

        mafia_player = random.choice(self.players)
        self.clear_items()
        await interaction.response.edit_message(
            content="🎭 **بدأت لعبة المافيا! تم توزيع الأدوار وإرسالها في الخاص لكل لاعب.**",
            view=self
        )

        for p in self.players:
            try:
                if p == mafia_player:
                    await p.send("🤫 **أنت المافيا!** مهمتك إقصاء المواطنين دون أن ينكشف أمرك.")
                else:
                    await p.send("🕵️ **أنت مواطن بريء!** حاول الكشف عن المافيا والتصويت ضده.")
            except discord.Forbidden:
                pass

@bot.command(name="مافيا")
async def mafia_game_cmd(ctx):
    view = MafiaLobbyView(ctx.author)
    await ctx.send(
        f"🕵️‍♂️ **تجميع لاعبين المافيا**\n\n**اللاعبين المنضمين (1):**\n- {ctx.author.mention}",
        view=view
    )


# --- 4. لعبة كراسي ---
class ChairsGameView(discord.ui.View):
    def __init__(self, max_seats):
        super().__init__(timeout=30)
        self.max_seats = max_seats
        self.seated_players = []

    @discord.ui.button(label="جلوس 🪑", style=discord.ButtonStyle.green)
    async def sit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user in self.seated_players:
            await interaction.response.send_message("أنت جالس بالفعل!", ephemeral=True)
            return
        
        if len(self.seated_players) >= self.max_seats:
            await interaction.response.send_message("للأسف نفدت الكراسي!", ephemeral=True)
            return

        self.seated_players.append(interaction.user)
        await interaction.response.send_message(f"🪑 جلس {interaction.user.mention} بسرعة!")

        if len(self.seated_players) == self.max_seats:
            self.clear_items()
            seated_mentions = ", ".join([p.mention for p in self.seated_players])
            await interaction.channel.send(f"🎉 **انتهت الكراسي! اللاعبون الفائزون بالجلسة:**\n{seated_mentions}")

@bot.command(name="كراسي")
async def chairs_game_cmd(ctx):
    seats = random.randint(1, 3)
    msg = await ctx.send("🪑 **تجهزوا... اللعبة ستشغّل الموسيقى وتظهر الكراسي فجأة!**")
    await asyncio.sleep(random.randint(3, 7))
    await msg.edit(content=f"🪑 **ظهرت الكراسي ({seats} كرسي)! اضغط بسرعة!!**", view=ChairsGameView(seats))


# --- 5. لعبة حجرة ورقة مقص ---
class RPSGameView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=30)

    @discord.ui.button(label="حجرة 🪨", style=discord.ButtonStyle.secondary)
    async def rock_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_choice(interaction, "حجرة")

    @discord.ui.button(label="ورقة 📄", style=discord.ButtonStyle.primary)
    async def paper_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_choice(interaction, "ورقة")

    @discord.ui.button(label="مقص ✂️", style=discord.ButtonStyle.danger)
    async def scissors_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_choice(interaction, "مقص")

    async def process_choice(self, interaction: discord.Interaction, user_choice: str):
        bot_choice = random.choice(["حجرة", "ورقة", "مقص"])
        
        if user_choice == bot_choice:
            result = "تعادل! 🤝"
        elif (user_choice == "حجرة" and bot_choice == "مقص") or \
             (user_choice == "ورقة" and bot_choice == "حجرة") or \
             (user_choice == "مقص" and bot_choice == "ورقة"):
            result = "🎉 **فزت أنت على البوت!**"
        else:
            result = "🤖 **فاز البوت عليك!**"

        await interaction.response.send_message(
            f"اختيارك: **{user_choice}** | اختيار البوت: **{bot_choice}**\n\nالنتيجة: {result}",
            ephemeral=True
        )

@bot.command(name="حجرة")
async def rps_game_cmd(ctx):
    await ctx.send("🪨📄✂️ **لعبة حجرة ورقة مقص! اختر حركتك:**", view=RPSGameView())


# --- 6. لعبة نرد ---
@bot.command(name="نرد")
async def dice_game_cmd(ctx):
    dice_result = random.randint(1, 6)
    embed = discord.Embed(
        title="🎲 رمي النرد",
        description=f"{ctx.author.mention} رميت النرد وحصلت على رقم: **{dice_result}**",
        color=discord.Color.purple()
    )
    await ctx.send(embed=embed)


# --- 7. لعبة عجلة ---
@bot.command(name="عجلة")
async def wheel_game_cmd(ctx):
    outcomes = [
        "جائزة كبرى 🎁",
        "حظ أوفر المرة القادمة ❌",
        "500 نقطة 🌟",
        "عقاب: غن أغنية في الصوتية 🎤",
        "تأهل للجولة التالية 🏆",
        "خصم نقاط 💀"
    ]
    res = random.choice(outcomes)
    embed = discord.Embed(
        title="🎡 عجلة الحظ",
        description=f"دارت العجلة وكانت النتيجة لـ {ctx.author.mention}:\n\n✨ **{res}**",
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed)


# --- 8. لعبة HOT XO ---
@bot.command(name="hotxo")
async def hotxo_game_cmd(ctx):
    embed = discord.Embed(
        title="🔥 لعبة HOT XO",
        description="نسخة سريعة ومشتعلة من XO! اكتب رقم الخانة من 1 إلى 9 بسرعة بمجرد دورك.",
        color=discord.Color.orange()
    )
    await ctx.send(embed=embed)


# --- 9. لعبة غميضة ---
@bot.command(name="غميضة")
async def hide_game_cmd(ctx):
    hiding_places = [
        "خلف الباب 🚪",
        "تحت الطاولة 📑",
        "داخل الخزانة 🗄️",
        "فوق السطح 🏠",
        "خلف الستارة 🪟"
    ]
    chosen = random.choice(hiding_places)
    await ctx.send(f"🙈 {ctx.author.mention} اختبأ في: **{chosen}**! هل سيجده أحد؟")

# ==============================================================================
#                      4. SOLO & SPEED QUIZ GAMES
# ==============================================================================

async def run_quiz_game(ctx, question_text: str, correct_answers: list, game_name: str):
    channel_id = ctx.channel.id
    active_games[channel_id] = correct_answers
    
    embed = discord.Embed(
        title=f"🎮 لعبة: {game_name}",
        description=f"**{question_text}**\n\n*(أول شخص يكتب الإجابة الصحيحة هو الفائز!)*",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed)

    def check_message(m):
        if m.channel.id != channel_id or m.author.bot:
            return False
        user_input = m.content.lower().strip()
        return any(user_input == ans.lower().strip() for ans in correct_answers)

    try:
        winner_msg = await bot.wait_for('message', check=check_message, timeout=25.0)
        await ctx.send(f"🎉 **مبروك {winner_msg.author.mention}!** إجابتك صحيحة: **{winner_msg.content}**")
    except asyncio.TimeoutError:
        ans_str = " / ".join(correct_answers)
        await ctx.send(f"⏱️ **انتهى الوقت!** لم يعرف أحد الإجابة الصحيحة. الإجابة هي: **{ans_str}**")
    finally:
        active_games.pop(channel_id, None)


# --- 1. زر ---
class FastButtonLobby(discord.ui.View):
    def __init__(self, host):
        super().__init__(timeout=60)
        self.host = host
        self.players = []

    @discord.ui.button(label="انضمام 🎮", style=discord.ButtonStyle.green)
    async def join_fast_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user in self.players:
            await interaction.response.send_message("أنت منضم بالفعل!", ephemeral=True)
            return
        self.players.append(interaction.user)
        await interaction.response.send_message(f"✅ انضم {interaction.user.mention}!")

    @discord.ui.button(label="بدء اللعبة 🚀", style=discord.ButtonStyle.primary)
    async def start_fast_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.host:
            await interaction.response.send_message("صاحب اللعبة فقط هو من يستطيع البدء!", ephemeral=True)
            return
        self.clear_items()
        await interaction.response.edit_message(content="⏳ **تجهزوا... الأزرار ستظهر في أي لحظة!**", view=self)
        
        await asyncio.sleep(random.randint(2, 6))
        click_view = ClickFastButtonView()
        await interaction.channel.send("🔴 **اضغط الزر الأحمر الآن بأسرع ما يمكن!!**", view=click_view)

class ClickFastButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=15)
        self.winner = None

    @discord.ui.button(label="اضغط هناااا!! ⚡", style=discord.ButtonStyle.danger)
    async def press_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.winner is None:
            self.winner = interaction.user
            button.disabled = True
            button.label = f"الفائز: {self.winner.display_name}"
            await interaction.response.edit_message(view=self)
            await interaction.channel.send(f"🎉 **مبروك {self.winner.mention}! أنت أسرع شخص وضغطت على الزر!**")

@bot.command(name="زر")
async def fast_button_cmd(ctx):
    await ctx.send("🔘 **لعبة الزر السريع!** اضغط انضمام للتجمع.", view=FastButtonLobby(ctx.author))


# --- 2. اسرع ---
@bot.command(name="اسرع")
async def speed_text_cmd(ctx):
    words_data = [
        "سعودية", "فعاليات", "تحديات", "سيرفرات", "برمجة",
        "ديسكورد", "ألعاب", "سرعة", "بطولة", "انتصار"
    ]
    target = random.choice(words_data)
    await run_quiz_game(ctx, f"أسرع شخص يكتب الكلمة التالية:\n\n`{target}`", [target], "اسرع")


# --- 3. فكك ---
@bot.command(name="فكك")
async def disassemble_game_cmd(ctx):
    data = {
        "مدرسة": ["م د ر س ة"],
        "ديسكورد": ["د ي س ك و ر د"],
        "رياض": ["ر ي ا ض"],
        "سيرفر": ["س ي ر ف ر"],
        "كمبيوتر": ["ك م ب ي و ت ر"],
        "هاتف": ["هـ ا ت ف", "ه ا ت ف"]
    }
    word, ans = random.choice(list(data.items()))
    await run_quiz_game(ctx, f"فكك الكلمة التالية بحروف متباعدة:\n\n`{word}`", ans, "فكك")


# --- 4. ادمج ---
@bot.command(name="ادمج")
async def merge_game_cmd(ctx):
    data = {
        "س ي ر ف ر": ["سيرفر"],
        "ب و ت": ["بوت"],
        "ع ل م": ["علم"],
        "د ي س ك و ر د": ["ديسكورد"],
        "س ع و د ي ة": ["سعودية"]
    }
    word, ans = random.choice(list(data.items()))
    await run_quiz_game(ctx, f"ادمج الحروف التالية لتكوين كلمة مفيدة:\n\n`{word}`", ans, "ادمج")


# --- 5. اعلام ---
@bot.command(name="اعلام")
async def flags_game_cmd(ctx):
    flags_data = {
        "🇸🇦": ["السعودية", "سعودية", "ksa"],
        "🇪🇬": ["مصر"],
        "🇦🇪": ["الامارات", "الإمارات"],
        "🇶🇦": ["قطر"],
        "🇰🇼": ["الكويت"],
        "🇧🇭": ["البحرين"],
        "🇴🇲": ["عمان", "عُمان"]
    }
    flag_emoji, ans = random.choice(list(flags_data.items()))
    await run_quiz_game(ctx, f"ما هي الدولة صاحب هذا العلم: {flag_emoji} ؟", ans, "اعلام")


# --- 6. اعكس ---
@bot.command(name="اعكس")
async def reverse_game_cmd(ctx):
    data = {
        "تفاح": ["حافت"],
        "شمس": ["سمش"],
        "قمر": ["رمق"],
        "مدرسة": ["ةسردم"],
        "سيرفر": ["رفريس"]
    }
    word, ans = random.choice(list(data.items()))
    await run_quiz_game(ctx, f"اعكس الكلمة التالية:\n\n`{word}`", ans, "اعكس")


# --- 7. حرف ---
@bot.command(name="حرف")
async def letter_game_cmd(ctx):
    letters = ["أ", "ب", "ت", "م", "ر", "س", "ج", "ع"]
    chosen_let = random.choice(letters)
    embed = discord.Embed(
        title="🔤 لعبة حرف",
        description=f"اكتب أي كلمة تبدأ بحرف: **{chosen_let}**",
        color=discord.Color.teal()
    )
    await ctx.send(embed=embed)


# --- 8. صحح ---
@bot.command(name="صحح")
async def correct_game_cmd(ctx):
    data = {
        "دسكورد": ["ديسكورد"],
        "طاوله": ["طاولة"],
        "مستشفي": ["مستشفى"],
        "الرياضض": ["الرياض"]
    }
    word, ans = random.choice(list(data.items()))
    await run_quiz_game(ctx, f"صحح الإملاء الخاطئ للكلمة التالية:\n\n`{word}`", ans, "صحح")


# --- 9. ترتيب ---
@bot.command(name="ترتيب")
async def sort_game_cmd(ctx):
    data = {
        "ر د ك و س ي": ["ديسكورد"],
        "ة س د ر م": ["مدرسة"],
        "ر ف ر ي س": ["سيرفر"]
    }
    scrambled, ans = random.choice(list(data.items()))
    await run_quiz_game(ctx, f"رتب الحروف التالية لتكوين كلمة صحيحة:\n\n`{scrambled}`", ans, "ترتيب")


# --- 10. الوان ---
@bot.command(name="الوان")
async def colors_game_cmd(ctx):
    colors_data = {
        "🔴": ["احمر", "أحمر"],
        "🔵": ["ازرق", "أزرق"],
        "🟢": ["اخضر", "أخضر"],
        "🟡": ["اصفر", "أصفر"],
        "⚫": ["اسود", "أسود"],
        "⚪": ["ابيض", "أبيض"]
    }
    emoji_color, ans = random.choice(list(colors_data.items()))
    await run_quiz_game(ctx, f"ما هو اسم هذا اللون: {emoji_color} ؟", ans, "الوان")


# --- 11. ايموجي ---
@bot.command(name="ايموجي")
async def emoji_game_cmd(ctx):
    emojis_data = {
        "⚽": ["كرة قدم", "كرة القدم"],
        "🍕": ["بيتزا", "البيتزا"],
        "🚗": ["سيارة", "السيارة"],
        "🚀": ["صاروخ", "الصاروخ"]
    }
    emoji_icon, ans = random.choice(list(emojis_data.items()))
    await run_quiz_game(ctx, f"خمن اسم هذا الشئ الممثل بالإيموجي: {emoji_icon} ؟", ans, "ايموجي")


# --- 12. خمن ---
@bot.command(name="خمن")
async def guess_game_cmd(ctx):
    secret_num = str(random.randint(1, 10))
    await run_quiz_game(ctx, "خمن الرقم الصحيح المخفي من 1 إلى 10!", [secret_num], "خمن")


# --- 13. ريبيلكا ---
@bot.command(name="ريبيلكا")
async def replica_game_cmd(ctx):
    phrases = [
        "سيرفر الفعاليات الأفضل",
        "ديسكورد بوت ألعاب",
        "مرحباً بكم جميعاً"
    ]
    phrase = random.choice(phrases)
    await run_quiz_game(ctx, f"انسخ النص التالي بدقة وسرعة:\n\n`{phrase}`", [phrase], "ريبيلكا")


# --- 14. رسمة ---
@bot.command(name="رسمة")
async def draw_game_cmd(ctx):
    embed = discord.Embed(
        title="🎨 لعبة رسمة",
        description="تجهز! سيقوم البوت بإرسال رسمة ومطلوب من الجميع التخمين.",
        color=discord.Color.magenta()
    )
    await ctx.send(embed=embed)


# --- 15. اكشف ---
@bot.command(name="اكشف")
async def reveal_game_cmd(ctx):
    embed = discord.Embed(
        title="🔍 لعبة اكشف",
        description="اكشف الصورة أو الكلمة المغطاة بالتضليل!",
        color=discord.Color.dark_grey()
    )
    await ctx.send(embed=embed)

# ==============================================================================
#                             5. BOT RUNNER
# ==============================================================================

keep_alive()

token = os.getenv("TOKEN")

if __name__ == "__main__":
    if token:
        bot.run(token)
    else:
        print("❌ خطأ: لم يتم العثور على متغير البيئة TOKEN في Render!")
