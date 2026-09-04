import os
import secrets
import urllib.parse
import urllib.request
import json

from flask import Flask, render_template, redirect, request, session
from threading import Thread


app = Flask(__name__)

app.secret_key = os.getenv("FLASK_SECRET_KEY", "temporary-secret-key")


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
    code = request.args.get("code")
    state = request.args.get("state")

    if not code or state != session.get("oauth_state"):
        return "فشل تسجيل الدخول.", 400

    data = urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI
    }).encode()

    token_request = urllib.request.Request(
        "https://discord.com/api/oauth2/token",
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(token_request) as response:
            token_data = json.loads(
                response.read().decode()
            )

        access_token = token_data["access_token"]

        user_request = urllib.request.Request(
            "https://discord.com/api/users/@me",
            headers={
                "Authorization": f"Bearer {access_token}"
            }
        )

        guild_request = urllib.request.Request(
            "https://discord.com/api/users/@me/guilds",
            headers={
                "Authorization": f"Bearer {access_token}"
            }
        )

        with urllib.request.urlopen(user_request) as response:
            user = json.loads(
                response.read().decode()
            )

        with urllib.request.urlopen(guild_request) as response:
            guilds = json.loads(
                response.read().decode()
            )

        session["user"] = user
        session["guilds"] = guilds

        session.pop("oauth_state", None)

        return redirect("/")

    except Exception as e:
        print("OAuth Error:", repr(e))
        return "حدث خطأ أثناء تسجيل الدخول.", 500


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


def run():
    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
    )


def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()
