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


# الصفحة الرئيسية
@app.route("/")
def home():

    app.logger.info(
        "HOME SESSION: %s",
        dict(session)
    )

    return render_template(
        "index.html",
        user=session.get("user"),
        guilds=session.get("guilds", [])
    )


# تسجيل الدخول
@app.route("/login")
def login():

    state = secrets.token_urlsafe(32)

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


# Discord Callback
@app.route("/callback")
def callback():

    try:

        code = request.args.get("code")
        state = request.args.get("state")

        app.logger.info(
            "CALLBACK SESSION: %s",
            dict(session)
        )

        if not code:

            app.logger.error(
                "CALLBACK ERROR: NO CODE"
            )

            return (
                "فشل تسجيل الدخول: لا يوجد code.",
                400
            )

        saved_state = session.get(
            "oauth_state"
        )

        if not saved_state:

            app.logger.error(
                "STATE LOST: session has no oauth_state"
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


        # طلب Access Token
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


        # بيانات المستخدم
        headers = {
            "Authorization":
                f"Bearer {access_token}"
        }


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


        user = user_response.json()


        # سيرفرات المستخدم
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


        guilds = guild_response.json()


        # حفظ بيانات المستخدم
        session["user"] = user

        session["guilds"] = guilds

        session.pop(
            "oauth_state",
            None
        )


        app.logger.info(
            "LOGIN SUCCESS - SESSION USER SAVED"
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


# تسجيل الخروج
@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")


# تشغيل Flask
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


# تشغيل السيرفر
def keep_alive():

    t = Thread(
        target=run
    )

    t.daemon = True

    t.start()
