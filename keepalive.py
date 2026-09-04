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

app = Flask(__name__)

app.secret_key = os.getenv(
    "FLASK_SECRET_KEY",
    "change-this-secret"
)

# =========================================================
# DISCORD OAUTH
# =========================================================

DISCORD_CLIENT_ID = os.getenv(
    "DISCORD_CLIENT_ID"
)

DISCORD_CLIENT_SECRET = os.getenv(
    "DISCORD_CLIENT_SECRET"
)

DISCORD_REDIRECT_URI = os.getenv(
    "DISCORD_REDIRECT_URI",
    "https://liver-1.onrender.com/callback"
)

# توكن البوت
DISCORD_BOT_TOKEN = os.getenv(
    "TOKEN"
)

DB_FILE = "mt_bot.db"

BOT = None


# =========================================================
# DATABASE
# =========================================================

def db_connect():

    conn = sqlite3.connect(
        DB_FILE
    )

    conn.row_factory = sqlite3.Row

    return conn


def safe_count(
    conn,
    table,
    guild_id
):

    try:

        row = conn.execute(
            f"""
            SELECT COUNT(*) AS c
            FROM {table}
            WHERE guild_id = ?
            """,
            (guild_id,)
        ).fetchone()

        return (
            row["c"]
            if row
            else 0
        )

    except Exception:

        return 0


def get_settings(guild_id):

    conn = db_connect()

    try:

        row = conn.execute(
            """
            SELECT *
            FROM settings
            WHERE guild_id = ?
            """,
            (guild_id,)
        ).fetchone()

        if row:

            return dict(row)

        return {}

    except Exception:

        return {}

    finally:

        conn.close()


def get_excluded_roles(guild_id):

    conn = db_connect()

    try:

        rows = conn.execute(
            """
            SELECT role_id
            FROM excluded_roles
            WHERE guild_id = ?
            """,
            (guild_id,)
        ).fetchall()

        return [
            str(row["role_id"])
            for row in rows
        ]

    except Exception:

        return []

    finally:

        conn.close()


def get_security_logs(guild_id):

    conn = db_connect()

    try:

        rows = conn.execute(
            """
            SELECT *
            FROM security_logs
            WHERE guild_id = ?
            ORDER BY id DESC
            LIMIT 50
            """,
            (guild_id,)
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    except Exception:

        return []

    finally:

        conn.close()


def get_tickets(guild_id):

    conn = db_connect()

    try:

        rows = conn.execute(
            """
            SELECT *
            FROM tickets
            WHERE guild_id = ?
            ORDER BY id DESC
            LIMIT 50
            """,
            (guild_id,)
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    except Exception:

        return []

    finally:

        conn.close()


# =========================================================
# DISCORD API
# =========================================================

def discord_headers():

    return {
        "Authorization": (
            f"Bot {DISCORD_BOT_TOKEN}"
        ),
        "Content-Type": "application/json"
    }


def discord_api_get(endpoint):

    if not DISCORD_BOT_TOKEN:

        print(
            "DASHBOARD ERROR: TOKEN غير موجود."
        )

        return None

    url = (
        "https://discord.com/api/v10"
        + endpoint
    )

    try:

        response = requests.get(
            url,
            headers=discord_headers(),
            timeout=15
        )

        print(
            "DISCORD API:",
            response.status_code,
            endpoint
        )

        if response.status_code != 200:

            print(
                "DISCORD API ERROR:",
                response.text
            )

            return None

        return response.json()

    except Exception as e:

        print(
            "DISCORD API REQUEST ERROR:",
            repr(e)
        )

        return None


# =========================================================
# CHECK BOT IN GUILD
# =========================================================

def bot_is_in_guild(guild_id):

    data = discord_api_get(
        f"/guilds/{guild_id}"
    )

    if data is None:

        return False

    return True


# =========================================================
# GET CHANNELS FROM SELECTED GUILD
# =========================================================

def get_discord_channels(guild_id):

    channels = []

    data = discord_api_get(
        f"/guilds/{guild_id}/channels"
    )

    if data is None:

        print(
            "DASHBOARD CHANNELS: API FAILED"
        )

        return channels

    try:

        # إنشاء قائمة التصنيفات
        categories = {}

        for channel in data:

            if channel.get("type") == 4:

                categories[
                    str(channel.get("id"))
                ] = channel.get(
                    "name",
                    "بدون تصنيف"
                )

        for channel in data:

            channel_type = channel.get(
                "type"
            )

            # 0 = Text
            # 5 = Announcement
            # 15 = Forum
            # نسمح بالقنوات النصية وما يشابهها
            if channel_type not in (
                0,
                5,
                15
            ):

                continue

            channel_id = str(
                channel.get(
                    "id",
                    ""
                )
            )

            channel_name = channel.get(
                "name",
                "بدون اسم"
            )

            parent_id = channel.get(
                "parent_id"
            )

            category_name = (
                categories.get(
                    str(parent_id),
                    "بدون تصنيف"
                )
                if parent_id
                else
                "بدون تصنيف"
            )

            channels.append({

                "id":
                    channel_id,

                "name":
                    channel_name,

                "category":
                    category_name,

                "type":
                    channel_type

            })

    except Exception as e:

        print(
            "CHANNEL PARSE ERROR:",
            repr(e)
        )

        return []

    channels.sort(
        key=lambda x: (
            x["category"].lower(),
            x["name"].lower()
        )
    )

    print(
        "DASHBOARD CHANNELS:",
        len(channels)
    )

    for channel in channels:

        print(
            "CHANNEL:",
            channel["category"],
            "/",
            channel["name"],
            "|",
            channel["id"]
        )

    return channels


# =========================================================
# GET ROLES FROM SELECTED GUILD
# =========================================================

def get_discord_roles(guild_id):

    roles = []

    data = discord_api_get(
        f"/guilds/{guild_id}/roles"
    )

    if data is None:

        print(
            "DASHBOARD ROLES: API FAILED"
        )

        return roles

    try:

        for role in data:

            role_id = str(
                role.get(
                    "id",
                    ""
                )
            )

            role_name = role.get(
                "name",
                "بدون اسم"
            )

            position = int(
                role.get(
                    "position",
                    0
                )
            )

            # تجاهل @everyone
            if role_id == str(guild_id):

                continue

            roles.append({

                "id":
                    role_id,

                "name":
                    role_name,

                "position":
                    position

            })

    except Exception as e:

        print(
            "ROLE PARSE ERROR:",
            repr(e)
        )

        return []

    # الأعلى أولاً
    roles.sort(
        key=lambda x: x["position"],
        reverse=True
    )

    print(
        "DASHBOARD ROLES:",
        len(roles)
    )

    for role in roles:

        print(
            "ROLE:",
            role["name"],
            "|",
            role["id"],
            "| POSITION:",
            role["position"]
        )

    return roles


# =========================================================
# DISCORD OAUTH
# =========================================================

@app.route("/")
def index():

    user = session.get(
        "user"
    )

    guilds = session.get(
        "guilds",
        []
    )

    if not user:

        return render_template(
            "index.html",
            user=None,
            guilds=[]
        )

    # =====================================================
    # ONLY GUILDS WHERE BOT EXISTS
    # =====================================================

    bot_guilds = []

    for guild in guilds:

        guild_id = str(
            guild.get(
                "id",
                ""
            )
        )

        if not guild_id:

            continue

        if bot_is_in_guild(
            guild_id
        ):

            bot_guilds.append(
                guild
            )

    print(
        "DASHBOARD USER GUILDS:",
        len(guilds)
    )

    print(
        "DASHBOARD BOT GUILDS:",
        len(bot_guilds)
    )

    session["guilds"] = bot_guilds

    return render_template(
        "index.html",
        user=user,
        guilds=bot_guilds
    )


@app.route("/login")
def login():

    params = {

        "client_id":
            DISCORD_CLIENT_ID,

        "redirect_uri":
            DISCORD_REDIRECT_URI,

        "response_type":
            "code",

        "scope":
            "identify guilds"
    }

    query = "&".join(

        f"{key}="
        f"{requests.utils.quote(str(value), safe='')}"

        for key, value
        in params.items()
    )

    return redirect(
        "https://discord.com/oauth2/authorize?"
        + query
    )


@app.route("/callback")
def callback():

    code = request.args.get(
        "code"
    )

    if not code:

        return redirect("/")

    token_response = requests.post(

        "https://discord.com/api/v10/oauth2/token",

        data={

            "client_id":
                DISCORD_CLIENT_ID,

            "client_secret":
                DISCORD_CLIENT_SECRET,

            "grant_type":
                "authorization_code",

            "code":
                code,

            "redirect_uri":
                DISCORD_REDIRECT_URI
        },

        headers={
            "Content-Type":
                "application/x-www-form-urlencoded"
        },

        timeout=15
    )

    if token_response.status_code != 200:

        print(
            "Discord OAuth Token Error:",
            token_response.status_code,
            token_response.text
        )

        return (
            "Discord OAuth Error",
            400
        )

    token_data = (
        token_response.json()
    )

    access_token = (
        token_data.get(
            "access_token"
        )
    )

    if not access_token:

        return (
            "No access token",
            400
        )

    headers = {
        "Authorization":
            f"Bearer {access_token}"
    }

    user_response = requests.get(

        "https://discord.com/api/v10/users/@me",

        headers=headers,

        timeout=15
    )

    guild_response = requests.get(

        "https://discord.com/api/v10/users/@me/guilds",

        headers=headers,

        timeout=15
    )

    if user_response.status_code != 200:

        return (
            "Discord User Error",
            400
        )

    user_data = (
        user_response.json()
    )

    guild_data = []

    if guild_response.status_code == 200:

        guild_data = (
            guild_response.json()
        )

    session["user"] = {

        "id": str(
            user_data.get(
                "id",
                ""
            )
        ),

        "username":
            user_data.get(
                "username",
                ""
            ),

        "global_name":
            user_data.get(
                "global_name"
            )
            or
            user_data.get(
                "username",
                ""
            ),

        "avatar":
            user_data.get(
                "avatar"
            )
    }

    # =====================================================
    # SAVE USER GUILDS
    # =====================================================

    session["guilds"] = [

        {

            "id": str(
                guild.get(
                    "id",
                    ""
                )
            ),

            "name":
                guild.get(
                    "name",
                    ""
                ),

            "icon":
                guild.get(
                    "icon"
                ),

            "owner":
                guild.get(
                    "owner",
                    False
                ),

            "permissions":
                str(
                    guild.get(
                        "permissions",
                        "0"
                    )
                )

        }

        for guild
        in guild_data
    ]

    return redirect("/")


# =========================================================
# SERVER
# =========================================================

@app.route(
    "/server/<guild_id>"
)
def server(guild_id):

    user = session.get(
        "user"
    )

    guilds = session.get(
        "guilds",
        []
    )

    if not user:

        return redirect(
            "/login"
        )

    # =====================================================
    # FIND SELECTED GUILD
    # =====================================================

    selected_guild = None

    for guild in guilds:

        if (
            str(
                guild.get(
                    "id"
                )
            )
            ==
            str(guild_id)
        ):

            selected_guild = guild

            break

    if not selected_guild:

        return redirect("/")


    # =====================================================
    # MAKE SURE BOT IS IN THIS GUILD
    # =====================================================

    if not bot_is_in_guild(
        guild_id
    ):

        print(
            "DASHBOARD: BOT NOT IN GUILD:",
            guild_id
        )

        return redirect("/")


    # =====================================================
    # SETTINGS
    # =====================================================

    settings = get_settings(
        guild_id
    )


    # =====================================================
    # STATS
    # =====================================================

    stats = {

        "criminal_records": 0,
        "warnings": 0,
        "security_logs": 0,
        "tickets": 0,
        "deeds": 0,
        "warrants": 0,
        "dispatches": 0,
        "medical_reports": 0
    }

    conn = db_connect()

    try:

        for key, table in {

            "criminal_records":
                "criminal_records",

            "warnings":
                "warnings",

            "security_logs":
                "security_logs",

            "tickets":
                "tickets",

            "deeds":
                "deeds",

            "warrants":
                "warrants",

            "dispatches":
                "dispatches",

            "medical_reports":
                "medical_reports"

        }.items():

            stats[key] = safe_count(
                conn,
                table,
                guild_id
            )

    finally:

        conn.close()


    # =====================================================
    # GET SELECTED GUILD CHANNELS
    # =====================================================

    channels = get_discord_channels(
        guild_id
    )


    # =====================================================
    # GET SELECTED GUILD ROLES
    # =====================================================

    roles = get_discord_roles(
        guild_id
    )


    # =====================================================
    # DEBUG
    # =====================================================

    print("")
    print(
        "=========================================="
    )
    print(
        "        MT DASHBOARD SERVER"
    )
    print(
        "=========================================="
    )
    print(
        "Guild ID:",
        guild_id
    )
    print(
        "Guild Name:",
        selected_guild.get(
            "name"
        )
    )
    print(
        "Channels:",
        len(channels)
    )
    print(
        "Roles:",
        len(roles)
    )
    print(
        "=========================================="
    )
    print("")


    # =====================================================
    # DATA
    # =====================================================

    excluded_roles = get_excluded_roles(
        guild_id
    )

    logs = get_security_logs(
        guild_id
    )

    tickets = get_tickets(
        guild_id
    )


    # =====================================================
    # PAGE
    # =====================================================

    return render_template(

        "server.html",

        user=user,

        guild=selected_guild,

        settings=settings,

        stats=stats,

        excluded_roles=excluded_roles,

        logs=logs,

        tickets=tickets,

        channels=channels,

        roles=roles
    )


# =========================================================
# SERVER ACTIONS
# =========================================================

@app.route(
    "/server/<guild_id>/action",
    methods=["POST"]
)
def server_action(guild_id):

    user = session.get(
        "user"
    )

    guilds = session.get(
        "guilds",
        []
    )

    if not user:

        return redirect(
            "/login"
        )

    # =====================================================
    # CHECK USER ACCESS
    # =====================================================

    allowed = any(

        str(
            g.get("id")
        )
        ==
        str(guild_id)

        for g in guilds
    )

    if not allowed:

        return redirect("/")


    # =====================================================
    # CHECK BOT ACCESS
    # =====================================================

    if not bot_is_in_guild(
        guild_id
    ):

        return redirect("/")


    action = request.form.get(
        "action"
    )

    value = request.form.get(
        "value",
        ""
    ).strip()


    # =====================================================
    # DATABASE
    # =====================================================

    conn = db_connect()

    try:

        # =================================================
        # AI ENABLE
        # =================================================

        if action == "ai_enable":

            conn.execute(

                """
                UPDATE settings
                SET ai_enabled = 1
                WHERE guild_id = ?
                """,

                (guild_id,)
            )

            conn.commit()

            return redirect(

                url_for(
                    "server",
                    guild_id=guild_id
                )
                +
                "?section=ai&saved=1"
            )


        # =================================================
        # AI DISABLE
        # =================================================

        if action == "ai_disable":

            conn.execute(

                """
                UPDATE settings
                SET ai_enabled = 0
                WHERE guild_id = ?
                """,

                (guild_id,)
            )

            conn.commit()

            return redirect(

                url_for(
                    "server",
                    guild_id=guild_id
                )
                +
                "?section=ai&saved=1"
            )


        # =================================================
        # AI CHANNEL
        # =================================================

        if action == "ai_channel":

            if value.isdigit():

                channels = get_discord_channels(
                    guild_id
                )

                valid = any(

                    str(
                        channel["id"]
                    )
                    ==
                    str(value)

                    for channel
                    in channels
                )

                if valid:

                    conn.execute(

                        """
                        UPDATE settings
                        SET ai_channel_id = ?
                        WHERE guild_id = ?
                        """,

                        (
                            int(value),
                            guild_id
                        )
                    )

                    conn.commit()

            return redirect(

                url_for(
                    "server",
                    guild_id=guild_id
                )
                +
                "?section=ai&saved=1"
            )


        # =================================================
        # LOG CHANNELS
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

            if value.isdigit():

                channels = get_discord_channels(
                    guild_id
                )

                valid = any(

                    str(
                        channel["id"]
                    )
                    ==
                    str(value)

                    for channel
                    in channels
                )

                if valid:

                    column = log_actions[
                        action
                    ]

                    conn.execute(

                        f"""
                        UPDATE settings
                        SET {column} = ?
                        WHERE guild_id = ?
                        """,

                        (
                            int(value),
                            guild_id
                        )
                    )

                    conn.commit()

            return redirect(

                url_for(
                    "server",
                    guild_id=guild_id
                )
                +
                "?section=logs&saved=1"
            )


        # =================================================
        # ADD EXCLUDED ROLE
        # =================================================

        if action == "add_excluded_role":

            if value.isdigit():

                roles = get_discord_roles(
                    guild_id
                )

                valid_role = None

                for role in roles:

                    if (
                        str(
                            role["id"]
                        )
                        ==
                        str(value)
                    ):

                        valid_role = role

                        break

                if valid_role:

                    existing = conn.execute(

                        """
                        SELECT 1
                        FROM excluded_roles
                        WHERE guild_id = ?
                        AND role_id = ?
                        """,

                        (
                            guild_id,
                            int(value)
                        )
                    ).fetchone()

                    if not existing:

                        conn.execute(

                            """
                            INSERT INTO excluded_roles
                            (
                                guild_id,
                                role_id
                            )
                            VALUES (?, ?)
                            """,

                            (
                                guild_id,
                                int(value)
                            )
                        )

                        conn.commit()

            return redirect(

                url_for(
                    "server",
                    guild_id=guild_id
                )
                +
                "?section=protection&saved=1"
            )


        # =================================================
        # REMOVE EXCLUDED ROLE
        # =================================================

        if action == "remove_excluded_role":

            if value.isdigit():

                conn.execute(

                    """
                    DELETE FROM excluded_roles
                    WHERE guild_id = ?
                    AND role_id = ?
                    """,

                    (
                        guild_id,
                        int(value)
                    )
                )

                conn.commit()

            return redirect(

                url_for(
                    "server",
                    guild_id=guild_id
                )
                +
                "?section=protection&saved=1"
            )


    except Exception as e:

        print(
            "DASHBOARD ACTION ERROR:",
            repr(e)
        )

    finally:

        conn.close()


    return redirect(

        url_for(
            "server",
            guild_id=guild_id
        )
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")


# =========================================================
# KEEP ALIVE
# =========================================================

def keep_alive(bot):

    global BOT

    BOT = bot

    port = int(
        os.getenv(
            "PORT",
            10000
        )
    )

    print(
        f"DASHBOARD: Starting Flask on port {port}"
    )

    flask_thread = threading.Thread(

        target=lambda: app.run(

            host="0.0.0.0",

            port=port,

            debug=False,

            use_reloader=False

        ),

        daemon=True
    )

    flask_thread.start()

    print(
        "DASHBOARD: Flask thread started."
    )
