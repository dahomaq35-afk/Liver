import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# قائمة الرتب المستخرجة من الصور (بدون تكرار)
ROLES_DATA = [
    # Top Leadership & Special Roles
    "#",
    "MT | Owner",
    "MT | HEADowner",
    "MT | Lead Developer",
    "『MT』 Dahom",
    "『MT』 Willy",
    "MT | COowner",
    "MT | Ceo",
    "Bot",
    "MT | FOUNDERS",
    "MT | Executive",
    "MT | Controller",
    "MT | Console",
    "MT | Head Admin",
    "|———— Bots ————|",
    "MT | Strategy Team",
    "Honorary Founders",
    "MT | High Management",
    "MT | Strategy Director",
    "MT | MANAGEMENT 👑",
    
    # Overseer & Administration
    "👁️ • MT • SERVER OVERSEER",
    "MT | CERTIFIED 🥇",
    "MT | TRAINEE 🎯",
    "|———— الادارة ————|",
    "Staff Manager",
    "🎥 • Content • Creation • Manager",
    "MT | Admin",
    "Management Head",
    "MT | Operator",
    "MT | Dev Director",
    "MT | Dev Vice Director",
    
    # Responsibilities & Development
    "Responsibilities-Committe...",
    "MT | Banned Manager",
    "MT | Assistant Banned Manager",
    "MT | Store Manager",
    "MT | Discord Developer ⚒️",
    "MT | Assistant Car Developer",
    "MT | Environment Control",
    "MT | Content Creators Management",
    "MT | Technical Support Manager",
    "MT | Activation Manager",
    "MT | Activation",
    
    # Staff & Support
    "MT | Development Supervisor",
    "MT | Organizer",
    "Staff Assistant",
    "MT | Cordinator",
    "MT | Staff",
    "MT | Expert",
    "MT | Supervisor",
    "MT | Developer",
    "MT | Content Creator Manager",
    "MT | Monthly Employee",
    "MT | Support of Week",
    "MT | Trusted",
    "MT | Content manager",
    "MT | Trial",
    "MT | Senior Mod",
    "MT | Mod",
    "MT | Trial Mod",
    "MT | Management",
    "MT | Support",
    "MT | Active",
    "MT | Ticketer Admin",
    "MT | Whitelist"
]

# قائمة الرومات والتصنيفات المستخرجة من الصور
CATEGORIES_AND_CHANNELS = [
    {
        "category": "welcome",
        "channels": [
            {"name": "MYSTERY-AIRPORT✈️", "type": "text"}
        ]
    },
    {
        "category": "Rules",
        "channels": [
            {"name": "Rules-القوانين", "type": "text"},
            {"name": "Rules-قوانين-السرقة", "type": "text"},
            {"name": "Rules-قوانين-الاعدام", "type": "text"},
            {"name": "servers-سيرفراتنا", "type": "text"}
        ]
    },
    {
        "category": "DONATE",
        "channels": [
            {"name": "🔮-NitroBooster", "type": "text"}
        ]
    },
    {
        "category": "Application",
        "channels": [
            {"name": "شرح-التفعيل", "type": "text"},
            {"name": "اخبار-التفعيل", "type": "text"},
            {"name": "اسئله-التفعيل", "type": "text"},
            {"name": "اوقات-التفعيل", "type": "text"},
            {"name": "تفعيل-الالكتروني", "type": "text"}
        ]
    },
    {
        "category": "Interviews & Submissions",
        "channels": [
            {"name": "المقبولين", "type": "text"},
            {"name": "المرفوضين", "type": "text"},
            {"name": "جاري المقابلة", "type": "voice"},
            {"name": "جاري المقابلة", "type": "voice"},
            {"name": "جاري المقابلة", "type": "voice"},
            {"name": "جاري المقابلة", "type": "voice"},
            {"name": "جاري المقابلة", "type": "voice"},
            {"name": "جاري المقابلة", "type": "voice"},
            {"name": "⏰-انتظار المقابلة", "type": "voice"}
        ]
    },
    {
        "category": "Management",
        "channels": [
            {"name": "🔶قوانين_الادارة", "type": "text"},
            {"name": "🔶تعميمات_الادارة", "type": "text"},
            {"name": "🔶ملخص_الإجتماع", "type": "text"},
            {"name": "🔶استدعاء_اداري", "type": "text"},
            {"name": "🔶دليل_الباند", "type": "text"}
        ]
    },
    {
        "category": "Logs & Moderation",
        "channels": [
            {"name": "security-logs", "type": "text"},
            {"name": "🔒-6", "type": "text"},
            {"name": "moderator-only", "type": "text"},
            {"name": "rules", "type": "forum"},
            {"name": "📖-اجر", "type": "text"},
            {"name": "📖-قران-كريم", "type": "text"},
            {"name": "📋-case-submission", "type": "text"},
            {"name": "📋-recruit-justice", "type": "text"},
            {"name": "🚫المغادرات", "type": "text"},
            {"name": "تجارب", "type": "text"},
            {"name": "التآق", "type": "text"},
            {"name": "For all", "type": "voice"},
            {"name": "تجربة", "type": "voice"}
        ]
    }
]

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_server(ctx):
    guild = ctx.guild
    await ctx.send("⏳ جاري إنشاء الرتب والرومات...")

    # 1. إنشاء الرتب
    for role_name in ROLES_DATA:
        existing_role = discord.utils.get(guild.roles, name=role_name)
        if not existing_role:
            await guild.create_role(name=role_name)
            
    # 2. إنشاء التصنيفات والرومات
    for cat_data in CATEGORIES_AND_CHANNELS:
        category = await guild.create_category(cat_data["category"])
        for ch_data in cat_data["channels"]:
            if ch_data["type"] == "text":
                await guild.create_text_channel(ch_data["name"], category=category)
            elif ch_data["type"] == "voice":
                await guild.create_voice_channel(ch_data["name"], category=category)
            elif ch_data["type"] == "forum":
                await guild.create_forum_channel(ch_data["name"], category=category)

    await ctx.send("✅ تم إعداد السيرفر بنجاح بجميع الرتب والرومات المطلوبة!")

bot.run("MTUzODgzNzI4Mjk3NzQ4ODkwNg.GA6_Mj.kAZ_53qJjs6PkFFFLt33lhZhf9WIVmN7FmyZtc")
