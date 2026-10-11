import os, re, sqlite3, asyncio, ast
from threading import Thread
from datetime import datetime, timezone
from flask import Flask
import discord
from discord import app_commands
from discord.ext import commands

TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    raise RuntimeError('DISCORD_TOKEN is missing')
DB_FILE = 'mt_ticket_system.db'
MAX_TICKETS = 25

# ---------------- Render health server ----------------
app = Flask(__name__)
@app.route('/')
def home(): return 'MT Ticket System is Online!'
@app.route('/health')
def health(): return 'OK'
def run_flask(): app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
Thread(target=run_flask, daemon=True).start()

# ---------------- Database ----------------
def get_db():
    conn = sqlite3.connect(DB_FILE); conn.row_factory = sqlite3.Row; return conn

def init_database():
    with get_db() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS ticket_setups ( guild_id INTEGER NOT NULL, ticket_number INTEGER NOT NULL, ticket_name TEXT NOT NULL, category_id INTEGER NOT NULL, staff_role_id INTEGER NOT NULL, log_channel_id INTEGER NOT NULL, ticket_message TEXT NOT NULL DEFAULT 'أهلًا بك، اشرح مشكلتك بالتفصيل وسيتم الرد عليك من فريق الدعم.', image_url TEXT, points_enabled INTEGER NOT NULL DEFAULT 0, points_amount INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(guild_id,ticket_number))''')
        conn.execute('''CREATE TABLE IF NOT EXISTS open_tickets ( channel_id INTEGER PRIMARY KEY, guild_id INTEGER NOT NULL, owner_id INTEGER NOT NULL, ticket_number INTEGER NOT NULL, claimer_id INTEGER, serial_number INTEGER NOT NULL DEFAULT 1, points_awarded INTEGER NOT NULL DEFAULT 0)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS panel_configs ( panel_id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, title TEXT NOT NULL, description TEXT NOT NULL, image_url TEXT, footer TEXT, ticket_message TEXT NOT NULL, method TEXT NOT NULL, ticket_numbers TEXT NOT NULL DEFAULT '')''')
        conn.execute('''CREATE TABLE IF NOT EXISTS guild_ticket_counters ( guild_id INTEGER PRIMARY KEY, last_number INTEGER NOT NULL DEFAULT 0)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS ticket_points ( guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, points INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(guild_id,user_id))''')
        # Safe migrations for databases created by older versions.
        migrations = {
            'ticket_setups': [('ticket_message', "TEXT NOT NULL DEFAULT 'أهلًا بك، اشرح مشكلتك بالتفصيل وسيتم الرد عليك من فريق الدعم.'"), ('image_url','TEXT'), ('points_enabled','INTEGER NOT NULL DEFAULT 0'), ('points_amount','INTEGER NOT NULL DEFAULT 0')],
            'open_tickets': [('serial_number','INTEGER NOT NULL DEFAULT 1'), ('points_awarded','INTEGER NOT NULL DEFAULT 0')],
            'panel_configs': [('ticket_numbers', "TEXT NOT NULL DEFAULT ''")]
        }
        for table, cols in migrations.items():
            existing = {r['name'] for r in conn.execute(f'PRAGMA table_info({table})')}
            for name, declaration in cols:
                if name not in existing: conn.execute(f'ALTER TABLE {table} ADD COLUMN {name} {declaration}')

def save_ticket(guild_id, number, name, category_id, role_id, log_id, message, image, points_enabled, points_amount):
    with get_db() as c:
        c.execute('''INSERT OR REPLACE INTO ticket_setups (guild_id,ticket_number,ticket_name,category_id,staff_role_id,log_channel_id,ticket_message,image_url,points_enabled,points_amount) VALUES(?,?,?,?,?,?,?,?,?,?)''', (guild_id,number,name,category_id,role_id,log_id,message,image,int(points_enabled),points_amount))

def get_ticket(guild_id, number):
    with get_db() as c: return c.execute('SELECT * FROM ticket_setups WHERE guild_id=? AND ticket_number=?',(guild_id,number)).fetchone()
def get_all_tickets(guild_id):
    with get_db() as c: return c.execute('SELECT * FROM ticket_setups WHERE guild_id=? ORDER BY ticket_number',(guild_id,)).fetchall()
def get_panel(panel_id):
    with get_db() as c: return c.execute('SELECT * FROM panel_configs WHERE panel_id=?',(panel_id,)).fetchone()
def get_all_panels():
    with get_db() as c: return c.execute('SELECT * FROM panel_configs').fetchall()
def save_panel(guild_id,title,description,image,footer,message,method,numbers):
    with get_db() as c:
        cur=c.execute('''INSERT INTO panel_configs(guild_id,title,description,image_url,footer,ticket_message,method,ticket_numbers) VALUES(?,?,?,?,?,?,?,?)''',(guild_id,title,description,image,footer,message,method,','.join(map(str,numbers))))
        return cur.lastrowid
def get_open_ticket(channel_id):
    with get_db() as c: return c.execute('SELECT * FROM open_tickets WHERE channel_id=?',(channel_id,)).fetchone()
def find_open_ticket(guild,user_id):
    with get_db() as c: row=c.execute('SELECT channel_id FROM open_tickets WHERE guild_id=? AND owner_id=? LIMIT 1',(guild.id,user_id)).fetchone()
    return guild.get_channel(row['channel_id']) if row else None
def set_ticket_claimer(channel_id,user_id):
    with get_db() as c: c.execute('UPDATE open_tickets SET claimer_id=? WHERE channel_id=?',(user_id,channel_id))
def delete_open_ticket(channel_id):
    with get_db() as c: c.execute('DELETE FROM open_tickets WHERE channel_id=?',(channel_id,))
def next_serial(guild_id):
    with get_db() as c:
        c.execute('INSERT OR IGNORE INTO guild_ticket_counters(guild_id,last_number) VALUES(?,0)',(guild_id,))
        c.execute('UPDATE guild_ticket_counters SET last_number=last_number+1 WHERE guild_id=?',(guild_id,))
        return c.execute('SELECT last_number FROM guild_ticket_counters WHERE guild_id=?',(guild_id,)).fetchone()['last_number']
def add_points(guild_id,user_id,amount):
    with get_db() as c:
        c.execute('INSERT INTO ticket_points(guild_id,user_id,points) VALUES(?,?,?) ON CONFLICT(guild_id,user_id) DO UPDATE SET points=points+excluded.points',(guild_id,user_id,amount))
def get_points(guild_id,user_id):
    with get_db() as c:
        r=c.execute('SELECT points FROM ticket_points WHERE guild_id=? AND user_id=?',(guild_id,user_id)).fetchone()
        return r['points'] if r else 0

def clean_channel_name(name):
    name=name.lower(); name=re.sub(r'[^a-zA-Z0-9\u0600-\u06FF\s\-]','',name); name=re.sub(r'\s+','-',name); name=re.sub(r'-+','-',name).strip('-')
    return (name or 'ticket')[:70]
def valid_image_url(url): return not url or url.startswith(('https://','http://'))
def is_admin(member): return isinstance(member,discord.Member) and member.guild_permissions.administrator
def selected_panel_tickets(guild_id,panel):
    try: numbers=[int(x) for x in (panel['ticket_numbers'] or '').split(',') if x.strip()]
    except Exception: numbers=[]
    all_tickets=get_all_tickets(guild_id)
    return [t for t in all_tickets if not numbers or t['ticket_number'] in numbers]
def staff_allowed(member,ticket):
    role=member.guild.get_role(ticket['staff_role_id'])
    return bool(role and role in member.roles) or member.guild_permissions.administrator

# ---------------- Bot ----------------
class MTBot(commands.Bot):
    async def setup_hook(self):
        init_database()
        self.add_view(TicketControlsView())
        self.add_view(TicketActionsView())
        for panel in get_all_panels():
            tickets=selected_panel_tickets(panel['guild_id'],panel)
            if tickets:
                self.add_view(TicketMenuPanelView(tickets,panel['panel_id']) if panel['method']=='menu' else TicketButtonsPanelView(tickets,panel['panel_id']))
        # Re-register persistent application controls for saved pending applications.
        try:
            with get_db() as c:
                rows=c.execute("SELECT application_id FROM applications WHERE status='pending'").fetchall()
            for row in rows: self.add_view(ApplicationReviewView(row['application_id']))
        except sqlite3.Error: pass
        try:
            synced=await self.tree.sync(); print(f'Synced {len(synced)} slash commands.')
        except Exception as e: print('Slash sync error:',e)

intents=discord.Intents.default(); intents.guilds=True; intents.members=True
bot=MTBot(command_prefix='-',intents=intents)

# ---------------- Ticket setup slash command ----------------
@app_commands.choices(points_enabled=[app_commands.Choice(name='نعم',value='yes'),app_commands.Choice(name='لا',value='no')])
@bot.tree.command(name='ticket_setup',description='تجهيز نوع تذكرة جديد بكل إعداداته')
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(number='رقم نوع التذكرة من 1 إلى 25، يجب ألا يكون مستخدمًا لنوع آخر', name='اسم نوع التذكرة الذي يظهر في البانل', ticket_message='رسالة الإدارة داخل التذكرة. يمكنك استخدام {user} و{support}', image_url='رابط صورة اختياري يظهر داخل التذكرة', category='التصنيف الذي ستنشأ بداخله التذاكر', staff_role='رتبة فريق الدعم التي تستطيع مشاهدة التذكرة', log_channel='روم تسجيل فتح وإغلاق التذاكر', points_enabled='هل تريد تفعيل نقاط لمستلم التذكرة عند إغلاقها؟', points_amount='عدد النقاط التي تمنح عند الإغلاق إذا كانت النقاط مفعلة')
async def ticket_setup(interaction:discord.Interaction, number:app_commands.Range[int,1,25], name:str, ticket_message:str, category:discord.CategoryChannel, staff_role:discord.Role, log_channel:discord.TextChannel, points_enabled:app_commands.Choice[str], points_amount:app_commands.Range[int,0,10000]=0, image_url:str=''):
    if not name.strip() or not ticket_message.strip():
        return await interaction.response.send_message('❌ اسم التذكرة ورسالة الإدارة لا يمكن أن يكونا فارغين.',ephemeral=True)
    if not valid_image_url(image_url): return await interaction.response.send_message('❌ رابط الصورة يجب أن يبدأ بـ https:// أو http://',ephemeral=True)
    old=get_ticket(interaction.guild.id,number)
    if old and old['ticket_name'].lower()!=name.strip().lower():
        # Number is the configured ticket type key; replacing the same key is allowed.
        pass
    enabled=points_enabled.value=='yes'
    save_ticket(interaction.guild.id,number,name.strip(),category.id,staff_role.id,log_channel.id,ticket_message.strip(),image_url.strip(),enabled,points_amount if enabled else 0)
    embed=discord.Embed(title='✅ تم إعداد نوع التذكرة',color=discord.Color.green())
    embed.add_field(name='رقم النوع',value=str(number),inline=True)
    embed.add_field(name='اسم التذكرة',value=name.strip(),inline=True)
    embed.add_field(name='التصنيف',value=category.mention,inline=True)
    embed.add_field(name='رتبة الدعم',value=staff_role.mention,inline=True)
    embed.add_field(name='روم السجلات',value=log_channel.mention,inline=True)
    embed.add_field(name='النقاط',value=f'مفعلة: {points_amount} نقطة عند الإغلاق' if enabled else 'غير مفعلة',inline=False)
    embed.add_field(name='رسالة الإدارة',value=ticket_message.strip()[:1024],inline=False)
    if image_url.strip(): embed.set_thumbnail(url=image_url.strip())
    await interaction.response.send_message(embed=embed,ephemeral=True)

# ---------------- Panel setup ----------------
@bot.tree.command(name='ticket_panel',description='إنشاء بانل واختيار أنواع التذاكر التي تظهر فيه')
@app_commands.checks.has_permissions(administrator=True)
@app_commands.choices(method=[app_commands.Choice(name='منيو',value='menu'),app_commands.Choice(name='أزرار',value='buttons')])
@app_commands.describe(title='عنوان البانل', description='النص الذي يظهر في البانل', image_url='رابط صورة اختياري', method='طريقة عرض أنواع التذاكر', ticket_numbers='أرقام أنواع التذاكر التي تظهر، مفصولة بفاصلة مثل 1,3. اكتب all لعرض الكل', footer='نص أسفل البانل - اختياري', channel='الروم الذي تريد إرسال البانل فيه')
async def ticket_panel(interaction:discord.Interaction,title:str,description:str,method:app_commands.Choice[str],ticket_numbers:str='all',image_url:str='',footer:str='',channel:discord.TextChannel=None):
    tickets=get_all_tickets(interaction.guild.id)
    if not tickets: return await interaction.response.send_message('❌ جهّز نوع تذكرة أولًا باستخدام `/ticket_setup`.',ephemeral=True)
    if not valid_image_url(image_url): return await interaction.response.send_message('❌ رابط الصورة يجب أن يبدأ بـ https:// أو http://',ephemeral=True)
    if ticket_numbers.strip().lower()=='all': numbers=[t['ticket_number'] for t in tickets]
    else:
        try: numbers=sorted(set(int(x.strip()) for x in ticket_numbers.split(',') if x.strip()))
        except ValueError: return await interaction.response.send_message('❌ اكتب أرقام الأنواع بهذا الشكل: `1,3` أو `all`.',ephemeral=True)
    available={t['ticket_number'] for t in tickets}; invalid=[n for n in numbers if n not in available]
    if invalid: return await interaction.response.send_message('❌ أرقام الأنواع غير المجهزة: '+', '.join(map(str,invalid)),ephemeral=True)
    if not numbers: return await interaction.response.send_message('❌ اختر نوع تذكرة واحدًا على الأقل.',ephemeral=True)
    if len(numbers)>25: return await interaction.response.send_message('❌ الحد الأقصى 25 نوعًا في البانل.',ephemeral=True)
    panel_id=save_panel(interaction.guild.id,title,description,image_url.strip(),footer.strip(),'',method.value,numbers)
    panel=get_panel(panel_id); chosen=[t for t in tickets if t['ticket_number'] in numbers]
    embed=discord.Embed(title=title,description=description,color=discord.Color.blue())
    if image_url.strip(): embed.set_thumbnail(url=image_url.strip())
    if footer.strip(): embed.set_footer(text=footer.strip())
    if interaction.guild.icon: embed.set_author(name=interaction.guild.name,icon_url=interaction.guild.icon.url)
    embed.add_field(name='طريقة فتح التذكرة',value='📋 اختر نوع التذكرة من القائمة.' if method.value=='menu' else '🔘 اضغط زر نوع التذكرة.',inline=False)
    target=channel or interaction.channel
    view=TicketMenuPanelView(chosen,panel_id) if method.value=='menu' else TicketButtonsPanelView(chosen,panel_id)
    await target.send(embed=embed,view=view)
    await interaction.response.send_message(f'✅ تم إرسال البانل في {target.mention}.\nالأنواع: '+', '.join(f'**{n}**' for n in numbers),ephemeral=True)

# ---------------- Ticket panel components ----------------
class TicketMenuSelect(discord.ui.Select):
    def __init__(self,tickets,panel_id):
        self.panel_id=panel_id
        options=[discord.SelectOption(label=t['ticket_name'][:100],value=str(t['ticket_number']),emoji='🎫',description=f"فتح {t['ticket_name']}"[:100]) for t in tickets[:25]]
        super().__init__(placeholder='اختر نوع التذكرة',min_values=1,max_values=1,options=options,custom_id=f'mt_ticket_menu_{panel_id}')
    async def callback(self,interaction):
        ticket=get_ticket(interaction.guild.id,int(self.values[0])); panel=get_panel(self.panel_id)
        if not ticket or not panel: return await interaction.response.send_message('❌ نوع التذكرة أو البانل غير موجود.',ephemeral=True)
        await create_ticket(interaction,ticket,panel)
class TicketMenuPanelView(discord.ui.View):
    def __init__(self,tickets,panel_id):
        super().__init__(timeout=None); self.add_item(TicketMenuSelect(tickets,panel_id))
class TicketOpenTypeButton(discord.ui.Button):
    def __init__(self,ticket,panel_id):
        self.ticket_number=ticket['ticket_number']; self.panel_id=panel_id
        super().__init__(label=ticket['ticket_name'][:80],style=discord.ButtonStyle.primary,emoji='🎫',custom_id=f'mt_ticket_button_{panel_id}_{self.ticket_number}')
    async def callback(self,interaction):
        ticket=get_ticket(interaction.guild.id,self.ticket_number); panel=get_panel(self.panel_id)
        if not ticket or not panel: return await interaction.response.send_message('❌ نوع التذكرة أو البانل غير موجود.',ephemeral=True)
        await create_ticket(interaction,ticket,panel)
class TicketButtonsPanelView(discord.ui.View):
    def __init__(self,tickets,panel_id):
        super().__init__(timeout=None)
        for ticket in tickets[:25]: self.add_item(TicketOpenTypeButton(ticket,panel_id))

# ---------------- Create ticket ----------------
async def create_ticket(interaction,ticket,panel):
    guild,user=interaction.guild,interaction.user
    existing=find_open_ticket(guild,user.id)
    if existing: return await interaction.response.send_message(f'❌ لديك تذكرة مفتوحة بالفعل: {existing.mention}',ephemeral=True)
    category=guild.get_channel(ticket['category_id']); role=guild.get_role(ticket['staff_role_id']); log=guild.get_channel(ticket['log_channel_id'])
    if not category or not role: return await interaction.response.send_message('❌ تصنيف التذكرة أو رتبة الدعم غير موجودة.',ephemeral=True)
    serial=next_serial(guild.id)
    overwrites={guild.default_role:discord.PermissionOverwrite(view_channel=False),user:discord.PermissionOverwrite(view_channel=True,send_messages=True,read_message_history=True,attach_files=True,embed_links=True),role:discord.PermissionOverwrite(view_channel=True,send_messages=True,read_message_history=True,attach_files=True,embed_links=True)}
    me=guild.me
    if me: overwrites[me]=discord.PermissionOverwrite(view_channel=True,send_messages=True,manage_channels=True,manage_messages=True,read_message_history=True,attach_files=True,embed_links=True)
    try:
        channel=await guild.create_text_channel(name=f'{clean_channel_name(ticket["ticket_name"])}-{serial:04d}',category=category,topic=f'ticket_owner:{user.id}|ticket_type:{ticket["ticket_number"]}|serial:{serial}',overwrites=overwrites,reason='Ticket system')
    except discord.Forbidden: return await interaction.response.send_message('❌ البوت لا يملك صلاحية إنشاء الرومات.',ephemeral=True)
    except Exception as e:
        print('Create ticket error:',e); return await interaction.response.send_message('❌ حدث خطأ أثناء إنشاء التذكرة.',ephemeral=True)
    with get_db() as c: c.execute('INSERT INTO open_tickets(channel_id,guild_id,owner_id,ticket_number,claimer_id,serial_number,points_awarded) VALUES(?,?,?,?,NULL,?,0)',(channel.id,guild.id,user.id,ticket['ticket_number'],serial))
    msg=(ticket['ticket_message'] or 'أهلًا بك، اشرح مشكلتك بالتفصيل وسيتم الرد عليك من فريق الدعم.').replace('{user}',user.mention).replace('{support}',role.mention)
    embed=discord.Embed(title=f'🎫 {ticket["ticket_name"]}',description=f'**رقم التذكرة:** `#{serial:04d}`\n👤 **صاحب التذكرة:** {user.mention}\n🟢 **مستلم التذكرة:** لم يتم الاستلام بعد\n\n**رسالة الإدارة**\n{msg}\n\n*تنتهي الرسالة*',color=discord.Color.blue())
    if ticket['image_url']: embed.set_thumbnail(url=ticket['image_url'])
    embed.set_footer(text='MT Ticket System')
    await channel.send(content=f'{user.mention} {role.mention}',embed=embed,view=TicketControlsView())
    await channel.send('**إجراءات التذكرة**',view=TicketActionsView())
    await interaction.response.send_message(f'✅ تم فتح التذكرة: {channel.mention} — الرقم `#{serial:04d}`',ephemeral=True)
    if log:
        le=discord.Embed(title='🎫 فتح تذكرة',color=discord.Color.green()); le.add_field(name='العضو',value=f'{user.mention} (`{user.id}`)',inline=False); le.add_field(name='النوع',value=ticket['ticket_name'],inline=True); le.add_field(name='الرقم التسلسلي',value=f'#{serial:04d}',inline=True); le.add_field(name='الروم',value=channel.mention,inline=False); await log.send(embed=le)

# ---------------- Ticket claim / close ----------------
class ClaimTicketButton(discord.ui.Button):
    def __init__(self): super().__init__(label='استلام التذكرة',style=discord.ButtonStyle.success,emoji='🟢',custom_id='mt_claim_ticket')
    async def callback(self,interaction):
        data=get_open_ticket(interaction.channel.id)
        if not data: return await interaction.response.send_message('❌ هذا الروم ليس تذكرة مفتوحة.',ephemeral=True)
        if interaction.user.id==data['owner_id']: return await interaction.response.send_message('❌ صاحب التذكرة لا يستطيع استلامها.',ephemeral=True)
        ticket=get_ticket(interaction.guild.id,data['ticket_number'])
        if not ticket or not staff_allowed(interaction.user,ticket): return await interaction.response.send_message('❌ لا تملك صلاحية استلام هذه التذكرة.',ephemeral=True)
        if data['claimer_id']:
            return await interaction.response.send_message(f'❌ التذكرة مستلمة بالفعل من <@{data["claimer_id"]}>.',ephemeral=True)
        set_ticket_claimer(interaction.channel.id,interaction.user.id)
        await interaction.response.send_message(f'🟢 تم استلام التذكرة بواسطة {interaction.user.mention}.')
        await refresh_ticket_embed(interaction.channel,claimed=True)
        await interaction.channel.send('تم تفعيل خيارات التذكير بعد استلام التذكرة.')
        log=interaction.guild.get_channel(ticket['log_channel_id'])
        if log: await log.send(f'🟢 {interaction.user.mention} استلم التذكرة {interaction.channel.mention}.')
class CloseTicketButton(discord.ui.Button):
    def __init__(self): super().__init__(label='إغلاق التذكرة',style=discord.ButtonStyle.danger,emoji='🔒',custom_id='mt_close_ticket')
    async def callback(self,interaction):
        channel=interaction.channel; data=get_open_ticket(channel.id)
        if not data: return await interaction.response.send_message('❌ هذا الروم ليس تذكرة مفتوحة.',ephemeral=True)
        ticket=get_ticket(interaction.guild.id,data['ticket_number'])
        if not ticket: return await interaction.response.send_message('❌ إعداد التذكرة غير موجود.',ephemeral=True)
        role=interaction.guild.get_role(ticket['staff_role_id'])
        allowed=(data['claimer_id']==interaction.user.id if data['claimer_id'] else False) or interaction.user.guild_permissions.administrator or bool(role and role in interaction.user.roles) or (role and interaction.user.top_role>role)
        if not allowed: return await interaction.response.send_message('❌ الإغلاق مسموح لمستلم التذكرة أو فريق الدعم أو الإدارة.',ephemeral=True)
        await interaction.response.send_message('🔒 سيتم إغلاق التذكرة خلال **5 ثوانٍ**.'); await asyncio.sleep(5)
        if data['claimer_id'] and ticket['points_enabled'] and not data['points_awarded']:
            add_points(interaction.guild.id,data['claimer_id'],ticket['points_amount'])
            with get_db() as c: c.execute('UPDATE open_tickets SET points_awarded=1 WHERE channel_id=?',(channel.id,))
        log=interaction.guild.get_channel(ticket['log_channel_id'])
        if log:
            e=discord.Embed(title='🔒 إغلاق تذكرة',color=discord.Color.red()); e.add_field(name='صاحب التذكرة',value=f'<@{data["owner_id"]}> (`{data["owner_id"]}`)',inline=False); e.add_field(name='نوع التذكرة',value=ticket['ticket_name'],inline=True); e.add_field(name='الرقم التسلسلي',value=f'#{data["serial_number"]:04d}',inline=True); e.add_field(name='المستلم',value=f'<@{data["claimer_id"]}>' if data['claimer_id'] else 'لم يتم الاستلام',inline=True); e.add_field(name='أغلقها',value=interaction.user.mention,inline=True)
            if data['claimer_id'] and ticket['points_enabled']: e.add_field(name='النقاط الممنوحة',value=f'<@{data["claimer_id"]}> حصل على {ticket["points_amount"]} نقطة.',inline=False)
            await log.send(embed=e)
        delete_open_ticket(channel.id)
        try: await channel.delete(reason='Ticket closed')
        except Exception as e: print('Delete ticket error:',e)

async def refresh_ticket_embed(channel,claimed=False):
    data=get_open_ticket(channel.id)
    if not data: return
    async for message in channel.history(limit=30,oldest_first=True):
        if message.author==bot.user and message.embeds and message.embeds[0].title and message.embeds[0].title.startswith('🎫'):
            emb=discord.Embed.from_dict(message.embeds[0].to_dict())
            for i,f in enumerate(emb.fields):
                if f.name=='🟢 المستلم': emb.set_field_at(i,name='🟢 المستلم',value=f'<@{data["claimer_id"]}>' if data['claimer_id'] else 'لم يتم الاستلام بعد',inline=False)
            if 'مستلم التذكرة' in (emb.description or ''):
                emb.description=re.sub(r'🟢 \*\*مستلم التذكرة:\*\*.*?(?=\n|$)',f'🟢 **مستلم التذكرة:** <@{data["claimer_id"]}>' if data['claimer_id'] else '🟢 **مستلم التذكرة:** لم يتم الاستلام بعد',emb.description)
            await message.edit(embed=emb,view=TicketControlsView(claimed=claimed)); return

class TicketControlsView(discord.ui.View):
    def __init__(self,claimed=False):
        super().__init__(timeout=None); claim=ClaimTicketButton()
        if claimed: claim.disabled=True; claim.label='تم استلام التذكرة'
        self.add_item(claim); self.add_item(CloseTicketButton())

# ---------------- Actions dropdown ----------------
class TicketActionSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(placeholder='اختر إجراءً للتذكرة',min_values=1,max_values=1,options=[discord.SelectOption(label='تذكير العضو',value='owner',emoji='🔔'),discord.SelectOption(label='تذكير المشرف',value='staff',emoji='👮'),discord.SelectOption(label='إضافة عضو للتذكرة',value='add',emoji='➕'),discord.SelectOption(label='تغيير اسم التذكرة',value='rename',emoji='✏️')],custom_id='mt_ticket_actions')
    async def callback(self,interaction):
        data=get_open_ticket(interaction.channel.id)
        if not data: return await interaction.response.send_message('❌ هذه ليست تذكرة مفتوحة.',ephemeral=True)
        choice=self.values[0]; ticket=get_ticket(interaction.guild.id,data['ticket_number'])
        if not ticket: return await interaction.response.send_message('❌ إعداد التذكرة غير موجود.',ephemeral=True)
        if choice in ('owner','staff') and not data['claimer_id']:
            return await interaction.response.send_message('❌ خيارات التذكير متاحة بعد استلام التذكرة فقط.',ephemeral=True)
        if choice in ('owner','staff') and not staff_allowed(interaction.user,ticket):
            return await interaction.response.send_message('❌ هذا الإجراء لفريق الدعم فقط.',ephemeral=True)
        if choice=='owner':
            await interaction.channel.send(f'🔔 <@{data["owner_id"]}> يرجى الرد على التذكرة، فريق الدعم بانتظار ردك.')
            await interaction.response.send_message('✅ تم تذكير صاحب التذكرة.',ephemeral=True)
        elif choice=='staff':
            await interaction.channel.send(f'👮 تنبيه لفريق الدعم: التذكرة {interaction.channel.mention} مستلمة من <@{data["claimer_id"]}> وتحتاج متابعة.')
            await interaction.response.send_message('✅ تم إرسال تذكير فريق الدعم.',ephemeral=True)
        elif choice=='add': await interaction.response.send_message('اختر العضو الذي تريد إضافته:',view=AddMemberView(),ephemeral=True)
        elif choice=='rename':
            if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message('❌ تغيير اسم التذكرة متاح للإداريين فقط.',ephemeral=True)
            await interaction.response.send_modal(RenameTicketModal())
class TicketActionsView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None); self.add_item(TicketActionSelect())
class AddMemberSelect(discord.ui.UserSelect):
    def __init__(self): super().__init__(placeholder='اختر عضوًا لإضافته للتذكرة',min_values=1,max_values=1,custom_id='mt_ticket_add_member')
    async def callback(self,interaction):
        member=interaction.guild.get_member(self.values[0].id)
        if not member: return await interaction.response.send_message('❌ العضو غير موجود في السيرفر.',ephemeral=True)
        try:
            await interaction.channel.set_permissions(member,view_channel=True,send_messages=True,read_message_history=True,attach_files=True,embed_links=True,reason=f'Added to ticket by {interaction.user}')
            await interaction.response.send_message(f'✅ تمت إضافة {member.mention} إلى التذكرة.')
        except discord.Forbidden: await interaction.response.send_message('❌ البوت لا يملك صلاحية تعديل صلاحيات الروم.',ephemeral=True)
class AddMemberView(discord.ui.View):
    def __init__(self): super().__init__(timeout=180); self.add_item(AddMemberSelect())
class RenameTicketModal(discord.ui.Modal,title='تغيير اسم التذكرة'):
    new_name=discord.ui.TextInput(label='الاسم الجديد',placeholder='اكتب اسم الروم الجديد',max_length=90,required=True)
    async def on_submit(self,interaction):
        try:
            await interaction.channel.edit(name=clean_channel_name(str(self.new_name.value)),reason=f'Renamed by admin {interaction.user}')
            await interaction.response.send_message('✅ تم تغيير اسم التذكرة.',ephemeral=True)
        except discord.Forbidden: await interaction.response.send_message('❌ البوت لا يملك صلاحية تغيير اسم الروم.',ephemeral=True)

# ---------------- Ticket points command ----------------
@bot.tree.command(name='ticket_points',description='عرض نقاط عضو في نظام التذاكر')
@app_commands.describe(member='العضو الذي تريد عرض نقاطه؛ اتركه فارغًا لعرض نقاطك')
async def ticket_points(interaction:discord.Interaction,member:discord.Member=None):
    member=member or interaction.user; await interaction.response.send_message(f'🏆 نقاط {member.mention}: **{get_points(interaction.guild.id,member.id)}**',ephemeral=True)

@bot.event
async def on_ready(): print(f'Logged in as {bot.user} ({bot.user.id}) | Servers: {len(bot.guilds)}')

# ---------------- Application system ----------------
def app_db():
    conn=sqlite3.connect(DB_FILE); conn.row_factory=sqlite3.Row; return conn
def init_application_database():
    with app_db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS application_settings(guild_id INTEGER PRIMARY KEY,review_channel_id INTEGER,reviewer_role_id INTEGER,instructions TEXT,accept_message TEXT,reject_message TEXT,panel_title TEXT,panel_description TEXT,panel_image TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS application_roles(guild_id INTEGER NOT NULL,role_id INTEGER NOT NULL,PRIMARY KEY(guild_id,role_id))''')
        c.execute('''CREATE TABLE IF NOT EXISTS application_questions(guild_id INTEGER NOT NULL,question_number INTEGER NOT NULL,question TEXT NOT NULL,PRIMARY KEY(guild_id,question_number))''')
        c.execute('''CREATE TABLE IF NOT EXISTS applications(application_id INTEGER PRIMARY KEY AUTOINCREMENT,guild_id INTEGER NOT NULL,user_id INTEGER NOT NULL,answers TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',review_message_id INTEGER,created_at TEXT NOT NULL)''')
init_application_database()
def get_application_settings(guild_id):
    with app_db() as c: return c.execute('SELECT * FROM application_settings WHERE guild_id=?',(guild_id,)).fetchone()
def save_application_settings(guild_id,**kwargs):
    fields=['review_channel_id','reviewer_role_id','instructions','accept_message','reject_message','panel_title','panel_description','panel_image']; old=get_application_settings(guild_id); values={k:(kwargs.get(k) if kwargs.get(k) is not None else (old[k] if old else None)) for k in fields}
    with app_db() as c: c.execute('INSERT OR REPLACE INTO application_settings(guild_id,review_channel_id,reviewer_role_id,instructions,accept_message,reject_message,panel_title,panel_description,panel_image) VALUES(?,?,?,?,?,?,?,?,?)',(guild_id,*[values[k] for k in fields]))
def get_application_roles(guild_id):
    with app_db() as c: return [r['role_id'] for r in c.execute('SELECT role_id FROM application_roles WHERE guild_id=?',(guild_id,)).fetchall()]
def get_application_questions(guild_id):
    with app_db() as c: return c.execute('SELECT * FROM application_questions WHERE guild_id=? ORDER BY question_number',(guild_id,)).fetchall()
def get_application(app_id):
    with app_db() as c: return c.execute('SELECT * FROM applications WHERE application_id=?',(app_id,)).fetchone()
def set_application_status(app_id,status,message_id=None):
    with app_db() as c:
        if message_id is None: c.execute('UPDATE applications SET status=? WHERE application_id=?',(status,app_id))
        else: c.execute('UPDATE applications SET status=?,review_message_id=? WHERE application_id=?',(status,message_id,app_id))
def create_application(guild_id,user_id,answers):
    with app_db() as c:
        cur=c.execute('INSERT INTO applications(guild_id,user_id,answers,status,created_at) VALUES(?,?,?,\'pending\',?)',(guild_id,user_id,repr(answers),datetime.now(timezone.utc).isoformat())); return cur.lastrowid

class ApplicationReviewChannelSelect(discord.ui.ChannelSelect):
    def __init__(self): super().__init__(placeholder='اختر روم استقبال التقديمات',channel_types=[discord.ChannelType.text],min_values=1,max_values=1)
    async def callback(self,i): save_application_settings(i.guild.id,review_channel_id=self.values[0].id); await i.response.send_message(f'✅ تم تحديد روم التقديمات: {self.values[0].mention}',ephemeral=True)
class ApplicationReviewChannelView(discord.ui.View):
    def __init__(self): super().__init__(timeout=300); self.add_item(ApplicationReviewChannelSelect())
@bot.tree.command(name='تقديم_روم',description='تحديد روم استقبال التقديمات')
@app_commands.checks.has_permissions(administrator=True)
async def application_channel(i:discord.Interaction): await i.response.send_message('اختر روم استقبال التقديمات:',view=ApplicationReviewChannelView(),ephemeral=True)
class ApplicationReviewerRoleSelect(discord.ui.RoleSelect):
    def __init__(self): super().__init__(placeholder='اختر رتبة مراجعة التقديمات',min_values=1,max_values=1)
    async def callback(self,i): save_application_settings(i.guild.id,reviewer_role_id=self.values[0].id); await i.response.send_message(f'✅ تم تحديد رتبة المراجعة: {self.values[0].mention}',ephemeral=True)
class ApplicationReviewerRoleView(discord.ui.View):
    def __init__(self): super().__init__(timeout=300); self.add_item(ApplicationReviewerRoleSelect())
@bot.tree.command(name='تقديم_مراجعين',description='تحديد رتبة قبول ورفض التقديمات')
@app_commands.checks.has_permissions(administrator=True)
async def application_reviewer_role(i:discord.Interaction): await i.response.send_message('اختر رتبة مراجعة التقديمات:',view=ApplicationReviewerRoleView(),ephemeral=True)
class ApplicationAcceptRolesSelect(discord.ui.RoleSelect):
    def __init__(self): super().__init__(placeholder='اختر الرتب التي تعطى عند القبول',min_values=1,max_values=10)
    async def callback(self,i):
        with app_db() as c:
            c.execute('DELETE FROM application_roles WHERE guild_id=?',(i.guild.id,))
            for r in self.values: c.execute('INSERT OR IGNORE INTO application_roles(guild_id,role_id) VALUES(?,?)',(i.guild.id,r.id))
        await i.response.send_message('✅ تم حفظ رتب القبول:\n'+'\n'.join(r.mention for r in self.values),ephemeral=True)
class ApplicationAcceptRolesView(discord.ui.View):
    def __init__(self): super().__init__(timeout=300); self.add_item(ApplicationAcceptRolesSelect())
@bot.tree.command(name='تقديم_رتب',description='تحديد الرتب التي يحصل عليها المقبول')
@app_commands.checks.has_permissions(administrator=True)
async def application_roles(i:discord.Interaction): await i.response.send_message('اختر رتب القبول (حتى 10 رتب):',view=ApplicationAcceptRolesView(),ephemeral=True)
class ApplicationMessagesModal(discord.ui.Modal,title='رسائل نظام التقديم'):
    instructions=discord.ui.TextInput(label='رسالة التعليمات',style=discord.TextStyle.paragraph,max_length=4000)
    accept=discord.ui.TextInput(label='رسالة القبول',style=discord.TextStyle.paragraph,max_length=4000)
    reject=discord.ui.TextInput(label='رسالة الرفض',style=discord.TextStyle.paragraph,max_length=4000)
    async def on_submit(self,i): save_application_settings(i.guild.id,instructions=str(self.instructions),accept_message=str(self.accept),reject_message=str(self.reject)); await i.response.send_message('✅ تم حفظ رسائل التعليمات والقبول والرفض.',ephemeral=True)
@bot.tree.command(name='تقديم_رسائل',description='تحديد رسائل التعليمات والقبول والرفض')
@app_commands.checks.has_permissions(administrator=True)
async def application_messages(i:discord.Interaction): await i.response.send_modal(ApplicationMessagesModal())
class ApplicationQuestionModal(discord.ui.Modal):
    def __init__(self,n): super().__init__(title=f'إضافة سؤال رقم {n}'); self.n=n; self.question=discord.ui.TextInput(label='السؤال',style=discord.TextStyle.paragraph,max_length=1000); self.add_item(self.question)
    async def on_submit(self,i):
        with app_db() as c: c.execute('INSERT OR REPLACE INTO application_questions(guild_id,question_number,question) VALUES(?,?,?)',(i.guild.id,self.n,str(self.question)))
        await i.response.send_message(f'✅ تم حفظ السؤال رقم {self.n}.',ephemeral=True)
class ApplicationQuestionNumberSelect(discord.ui.Select):
    def __init__(self): super().__init__(placeholder='اختر رقم السؤال',options=[discord.SelectOption(label=f'السؤال {n}',value=str(n),emoji='📝') for n in range(1,11)])
    async def callback(self,i): await i.response.send_modal(ApplicationQuestionModal(int(self.values[0])))
class ApplicationQuestionView(discord.ui.View):
    def __init__(self): super().__init__(timeout=300); self.add_item(ApplicationQuestionNumberSelect())
@bot.tree.command(name='تقديم_سؤال',description='إضافة أو تعديل سؤال تقديم')
@app_commands.checks.has_permissions(administrator=True)
async def application_question(i:discord.Interaction): await i.response.send_message('اختر رقم السؤال:',view=ApplicationQuestionView(),ephemeral=True)
class ApplicationPanelModal(discord.ui.Modal,title='إعداد بانل التقديم'):
    title_input=discord.ui.TextInput(label='عنوان البانل',default='التقديم على الإدارة',max_length=256)
    description=discord.ui.TextInput(label='وصف البانل',style=discord.TextStyle.paragraph,default='اضغط على الزر بالأسفل للتقديم.',max_length=4000)
    image=discord.ui.TextInput(label='رابط الصورة - اختياري',required=False,max_length=1000)
    async def on_submit(self,i):
        image=str(self.image).strip()
        if image and not valid_image_url(image): return await i.response.send_message('❌ رابط الصورة غير صحيح.',ephemeral=True)
        save_application_settings(i.guild.id,panel_title=str(self.title_input),panel_description=str(self.description),panel_image=image)
        e=discord.Embed(title=str(self.title_input),description=str(self.description),color=discord.Color.blue())
        if image: e.set_thumbnail(url=image)
        if i.guild.icon: e.set_author(name=i.guild.name,icon_url=i.guild.icon.url)
        else: e.set_author(name=i.guild.name)
        await i.channel.send(embed=e,view=ApplicationPanelView()); await i.response.send_message('✅ تم إرسال بانل التقديم.',ephemeral=True)
@bot.tree.command(name='تقديم_بانل',description='إرسال بانل التقديم')
@app_commands.checks.has_permissions(administrator=True)
async def application_panel(i:discord.Interaction): await i.response.send_modal(ApplicationPanelModal())
class StartApplicationButton(discord.ui.Button):
    def __init__(self): super().__init__(label='تقديم',emoji='📝',style=discord.ButtonStyle.primary,custom_id='mt_application_start')
    async def callback(self,i):
        settings=get_application_settings(i.guild.id); qs=get_application_questions(i.guild.id)
        if not settings or not settings['review_channel_id']: return await i.response.send_message('❌ لم يتم تحديد روم استقبال التقديمات.',ephemeral=True)
        if not qs: return await i.response.send_message('❌ لم تتم إضافة أسئلة للتقديم.',ephemeral=True)
        if settings['instructions']: return await i.response.send_message(embed=discord.Embed(title='📋 تعليمات التقديم',description=settings['instructions'],color=discord.Color.blue()),view=ApplicationConfirmView(),ephemeral=True)
        await i.response.send_modal(ApplicationFormModal(qs[:5],0,{}))
class ApplicationPanelView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None); self.add_item(StartApplicationButton())
class ApplicationConfirmView(discord.ui.View):
    def __init__(self): super().__init__(timeout=300); self.add_item(ApplicationConfirmButton()); self.add_item(ApplicationCancelButton())
class ApplicationConfirmButton(discord.ui.Button):
    def __init__(self): super().__init__(label='بدء التقديم',emoji='📝',style=discord.ButtonStyle.success)
    async def callback(self,i):
        qs=get_application_questions(i.guild.id)
        if not qs: return await i.response.send_message('❌ لا توجد أسئلة للتقديم.',ephemeral=True)
        await i.response.send_modal(ApplicationFormModal(qs[:5],0,{}))
class ApplicationCancelButton(discord.ui.Button):
    def __init__(self): super().__init__(label='إلغاء',emoji='❌',style=discord.ButtonStyle.danger)
    async def callback(self,i): await i.response.edit_message(content='❌ تم إلغاء التقديم.',embed=None,view=None)
class ApplicationFormModal(discord.ui.Modal):
    def __init__(self,questions,page,previous):
        super().__init__(title=f'تقديم - صفحة {page+1}'); self.questions=list(questions); self.page=page; self.previous=dict(previous); self.inputs=[]
        for q in self.questions:
            field=discord.ui.TextInput(label=f"{q['question_number']}. {q['question']}"[:45],style=discord.TextStyle.paragraph,required=True,max_length=1000); self.inputs.append(field); self.add_item(field)
    async def on_submit(self,i):
        answers=dict(self.previous)
        for q,field in zip(self.questions,self.inputs): answers[str(q['question_number'])]=str(field.value)
        allq=get_application_questions(i.guild.id); nextq=allq[(self.page+1)*5:(self.page+2)*5]
        if nextq: return await i.response.send_modal(ApplicationFormModal(nextq,self.page+1,answers))
        await finish_application(i,answers)
async def finish_application(i,answers):
    settings=get_application_settings(i.guild.id); channel=i.guild.get_channel(settings['review_channel_id']) if settings and settings['review_channel_id'] else None
    if not channel: return await i.response.send_message('❌ روم استقبال التقديمات غير موجود.',ephemeral=True)
    app_id=create_application(i.guild.id,i.user.id,answers); e=discord.Embed(title='📥 تقديم جديد',color=discord.Color.blue()); e.set_author(name=str(i.user),icon_url=i.user.display_avatar.url); e.add_field(name='المتقدم',value=f'{i.user.mention}\n`{i.user.id}`',inline=False)
    for q in get_application_questions(i.guild.id): e.add_field(name=f"📝 {q['question_number']}. {q['question']}"[:256],value=answers.get(str(q['question_number']),'—')[:1024],inline=False)
    e.set_footer(text=f'Application ID: {app_id}'); m=await channel.send(content=f'📥 تقديم جديد من {i.user.mention}',embed=e,view=ApplicationReviewView(app_id)); set_application_status(app_id,'pending',m.id); await i.response.send_message('✅ تم إرسال تقديمك بنجاح. انتظر مراجعة الإدارة.',ephemeral=True)
def can_review_application(i):
    s=get_application_settings(i.guild.id)
    if not s: return False
    if i.user.guild_permissions.administrator: return True
    role=i.guild.get_role(s['reviewer_role_id']) if s['reviewer_role_id'] else None
    return bool(role and role in i.user.roles)
class AcceptApplicationButton(discord.ui.Button):
    def __init__(self,app_id): self.app_id=app_id; super().__init__(label='قبول',emoji='🟢',style=discord.ButtonStyle.success,custom_id=f'mt_application_accept_{app_id}')
    async def callback(self,i):
        if not can_review_application(i): return await i.response.send_message('❌ لا تملك صلاحية قبول التقديمات.',ephemeral=True)
        a=get_application(self.app_id)
        if not a or a['status']!='pending': return await i.response.send_message('❌ تمت معالجة هذا التقديم مسبقًا أو أنه غير موجود.',ephemeral=True)
        member=i.guild.get_member(a['user_id'])
        if not member: return await i.response.send_message('❌ المتقدم غير موجود في السيرفر.',ephemeral=True)
        added=[]
        for rid in get_application_roles(i.guild.id):
            role=i.guild.get_role(rid)
            if role:
                try: await member.add_roles(role,reason='Application accepted'); added.append(role.mention)
                except discord.Forbidden: pass
        s=get_application_settings(i.guild.id); msg=(s['accept_message'] if s and s['accept_message'] else 'مبروك! تم قبول تقديمك.').replace('{user}',member.mention).replace('{server}',i.guild.name)
        try: await member.send(msg); dm='📩 تم إرسال رسالة القبول في الخاص.'
        except discord.Forbidden: dm='⚠️ تعذر إرسال رسالة القبول في الخاص.'
        set_application_status(self.app_id,'accepted'); e=discord.Embed(title='🟢 تم قبول التقديم',description=f'المتقدم: {member.mention}\nبواسطة: {i.user.mention}\n{dm}',color=discord.Color.green()); await i.response.edit_message(content=None,embed=e,view=None)
class RejectApplicationButton(discord.ui.Button):
    def __init__(self,app_id): self.app_id=app_id; super().__init__(label='رفض',emoji='🔴',style=discord.ButtonStyle.danger,custom_id=f'mt_application_reject_{app_id}')
    async def callback(self,i):
        if not can_review_application(i): return await i.response.send_message('❌ لا تملك صلاحية رفض التقديمات.',ephemeral=True)
        a=get_application(self.app_id)
        if not a or a['status']!='pending': return await i.response.send_message('❌ تمت معالجة هذا التقديم مسبقًا أو أنه غير موجود.',ephemeral=True)
        member=i.guild.get_member(a['user_id'])
        if not member: return await i.response.send_message('❌ المتقدم غير موجود في السيرفر.',ephemeral=True)
        s=get_application_settings(i.guild.id); msg=(s['reject_message'] if s and s['reject_message'] else 'نعتذر، لم يتم قبول تقديمك.').replace('{user}',member.mention).replace('{server}',i.guild.name)
        try: await member.send(msg); dm='📩 تم إرسال رسالة الرفض في الخاص.'
        except discord.Forbidden: dm='⚠️ تعذر إرسال رسالة الرفض في الخاص.'
        set_application_status(self.app_id,'rejected'); e=discord.Embed(title='🔴 تم رفض التقديم',description=f'المتقدم: {member.mention}\nبواسطة: {i.user.mention}\n{dm}',color=discord.Color.red()); await i.response.edit_message(content=None,embed=e,view=None)
class ApplicationReviewView(discord.ui.View):
    def __init__(self,app_id): super().__init__(timeout=None); self.add_item(AcceptApplicationButton(app_id)); self.add_item(RejectApplicationButton(app_id))
@bot.tree.command(name='تقديم_الحالة',description='عرض إعدادات نظام التقديم')
@app_commands.checks.has_permissions(administrator=True)
async def application_status(i):
    s=get_application_settings(i.guild.id)
    if not s: return await i.response.send_message('❌ لم يتم إعداد نظام التقديم.',ephemeral=True)
    ch=i.guild.get_channel(s['review_channel_id']) if s['review_channel_id'] else None; role=i.guild.get_role(s['reviewer_role_id']) if s['reviewer_role_id'] else None; qs=get_application_questions(i.guild.id); roles=get_application_roles(i.guild.id)
    e=discord.Embed(title='⚙️ إعدادات نظام التقديم',color=discord.Color.blue()); e.add_field(name='روم التقديمات',value=ch.mention if ch else 'غير محدد',inline=False); e.add_field(name='رتبة المراجعة',value=role.mention if role else 'غير محددة',inline=False); e.add_field(name='رتب القبول',value='\n'.join(f'<@&{r}>' for r in roles) or 'لا توجد رتب',inline=False); e.add_field(name='عدد الأسئلة',value=str(len(qs)),inline=False); await i.response.send_message(embed=e,ephemeral=True)
@bot.tree.command(name='تقديم_مسح_الاسئلة',description='مسح جميع أسئلة التقديم')
@app_commands.checks.has_permissions(administrator=True)
async def application_clear_questions(i):
    with app_db() as c: c.execute('DELETE FROM application_questions WHERE guild_id=?',(i.guild.id,))
    await i.response.send_message('🗑️ تم مسح جميع أسئلة التقديم.',ephemeral=True)

# ---------------- Error handling ----------------
@bot.tree.error
async def global_app_command_error(interaction,error):
    if isinstance(error,app_commands.errors.MissingPermissions):
        msg='❌ هذا الأمر للإدارة فقط.'
        try:
            if interaction.response.is_done(): await interaction.followup.send(msg,ephemeral=True)
            else: await interaction.response.send_message(msg,ephemeral=True)
        except discord.HTTPException: pass
    else: print('Application command error:',repr(error))

if __name__=='__main__':
    init_database(); init_application_database(); bot.run(TOKEN)
