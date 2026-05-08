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

from flask import Flask, jsonify
from threading import Thread

# ================= FLASK DASHBOARD =================

app = Flask(__name__)

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Mod.AI Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg: #0d0f14;
            --surface: #13161e;
            --border: #1e2230;
            --accent: #5865f2;
            --accent2: #eb459e;
            --text: #c8ccd8;
            --muted: #555b70;
            --warn: #faa61a;
            --ban: #ed4245;
            --kick: #eb459e;
            --timeout: #5865f2;
            --safe: #3ba55c;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            background: var(--bg);
            color: var(--text);
            font-family: 'Space Mono', monospace;
            min-height: 100vh;
        }}
        .header {{
            background: var(--surface);
            border-bottom: 1px solid var(--border);
            padding: 20px 40px;
            display: flex;
            align-items: center;
            gap: 14px;
        }}
        .header h1 {{
            font-family: 'Syne', sans-serif;
            font-weight: 800;
            font-size: 1.6rem;
            color: #fff;
        }}
        .header .dot {{
            width: 10px; height: 10px;
            background: var(--safe);
            border-radius: 50%;
            box-shadow: 0 0 8px var(--safe);
            animation: pulse 2s infinite;
        }}
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.4; }}
        }}
        .container {{
            padding: 30px 40px;
            max-width: 1200px;
            margin: 0 auto;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
            margin-bottom: 36px;
        }}
        .stat-card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 20px;
        }}
        .stat-card .label {{
            font-size: 0.7rem;
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: 0.1em;
            margin-bottom: 8px;
        }}
        .stat-card .value {{
            font-family: 'Syne', sans-serif;
            font-size: 2rem;
            font-weight: 800;
            color: #fff;
        }}
        .section {{
            margin-bottom: 36px;
        }}
        .section-title {{
            font-family: 'Syne', sans-serif;
            font-size: 0.85rem;
            font-weight: 700;
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: 0.12em;
            margin-bottom: 14px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            overflow: hidden;
        }}
        th {{
            padding: 12px 16px;
            text-align: left;
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--muted);
            border-bottom: 1px solid var(--border);
        }}
        td {{
            padding: 11px 16px;
            font-size: 0.82rem;
            border-bottom: 1px solid var(--border);
        }}
        tr:last-child td {{
            border-bottom: none;
        }}
        tr:hover td {{
            background: rgba(255,255,255,0.02);
        }}
        .badge {{
            display: inline-block;
            padding: 2px 9px;
            border-radius: 4px;
            font-size: 0.72rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        .badge-warn {{
            background: rgba(250,166,26,0.15);
            color: var(--warn);
            border: 1px solid rgba(250,166,26,0.3);
        }}
        .badge-ban {{
            background: rgba(237,66,69,0.15);
            color: var(--ban);
            border: 1px solid rgba(237,66,69,0.3);
        }}
        .badge-kick {{
            background: rgba(235,69,158,0.15);
            color: var(--kick);
            border: 1px solid rgba(235,69,158,0.3);
        }}
        .badge-timeout {{
            background: rgba(88,101,242,0.15);
            color: var(--timeout);
            border: 1px solid rgba(88,101,242,0.3);
        }}
        .badge-automod {{
            background: rgba(58,165,92,0.15);
            color: var(--safe);
            border: 1px solid rgba(58,165,92,0.3);
        }}
        .warn-count {{
            display: inline-block;
            background: rgba(250,166,26,0.1);
            color: var(--warn);
            border: 1px solid rgba(250,166,26,0.25);
            border-radius: 4px;
            padding: 1px 8px;
            font-size: 0.8rem;
            font-weight: 700;
        }}
        .empty {{
            color: var(--muted);
            font-size: 0.85rem;
            padding: 20px 16px;
        }}
        .ts {{
            color: var(--muted);
            font-size: 0.75rem;
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="dot"></div>
        <h1>Mod.AI Dashboard</h1>
    </div>
    <div class="container">
        <div class="stats-grid">
            <div class="stat-card">
                <div class="label">Total Actions</div>
                <div class="value">{total_actions}</div>
            </div>
            <div class="stat-card">
                <div class="label">Warned Users</div>
                <div class="value">{warned_users}</div>
            </div>
            <div class="stat-card">
                <div class="label">Bans</div>
                <div class="value">{total_bans}</div>
            </div>
            <div class="stat-card">
                <div class="label">Timeouts</div>
                <div class="value">{total_timeouts}</div>
            </div>
        </div>

        <div class="section">
            <div class="section-title">Top Warned Users</div>
            <table>
                <tr><th>User ID</th><th>Warnings</th></tr>
                {warnings_rows}
            </table>
        </div>

        <div class="section">
            <div class="section-title">Recent Actions</div>
            <table>
                <tr><th>Time</th><th>User</th><th>Action</th><th>Reason</th><th>Moderator</th></tr>
                {actions_rows}
            </table>
        </div>
    </div>
</body>
</html>
"""

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

@app.route('/')
def home():
    return "Bot is alive"

@app.route('/dashboard')
def dashboard():
    try:
        conn = sqlite3.connect("modbot.db")
        c = conn.cursor()

        c.execute("SELECT COUNT(*) FROM mod_actions")
        total_actions = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM warnings")
        warned_users = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM mod_actions WHERE action LIKE '%ban%'")
        total_bans = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM mod_actions WHERE action LIKE '%timed out%' OR action LIKE '%timeout%' OR action LIKE '%mute%'")
        total_timeouts = c.fetchone()[0]

        c.execute("SELECT user_id, count FROM warnings ORDER BY count DESC LIMIT 10")
        top_warned = c.fetchall()

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

keep_alive()

# ================= CONFIG =================

TOKEN = os.getenv("TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

BASE_URL = "https://integrate.api.nvidia.com/v1"
LOG_CHANNEL_NAME = "mod-logs"

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
            command_prefix="!",
            intents=intents
        )

    async def setup_hook(self):

        await init_db()

        await self.tree.sync()

        print(f"✅ Logged in as {self.user}")
        print("✅ Slash commands synced")

bot = ModBot()

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

        cursor = await db.execute(
            "SELECT count FROM warnings WHERE user_id=?",
            (user_id,)
        )

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

        cursor = await db.execute(
            "SELECT count FROM warnings WHERE user_id=?",
            (user_id,)
        )

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

        cursor = await db.execute(
            "SELECT rules_text FROM rules WHERE guild_id=?",
            (guild_id,)
        )

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

    # Keep only messages from last 4 seconds
    user_message_buffer[user_id] = [
        (t, c, m) for t, c, m in user_message_buffer[user_id]
        if now - t <= 4.0
    ]

    recent = user_message_buffer[user_id]

    # Burst = 3+ messages where the gap between first and third is under 1.5s
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

        numbered = "\n".join(
            f'{i+1}. "{m}"' for i, m in enumerate(messages)
        )

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

INSULT_WORDS = [
    "stupid",
    "idiot",
    "moron",
    "dumbass",
    "loser",
    "fatass",
    "ugly",
    "worthless",
    "pathetic",
    "brainless",
    "dimwit",
    "imbecile"
]

TARGET_WORDS = [
    "you",
    "ur",
    "u ",
    "he ",
    "she ",
    "they ",
    "him",
    "her"
]

def is_direct_insult(content):
    lowered = content.lower()
    has_insult = any(word in lowered for word in INSULT_WORDS)
    has_target = any(t in lowered for t in TARGET_WORDS)
    return has_insult and has_target

def should_ai_scan(content):

    original = content
    lowered = content.lower()
    words = lowered.split()

    if len(words) < 3:
        return False

    suspicious_keywords = [
        "kill yourself", "kys", "stupid", "idiot", "retard",
        "dumbass", "bitch", "fuck you", "moron", "loser",
        "hate you", "die", "racist", "nazi", "fatass"
    ]

    if any(word in lowered for word in suspicious_keywords):
        return True

    if len(original) > 15:
        caps = sum(1 for c in original if c.isupper())
        letters = sum(1 for c in original if c.isalpha())
        if letters > 0 and (caps / letters) > 0.6:
            return True

    if lowered.count("!") >= 4 or lowered.count("?") >= 4:
        return True

    aggressive_words = ["fuck", "shit", "bitch", "asshole", "retard", "idiot"]
    aggression_score = sum(1 for word in aggressive_words if word in lowered)

    if aggression_score >= 1 and len(words) >= 5:
        return True

    return False

# ================= AI ANALYSIS =================

def analyze_message(text, rules=None):

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
                    "content": f"""You classify Discord messages.

Respond ONLY in this format:
LABEL|REASON

Labels: SAFE, TOXIC, SPAM

Reason must be under 10 words.
TOXIC means ANY insult, disrespect, or attack toward a person.
This includes: calling someone stupid, idiot, dumb, moron, ugly, loser, or any variation.
Even indirect or mild insults like "ur stupid" or "you're an idiot" = TOXIC.
Phrases like "ur a stupid idiot" are always TOXIC.
When in doubt, label TOXIC.
Be VERY STRICT. If server rules are provided and a rule is violated, cite the rule number.{rules_section}"""
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
                    "content": "You are a helpful Discord bot assistant. Answer questions clearly and concisely. Keep responses short and friendly unless detail is needed."
                },
                {
                    "role": "user",
                    "content": question
                }
            ],
            temperature=0.7
        )

        return response.choices[0].message.content.strip()

    except Exception as e:

        import traceback
        traceback.print_exc()
        return f"❌ Error: {str(e)}"

# ================= LOGGING =================

async def log_action(guild, msg):

    channel = discord.utils.get(
        guild.text_channels,
        name=LOG_CHANNEL_NAME
    )

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

            until = discord.utils.utcnow() + datetime.timedelta(
                minutes=duration_mins
            )

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

        msg = (
            f"🔇 {member.mention} was {action_desc}.\n"
            f"Reason: {reason}"
        )

        if isinstance(ctx, discord.Interaction):
            await ctx.followup.send(msg)
        else:
            await ctx.channel.send(msg)

        await log_action(
            member.guild,
            f"{member} | {action_desc} | {reason} | by {moderator}"
        )

        await store_action(
            member.guild.id,
            f"{member} ({member.id})",
            action_desc,
            reason,
            moderator
        )

    except discord.Forbidden:

        error = "❌ Cannot punish user. Check role hierarchy."

        if isinstance(ctx, discord.Interaction):
            await ctx.followup.send(error)
        else:
            await ctx.channel.send(error)

# ================= WARNING LOGIC =================

async def handle_warning_logic(ctx, member, warnings, reason, moderator="AutoMod"):

    if warnings == 1:

        msg = (
            f"⚠️ {member.mention}, first warning.\n"
            f"Reason: {reason}"
        )

        if isinstance(ctx, discord.Interaction):
            await ctx.followup.send(msg)
        else:
            await ctx.channel.send(msg)

        await store_action(
            member.guild.id,
            f"{member} ({member.id})",
            "warned (1st)",
            reason,
            moderator
        )

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

    await handle_warning_logic(
        interaction, member, count, reason,
        moderator=str(interaction.user)
    )


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

        await log_action(
            interaction.guild,
            f"{member} | timed out {duration}m | {reason} | by {interaction.user}"
        )

        await store_action(
            interaction.guild.id,
            f"{member} ({member.id})",
            f"timed out for {duration}m",
            reason,
            str(interaction.user)
        )

    except discord.Forbidden:
        await interaction.followup.send("❌ Cannot mute user. Check role hierarchy.")


@bot.tree.command(name="unmute", description="Remove a timeout from a user")
@app_commands.checks.has_permissions(moderate_members=True)
async def unmute(interaction: discord.Interaction, member: discord.Member):

    await interaction.response.defer()

    try:
        await member.timeout(None)

        await interaction.followup.send(
            f"🔊 {member.mention}'s timeout has been removed."
        )

        await log_action(
            interaction.guild,
            f"{member} | timeout removed | by {interaction.user}"
        )

        await store_action(
            interaction.guild.id,
            f"{member} ({member.id})",
            "unmuted",
            "Manual unmute",
            str(interaction.user)
        )

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

        await interaction.followup.send(
            f"👢 {member.mention} has been kicked.\nReason: {reason}"
        )

        await log_action(
            interaction.guild,
            f"{member} | kicked | {reason} | by {interaction.user}"
        )

        await store_action(
            interaction.guild.id,
            f"{member} ({member.id})",
            "kicked",
            reason,
            str(interaction.user)
        )

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

        await interaction.followup.send(
            f"🔨 {member.mention} has been banned.\nReason: {reason}"
        )

        await log_action(
            interaction.guild,
            f"{member} | banned | {reason} | by {interaction.user}"
        )

        await store_action(
            interaction.guild.id,
            f"{member} ({member.id})",
            "banned permanently",
            reason,
            str(interaction.user)
        )

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

    verdict, reason = await asyncio.to_thread(
        analyze_message, target_msg.content, rules
    )

    if verdict in ["TOXIC", "SPAM"]:

        try:
            await target_msg.delete()
        except:
            pass

        member = interaction.guild.get_member(target_msg.author.id)

        if member and can_warn(member.id):

            warnings = await add_warning(member.id)

            await handle_warning_logic(
                interaction, member, warnings,
                f"Reported: {reason}",
                moderator=str(interaction.user)
            )

        await interaction.followup.send(
            f"✅ Report confirmed. Action taken against {target_msg.author.mention}.\nReason: {reason}",
            ephemeral=True
        )

        await log_action(
            interaction.guild,
            f"Report by {interaction.user} | Target: {target_msg.author} | Verdict: {verdict} | Reason: {reason}"
        )

    else:

        await interaction.followup.send(
            f"✅ Report reviewed. Message deemed **{verdict}** — no action taken.",
            ephemeral=True
        )

        await log_action(
            interaction.guild,
            f"Report by {interaction.user} | Target: {target_msg.author} | Verdict: {verdict} (no action)"
        )


@bot.tree.command(name="clear_warnings", description="Clear warnings for a user")
@app_commands.checks.has_permissions(administrator=True)
async def clear_warnings(interaction: discord.Interaction, member: discord.Member):

    async with aiosqlite.connect("modbot.db") as db:
        await db.execute("DELETE FROM warnings WHERE user_id=?", (member.id,))
        await db.commit()

    await interaction.response.send_message(
        f"✅ Cleared warnings for {member.mention}"
    )

    await store_action(
        interaction.guild.id,
        f"{member} ({member.id})",
        "warnings cleared",
        "Manual clear",
        str(interaction.user)
    )

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
        await interaction.response.send_message(
            f"📋 **Server Rules:**\n{r}",
            ephemeral=True
        )
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

    if bot.user in message.mentions:

        if message.reference and message.reference.message_id:

            try:
                replied_msg = await message.channel.fetch_message(
                    message.reference.message_id
                )
            except:
                replied_msg = None

            if replied_msg and not replied_msg.author.bot:

                rules = await get_rules(message.guild.id)

                verdict, reason = await asyncio.to_thread(
                    analyze_message, replied_msg.content, rules
                )

                if verdict in ["TOXIC", "SPAM"]:

                    try:
                        await replied_msg.delete()
                    except:
                        pass

                    member = message.guild.get_member(replied_msg.author.id)

                    if member and can_warn(member.id):

                        warnings = await add_warning(member.id)

                        await handle_warning_logic(
                            message, member, warnings,
                            f"Reported via mention: {reason}",
                            moderator=str(message.author)
                        )

                    await log_action(
                        message.guild,
                        f"Mention-report by {message.author} | Target: {replied_msg.author} | Verdict: {verdict} | {reason}"
                    )

                else:
                    await message.channel.send(
                        f"✅ Message reviewed — deemed **{verdict}**. No action taken."
                    )

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
- `@Mod.AI [prompt]: Ask the AI a question

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

    if any(word in lowered for word in BAD_WORDS):

        try:
            await message.delete()
        except:
            pass

        if can_warn(message.author.id):
            warnings = await add_warning(message.author.id)
            await handle_warning_logic(message, message.author, warnings, "Slur usage")

        return

    # ================= AI SPAM DETECTION =================

    burst_messages, burst_objects = record_message(
        message.author.id,
        message.content,
        message
    )

    if burst_messages:

        verdict, reason = await asyncio.to_thread(
            check_spam_ai, burst_messages
        )

        if verdict == "SPAM":

            # Delete all buffered messages from the burst
            for msg_obj in burst_objects:
                try:
                    await msg_obj.delete()
                except:
                    pass

            # Clear buffer so we don't re-trigger
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

        verdict, reason = await asyncio.to_thread(
            analyze_message, message.content, rules
        )

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

# ================= RUN =================

bot.run(TOKEN)