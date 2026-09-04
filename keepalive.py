import os
import sqlite3
import threading
import requests

from flask import Flask, redirect, request, session, render_template, url_for

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-this-secret")

DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")

DISCORD_REDIRECT_URI = os.getenv(
    "DISCORD_REDIRECT_URI",
    "https://liver-1.onrender.com/callback"
)

DB_FILE = "mt_bot.db"

BOT = None


# =========================================================
# DATABASE
# =========================================================

def db_connect():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def safe_count(conn, table, guild_id):
    try:
        row = conn.execute(
            f"""
            SELECT COUNT(*) AS c
            FROM {table}
            WHERE guild_id = ?
            """,
            (guild_id,)
        ).fetchone()

        return row["c"] if row else 0

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

        return dict(row) if row else {}

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

        return [dict(row) for row in rows]

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

        return [dict(row) for row in rows]

    except Exception:
        return []

    finally:
        conn.close()


# =========================================================
# DISCORD OAUTH
# =========================================================

@app.route("/")
def index():

    user = session.get("user")
    guilds = session.get("guilds", [])

    return render_template(
        "index.html",
        user=user,
        guilds=guilds
    )


@app.route("/login")
def login():

    params = {
        "client_id": DISCORD_CLIENT_ID,
        "redirect_uri": DISCORD_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify guilds"
    }

    query = "&".join(
        f"{key}={requests.utils.quote(str(value), safe='')}"
        for key, value in params.items()
    )

    return redirect(
        "https://discord.com/oauth2/authorize?" + query
    )


@app.route("/callback")
def callback():

    code = request.args.get("code")

    if not code:
        return redirect("/")

    token_response = requests.post(
        "https://discord.com/api/v10/oauth2/token",
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
            "Discord OAuth Token Error:",
            token_response.status_code,
            token_response.text
        )
        return "Discord OAuth Error", 400

    token_data = token_response.json()

    access_token = token_data.get("access_token")

    if not access_token:
        return "No access token", 400

    headers = {
        "Authorization": f"Bearer {access_token}"
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
        return "Discord User Error", 400

    user_data = user_response.json()

    guild_data = []

    if guild_response.status_code == 200:
        guild_data = guild_response.json()

    session["user"] = {
        "id": str(user_data.get("id", "")),
        "username": user_data.get("username", ""),
        "global_name": user_data.get("global_name")
        or user_data.get("username", ""),
        "avatar": user_data.get("avatar"),
    }

    session["guilds"] = [
        {
            "id": str(guild.get("id", "")),
            "name": guild.get("name", ""),
            "icon": guild.get("icon"),
            "owner": guild.get("owner", False),
            "permissions": str(
                guild.get("permissions", "0")
            )
        }
        for guild in guild_data
    ]

    return redirect("/")


# =========================================================
# DISCORD GUILD
# =========================================================

def get_discord_guild(guild_id):

    if BOT is None:
        print("DASHBOARD: BOT is None")
        return None

    try:
        guild_id = int(guild_id)
    except Exception:
        print("DASHBOARD: Invalid Guild ID:", guild_id)
        return None

    guild = BOT.get_guild(guild_id)

    if guild:
        return guild

    print(
        "DASHBOARD: Guild not found in cache:",
        guild_id
    )

    return None


# =========================================================
# CHANNELS
# =========================================================

def get_guild_channels(guild):

    channels = []

    if guild is None:
        return channels

    try:

        for channel in guild.channels:

            channel_type = str(
                getattr(channel, "type", "")
            )

            if channel_type != "text":
                continue

            category_name = "بدون تصنيف"

            if channel.category:
                category_name = channel.category.name

            channels.append({
                "id": str(channel.id),
                "name": channel.name,
                "category": category_name
            })

    except Exception as e:

        print(
            "DASHBOARD CHANNEL ERROR:",
            repr(e)
        )

    channels.sort(
        key=lambda x: (
            x["category"].lower(),
            x["name"].lower()
        )
    )

    return channels


# =========================================================
# ROLES
# =========================================================

def get_guild_roles(guild):

    roles = []

    if guild is None:
        return roles

    try:

        for role in guild.roles:

            if role.is_default():
                continue

            roles.append({
                "id": str(role.id),
                "name": role.name,
                "position": role.position
            })

    except Exception as e:

        print(
            "DASHBOARD ROLE ERROR:",
            repr(e)
        )

    roles.sort(
        key=lambda x: x["position"],
        reverse=True
    )

    return roles


# =========================================================
# SERVER
# =========================================================

@app.route("/server/<guild_id>")
def server(guild_id):

    user = session.get("user")
    guilds = session.get("guilds", [])

    if not user:
        return redirect("/login")

    selected_guild = None

    for guild in guilds:

        if str(guild.get("id")) == str(guild_id):

            selected_guild = guild
            break

    if not selected_guild:
        return redirect("/")


    # =====================================================
    # SETTINGS
    # =====================================================

    settings = get_settings(guild_id)


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

        stats["criminal_records"] = safe_count(
            conn,
            "criminal_records",
            guild_id
        )

        stats["warnings"] = safe_count(
            conn,
            "warnings",
            guild_id
        )

        stats["security_logs"] = safe_count(
            conn,
            "security_logs",
            guild_id
        )

        stats["tickets"] = safe_count(
            conn,
            "tickets",
            guild_id
        )

        stats["deeds"] = safe_count(
            conn,
            "deeds",
            guild_id
        )

        stats["warrants"] = safe_count(
            conn,
            "warrants",
            guild_id
        )

        stats["dispatches"] = safe_count(
            conn,
            "dispatches",
            guild_id
        )

        stats["medical_reports"] = safe_count(
            conn,
            "medical_reports",
            guild_id
        )

    except Exception as e:

        print(
            "DASHBOARD STATS ERROR:",
            repr(e)
        )

    finally:

        conn.close()


    # =====================================================
    # GET DISCORD SERVER
    # =====================================================

    discord_guild = None

    if BOT is not None:

        try:

            discord_guild = BOT.get_guild(
                int(guild_id)
            )

        except Exception as e:

            print(
                "DASHBOARD GUILD ERROR:",
                repr(e)
            )


    # =====================================================
    # DEBUG
    # =====================================================

    print("")
    print("==========================================")
    print("       DASHBOARD DISCORD CHECK")
    print("==========================================")
    print("Requested Guild ID:", guild_id)
    print("Bot:", BOT)
    print(
        "Bot User:",
        BOT.user if BOT else None
    )

    if BOT:

        print(
            "Bot Guild Count:",
            len(BOT.guilds)
        )

        for g in BOT.guilds:

            print(
                "BOT SERVER:",
                g.id,
                "|",
                g.name
            )

    print(
        "MATCHED GUILD:",
        discord_guild
    )


    # =====================================================
    # CHANNELS
    # =====================================================

    channels = get_guild_channels(
        discord_guild
    )


    # =====================================================
    # ROLES
    # =====================================================

    roles = get_guild_roles(
        discord_guild
    )


    print(
        "CHANNEL COUNT:",
        len(channels)
    )

    print(
        "ROLE COUNT:",
        len(roles)
    )

    print("==========================================")
    print("")


    # =====================================================
    # OTHER DATA
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
    # RENDER
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

    user = session.get("user")
    guilds = session.get("guilds", [])

    if not user:
        return redirect("/login")

    allowed = any(
        str(g.get("id")) == str(guild_id)
        for g in guilds
    )

    if not allowed:
        return redirect("/")

    action = request.form.get("action")

    value = request.form.get(
        "value",
        ""
    ).strip()


    # =====================================================
    # BOT GUILD
    # =====================================================

    discord_guild = get_discord_guild(
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
                (guild_id,)
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
                (guild_id,)
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

            if (
                value.isdigit()
                and discord_guild
            ):

                channel = discord_guild.get_channel(
                    int(value)
                )

                if (
                    channel
                    and str(channel.type) == "text"
                ):

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

            if (
                value.isdigit()
                and discord_guild
            ):

                channel = discord_guild.get_channel(
                    int(value)
                )

                if (
                    channel
                    and str(channel.type) == "text"
                ):

                    column = log_actions[action]

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

            if (
                value.isdigit()
                and discord_guild
            ):

                role = discord_guild.get_role(
                    int(value)
                )

                if (
                    role
                    and not role.is_default()
                ):

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
