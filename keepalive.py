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
# FLASK
# =========================================================

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

DISCORD_BOT_TOKEN = os.getenv(
    "TOKEN"
)


# =========================================================
# DATABASE
# =========================================================

DATA_DIR = os.getenv(
    "DATA_DIR",
    "."
)

os.makedirs(
    DATA_DIR,
    exist_ok=True
)

DB_FILE = os.path.join(
    DATA_DIR,
    "mt_bot.db"
)

BOT = None


def db_connect():

    conn = sqlite3.connect(
        DB_FILE
    )

    conn.row_factory = sqlite3.Row

    return conn


# =========================================================
# SETTINGS
# =========================================================

def ensure_settings(guild_id):

    conn = db_connect()

    try:

        conn.execute(
            """
            INSERT OR IGNORE INTO settings
            (
                guild_id,
                ai_enabled
            )
            VALUES (?, 0)
            """,
            (
                guild_id,
            )
        )

        conn.commit()

    except Exception as e:

        print(
            "ENSURE SETTINGS ERROR:",
            repr(e)
        )

    finally:

        conn.close()


def get_settings(guild_id):

    ensure_settings(
        guild_id
    )

    conn = db_connect()

    try:

        row = conn.execute(
            """
            SELECT *
            FROM settings
            WHERE guild_id = ?
            """,
            (
                guild_id,
            )
        ).fetchone()

        if row:

            return dict(row)

        return {}

    except Exception as e:

        print(
            "GET SETTINGS ERROR:",
            repr(e)
        )

        return {}

    finally:

        conn.close()


# =========================================================
# DATABASE COUNTS
# =========================================================

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
            (
                guild_id,
            )
        ).fetchone()

        if row:

            return row["c"]

        return 0

    except Exception as e:

        print(
            f"COUNT ERROR [{table}]:",
            repr(e)
        )

        return 0


# =========================================================
# EXCLUDED ROLES
# =========================================================

def get_excluded_roles(guild_id):

    conn = db_connect()

    try:

        rows = conn.execute(
            """
            SELECT role_id
            FROM excluded_roles
            WHERE guild_id = ?
            """,
            (
                guild_id,
            )
        ).fetchall()

        return [
            str(row["role_id"])
            for row in rows
        ]

    except Exception as e:

        print(
            "GET EXCLUDED ROLES ERROR:",
            repr(e)
        )

        return []

    finally:

        conn.close()


def get_excluded_role_objects(
    guild_id,
    roles
):

    excluded_ids = set(
        get_excluded_roles(
            guild_id
        )
    )

    found = []

    for role in roles:

        if str(role["id"]) in excluded_ids:

            found.append(role)

    return found


# =========================================================
# SECURITY LOGS
# =========================================================

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
            (
                guild_id,
            )
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    except Exception as e:

        print(
            "GET SECURITY LOGS ERROR:",
            repr(e)
        )

        return []

    finally:

        conn.close()


# =========================================================
# TICKETS
# =========================================================

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
            (
                guild_id,
            )
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    except Exception as e:

        print(
            "GET TICKETS ERROR:",
            repr(e)
        )

        return []

    finally:

        conn.close()


# =========================================================
# DISCORD API HEADERS
# =========================================================

def discord_headers():

    return {
        "Authorization":
            f"Bot {DISCORD_BOT_TOKEN}",

        "Content-Type":
            "application/json"
    }


# =========================================================
# DISCORD API GET
# =========================================================

def discord_api_get(
    endpoint,
    silent=False
):

    if not DISCORD_BOT_TOKEN:

        if not silent:

            print(
                "DASHBOARD ERROR: "
                "TOKEN غير موجود."
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

        if not silent:

            print(
                "DISCORD API:",
                response.status_code,
                endpoint
            )

        if response.status_code != 200:

            if not silent:

                print(
                    "DISCORD API ERROR:",
                    response.text
                )

            return None

        return response.json()

    except Exception as e:

        if not silent:

            print(
                "DISCORD API REQUEST ERROR:",
                repr(e)
            )

        return None


# =========================================================
# GET EXACT BOT GUILD
# =========================================================

def get_bot_guild(guild_id):

    return discord_api_get(
        f"/guilds/{guild_id}",
        silent=True
    )


# =========================================================
# CHECK BOT IN GUILD
# =========================================================

def bot_is_in_guild(guild_id):

    data = get_bot_guild(
        guild_id
    )

    return data is not None


# =========================================================
# GET CHANNELS FROM EXACT GUILD
# =========================================================

def get_discord_channels(guild_id):

    channels = []

    data = discord_api_get(
        f"/guilds/{guild_id}/channels"
    )

    if data is None:

        print(
            "DASHBOARD: "
            "لم يتم العثور على رومات السيرفر."
        )

        return channels

    if not isinstance(
        data,
        list
    ):

        print(
            "DASHBOARD: "
            "بيانات الرومات غير صحيحة."
        )

        return channels

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

        if channel_type not in (
            0,
            5
        ):

            continue

        channel_id = channel.get(
            "id"
        )

        channel_name = channel.get(
            "name",
            "بدون اسم"
        )

        parent_id = channel.get(
            "parent_id"
        )

        category_name = "بدون تصنيف"

        if parent_id:

            category_name = categories.get(
                str(parent_id),
                "بدون تصنيف"
            )

        channels.append(
            {
                "id":
                    str(channel_id),

                "name":
                    str(channel_name),

                "category":
                    str(category_name),

                "type":
                    channel_type
            }
        )

    channels.sort(
        key=lambda x: (
            x["category"].lower(),
            x["name"].lower()
        )
    )

    print(
        "DASHBOARD EXACT GUILD CHANNELS:",
        len(channels)
    )

    return channels


# =========================================================
# GET ROLES FROM EXACT GUILD
# =========================================================

def get_discord_roles(guild_id):

    roles = []

    data = discord_api_get(
        f"/guilds/{guild_id}/roles"
    )

    if data is None:

        print(
            "DASHBOARD: "
            "لم يتم العثور على رتب السيرفر."
        )

        return roles

    if not isinstance(
        data,
        list
    ):

        print(
            "DASHBOARD: "
            "بيانات الرتب غير صحيحة."
        )

        return roles

    for role in data:

        role_id = str(
            role.get(
                "id",
                ""
            )
        )

        if role_id == str(guild_id):

            continue

        role_name = role.get(
            "name",
            "بدون اسم"
        )

        role_position = role.get(
            "position",
            0
        )

        roles.append(
            {
                "id":
                    role_id,

                "name":
                    str(role_name),

                "position":
                    int(role_position),

                "managed":
                    bool(
                        role.get(
                            "managed",
                            False
                        )
                    )
            }
        )

    roles.sort(
        key=lambda x: x["position"],
        reverse=True
    )

    print(
        "DASHBOARD EXACT GUILD ROLES:",
        len(roles)
    )

    return roles


# =========================================================
# HOME
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

    return render_template(
        "index.html",
        user=user,
        guilds=guilds
    )


# =========================================================
# LOGIN
# =========================================================

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
        f"{requests.utils.quote(
            str(value),
            safe=''
        )}"
        for key, value in params.items()
    )

    return redirect(
        "https://discord.com/oauth2/authorize?"
        + query
    )


# =========================================================
# CALLBACK
# =========================================================

@app.route("/callback")
def callback():

    code = request.args.get(
        "code"
    )

    if not code:

        return redirect("/")

    try:

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

    except Exception as e:

        print(
            "Discord OAuth Token Request Error:",
            repr(e)
        )

        return "Discord OAuth Error", 400

    if token_response.status_code != 200:

        print(
            "Discord OAuth Token Error:",
            token_response.status_code,
            token_response.text
        )

        return "Discord OAuth Error", 400

    token_data = token_response.json()

    access_token = token_data.get(
        "access_token"
    )

    if not access_token:

        return "No access token", 400

    headers = {
        "Authorization":
            f"Bearer {access_token}"
    }

    try:

        user_response = requests.get(
            "https://discord.com/api/v10/users/@me",
            headers=headers,
            timeout=15
        )

    except Exception as e:

        print(
            "Discord User Request Error:",
            repr(e)
        )

        return "Discord User Error", 400

    if user_response.status_code != 200:

        print(
            "Discord User Error:",
            user_response.status_code,
            user_response.text
        )

        return "Discord User Error", 400

    try:

        guild_response = requests.get(
            "https://discord.com/api/v10/users/@me/guilds",
            headers=headers,
            timeout=15
        )

    except Exception as e:

        print(
            "Discord Guild Request Error:",
            repr(e)
        )

        return "Discord Guild Error", 400

    user_data = user_response.json()

    guild_data = []

    if guild_response.status_code == 200:

        guild_data = guild_response.json()

    session["user"] = {

        "id":
            str(
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

    usable_guilds = []

    for guild in guild_data:

        guild_id = str(
            guild.get(
                "id",
                ""
            )
        )

        if not guild_id:

            continue

        bot_guild = get_bot_guild(
            guild_id
        )

        if not bot_guild:

            continue

        usable_guilds.append(
            {
                "id":
                    guild_id,

                "name":
                    guild.get(
                        "name",
                        bot_guild.get(
                            "name",
                            ""
                        )
                    ),

                "icon":
                    guild.get(
                        "icon"
                    )
                    or
                    bot_guild.get(
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
        )

    session["guilds"] = usable_guilds

    session.modified = True

    print("")
    print(
        "=========================================="
    )
    print(
        "        MT DASHBOARD LOGIN"
    )
    print(
        "=========================================="
    )
    print(
        "User:",
        session["user"]["username"]
    )
    print(
        "Total OAuth Guilds:",
        len(guild_data)
    )
    print(
        "Usable Bot Guilds:",
        len(usable_guilds)
    )
    print(
        "=========================================="
    )
    print("")

    return redirect("/")


# =========================================================
# SERVER PAGE
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

    selected_guild = None

    for guild in guilds:

        if (
            str(guild.get("id"))
            ==
            str(guild_id)
        ):

            selected_guild = guild

            break

    if not selected_guild:

        return redirect("/")

    bot_guild = get_bot_guild(
        guild_id
    )

    if not bot_guild:

        print(
            "DASHBOARD: "
            "البوت غير موجود في السيرفر:",
            guild_id
        )

        return redirect("/")

    selected_guild["name"] = (
        bot_guild.get(
            "name"
        )
        or
        selected_guild.get(
            "name",
            ""
        )
    )

    selected_guild["icon"] = (
        bot_guild.get(
            "icon"
        )
        or
        selected_guild.get(
            "icon"
        )
    )

    settings = get_settings(
        guild_id
    )

    stats = {

        "criminal_records":
            0,

        "warnings":
            0,

        "security_logs":
            0,

        "tickets":
            0,

        "deeds":
            0,

        "warrants":
            0,

        "dispatches":
            0,

        "medical_reports":
            0
    }

    conn = db_connect()

    try:

        tables = {

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
        }

        for key, table in tables.items():

            stats[key] = safe_count(
                conn,
                table,
                guild_id
            )

    finally:

        conn.close()

    channels = get_discord_channels(
        guild_id
    )

    roles = get_discord_roles(
        guild_id
    )

    excluded_roles = get_excluded_roles(
        guild_id
    )

    excluded_role_objects = (
        get_excluded_role_objects(
            guild_id,
            roles
        )
    )

    logs = get_security_logs(
        guild_id
    )

    tickets = get_tickets(
        guild_id
    )

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
        "Exact Channels:",
        len(channels)
    )
    print(
        "Exact Roles:",
        len(roles)
    )
    print(
        "Excluded Roles:",
        len(excluded_roles)
    )
    print(
        "=========================================="
    )
    print("")

    return render_template(
        "server.html",

        user=user,

        guild=selected_guild,

        settings=settings,

        stats=stats,

        excluded_roles=excluded_roles,

        excluded_role_objects=excluded_role_objects,

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

    allowed = any(

        str(g.get("id"))
        ==
        str(guild_id)

        for g in guilds
    )

    if not allowed:

        return redirect("/")

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

    ensure_settings(
        guild_id
    )

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
                (
                    guild_id,
                )
            )

            conn.commit()

            return redirect(
                url_for(
                    "server",
                    guild_id=guild_id
                )
                + "?section=ai&saved=1"
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
                (
                    guild_id,
                )
            )

            conn.commit()

            return redirect(
                url_for(
                    "server",
                    guild_id=guild_id
                )
                + "?section=ai&saved=1"
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

                    str(channel["id"])
                    ==
                    str(value)

                    for channel in channels
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
                + "?section=ai&saved=1"
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

                    str(channel["id"])
                    ==
                    str(value)

                    for channel in channels
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
                + "?section=logs&saved=1"
            )


        # =================================================
        # ADD EXCLUDED ROLE
        # =================================================

        if action == "add_excluded_role":

            if value.isdigit():

                roles = get_discord_roles(
                    guild_id
                )

                selected_role = None

                for role in roles:

                    if (
                        str(role["id"])
                        ==
                        str(value)
                    ):

                        selected_role = role

                        break

                if selected_role:

                    if selected_role.get(
                        "managed",
                        False
                    ):

                        print(
                            "DASHBOARD: "
                            "Managed role cannot be excluded:",
                            selected_role.get(
                                "name"
                            )
                        )

                    else:

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
                + "?section=protection&saved=1"
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
                + "?section=protection&saved=1"
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
