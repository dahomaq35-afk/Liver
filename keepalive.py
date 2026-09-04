import os
import secrets
import urllib.parse
import urllib.request
import urllib.error
import json

from flask import Flask, render_template, redirect, request, session
from threading import Thread


app = Flask(__name__)

app.secret_key = os.getenv(
    "FLASK_SECRET_KEY",
    "temporary-secret-key"
)


CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")

REDIRECT_URI = os.getenv(
    "DISCORD_REDIRECT_URI",
    "https://liver-1.onrender.com/callback"
)


@app.route("/")
def home():
    return render_template(
        "index.html",
        user=session.get("user"),
        guilds=session.get("guilds", [])
    )


@app.route("/login")
def login():
    state = secrets.token_urlsafe(32)

    session["oauth_state"] = state

    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": "identify guilds",
        "state": state
    }

    url = (
        "https://discord.com/oauth2/authorize?"
        + urllib.parse.urlencode(params)
    )

    return redirect(url)


@app.route("/callback")
def callback():
    try:
        code = request.args.get("code")
        state = request.args.get("state")

        app.logger.info("OAuth callback started")

        if not code:
            app.logger.error(
                "OAuth callback: missing code"
            )
            return "فشل تسجيل الدخول: لا يوجد code.", 400

        if state != session.get("oauth_state"):
            app.logger.error(
                "OAuth callback: state mismatch"
            )
            return "فشل تسجيل الدخول: state غير صحيح.", 400

        data = urllib.parse.urlencode({
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI
        }).encode()

        token_request = urllib.request.Request(
            "https://discord.com/api/v10/oauth2/token",
            data=data,
            headers={
                "Content-Type":
                    "application/x-www-form-urlencoded"
            },
            method="POST"
        )

        with urllib.request.urlopen(
            token_request,
            timeout=15
        ) as response:

            token_data = json.loads(
                response.read().decode()
            )

        access_token = token_data.get(
            "access_token"
        )

        if not access_token:
            app.logger.error(
                "OAuth callback: no access token"
            )

            app.logger.error(
                "Discord response: %s",
                token_data
            )

            return "فشل الحصول على رمز الدخول.", 500

        headers = {
            "Authorization":
                f"Bearer {access_token}"
        }

        user_request = urllib.request.Request(
            "https://discord.com/api/v10/users/@me",
            headers=headers
        )

        guild_request = urllib.request.Request(
            "https://discord.com/api/v10/users/@me/guilds",
            headers=headers
        )

        with urllib.request.urlopen(
            user_request,
            timeout=15
        ) as response:

            user = json.loads(
                response.read().decode()
            )

        with urllib.request.urlopen(
            guild_request,
            timeout=15
        ) as response:

            guilds = json.loads(
                response.read().decode()
            )

        session["user"] = user
        session["guilds"] = guilds

        session.pop(
            "oauth_state",
            None
        )

        app.logger.info(
            "OAuth login successful. User ID: %s",
            user.get("id")
        )

        return redirect("/")

    except urllib.error.HTTPError as e:

        error_body = e.read().decode(
            errors="replace"
        )

        app.logger.error(
            "OAuth HTTP Error %s: %s",
            e.code,
            error_body
        )

        return "حدث خطأ أثناء تسجيل الدخول.", 500

    except Exception:

        app.logger.exception(
            "OAuth CALLBACK CRASH"
        )

        return "حدث خطأ أثناء تسجيل الدخول.", 500


@app.route("/logout")
def logout():
    session.clear()

    return redirect("/")


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
