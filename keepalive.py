import os
import secrets
import requests

from flask import Flask, render_template, redirect, request, session
from threading import Thread
from werkzeug.middleware.proxy_fix import ProxyFix


app = Flask(__name__)

# Render يعمل خلف Reverse Proxy
app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=1,
    x_proto=1,
    x_host=1
)


# مفتاح الجلسة
app.secret_key = os.getenv(
    "FLASK_SECRET_KEY",
    "temporary-secret-key"
)


# إعدادات Session
app.config.update(
    SESSION_COOKIE_NAME="mtbot_session",
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_PATH="/"
)


# Discord OAuth
CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")

REDIRECT_URI = os.getenv(
    "DISCORD_REDIRECT_URI",
    "https://liver-1.onrender.com/callback"
)


# =========================
# الصفحة الرئيسية
# =========================

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


# =========================
# تسجيل الدخول
# =========================

@app.route("/login")
def login():

    state = secrets.token_urlsafe(32)

    # نحذف الجلسة القديمة
    session.clear()

    # نحفظ state فقط
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


# =========================
# Discord Callback
# =========================

@app.route("/callback")
def callback():

    try:

        code = request.args.get("code")
        state = request.args.get("state")

        app.logger.info(
            "CALLBACK SESSION HAS STATE: %s",
            bool(session.get("oauth_state"))
        )

        # التأكد من وجود code
        if not code:

            app.logger.error(
                "CALLBACK ERROR: NO CODE"
            )

            return (
                "فشل تسجيل الدخول: لا يوجد code.",
                400
            )


        # التأكد من State
        saved_state = session.get(
            "oauth_state"
        )

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


        # =========================
        # الحصول على Access Token
        # =========================

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


        # =========================
        # بيانات المستخدم
        # =========================

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


        # نخزن البيانات الضرورية فقط
        user = {
            "id": user_data.get("id"),
            "username": user_data.get("username"),
            "global_name": user_data.get("global_name"),
            "avatar": user_data.get("avatar")
        }


        # =========================
        # سيرفرات المستخدم
        # =========================

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


        # نخزن فقط البيانات التي نحتاجها للموقع
        guilds = []

        for guild in guild_data:

            guilds.append({
                "id": guild.get("id"),
                "name": guild.get("name"),
                "icon": guild.get("icon")
            })


        # =========================
        # حفظ Session
        # =========================

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


# =========================
# تسجيل الخروج
# =========================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")


# =========================
# تشغيل Flask
# =========================

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


# =========================
# Keep Alive
# =========================

def keep_alive():

    t = Thread(
        target=run
    )

    t.daemon = True
    t.start()
