import os
import secrets
import requests
import sqlite3

from flask import Flask, render_template, redirect, request, session
from threading import Thread
from werkzeug.middleware.proxy_fix import ProxyFix


# =========================================================
# Flask
# =========================================================

app = Flask(__name__)

app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=1,
    x_proto=1,
    x_host=1
)

app.secret_key = os.getenv(
    "FLASK_SECRET_KEY",
    "temporary-secret-key"
)

app.config.update(
    SESSION_COOKIE_NAME="mtbot_session",
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_PATH="/"
)


# =========================================================
# Discord OAuth
# =========================================================

CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")

REDIRECT_URI = os.getenv(
    "DISCORD_REDIRECT_URI",
    "https://liver-1.onrender.com/callback"
)


# =========================================================
# Database
# =========================================================

DB_FILE = "mt_bot.db"


def db_connect():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def safe_count(table, guild_id):
    try:
        conn = db_connect()

        row = conn.execute(
            f"SELECT COUNT(*) AS total FROM {table} WHERE guild_id = ?",
            (guild_id,)
        ).fetchone()

        conn.close()

        return row["total"] if row else 0

    except Exception:
        return 0


def get_settings(guild_id):
    default_settings = {
        "ai_enabled": 0,
        "ai_channel_id": None,
        "security_log_channel_id": None,
        "delete_log_channel_id": None,
        "edit_log_channel_id": None,
        "member_log_channel_id": None,
        "mod_log_channel_id": None,
        "role_log_channel_id": None,
        "channel_log_channel_id": None
    }

    try:
        conn = db_connect()

        row = conn.execute(
            """
            SELECT *
            FROM settings
            WHERE guild_id = ?
            """,
            (guild_id,)
        ).fetchone()

        conn.close()

        if not row:
            return default_settings

        result = dict(default_settings)

        for key in result:
            try:
                result[key] = row[key]
            except Exception:
                pass

        return result

    except Exception:
        return default_settings


def get_excluded_roles(guild_id):
    try:
        conn = db_connect()

        rows = conn.execute(
            """
            SELECT role_id
            FROM excluded_roles
            WHERE guild_id = ?
            ORDER BY role_id
            """,
            (guild_id,)
        ).fetchall()

        conn.close()

        return [
            str(row["role_id"])
            for row in rows
        ]

    except Exception:
        return []


def get_security_logs(guild_id, limit=50):
    try:
        conn = db_connect()

        rows = conn.execute(
            """
            SELECT
                id,
                event_type,
                actor_id,
                target_id,
                details,
                created_at
            FROM security_logs
            WHERE guild_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (guild_id, limit)
        ).fetchall()

        conn.close()

        return [dict(row) for row in rows]

    except Exception:
        return []


def get_tickets(guild_id, limit=50):
    try:
        conn = db_connect()

        rows = conn.execute(
            """
            SELECT
                id,
                user_id,
                channel_id,
                sector,
                claimed_by,
                created_at,
                closed
            FROM tickets
            WHERE guild_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (guild_id, limit)
        ).fetchall()

        conn.close()

        return [dict(row) for row in rows]

    except Exception:
        return []


# =========================================================
# الصفحة الرئيسية
# =========================================================

@app.route("/")
def home():

    app.logger.info(
        "HOME SESSION USER: %s",
        bool(session.get("user"))
    )

    app.logger.info(
        "HOME SESSION GUILDS: %s",
        len(session.get("guilds", []))
    )

    return render_template(
        "index.html",
        user=session.get("user"),
        guilds=session.get("guilds", [])
    )


# =========================================================
# تسجيل الدخول
# =========================================================

@app.route("/login")
def login():

    state = secrets.token_urlsafe(32)

    session.clear()
    session["oauth_state"] = state

    app.logger.info(
        "LOGIN SESSION STATE SAVED"
    )

    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": "identify guilds",
        "state": state
    }

    url = (
        "https://discord.com/oauth2/authorize?"
        + requests.compat.urlencode(params)
    )

    return redirect(url)


# =========================================================
# Discord Callback
# =========================================================

@app.route("/callback")
def callback():

    try:

        code = request.args.get("code")
        state = request.args.get("state")

        app.logger.info(
            "CALLBACK SESSION HAS STATE: %s",
            bool(session.get("oauth_state"))
        )

        if not code:

            app.logger.error(
                "CALLBACK ERROR: NO CODE"
            )

            return (
                "فشل تسجيل الدخول: لا يوجد code.",
                400
            )

        saved_state = session.get("oauth_state")

        if not saved_state:

            app.logger.error(
                "STATE LOST"
            )

            return (
                "الجلسة ضاعت أثناء تسجيل الدخول.",
                400
            )

        if state != saved_state:

            app.logger.error(
                "STATE MISMATCH"
            )

            return (
                "فشل تسجيل الدخول: state غير صحيح.",
                400
            )

        # =================================================
        # Access Token
        # =================================================

        token_response = requests.post(
            "https://discord.com/api/v10/oauth2/token",

            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI
            },

            headers={
                "Content-Type":
                    "application/x-www-form-urlencoded"
            },

            timeout=15
        )

        if not token_response.ok:

            app.logger.error(
                "TOKEN ERROR %s: %s",
                token_response.status_code,
                token_response.text
            )

            return (
                "فشل الاتصال مع Discord.",
                500
            )

        token_data = token_response.json()

        access_token = token_data.get(
            "access_token"
        )

        if not access_token:

            app.logger.error(
                "NO ACCESS TOKEN"
            )

            return (
                "لم يتم الحصول على رمز الدخول.",
                500
            )

        headers = {
            "Authorization":
                f"Bearer {access_token}"
        }

        # =================================================
        # User
        # =================================================

        user_response = requests.get(
            "https://discord.com/api/v10/users/@me",
            headers=headers,
            timeout=15
        )

        if not user_response.ok:

            app.logger.error(
                "USER ERROR %s: %s",
                user_response.status_code,
                user_response.text
            )

            return (
                "فشل الحصول على بيانات الحساب.",
                500
            )

        user_data = user_response.json()

        user = {
            "id": user_data.get("id"),
            "username": user_data.get("username"),
            "global_name": user_data.get("global_name"),
            "avatar": user_data.get("avatar")
        }

        # =================================================
        # Guilds
        # =================================================

        guild_response = requests.get(
            "https://discord.com/api/v10/users/@me/guilds",
            headers=headers,
            timeout=15
        )

        if not guild_response.ok:

            app.logger.error(
                "GUILD ERROR %s: %s",
                guild_response.status_code,
                guild_response.text
            )

            return (
                "فشل الحصول على السيرفرات.",
                500
            )

        guild_data = guild_response.json()

        guilds = []

        for guild in guild_data:

            guilds.append({
                "id": guild.get("id"),
                "name": guild.get("name"),
                "icon": guild.get("icon")
            })

        # =================================================
        # Save Session
        # =================================================

        session.clear()

        session["user"] = user
        session["guilds"] = guilds

        app.logger.info(
            "LOGIN SUCCESS - USER: %s - GUILDS: %s",
            user.get("username"),
            len(guilds)
        )

        return redirect("/")

    except Exception:

        app.logger.exception(
            "OAUTH CALLBACK CRASH"
        )

        return (
            "حدث خطأ أثناء تسجيل الدخول.",
            500
        )


# =========================================================
# إدارة السيرفر
# =========================================================

@app.route("/server/<guild_id>")
def server(guild_id):

    user = session.get("user")

    if not user:
        return redirect("/")

    guilds = session.get(
        "guilds",
        []
    )

    selected_guild = None

    for guild in guilds:

        if str(guild.get("id")) == str(guild_id):

            selected_guild = guild
            break

    if not selected_guild:
        return redirect("/")

    settings = get_settings(guild_id)

    excluded_roles = get_excluded_roles(
        guild_id
    )

    stats = {

        "tickets": safe_count(
            "tickets",
            guild_id
        ),

        "security_logs": safe_count(
            "security_logs",
            guild_id
        ),

        "criminal_records": safe_count(
            "criminal_records",
            guild_id
        ),

        "warnings": safe_count(
            "warnings",
            guild_id
        ),

        "deeds": safe_count(
            "deeds",
            guild_id
        ),

        "warrants": safe_count(
            "warrants",
            guild_id
        ),

        "dispatches": safe_count(
            "dispatches",
            guild_id
        ),

        "medical_reports": safe_count(
            "medical_reports",
            guild_id
        )
    }

    logs = get_security_logs(
        guild_id
    )

    tickets = get_tickets(
        guild_id
    )

    return render_template(

        "server.html",

        user=user,

        guild=selected_guild,

        settings=settings,

        stats=stats,

        excluded_roles=excluded_roles,

        logs=logs,

        tickets=tickets
    )


# =========================================================
# حفظ إعدادات السيرفر
# =========================================================

@app.route(
    "/server/<guild_id>/action",
    methods=["POST"]
)
def server_action(guild_id):

    user = session.get("user")

    if not user:
        return redirect("/")

    guilds = session.get(
        "guilds",
        []
    )

    allowed = any(
        str(g.get("id")) == str(guild_id)
        for g in guilds
    )

    if not allowed:
        return redirect("/")

    action = request.form.get(
        "action",
        ""
    )

    conn = db_connect()

    try:

        # =================================================
        # AI
        # =================================================

        if action == "ai_enable":

            conn.execute(
                """
                INSERT INTO settings (
                    guild_id,
                    ai_enabled
                )
                VALUES (?, 1)

                ON CONFLICT(guild_id)
                DO UPDATE SET
                    ai_enabled = 1
                """,
                (guild_id,)
            )

            conn.commit()

            return redirect(
                f"/server/{guild_id}?section=ai&saved=1"
            )

        if action == "ai_disable":

            conn.execute(
                """
                INSERT INTO settings (
                    guild_id,
                    ai_enabled
                )
                VALUES (?, 0)

                ON CONFLICT(guild_id)
                DO UPDATE SET
                    ai_enabled = 0
                """,
                (guild_id,)
            )

            conn.commit()

            return redirect(
                f"/server/{guild_id}?section=ai&saved=1"
            )

        if action == "ai_channel":

            channel_id = request.form.get(
                "channel_id",
                ""
            ).strip()

            channel_id = channel_id or None

            conn.execute(
                """
                INSERT INTO settings (
                    guild_id,
                    ai_channel_id
                )
                VALUES (?, ?)

                ON CONFLICT(guild_id)
                DO UPDATE SET
                    ai_channel_id = excluded.ai_channel_id
                """,
                (
                    guild_id,
                    channel_id
                )
            )

            conn.commit()

            return redirect(
                f"/server/{guild_id}?section=ai&saved=1"
            )

        # =================================================
        # Log Channels
        # =================================================

        log_actions = {

            "security_log":
                "security_log_channel_id",

            "delete_log":
                "delete_log_channel_id",

            "edit_log":
                "edit_log_channel_id",

            "member_log":
                "member_log_channel_id",

            "mod_log":
                "mod_log_channel_id",

            "role_log":
                "role_log_channel_id",

            "channel_log":
                "channel_log_channel_id"
        }

        if action in log_actions:

            column = log_actions[action]

            channel_id = request.form.get(
                "channel_id",
                ""
            ).strip()

            channel_id = channel_id or None

            conn.execute(
                f"""
                INSERT INTO settings (
                    guild_id,
                    {column}
                )
                VALUES (?, ?)

                ON CONFLICT(guild_id)
                DO UPDATE SET
                    {column} = excluded.{column}
                """,
                (
                    guild_id,
                    channel_id
                )
            )

            conn.commit()

            return redirect(
                f"/server/{guild_id}?section=settings&saved=1"
            )

        # =================================================
        # إضافة رتبة مستثناة
        # =================================================

        if action == "add_excluded_role":

            role_id = request.form.get(
                "role_id",
                ""
            ).strip()

            if role_id:

                conn.execute(
                    """
                    INSERT OR IGNORE INTO excluded_roles (
                        guild_id,
                        role_id
                    )
                    VALUES (?, ?)
                    """,
                    (
                        guild_id,
                        role_id
                    )
                )

                conn.commit()

            return redirect(
                f"/server/{guild_id}?section=protection&saved=1"
            )

        # =================================================
        # حذف رتبة مستثناة
        # =================================================

        if action == "remove_excluded_role":

            role_id = request.form.get(
                "role_id",
                ""
            ).strip()

            conn.execute(
                """
                DELETE FROM excluded_roles
                WHERE guild_id = ?
                AND role_id = ?
                """,
                (
                    guild_id,
                    role_id
                )
            )

            conn.commit()

            return redirect(
                f"/server/{guild_id}?section=protection&saved=1"
            )

    except Exception:

        app.logger.exception(
            "SERVER ACTION ERROR"
        )

    finally:

        conn.close()

    return redirect(
        f"/server/{guild_id}"
    )


# =========================================================
# تسجيل الخروج
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")


# =========================================================
# تشغيل Flask
# =========================================================

def run():

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )


def keep_alive():

    t = Thread(
        target=run
    )

    t.daemon = True

    t.start()
