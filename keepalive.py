import os
import sqlite3
import threading
import requests

from flask import (
    Flask,
    redirect,
    request,
    session,
    render_template,
    url_for
)

# =========================================================
# إعدادات
# =========================================================

app = Flask(__name__)

app.secret_key = os.getenv(
    "FLASK_SECRET_KEY",
    "change-this-secret-key"
)

TOKEN = os.getenv("TOKEN")
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_REDIRECT_URI = os.getenv(
    "DISCORD_REDIRECT_URI",
    "https://liver-1.onrender.com/callback"
)

DB_FILE = "mt_bot.db"

DISCORD_API = "https://discord.com/api/v10"

# =========================================================
# قاعدة البيانات
# =========================================================

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS server_settings (
            guild_id TEXT PRIMARY KEY,
            ai_enabled INTEGER DEFAULT 0,
            ai_channel_id TEXT,
            security_log_id TEXT,
            delete_log_id TEXT,
            edit_log_id TEXT,
            member_log_id TEXT,
            mod_log_id TEXT,
            role_log_id TEXT,
            channel_log_id TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS excluded_roles (
            guild_id TEXT,
            role_id TEXT,
            PRIMARY KEY (guild_id, role_id)
        )
    """)

    conn.commit()
    conn.close()


init_db()

# =========================================================
# Discord API
# =========================================================

def discord_headers():
    return {
        "Authorization": f"Bot {TOKEN}",
        "Content-Type": "application/json"
    }


def discord_get(url):
    try:
        response = requests.get(
            url,
            headers=discord_headers(),
            timeout=15
        )

        if response.status_code == 200:
            return response.json()

        return None

    except Exception as e:
        print("Discord API Error:", e)
        return None


def get_guild_channels(guild_id):
    data = discord_get(
        f"{DISCORD_API}/guilds/{guild_id}/channels"
    )

    if not data:
        return []

    return data


def get_guild_roles(guild_id):
    data = discord_get(
        f"{DISCORD_API}/guilds/{guild_id}/roles"
    )

    if not data:
        return []

    return data


# =========================================================
# إعدادات السيرفر
# =========================================================

def get_settings(guild_id):
    conn = get_db()

    row = conn.execute(
        """
        SELECT *
        FROM server_settings
        WHERE guild_id = ?
        """,
        (str(guild_id),)
    ).fetchone()

    conn.close()

    return row


def ensure_settings(guild_id):
    conn = get_db()

    conn.execute(
        """
        INSERT OR IGNORE INTO server_settings (guild_id)
        VALUES (?)
        """,
        (str(guild_id),)
    )

    conn.commit()
    conn.close()


def update_setting(guild_id, column, value):
    allowed = {
        "ai_enabled",
        "ai_channel_id",
        "security_log_id",
        "delete_log_id",
        "edit_log_id",
        "member_log_id",
        "mod_log_id",
        "role_log_id",
        "channel_log_id"
    }

    if column not in allowed:
        return

    ensure_settings(guild_id)

    conn = get_db()

    conn.execute(
        f"""
        UPDATE server_settings
        SET {column} = ?
        WHERE guild_id = ?
        """,
        (value, str(guild_id))
    )

    conn.commit()
    conn.close()


# =========================================================
# الرتب المستثناة
# =========================================================

def get_excluded_roles(guild_id):
    conn = get_db()

    rows = conn.execute(
        """
        SELECT role_id
        FROM excluded_roles
        WHERE guild_id = ?
        """,
        (str(guild_id),)
    ).fetchall()

    conn.close()

    return [row["role_id"] for row in rows]


def add_excluded_role(guild_id, role_id):
    conn = get_db()

    conn.execute(
        """
        INSERT OR IGNORE INTO excluded_roles
        (guild_id, role_id)
        VALUES (?, ?)
        """,
        (str(guild_id), str(role_id))
    )

    conn.commit()
    conn.close()


def remove_excluded_role(guild_id, role_id):
    conn = get_db()

    conn.execute(
        """
        DELETE FROM excluded_roles
        WHERE guild_id = ?
        AND role_id = ?
        """,
        (str(guild_id), str(role_id))
    )

    conn.commit()
    conn.close()


# =========================================================
# الصفحة الرئيسية
# =========================================================

@app.route("/")
def index():
    user = session.get("user")

    if not user:
        return render_template(
            "index.html",
            user=None
        )

    guilds = session.get("guilds", [])

    return render_template(
        "index.html",
        user=user,
        guilds=guilds
    )


# =========================================================
# تسجيل الدخول Discord
# =========================================================

@app.route("/login")
def login():
    discord_auth_url = (
        "https://discord.com/oauth2/authorize"
        f"?client_id={DISCORD_CLIENT_ID}"
        f"&redirect_uri={requests.utils.quote(DISCORD_REDIRECT_URI, safe='')}"
        "&response_type=code"
        "&scope=identify%20guilds"
    )

    return redirect(discord_auth_url)


# =========================================================
# Callback
# =========================================================

@app.route("/callback")
def callback():
    code = request.args.get("code")

    if not code:
        return redirect(url_for("index"))

    try:
        token_response = requests.post(
            f"{DISCORD_API}/oauth2/token",
            data={
                "client_id": DISCORD_CLIENT_ID,
                "client_secret": DISCORD_CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": DISCORD_REDIRECT_URI
            },
            headers={
                "Content-Type": "application/x-www-form-urlencoded"
            },
            timeout=15
        )

        if token_response.status_code != 200:
            print(
                "OAuth Token Error:",
                token_response.text
            )

            return redirect(url_for("index"))

        token_data = token_response.json()

        access_token = token_data.get(
            "access_token"
        )

        if not access_token:
            return redirect(url_for("index"))

        headers = {
            "Authorization": f"Bearer {access_token}"
        }

        # المستخدم
        user_response = requests.get(
            f"{DISCORD_API}/users/@me",
            headers=headers,
            timeout=15
        )

        if user_response.status_code != 200:
            return redirect(url_for("index"))

        user_data = user_response.json()

        # السيرفرات
        guild_response = requests.get(
            f"{DISCORD_API}/users/@me/guilds",
            headers=headers,
            timeout=15
        )

        oauth_guilds = []

        if guild_response.status_code == 200:
            oauth_guilds = guild_response.json()

        # =================================================
        # نعرض فقط السيرفرات التي البوت موجود فيها
        # =================================================

        bot_guilds = []

        for guild in oauth_guilds:
            guild_id = guild.get("id")

            if not guild_id:
                continue

            bot_check = discord_get(
                f"{DISCORD_API}/guilds/{guild_id}"
            )

            if bot_check:
                bot_guilds.append({
                    "id": guild_id,
                    "name": guild.get(
                        "name",
                        "سيرفر بدون اسم"
                    ),
                    "icon": guild.get("icon")
                })

        # نخزن بيانات صغيرة حتى ما تكبر Session
        session["user"] = {
            "id": user_data.get("id"),
            "username": user_data.get(
                "username",
                "User"
            ),
            "global_name": user_data.get(
                "global_name"
            ),
            "avatar": user_data.get("avatar")
        }

        session["guilds"] = bot_guilds

        return redirect(url_for("index"))

    except Exception as e:
        print("Callback Error:", e)

        return redirect(url_for("index"))


# =========================================================
# تسجيل الخروج
# =========================================================

@app.route("/logout")
def logout():
    session.clear()

    return redirect(url_for("index"))


# =========================================================
# صفحة السيرفر
# =========================================================

@app.route("/server/<guild_id>")
def server(guild_id):
    user = session.get("user")

    if not user:
        return redirect(url_for("login"))

    guilds = session.get("guilds", [])

    selected_guild = None

    for guild in guilds:
        if str(guild["id"]) == str(guild_id):
            selected_guild = guild
            break

    if not selected_guild:
        return "غير مصرح لك بالدخول لهذا السيرفر", 403

    # تأكد أن البوت موجود
    guild_data = discord_get(
        f"{DISCORD_API}/guilds/{guild_id}"
    )

    if not guild_data:
        return "البوت غير موجود في هذا السيرفر", 404

    # القنوات
    channels = get_guild_channels(guild_id)

    # الرتب
    roles = get_guild_roles(guild_id)

    # الإعدادات
    ensure_settings(guild_id)
    settings = get_settings(guild_id)

    # الرتب المستثناة
    excluded_roles = get_excluded_roles(guild_id)

    return render_template(
        "server.html",
        user=user,
        guild=selected_guild,
        guild_data=guild_data,
        channels=channels,
        roles=roles,
        settings=settings,
        excluded_roles=excluded_roles
    )


# =========================================================
# إجراءات لوحة التحكم
# =========================================================

@app.route(
    "/server/<guild_id>/action",
    methods=["POST"]
)
def server_action(guild_id):
    user = session.get("user")

    if not user:
        return redirect(url_for("login"))

    guilds = session.get("guilds", [])

    allowed = False

    for guild in guilds:
        if str(guild["id"]) == str(guild_id):
            allowed = True
            break

    if not allowed:
        return "غير مصرح لك", 403

    action = request.form.get("action")

    # =====================================================
    # تشغيل الذكاء الاصطناعي
    # =====================================================

    if action == "ai_enable":
        update_setting(
            guild_id,
            "ai_enabled",
            1
        )

    # =====================================================
    # إيقاف الذكاء الاصطناعي
    # =====================================================

    elif action == "ai_disable":
        update_setting(
            guild_id,
            "ai_enabled",
            0
        )

    # =====================================================
    # روم الذكاء الاصطناعي
    # =====================================================

    elif action == "ai_channel":
        channel_id = request.form.get(
            "channel_id"
        )

        update_setting(
            guild_id,
            "ai_channel_id",
            channel_id
        )

    # =====================================================
    # رومات السجلات
    # =====================================================

    elif action in {
        "security_log",
        "delete_log",
        "edit_log",
        "member_log",
        "mod_log",
        "role_log",
        "channel_log"
    }:

        channel_id = request.form.get(
            "channel_id"
        )

        update_setting(
            guild_id,
            action + "_id",
            channel_id
        )

    # =====================================================
    # إضافة رتبة مستثناة
    # =====================================================

    elif action == "add_excluded_role":
        role_id = request.form.get(
            "role_id"
        )

        if role_id:
            add_excluded_role(
                guild_id,
                role_id
            )

    # =====================================================
    # إزالة رتبة مستثناة
    # =====================================================

    elif action == "remove_excluded_role":
        role_id = request.form.get(
            "role_id"
        )

        if role_id:
            remove_excluded_role(
                guild_id,
                role_id
            )

    return redirect(
        url_for(
            "server",
            guild_id=guild_id
        )
    )


# =========================================================
# تشغيل Flask
# =========================================================

def run_flask():
    app.run(
        host="0.0.0.0",
        port=int(
            os.getenv(
                "PORT",
                10000
            )
        ),
        debug=False,
        use_reloader=False
    )


def keep_alive(bot=None):
    thread = threading.Thread(
        target=run_flask,
        daemon=True
    )

    thread.start()
