import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import sqlite3
import time
import re
import datetime
import asyncio
from openai import OpenAI
import os
import json
import aiohttp

from flask import (
    Flask,
    jsonify,
    redirect,
    request,
    session
)

import requests
from threading import Thread

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "supersecretkey")

# ================= FLASK DASHBOARD =================

@app.route("/")
def home():

    if "user" not in session:

        return f"""
        <html>
        <head>
            <title>Mod.AI Login</title>

            <style>
                body {{
                    background: #0d0f14;
                    color: white;
                    font-family: Arial;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                }}

                .box {{
                    background: #13161e;
                    padding: 40px;
                    border-radius: 14px;
                    border: 1px solid #1f2430;
                    text-align: center;
                    width: 340px;
                }}

                h1 {{
                    margin-bottom: 12px;
                }}

                p {{
                    color: #9aa3b2;
                    margin-bottom: 24px;
                }}

                .btn {{
                    display: inline-block;
                    background: #5865F2;
                    color: white;
                    text-decoration: none;
                    padding: 14px 22px;
                    border-radius: 10px;
                    font-weight: bold;
                    transition: 0.2s;
                }}

                .btn:hover {{
                    opacity: 0.9;
                    transform: translateY(-2px);
                }}
            </style>
        </head>

        <body>

            <div class="box">
                <h1>Mod.AI Dashboard</h1>

                <p>Login with Discord to continue</p>

                <a class="btn" href="/login">
                    Login with Discord
                </a>
            </div>

        </body>
        </html>
        """

    return redirect("/servers")


@app.route("/login")
def login():

    discord_login_url = (
        "https://discord.com/api/oauth2/authorize"
        f"?client_id={DISCORD_CLIENT_ID}"
        "&response_type=code"
        f"&redirect_uri={DISCORD_REDIRECT_URI}"
        "&scope=identify%20guilds"
    )

    return redirect(discord_login_url)


@app.route("/callback")
def callback():

    code = request.args.get("code")

    if not code:
        return "No code provided"

    data = {
        "client_id": DISCORD_CLIENT_ID,
        "client_secret": DISCORD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": DISCORD_REDIRECT_URI,
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    token_response = requests.post(
        "https://discord.com/api/oauth2/token",
        data=data,
        headers=headers
    )

    token_json = token_response.json()

    access_token = token_json.get("access_token")

    if not access_token:
        return f"OAuth failed: {token_json}"

    user_response = requests.get(
        "https://discord.com/api/users/@me",
        headers={
            "Authorization": f"Bearer {access_token}"
        }
    )

    user_json = user_response.json()

    session["user"] = {
        "id": user_json["id"],
        "username": user_json["username"],
        "avatar": user_json.get("avatar")
    }

    session["access_token"] = access_token
    return redirect("/servers")


@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")

def get_badge(action):
    a = action.lower()
    if "ban" in a:
        return f'<span class="badge badge-ban">ban</span>'
    elif "kick" in a:
        return f'<span class="badge badge-kick">kick</span>'
    elif "timed out" in a or "timeout" in a or "mute" in a:
        return f'<span class="badge badge-timeout">timeout</span>'
    elif "warn" in a:
        return f'<span class="badge badge-warn">warn</span>'
    else:
        return f'<span class="badge badge-automod">{action}</span>'
    

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>

<head>

    <title>Mod.AI Dashboard</title>

    <meta charset="UTF-8">

    <style>

        body {{
            margin: 0;
            background: #0d0f14;
            color: white;
            font-family: Arial, sans-serif;
        }}

        .container {{
            width: 92%;
            max-width: 1400px;
            margin: auto;
            padding: 30px;
        }}

        h1 {{
            margin-bottom: 25px;
        }}

        .topbar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 25px;
        }}

        .topbar-left {{
            display: flex;
            align-items: center;
            gap: 16px;
        }}

        .back-btn {{
            background: #1f2430;
            color: white;
            text-decoration: none;
            padding: 10px 18px;
            border-radius: 8px;
            font-weight: bold;
        }}

        .logout-btn {{
            background: #ff4d4d;
            color: white;
            text-decoration: none;
            padding: 10px 18px;
            border-radius: 8px;
            font-weight: bold;
        }}

        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 18px;
            margin-bottom: 35px;
        }}

        .card {{
            background: #13161e;
            border: 1px solid #1f2430;
            border-radius: 14px;
            padding: 22px;
        }}

        .card h2 {{
            margin: 0;
            font-size: 15px;
            color: #9aa3b2;
        }}

        .value {{
            margin-top: 12px;
            font-size: 34px;
            font-weight: bold;
        }}

        .tables {{
            display: grid;
            grid-template-columns: 1fr 2fr;
            gap: 20px;
        }}

        .table-card {{
            background: #13161e;
            border: 1px solid #1f2430;
            border-radius: 14px;
            padding: 20px;
            overflow-x: auto;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
        }}

        th {{
            text-align: left;
            padding: 12px;
            color: #9aa3b2;
            border-bottom: 1px solid #222734;
        }}

        td {{
            padding: 12px;
            border-bottom: 1px solid #1b1f2a;
        }}

        tr:hover {{
            background: #171b25;
        }}

        .warn-count {{
            background: #ffb84d;
            color: black;
            padding: 4px 10px;
            border-radius: 999px;
            font-weight: bold;
        }}

        .badge {{
            padding: 5px 10px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: bold;
            text-transform: uppercase;
        }}

        .badge-ban {{
            background: #ff4d4d;
        }}

        .badge-kick {{
            background: #ff944d;
        }}

        .badge-timeout {{
            background: #5865F2;
        }}

        .badge-warn {{
            background: #ffd24d;
            color: black;
        }}

        .badge-automod {{
            background: #2ecc71;
        }}

        .empty {{
            text-align: center;
            color: #777;
            padding: 20px;
        }}

        .ts {{
            color: #9aa3b2;
            font-size: 13px;
        }}

        .guild-label {{
            color: #9aa3b2;
            font-size: 14px;
            margin-bottom: 4px;
        }}

    </style>

</head>

<body>

    <div class="container">

        <div class="topbar">

            <div class="topbar-left">
                <a class="back-btn" href="/servers">← Servers</a>
                <div>
                    <div class="guild-label">Server ID: {guild_id_label}</div>
                    <h1 style="margin:0">🛡️ Mod.AI Dashboard</h1>
                </div>
            </div>

            <a class="logout-btn" href="/logout">
                Logout
            </a>

        </div>

        <div class="stats">

            <div class="card">
                <h2>Total Actions</h2>
                <div class="value">{total_actions}</div>
            </div>

            <div class="card">
                <h2>Warned Users</h2>
                <div class="value">{warned_users}</div>
            </div>

            <div class="card">
                <h2>Total Bans</h2>
                <div class="value">{total_bans}</div>
            </div>

            <div class="card">
                <h2>Total Timeouts</h2>
                <div class="value">{total_timeouts}</div>
            </div>

        </div>

        <div class="tables">

            <div class="table-card">

                <h2>⚠️ Top Warned Users</h2>

                <table>

                    <tr>
                        <th>User ID</th>
                        <th>Warnings</th>
                    </tr>

                    {warnings_rows}

                </table>

            </div>

            <div class="table-card">

                <h2>📜 Recent Moderation Actions</h2>

                <table>

                    <tr>
                        <th>Timestamp</th>
                        <th>User</th>
                        <th>Action</th>
                        <th>Reason</th>
                        <th>Moderator</th>
                    </tr>

                    {actions_rows}

                </table>

            </div>

        </div>

    </div>

</body>

</html>
"""


def build_dashboard(guild_id=None):
    """Shared dashboard builder. Filters by guild_id if provided."""
    try:
        conn = sqlite3.connect("modbot.db")
        c = conn.cursor()

        if guild_id:
            c.execute("SELECT COUNT(*) FROM mod_actions WHERE guild_id=?", (guild_id,))
        else:
            c.execute("SELECT COUNT(*) FROM mod_actions")
        total_actions = c.fetchone()[0]

        # Warnings are global per user (no guild_id in schema), show all
        c.execute("SELECT COUNT(*) FROM warnings")
        warned_users = c.fetchone()[0]

        if guild_id:
            c.execute("SELECT COUNT(*) FROM mod_actions WHERE action LIKE '%ban%' AND guild_id=?", (guild_id,))
        else:
            c.execute("SELECT COUNT(*) FROM mod_actions WHERE action LIKE '%ban%'")
        total_bans = c.fetchone()[0]

        if guild_id:
            c.execute(
                "SELECT COUNT(*) FROM mod_actions WHERE (action LIKE '%timed out%' OR action LIKE '%timeout%' OR action LIKE '%mute%') AND guild_id=?",
                (guild_id,)
            )
        else:
            c.execute("SELECT COUNT(*) FROM mod_actions WHERE action LIKE '%timed out%' OR action LIKE '%timeout%' OR action LIKE '%mute%'")
        total_timeouts = c.fetchone()[0]

        c.execute("SELECT user_id, count FROM warnings ORDER BY count DESC LIMIT 10")
        top_warned = c.fetchall()

        if guild_id:
            c.execute(
                "SELECT timestamp, target_user, action, reason, moderator FROM mod_actions WHERE guild_id=? ORDER BY id DESC LIMIT 30",
                (guild_id,)
            )
        else:
            c.execute("SELECT timestamp, target_user, action, reason, moderator FROM mod_actions ORDER BY id DESC LIMIT 30")
        recent_actions = c.fetchall()

        conn.close()

        if top_warned:
            warnings_rows = "".join(
                f"<tr><td>{uid}</td><td><span class='warn-count'>{cnt}</span></td></tr>"
                for uid, cnt in top_warned
            )
        else:
            warnings_rows = "<tr><td colspan='2' class='empty'>No warnings yet.</td></tr>"

        if recent_actions:
            actions_rows = "".join(
                f"<tr><td class='ts'>{ts[:19].replace('T',' ')}</td><td>{user}</td><td>{get_badge(action)}</td><td>{reason}</td><td>{mod}</td></tr>"
                for ts, user, action, reason, mod in recent_actions
            )
        else:
            actions_rows = "<tr><td colspan='5' class='empty'>No actions yet.</td></tr>"

        html = DASHBOARD_HTML.format(
            guild_id_label=str(guild_id) if guild_id else "All Servers",
            total_actions=total_actions,
            warned_users=warned_users,
            total_bans=total_bans,
            total_timeouts=total_timeouts,
            warnings_rows=warnings_rows,
            actions_rows=actions_rows
        )

        return html

    except Exception as e:
        return f"Dashboard error: {e}"


@app.route('/dashboard')
def dashboard():
    if "user" not in session:
        return redirect("/")
    return build_dashboard()


# FIX: This route was missing — server cards linked here but got 404
@app.route('/dashboard/<int:guild_id>')
def dashboard_guild(guild_id):
    if "user" not in session:
        return redirect("/")

    # Verify the user actually has admin in this guild before showing data
    try:
        user_guilds = requests.get(
            "https://discord.com/api/users/@me/guilds",
            headers={"Authorization": f"Bearer {session['access_token']}"}
        ).json()

        authorized = any(
            str(g["id"]) == str(guild_id) and (int(g.get("permissions", 0)) & 0x8)
            for g in user_guilds
        )

        if not authorized:
            return "❌ You don't have admin access to that server.", 403

    except Exception as e:
        return f"Auth check failed: {e}", 500

    return build_dashboard(guild_id=guild_id)


@app.route("/servers")
def servers():

    if "user" not in session:
        return redirect("/")

    try:
        user_guilds = requests.get(
            "https://discord.com/api/users/@me/guilds",
            headers={"Authorization": f"Bearer {session['access_token']}"}
        ).json()
    except Exception as e:
        return f"Failed to fetch guilds: {e}"

    guild_cards = ""

    for guild in user_guilds:

        permissions = int(guild.get("permissions", 0))

        if permissions & 0x8:

            icon_url = (
                f"https://cdn.discordapp.com/icons/{guild['id']}/{guild['icon']}.png"
                if guild.get("icon") else
                "https://cdn.discordapp.com/embed/avatars/0.png"
            )

            guild_cards += f"""
            <a class="server-card" href="/dashboard/{guild['id']}">
                <img src="{icon_url}" class="server-icon" onerror="this.src='https://cdn.discordapp.com/embed/avatars/0.png'">
                <div class="server-name">{guild['name']}</div>
            </a>
            """

    if not guild_cards:
        guild_cards = "<p style='color:#9aa3b2'>No servers found where you have admin permissions.</p>"

    return f"""
    <html>

    <head>

        <title>Select Server</title>

        <style>

            body {{
                background: #0d0f14;
                color: white;
                font-family: Arial;
                margin: 0;
            }}

            .container {{
                width: 90%;
                max-width: 1200px;
                margin: auto;
                padding: 40px;
            }}

            .topbar {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 30px;
            }}

            h1 {{
                margin: 0;
            }}

            .logout-btn {{
                background: #ff4d4d;
                color: white;
                text-decoration: none;
                padding: 10px 18px;
                border-radius: 8px;
                font-weight: bold;
            }}

            .grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
                gap: 20px;
            }}

            .server-card {{
                background: #13161e;
                border: 1px solid #1f2430;
                border-radius: 16px;
                padding: 24px;
                text-decoration: none;
                color: white;
                transition: 0.2s;
                text-align: center;
                cursor: pointer;
            }}

            .server-card:hover {{
                transform: translateY(-4px);
                background: #171b25;
                border-color: #5865F2;
            }}

            .server-icon {{
                width: 80px;
                height: 80px;
                border-radius: 50%;
                margin-bottom: 15px;
                object-fit: cover;
            }}

            .server-name {{
                font-size: 18px;
                font-weight: bold;
            }}

        </style>

    </head>

    <body>

        <div class="container">

            <div class="topbar">
                <h1>🛡️ Select a Server</h1>
                <a class="logout-btn" href="/logout">Logout</a>
            </div>

            <div class="grid">
                {guild_cards}
            </div>

        </div>

    </body>

    </html>
    """

@app.route('/api/warnings')
def api_warnings():
    try:
        conn = sqlite3.connect("modbot.db")
        c = conn.cursor()
        c.execute("SELECT user_id, count FROM warnings ORDER BY count DESC")
        rows = c.fetchall()
        conn.close()
        return jsonify([{"user_id": r[0], "count": r[1]} for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/api/actions')
def api_actions():
    try:
        conn = sqlite3.connect("modbot.db")
        c = conn.cursor()
        c.execute("SELECT timestamp, target_user, action, reason, moderator FROM mod_actions ORDER BY id DESC LIMIT 50")
        rows = c.fetchall()
        conn.close()
        return jsonify([
            {"timestamp": r[0], "target_user": r[1], "action": r[2], "reason": r[3], "moderator": r[4]}
            for r in rows
        ])
    except Exception as e:
        return jsonify({"error": str(e)})

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# ================= CONFIG =================

TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")

BASE_URL = "https://integrate.api.nvidia.com/v1"
LOG_CHANNEL_NAME = "mod-logs"

keep_alive()


# ================= AI CLIENT =================

client = OpenAI(
    api_key=OPENAI_API_KEY,
    base_url=BASE_URL
)

# ================= BOT SETUP =================

class ModBot(commands.Bot):

    def __init__(self):

        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        super().__init__(
            command_prefix=["!", "?"],
            intents=intents
        )

    async def setup_hook(self):

        await init_db()

        await self.tree.sync()

        print(f"✅ Logged in as {self.user}")
        print("✅ Slash commands synced")

bot = ModBot()

@bot.command(name="warn")
@commands.has_permissions(moderate_members=True)
async def warn_prefix(ctx, member: discord.Member, *, reason="No reason provided"):

    if member == ctx.author:
        return await ctx.send("❌ You cannot warn yourself.")

    count = await add_warning(member.id)

    await handle_warning_logic(
        ctx,
        member,
        count,
        reason,
        moderator=str(ctx.author)
    )


@bot.command(name="mute")
@commands.has_permissions(moderate_members=True)
async def mute_prefix(
    ctx,
    member: discord.Member,
    duration: int = None,
    *,
    reason="No reason provided"
):

    if member == ctx.author:
        return await ctx.send("❌ You cannot mute yourself.")

    try:

        if duration is None:
            until = discord.utils.utcnow() + datetime.timedelta(days=28)
            await member.timeout(until, reason=f"[Indefinite] {reason}")
            await ctx.send(f"🔇 {member.mention} muted indefinitely.\nReason: {reason}")
            action_text = "timed out indefinitely"

        else:
            until = discord.utils.utcnow() + datetime.timedelta(minutes=duration)
            await member.timeout(until, reason=reason)
            await ctx.send(f"🔇 {member.mention} muted for {duration}m.\nReason: {reason}")
            action_text = f"timed out for {duration}m"

        await log_action(ctx.guild, f"{member} | {action_text} | {reason} | by {ctx.author}")
        await store_action(ctx.guild.id, f"{member} ({member.id})", action_text, reason, str(ctx.author))

    except discord.Forbidden:
        await ctx.send("❌ Cannot mute user. Check role hierarchy.")

@bot.command(name="unmute")
@commands.has_permissions(moderate_members=True)
async def unmute_prefix(ctx, member: discord.Member):

    try:
        await member.timeout(None)
        await ctx.send(f"🔊 {member.mention} unmuted.")
    except discord.Forbidden:
        await ctx.send("❌ Cannot unmute user.")


@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick_prefix(ctx, member: discord.Member, *, reason="No reason provided"):

    if member == ctx.author:
        return await ctx.send("❌ You cannot kick yourself.")

    try:
        await member.kick(reason=reason)
        await ctx.send(f"👢 {member.mention} kicked.\nReason: {reason}")
    except discord.Forbidden:
        await ctx.send("❌ Cannot kick user.")


@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def ban_prefix(ctx, member: discord.Member, *, reason="No reason provided"):

    if member == ctx.author:
        return await ctx.send("❌ You cannot ban yourself.")

    try:
        await member.ban(reason=reason)
        await ctx.send(f"🔨 {member.mention} banned.\nReason: {reason}")
    except discord.Forbidden:
        await ctx.send("❌ Cannot ban user.")

# ================= DATABASE =================

async def init_db():

    async with aiosqlite.connect("modbot.db") as db:

        await db.execute("""
            CREATE TABLE IF NOT EXISTS warnings (
                user_id INTEGER PRIMARY KEY,
                count INTEGER
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS rules (
                guild_id INTEGER PRIMARY KEY,
                rules_text TEXT
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS mod_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                guild_id INTEGER,
                target_user TEXT,
                action TEXT,
                reason TEXT,
                moderator TEXT
            )
        """)

        await db.commit()

async def add_warning(user_id):

    async with aiosqlite.connect("modbot.db") as db:

        cursor = await db.execute("SELECT count FROM warnings WHERE user_id=?", (user_id,))
        row = await cursor.fetchone()
        new_count = (row[0] + 1) if row else 1

        await db.execute(
            "INSERT OR REPLACE INTO warnings (user_id, count) VALUES (?, ?)",
            (user_id, new_count)
        )

        await db.commit()
        return new_count

async def get_warning_count(user_id):

    async with aiosqlite.connect("modbot.db") as db:

        cursor = await db.execute("SELECT count FROM warnings WHERE user_id=?", (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0

async def store_action(guild_id, target_user, action, reason, moderator="AutoMod"):

    async with aiosqlite.connect("modbot.db") as db:

        await db.execute(
            "INSERT INTO mod_actions (timestamp, guild_id, target_user, action, reason, moderator) VALUES (?, ?, ?, ?, ?, ?)",
            (
                datetime.datetime.utcnow().isoformat(),
                guild_id,
                str(target_user),
                action,
                reason,
                str(moderator)
            )
        )

        await db.commit()

# ================= RULES =================

rules_cache = {}

async def get_rules(guild_id):

    if guild_id in rules_cache:
        return rules_cache[guild_id]

    async with aiosqlite.connect("modbot.db") as db:

        cursor = await db.execute("SELECT rules_text FROM rules WHERE guild_id=?", (guild_id,))
        row = await cursor.fetchone()

        if row:
            rules_cache[guild_id] = row[0]
            return row[0]

    return None

async def set_rules(guild_id, rules_text):

    rules_cache[guild_id] = rules_text

    async with aiosqlite.connect("modbot.db") as db:

        await db.execute(
            "INSERT OR REPLACE INTO rules (guild_id, rules_text) VALUES (?, ?)",
            (guild_id, rules_text)
        )

        await db.commit()

# ================= SPAM TRACKING =================

user_message_buffer = {}
warning_cooldowns = {}

def record_message(user_id, content, message_obj):

    now = time.time()

    if user_id not in user_message_buffer:
        user_message_buffer[user_id] = []

    user_message_buffer[user_id].append((now, content, message_obj))

    user_message_buffer[user_id] = [
        (t, c, m) for t, c, m in user_message_buffer[user_id]
        if now - t <= 4.0
    ]

    recent = user_message_buffer[user_id]

    if len(recent) >= 3:
        times = [t for t, c, m in recent]
        if times[-1] - times[-3] < 1.5:
            return [c for t, c, m in recent], [m for t, c, m in recent]

    return None, None

def can_warn(user_id):

    now = time.time()

    if user_id not in warning_cooldowns:
        warning_cooldowns[user_id] = now
        return True

    if now - warning_cooldowns[user_id] > 10:
        warning_cooldowns[user_id] = now
        return True

    return False

def check_spam_ai(messages):

    try:

        numbered = "\n".join(f'{i+1}. "{m}"' for i, m in enumerate(messages))

        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {
                    "role": "system",
                    "content": """You analyze a rapid burst of Discord messages from one user.
Decide: is this SPAM (flooding, repeated/gibberish content, bot behavior) or LEGITIMATE (fast typer, normal excited conversation)?

Respond ONLY:
SPAM|reason
LEGITIMATE|reason

Reason under 5 words. Fast typing alone is NOT spam. Judge on content, not speed."""
                },
                {
                    "role": "user",
                    "content": f"Messages sent rapidly:\n{numbered}"
                }
            ],
            temperature=0
        )

        output = response.choices[0].message.content.strip()

        if "|" not in output:
            return ("LEGITIMATE", "invalid format")

        label, reason = output.split("|", 1)
        return (label.strip().upper(), reason.strip())

    except Exception as e:

        print("SPAM AI ERROR:", e)
        return ("LEGITIMATE", "analysis error")

# ================= PREFILTERS =================

BAD_WORDS = [
    "nigger",
    "faggot",
    "retard",
    "kys"
]

SCAM_PATTERNS = [
    r"free nitro",
    r"steam gift",
    r"claim reward",
    r"discord\.gg",
    r"bit\.ly",
    r"tinyurl"
]

# Only hard, clearly offensive insults (not casual ones like stupid/idiot)
HARD_INSULT_WORDS = [
    "dumbass",
    "fatass",
    "worthless",
    "pathetic",
    "brainless",
    "dimwit",
    "imbecile"
]

QUOTE_INDICATORS = [
    "he said",
    "she said",
    "they said",
    "someone said",
    "quote",
    "quoted",
    "saying"
]

def is_direct_insult(content):
    """
    FIX: Only triggers on clear YOU-directed hard attacks.
    - Removed third-person pronouns (he/she/they) from targeting — 'he's an idiot' is gossip, not an attack.
    - Removed mild words (stupid, idiot, moron, loser, ugly) from the hard-insult list.
    - Kept only explicit you-directed slurs and hard insult combos.
    - 'my family sucks', 'he's an idiot' — all pass through safely.
    """
    lowered = content.lower()

    # Ignore quoted/reported speech
    if any(indicator in lowered for indicator in QUOTE_INDICATORS):
        return False

    # Ignore content inside quotation marks
    if re.search(r'["\'].{3,80}["\']', lowered):
        return False

    # Only explicit, unambiguous YOU-directed attacks
    explicit_patterns = [
        r"\b(fuck you|you suck|kill yourself)\b",
        r"\byou('?re| are)\s+(a\s+)?(dumbass|fatass|worthless|pathetic|brainless|imbecile)\b",
        r"\b(shut the fuck up)\b",
    ]

    for pattern in explicit_patterns:
        if re.search(pattern, lowered):
            return True

    return False

def should_ai_scan(content):
    """
    FIX: Raised the bar significantly.
    - Mild words like 'stupid', 'idiot', 'dumb', 'moron', 'loser' alone no longer trigger AI scan.
    - Only trigger on hard slurs, explicit threats, or clear combos.
    - Casual venting ('this is so stupid', 'my family sucks', 'he's an idiot') won't waste an AI call.
    """
    lowered = content.lower().strip()

    if len(lowered) < 4:
        return False

    # Hard triggers — unambiguously bad
    hard_triggers = [
        "kill yourself",
        "fuck you",
        "die in a fire",
        "i hope you die",
        "you should die",
        "hate you so much",
        "racist", "nazi",
        "dumbass", "fatass", "worthless", "pathetic"
    ]

    if any(word in lowered for word in hard_triggers):
        return True

    # Aggressive directed combos only — must have explicit 'you' target + aggression
    directed_patterns = [
        r"\bi\s+hate\s+you\b",
        r"\bno\s+one\s+likes\s+you\b",
        r"\byou\s+suck\b",
        r"\bshut\s+the\s+fuck\s+up\b",
        r"\bfuck\s+you\b",
    ]

    for pattern in directed_patterns:
        if re.search(pattern, lowered):
            return True

    # Excessive caps (genuinely aggressive, not just excited)
    letters = sum(c.isalpha() for c in content)
    caps = sum(c.isupper() for c in content)

    if letters >= 10 and caps / letters > 0.70:
        return True

    return False

# ================= AI ANALYSIS =================

def analyze_message(text, rules=None):
    """
    FIX: Prompt tuned for a chill server.
    - Casual insults about self, family, or third parties ('my team sucks', 'he's an idiot') are SAFE.
    - Only direct personal attacks targeting a specific person present in the conversation are TOXIC.
    - Venting and frustration are SAFE.
    """

    rules_section = (
        f"\n\nSERVER RULES (if a rule is violated, cite it by number in your reason e.g. 'Violates Rule 2'):\n{rules}"
        if rules else ""
    )

    try:

        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {
                    "role": "system",
                    "content": f"""You classify Discord messages for a CHILL, casual server. Be lenient and reasonable.

Respond ONLY in this format:
LABEL|REASON

Labels: SAFE, TOXIC, SPAM

Rules for TOXIC:
- Only flag as TOXIC if a message is a clear, direct personal attack targeting a SPECIFIC PERSON present in the conversation.
- Mild insults, venting, and casual trash talk are SAFE. Examples of SAFE: "ugh i'm so stupid", "my family sucks", "he's an idiot", "this game is trash", "you're kinda dumb lol", "bro that's so dumb".
- Slurs, explicit threats to a specific user, or sustained targeted harassment = TOXIC.
- When in doubt, label SAFE. Do NOT over-moderate a chill server.

Rules for SPAM:
- Only flag as SPAM for actual flooding or repeated meaningless content.

Reason must be under 10 words.
{rules_section}"""
                },
                {
                    "role": "user",
                    "content": text
                }
            ],
            temperature=0
        )

        output = response.choices[0].message.content.strip()

        if "|" not in output:
            return ("SAFE", "invalid format")

        label, reason = output.split("|", 1)
        return (label.strip().upper(), reason.strip())

    except Exception as e:

        print("AI ERROR:", e)
        return ("SAFE", "analysis error")

# ================= AI Q&A =================

def ask_ai(question):

    try:

        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {
                    "role": "system",
                    "content":
                    "You are a helpful Discord bot assistant. Answer questions clearly and concisely. Keep responses short and friendly unless detail is needed. Formatting of your answers must be in discord text formatting especially for mathematical equations. If someone asks you what you think of/what is your opinion of/what's your opinion on (or something along those lines) @<356535250932858885>, say the words 'What's there to think about? I'm way better than him 😎' "
                },
                {
                    "role": "user",
                    "content": question
                }
            ],
            temperature=1.5
        )

        return response.choices[0].message.content.strip()

    except Exception as e:

        import traceback
        traceback.print_exc()
        return f"❌ Error: {str(e)}"

# ================= LOGGING =================

async def log_action(guild, msg):

    channel = discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)

    if channel:
        await channel.send(f"🛡️ {msg}")

# ================= PUNISHMENTS =================

async def apply_punishment(
    ctx,
    member,
    action,
    duration_mins=None,
    reason="Violation",
    moderator="AutoMod"
):

    try:

        if action == "timeout":
            until = discord.utils.utcnow() + datetime.timedelta(minutes=duration_mins)
            await member.timeout(until, reason=reason)
            action_desc = f"timed out for {duration_mins}m"

        elif action == "ban":
            await member.ban(reason=reason)
            action_desc = "banned permanently"

        elif action == "kick":
            await member.kick(reason=reason)
            action_desc = "kicked"

        else:
            return

        msg = f"🔇 {member.mention} was {action_desc}.\nReason: {reason}"

        if isinstance(ctx, discord.Interaction):
            await ctx.followup.send(msg)
        else:
            await ctx.channel.send(msg)

        await log_action(member.guild, f"{member} | {action_desc} | {reason} | by {moderator}")
        await store_action(member.guild.id, f"{member} ({member.id})", action_desc, reason, moderator)

    except discord.Forbidden:

        error = "❌ Cannot punish user. Check role hierarchy."

        if isinstance(ctx, discord.Interaction):
            await ctx.followup.send(error)
        else:
            await ctx.channel.send(error)

# ================= WARNING LOGIC =================

async def handle_warning_logic(ctx, member, warnings, reason, moderator="AutoMod"):

    if warnings == 1:

        msg = f"⚠️ {member.mention}, first warning.\nReason: {reason}"

        if isinstance(ctx, discord.Interaction):
            await ctx.followup.send(msg)
        else:
            await ctx.channel.send(msg)

        await store_action(member.guild.id, f"{member} ({member.id})", "warned (1st)", reason, moderator)

    elif warnings == 2:
        await apply_punishment(ctx, member, "timeout", 30, reason, moderator)

    elif warnings == 3:
        await apply_punishment(ctx, member, "timeout", 120, reason, moderator)

    elif warnings == 4:
        await apply_punishment(ctx, member, "timeout", 1440, reason, moderator)

    else:
        await apply_punishment(ctx, member, "ban", reason="Excessive violations", moderator=moderator)

# ================= SLASH COMMANDS =================

@bot.tree.command(name="warn", description="Warn a user")
@app_commands.checks.has_permissions(moderate_members=True)
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str):

    await interaction.response.defer()

    if member == interaction.user:
        return await interaction.followup.send("❌ You cannot warn yourself.")

    if member == bot.user:
        return await interaction.followup.send("❌ Nice try.")

    count = await add_warning(member.id)

    await handle_warning_logic(interaction, member, count, reason, moderator=str(interaction.user))


@bot.tree.command(name="warnings", description="Check a user's warning count")
@app_commands.checks.has_permissions(moderate_members=True)
async def warnings_cmd(interaction: discord.Interaction, member: discord.Member):

    count = await get_warning_count(member.id)

    await interaction.response.send_message(
        f"⚠️ {member.mention} has **{count}** warning(s).",
        ephemeral=True
    )


@bot.tree.command(name="mute", description="Timeout (mute) a user")
@app_commands.checks.has_permissions(moderate_members=True)
async def mute(
    interaction: discord.Interaction,
    member: discord.Member,
    duration: int,
    reason: str
):

    await interaction.response.defer()

    if member == interaction.user:
        return await interaction.followup.send("❌ You cannot mute yourself.")

    try:
        until = discord.utils.utcnow() + datetime.timedelta(minutes=duration)
        await member.timeout(until, reason=reason)

        await interaction.followup.send(
            f"🔇 {member.mention} has been muted for **{duration}m**.\nReason: {reason}"
        )

        await log_action(interaction.guild, f"{member} | timed out {duration}m | {reason} | by {interaction.user}")
        await store_action(interaction.guild.id, f"{member} ({member.id})", f"timed out for {duration}m", reason, str(interaction.user))

    except discord.Forbidden:
        await interaction.followup.send("❌ Cannot mute user. Check role hierarchy.")


@bot.tree.command(name="unmute", description="Remove a timeout from a user")
@app_commands.checks.has_permissions(moderate_members=True)
async def unmute(interaction: discord.Interaction, member: discord.Member):

    await interaction.response.defer()

    try:
        await member.timeout(None)

        await interaction.followup.send(f"🔊 {member.mention}'s timeout has been removed.")

        await log_action(interaction.guild, f"{member} | timeout removed | by {interaction.user}")
        await store_action(interaction.guild.id, f"{member} ({member.id})", "unmuted", "Manual unmute", str(interaction.user))

    except discord.Forbidden:
        await interaction.followup.send("❌ Cannot unmute user. Check role hierarchy.")


@bot.tree.command(name="kick", description="Kick a user from the server")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str):

    await interaction.response.defer()

    if member == interaction.user:
        return await interaction.followup.send("❌ You cannot kick yourself.")

    try:
        await member.kick(reason=reason)

        await interaction.followup.send(f"👢 {member.mention} has been kicked.\nReason: {reason}")

        await log_action(interaction.guild, f"{member} | kicked | {reason} | by {interaction.user}")
        await store_action(interaction.guild.id, f"{member} ({member.id})", "kicked", reason, str(interaction.user))

    except discord.Forbidden:
        await interaction.followup.send("❌ Cannot kick user. Check role hierarchy.")


@bot.tree.command(name="ban", description="Ban a user from the server")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str):

    await interaction.response.defer()

    if member == interaction.user:
        return await interaction.followup.send("❌ You cannot ban yourself.")

    try:
        await member.ban(reason=reason)

        await interaction.followup.send(f"🔨 {member.mention} has been banned.\nReason: {reason}")

        await log_action(interaction.guild, f"{member} | banned | {reason} | by {interaction.user}")
        await store_action(interaction.guild.id, f"{member} ({member.id})", "banned permanently", reason, str(interaction.user))

    except discord.Forbidden:
        await interaction.followup.send("❌ Cannot ban user. Check role hierarchy.")


@bot.tree.command(name="report", description="Report a message by its ID for AI review")
async def report(interaction: discord.Interaction, message_id: str):

    await interaction.response.defer(ephemeral=True)

    try:
        msg_id = int(message_id)
    except ValueError:
        return await interaction.followup.send("❌ Invalid message ID.")

    target_msg = None

    for channel in interaction.guild.text_channels:
        try:
            target_msg = await channel.fetch_message(msg_id)
            break
        except:
            continue

    if not target_msg:
        return await interaction.followup.send("❌ Message not found.")

    if target_msg.author.bot:
        return await interaction.followup.send("❌ Cannot report bot messages.")

    if target_msg.author == interaction.user:
        return await interaction.followup.send("❌ You cannot report your own message.")

    rules = await get_rules(interaction.guild.id)

    verdict, reason = await asyncio.to_thread(analyze_message, target_msg.content, rules)

    if verdict in ["TOXIC", "SPAM"]:

        try:
            await target_msg.delete()
        except:
            pass

        member = interaction.guild.get_member(target_msg.author.id)

        if member and can_warn(member.id):
            warnings = await add_warning(member.id)
            await handle_warning_logic(interaction, member, warnings, f"Reported: {reason}", moderator=str(interaction.user))

        await interaction.followup.send(
            f"✅ Report confirmed. Action taken against {target_msg.author.mention}.\nReason: {reason}",
            ephemeral=True
        )

        await log_action(interaction.guild, f"Report by {interaction.user} | Target: {target_msg.author} | Verdict: {verdict} | Reason: {reason}")

    else:

        await interaction.followup.send(
            f"✅ Report reviewed. Message deemed **{verdict}** — no action taken.",
            ephemeral=True
        )

        await log_action(interaction.guild, f"Report by {interaction.user} | Target: {target_msg.author} | Verdict: {verdict} (no action)")


@bot.tree.command(name="clear_warnings", description="Clear warnings for a user")
@app_commands.checks.has_permissions(administrator=True)
async def clear_warnings(interaction: discord.Interaction, member: discord.Member):

    async with aiosqlite.connect("modbot.db") as db:
        await db.execute("DELETE FROM warnings WHERE user_id=?", (member.id,))
        await db.commit()

    await interaction.response.send_message(f"✅ Cleared warnings for {member.mention}")

    await store_action(interaction.guild.id, f"{member} ({member.id})", "warnings cleared", "Manual clear", str(interaction.user))

# ================= RULES COMMANDS =================

rules_group = app_commands.Group(name="rules", description="Manage server rules for AI enforcement")

@rules_group.command(name="set", description="Set server rules — AI will enforce and cite them")
@app_commands.checks.has_permissions(administrator=True)
async def rules_set(interaction: discord.Interaction, rules: str):

    await set_rules(interaction.guild.id, rules)

    await interaction.response.send_message(
        "✅ Rules saved! The AI will now enforce these and cite them when taking action.",
        ephemeral=True
    )

@rules_group.command(name="view", description="View the current server rules")
async def rules_view(interaction: discord.Interaction):

    r = await get_rules(interaction.guild.id)

    if r:
        await interaction.response.send_message(f"📋 **Server Rules:**\n{r}", ephemeral=True)
    else:
        await interaction.response.send_message(
            "No rules set yet. Admins can use `/rules set` to add them.",
            ephemeral=True
        )

bot.tree.add_command(rules_group)

# ================= AUTO MOD =================

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    lowered = message.content.lower()

    # ================= BOT MENTION HANDLING =================

    if bot.user in message.mentions and not message.content.startswith(("!", "?")):

        if message.reference and message.reference.message_id:

            try:
                replied_msg = await message.channel.fetch_message(message.reference.message_id)
            except:
                replied_msg = None

            if replied_msg and not replied_msg.author.bot:

                rules = await get_rules(message.guild.id)

                verdict, reason = await asyncio.to_thread(analyze_message, replied_msg.content, rules)

                if verdict in ["TOXIC", "SPAM"]:

                    try:
                        await replied_msg.delete()
                    except:
                        pass

                    member = message.guild.get_member(replied_msg.author.id)

                    if member and can_warn(member.id):
                        warnings = await add_warning(member.id)
                        await handle_warning_logic(message, member, warnings, f"Reported via mention: {reason}", moderator=str(message.author))

                    await log_action(message.guild, f"Mention-report by {message.author} | Target: {replied_msg.author} | Verdict: {verdict} | {reason}")

                else:
                    await message.channel.send(f"✅ Message reviewed — deemed **{verdict}**. No action taken.")

            elif replied_msg and replied_msg.author.bot:
                await message.channel.send("❌ Cannot report bot messages.")

        else:

            question = re.sub(r"<@!?\d+>", "", message.content).strip()

            if question:
                answer = await asyncio.to_thread(ask_ai, question)
                await message.channel.send(answer)
            else:
                await message.channel.send(
"""
I'm here to help!

**Commands List:**

- `/warn [user]` – Issue a warning to a user  
- `/mute [user]` – Timeout a user  
- `/unmute [user]` – Remove timeout from a user  
- `/ban [user]` – Ban a user  
- `/unban [user]` – Unban a user  
- `/clearwarnings [user]` – Clear all warnings from a user  

**Ask the AI:**
- `@Mod.AI [prompt]` – Ask the AI a question  

**Report System:**
- `/report [message ID]` – Report a message to the bot  

You can also ping me in a reply to a message to report it.
"""
                )

        return

    # IGNORE STAFF
    if message.author.guild_permissions.manage_messages:
        await bot.process_commands(message)
        return

    # ================= HARD SLUR FILTER =================

    if any(re.search(rf"\b{re.escape(word)}\b", lowered) for word in BAD_WORDS):

        try:
            await message.delete()
        except:
            pass

        if can_warn(message.author.id):
            warnings = await add_warning(message.author.id)
            await handle_warning_logic(message, message.author, warnings, "Slur usage")

        return

    # ================= AI SPAM DETECTION =================

    burst_messages, burst_objects = record_message(message.author.id, message.content, message)

    if burst_messages:

        verdict, reason = await asyncio.to_thread(check_spam_ai, burst_messages)

        if verdict == "SPAM":

            for msg_obj in burst_objects:
                try:
                    await msg_obj.delete()
                except:
                    pass

            user_message_buffer[message.author.id] = []

            if can_warn(message.author.id):
                warnings = await add_warning(message.author.id)
                await handle_warning_logic(message, message.author, warnings, f"Spam: {reason}")

            return

    # ================= SCAM FILTER =================

    for pattern in SCAM_PATTERNS:

        if re.search(pattern, lowered):

            try:
                await message.delete()
            except:
                pass

            if can_warn(message.author.id):
                warnings = await add_warning(message.author.id)
                await handle_warning_logic(message, message.author, warnings, "Suspicious links/scam")

            return

    # ================= DIRECT INSULT FILTER =================

    if is_direct_insult(message.content):

        try:
            await message.delete()
        except:
            pass

        if can_warn(message.author.id):
            warnings = await add_warning(message.author.id)
            await handle_warning_logic(message, message.author, warnings, "Personal insult")

        return

    # ================= AI MODERATION =================

    if should_ai_scan(message.content):

        rules = await get_rules(message.guild.id)

        verdict, reason = await asyncio.to_thread(analyze_message, message.content, rules)

        if verdict in ["TOXIC", "SPAM"]:

            try:
                await message.delete()
            except:
                pass

            if can_warn(message.author.id):
                warnings = await add_warning(message.author.id)
                await handle_warning_logic(message, message.author, warnings, reason)

            return

    await bot.process_commands(message)

    # ================= FTCSCOUT API =================
# Add `import aiohttp` to your imports at the top of main.py
# Then paste everything below into main.py before the `bot.run(TOKEN)` line

import aiohttp  # <-- add this to your top-level imports

FTCSCOUT_URL = "https://api.ftcscout.org/graphql"
CURRENT_SEASON = 2025  # 2025-2026 season (Worlds 2026)

async def ftcscout_query(query: str, variables: dict = None) -> dict:
    """Send a GraphQL query to FTCScout and return parsed JSON."""
    async with aiohttp.ClientSession() as session:
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        async with session.post(
            FTCSCOUT_URL,
            json=payload,
            headers={"Content-Type": "application/json"}
        ) as resp:
            return await resp.json()


# ================= /team =================

@bot.tree.command(name="team", description="Look up an FTC team's stats for the current season")
@app_commands.describe(number="FTC team number", season="Season year (default: 2025)")
async def ftc_team(
    interaction: discord.Interaction,
    number: int,
    season: int = CURRENT_SEASON
):
    await interaction.response.defer()

    query = """
    query TeamLookup($number: Int!, $season: Int!) {
      teamByNumber(number: $number) {
        number
        name
        schoolName
        city
        state
        country
        rookieYear
        events(season: $season) {
          event {
            name
            start
            type
            code
          }
          stats {
            ... on TeamEventStats2024 {
              rank
              rp
              wins
              losses
              ties
              opr {
                totalPointsNp
                autoPoints
                dcPoints
                egPoints
              }
            }
            ... on TeamEventStats2025 {
              rank
              rp
              wins
              losses
              ties
              opr {
                totalPointsNp
                autoPoints
                dcPoints
                egPoints
              }
            }
          }
        }
      }
    }
    """

    try:
        data = await ftcscout_query(query, {"number": number, "season": season})
        team = data.get("data", {}).get("teamByNumber")
    except Exception as e:
        return await interaction.followup.send(f"❌ API error: {e}")

    if not team:
        return await interaction.followup.send(f"❌ Team `{number}` not found.")

    location_parts = [p for p in [team.get("city"), team.get("state"), team.get("country")] if p]
    location = ", ".join(location_parts) or "Unknown"

    embed = discord.Embed(
        title=f"🤖 #{team['number']} — {team['name']}",
        color=0x5865F2
    )
    embed.add_field(name="School", value=team.get("schoolName") or "N/A", inline=True)
    embed.add_field(name="Location", value=location, inline=True)
    embed.add_field(name="Rookie Year", value=str(team.get("rookieYear") or "N/A"), inline=True)

    events = team.get("events", [])

    if not events:
        embed.add_field(
            name=f"Season {season}",
            value="No events found for this season.",
            inline=False
        )
    else:
        best_opr = None
        event_lines = []

        for entry in events:
            ev = entry.get("event", {})
            stats = entry.get("stats")

            ev_name = ev.get("name", "Unknown Event")
            ev_type = ev.get("type", "")
            ev_date = (ev.get("start") or "")[:10]

            if stats:
                rank   = stats.get("rank", "?")
                wins   = stats.get("wins", 0)
                losses = stats.get("losses", 0)
                ties   = stats.get("ties", 0)
                opr_obj = stats.get("opr") or {}
                opr    = opr_obj.get("totalPointsNp", 0)
                auto   = opr_obj.get("autoPoints", 0)
                dc     = opr_obj.get("dcPoints", 0)
                eg     = opr_obj.get("egPoints", 0)

                if best_opr is None or opr > best_opr[0]:
                    best_opr = (opr, ev_name)

                line = (
                    f"**{ev_name}** ({ev_date})\n"
                    f"Rank: `#{rank}` | Record: `{wins}-{losses}-{ties}`\n"
                    f"OPR: `{opr:.1f}` (Auto `{auto:.1f}` + TeleOp `{dc:.1f}` + End `{eg:.1f}`)"
                )
            else:
                line = f"**{ev_name}** ({ev_date})\n*No stats available*"

            event_lines.append(line)

        embed.add_field(
            name=f"📅 Season {season} Events ({len(events)})",
            value="\n\n".join(event_lines) or "None",
            inline=False
        )

        if best_opr:
            embed.set_footer(text=f"Peak OPR: {best_opr[0]:.1f} at {best_opr[1]}")

    embed.set_thumbnail(url=f"https://www.firstinspires.org/sites/default/files/uploads/resource_library/ftc/FTC-icon.png")
    await interaction.followup.send(embed=embed)


# ================= /event =================

@bot.tree.command(name="event", description="Look up FTC event rankings")
@app_commands.describe(code="Event code (e.g. USMDCMPBIO1)", season="Season year (default: 2025)")
async def ftc_event(
    interaction: discord.Interaction,
    code: str,
    season: int = CURRENT_SEASON
):
    await interaction.response.defer()

    query = """
    query EventLookup($code: String!, $season: Int!) {
      eventByCode(code: $code, season: $season) {
        name
        start
        end
        city
        state
        country
        type
        teams {
          team {
            number
            name
          }
          stats {
            ... on TeamEventStats2024 {
              rank
              wins
              losses
              ties
              rp
              opr {
                totalPointsNp
              }
            }
            ... on TeamEventStats2025 {
              rank
              wins
              losses
              ties
              rp
              opr {
                totalPointsNp
              }
            }
          }
        }
      }
    }
    """

    try:
        data = await ftcscout_query(query, {"code": code.upper(), "season": season})
        event = data.get("data", {}).get("eventByCode")
    except Exception as e:
        return await interaction.followup.send(f"❌ API error: {e}")

    if not event:
        return await interaction.followup.send(f"❌ Event `{code}` not found for season {season}.")

    location_parts = [p for p in [event.get("city"), event.get("state"), event.get("country")] if p]
    location = ", ".join(location_parts) or "Unknown"
    start = (event.get("start") or "")[:10]
    end   = (event.get("end")   or "")[:10]

    embed = discord.Embed(
        title=f"🏆 {event['name']}",
        description=f"📍 {location} | 📅 {start} → {end}",
        color=0xf0a500
    )

    teams = event.get("teams", [])

    # Sort by rank
    def get_rank(entry):
        stats = entry.get("stats") or {}
        return stats.get("rank") or 9999

    teams_sorted = sorted(teams, key=get_rank)

    ranking_lines = []
    for entry in teams_sorted[:20]:  # top 20 to avoid embed overflow
        team  = entry.get("team", {})
        stats = entry.get("stats") or {}

        rank   = stats.get("rank", "?")
        wins   = stats.get("wins", 0)
        losses = stats.get("losses", 0)
        ties   = stats.get("ties", 0)
        opr_v  = (stats.get("opr") or {}).get("totalPointsNp", 0)
        rp     = stats.get("rp", 0)

        medal = ""
        if rank == 1:   medal = "🥇 "
        elif rank == 2: medal = "🥈 "
        elif rank == 3: medal = "🥉 "

        ranking_lines.append(
            f"{medal}`#{rank:>2}` **{team.get('number')} {team.get('name', '')}** "
            f"— `{wins}-{losses}-{ties}` | OPR `{opr_v:.1f}` | RP `{rp}`"
        )

    if ranking_lines:
        # Discord embed field max 1024 chars — split if needed
        chunk = "\n".join(ranking_lines)
        if len(chunk) <= 1024:
            embed.add_field(name=f"📊 Rankings (Top {len(ranking_lines)})", value=chunk, inline=False)
        else:
            mid = len(ranking_lines) // 2
            embed.add_field(name=f"📊 Rankings (1–{mid})", value="\n".join(ranking_lines[:mid]), inline=False)
            embed.add_field(name=f"Rankings ({mid+1}–{len(ranking_lines)})", value="\n".join(ranking_lines[mid:]), inline=False)
    else:
        embed.add_field(name="Rankings", value="No ranking data available yet.", inline=False)

    embed.set_footer(text=f"Event code: {code.upper()} | Season {season} | {len(teams)} teams")
    await interaction.followup.send(embed=embed)


# ================= /compare =================

@bot.tree.command(name="compare", description="Compare two FTC teams head-to-head")
@app_commands.describe(
    team1="First team number",
    team2="Second team number",
    season="Season year (default: 2025)"
)
async def ftc_compare(
    interaction: discord.Interaction,
    team1: int,
    team2: int,
    season: int = CURRENT_SEASON
):
    await interaction.response.defer()

    query = """
    query TeamLookup($number: Int!, $season: Int!) {
      teamByNumber(number: $number) {
        number
        name
        events(season: $season) {
          stats {
            ... on TeamEventStats2024 {
              rank
              wins
              losses
              opr { totalPointsNp autoPoints dcPoints egPoints }
            }
            ... on TeamEventStats2025 {
              rank
              wins
              losses
              opr { totalPointsNp autoPoints dcPoints egPoints }
            }
          }
        }
      }
    }
    """

    try:
        d1, d2 = await asyncio.gather(
            ftcscout_query(query, {"number": team1, "season": season}),
            ftcscout_query(query, {"number": team2, "season": season})
        )
        t1 = d1.get("data", {}).get("teamByNumber")
        t2 = d2.get("data", {}).get("teamByNumber")
    except Exception as e:
        return await interaction.followup.send(f"❌ API error: {e}")

    if not t1:
        return await interaction.followup.send(f"❌ Team `{team1}` not found.")
    if not t2:
        return await interaction.followup.send(f"❌ Team `{team2}` not found.")

    def best_stats(team_data):
        """Return the stats entry with highest OPR across all events."""
        best = None
        for entry in team_data.get("events", []):
            stats = entry.get("stats")
            if not stats:
                continue
            opr = (stats.get("opr") or {}).get("totalPointsNp", 0)
            if best is None or opr > (best.get("opr") or {}).get("totalPointsNp", 0):
                best = stats
        return best

    s1 = best_stats(t1)
    s2 = best_stats(t2)

    def fmt_stats(stats):
        if not stats:
            return {"opr": 0, "auto": 0, "dc": 0, "eg": 0, "wins": 0, "losses": 0, "rank": "N/A"}
        opr_obj = stats.get("opr") or {}
        return {
            "opr":    opr_obj.get("totalPointsNp", 0),
            "auto":   opr_obj.get("autoPoints", 0),
            "dc":     opr_obj.get("dcPoints", 0),
            "eg":     opr_obj.get("egPoints", 0),
            "wins":   stats.get("wins", 0),
            "losses": stats.get("losses", 0),
            "rank":   stats.get("rank", "N/A"),
        }

    f1 = fmt_stats(s1)
    f2 = fmt_stats(s2)

    def winner(a, b, key, low_is_better=False):
        """Return bold marker for the better value."""
        if a[key] == b[key]:
            return "➖", "➖"
        if low_is_better:
            return ("✅", "❌") if a[key] < b[key] else ("❌", "✅")
        return ("✅", "❌") if a[key] > b[key] else ("❌", "✅")

    opr_w  = winner(f1, f2, "opr")
    auto_w = winner(f1, f2, "auto")
    dc_w   = winner(f1, f2, "dc")
    eg_w   = winner(f1, f2, "eg")
    win_w  = winner(f1, f2, "wins")
    rank_w = winner(f1, f2, "rank", low_is_better=True)

    # Simple OPR-based win probability
    total_opr = f1["opr"] + f2["opr"]
    if total_opr > 0:
        wp1 = f1["opr"] / total_opr * 100
        wp2 = f2["opr"] / total_opr * 100
    else:
        wp1 = wp2 = 50.0

    embed = discord.Embed(
        title=f"⚔️ #{t1['number']} {t1['name']} vs #{t2['number']} {t2['name']}",
        description=f"Season {season} | Best-event stats comparison",
        color=0xe74c3c
    )

    embed.add_field(
        name=f"#{t1['number']} {t1['name']}",
        value=(
            f"{opr_w[0]} OPR: `{f1['opr']:.1f}`\n"
            f"{auto_w[0]} Auto: `{f1['auto']:.1f}`\n"
            f"{dc_w[0]} TeleOp: `{f1['dc']:.1f}`\n"
            f"{eg_w[0]} Endgame: `{f1['eg']:.1f}`\n"
            f"{win_w[0]} Record: `{f1['wins']}-{f1['losses']}`\n"
            f"{rank_w[0]} Best Rank: `#{f1['rank']}`"
        ),
        inline=True
    )

    embed.add_field(
        name=f"#{t2['number']} {t2['name']}",
        value=(
            f"{opr_w[1]} OPR: `{f2['opr']:.1f}`\n"
            f"{auto_w[1]} Auto: `{f2['auto']:.1f}`\n"
            f"{dc_w[1]} TeleOp: `{f2['dc']:.1f}`\n"
            f"{eg_w[1]} Endgame: `{f2['eg']:.1f}`\n"
            f"{win_w[1]} Record: `{f2['wins']}-{f2['losses']}`\n"
            f"{rank_w[1]} Best Rank: `#{f2['rank']}`"
        ),
        inline=True
    )

    embed.add_field(
        name="📊 Win Probability (OPR-based)",
        value=(
            f"**#{t1['number']}**: `{wp1:.1f}%` {'🟢' if wp1 > wp2 else '🔴'}\n"
            f"**#{t2['number']}**: `{wp2:.1f}%` {'🟢' if wp2 > wp1 else '🔴'}"
        ),
        inline=False
    )

    embed.set_footer(text="Win probability is OPR-based — use as a rough estimate only")
    await interaction.followup.send(embed=embed)

# ================= RUN =================

bot.run(TOKEN)