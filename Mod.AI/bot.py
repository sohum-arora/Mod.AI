import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import time
import re
import datetime
import asyncio
from openai import OpenAI
import os

from flask import Flask
from threading import Thread
import os

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive"

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

BASE_URL = "https://api.openai.com/v1"
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

        # GLOBAL SYNC
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

# ================= SPAM TRACKING =================

user_data = {}
warning_cooldowns = {}

def check_spam_strict(user_id):

    now = time.time()

    if user_id not in user_data:
        user_data[user_id] = [now, 1]
        return False

    last_time, count = user_data[user_id]

    # 3 messages under 1.5s
    if now - last_time < 1.5:

        user_data[user_id][1] += 1
        user_data[user_id][0] = now

        return user_data[user_id][1] >= 3

    else:

        user_data[user_id] = [now, 1]
        return False

def can_warn(user_id):

    now = time.time()

    if user_id not in warning_cooldowns:
        warning_cooldowns[user_id] = now
        return True

    if now - warning_cooldowns[user_id] > 10:
        warning_cooldowns[user_id] = now
        return True

    return False

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

    # Ignore extremely tiny messages
    if len(words) < 3:
        return False

    # Hard suspicious keywords
    suspicious_keywords = [
        "kill yourself",
        "kys",
        "stupid",
        "idiot",
        "retard",
        "dumbass",
        "bitch",
        "fuck you",
        "moron",
        "loser",
        "hate you",
        "die",
        "racist",
        "nazi",
        "fatass"
    ]

    if any(word in lowered for word in suspicious_keywords):
        return True

    # CAPS DETECTION
    if len(original) > 15:

        caps = sum(1 for c in original if c.isupper())
        letters = sum(1 for c in original if c.isalpha())

        if letters > 0 and (caps / letters) > 0.6:
            return True

    # Excessive punctuation
    if (
        lowered.count("!") >= 4 or
        lowered.count("?") >= 4
    ):
        return True

    # Long aggressive messages
    aggressive_words = [
        "fuck",
        "shit",
        "bitch",
        "asshole",
        "retard",
        "idiot"
    ]

    aggression_score = sum(
        1 for word in aggressive_words
        if word in lowered
    )

    if aggression_score >= 1 and len(words) >= 5:
        return True

    return False

# ================= AI ANALYSIS =================

def analyze_message(text):

    try:

        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {
                    "role": "system",
                    "content": """
You classify Discord messages.

Respond ONLY in this format:

LABEL|REASON

Labels:
SAFE
TOXIC
SPAM

Reason must be under 5 words.
TOXIC means ANY insult, disrespect, or attack toward a person.
This includes: calling someone stupid, idiot, dumb, moron, ugly, loser, or any variation.
Even indirect or mild insults like "ur stupid" or "you're an idiot" = TOXIC.
Phrases like "ur a stupid idiot" are always TOXIC.
When in doubt, label TOXIC.
"""
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

        return (
            label.strip().upper(),
            reason.strip()
        )

    except Exception as e:

        print("AI ERROR:", e)

        return ("SAFE", "analysis error")

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
    reason="Violation"
):

    try:

        if action == "timeout":

            until = discord.utils.utcnow() + datetime.timedelta(
                minutes=duration_mins
            )

            await member.timeout(
                until,
                reason=reason
            )

            action_desc = f"timed out for {duration_mins}m"

        elif action == "ban":
            await member.ban(reason=reason)
            action_desc = "banned permanently"

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
            f"{member} | {action_desc} | {reason}"
        )

    except discord.Forbidden:

        error = "❌ Cannot punish user. Check role hierarchy."

        if isinstance(ctx, discord.Interaction):
            await ctx.followup.send(error)
        else:
            await ctx.channel.send(error)

# ================= WARNING LOGIC =================

async def handle_warning_logic(
    ctx,
    member,
    warnings,
    reason
):

    if warnings == 1:

        msg = (
            f"⚠️ {member.mention}, first warning.\n"
            f"Reason: {reason}"
        )

        if isinstance(ctx, discord.Interaction):
            await ctx.followup.send(msg)
        else:
            await ctx.channel.send(msg)

    elif warnings == 2:

        await apply_punishment(
            ctx,
            member,
            "timeout",
            30,
            reason
        )

    elif warnings == 3:

        await apply_punishment(
            ctx,
            member,
            "timeout",
            120,
            reason
        )

    elif warnings == 4:

        await apply_punishment(
            ctx,
            member,
            "timeout",
            1440,
            reason
        )

    else:

        await apply_punishment(
            ctx,
            member,
            "ban",
            reason="Excessive violations"
        )

# ================= SLASH COMMANDS =================

@bot.tree.command(
    name="warn",
    description="Warn a user"
)
@app_commands.checks.has_permissions(
    moderate_members=True
)
async def warn(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str
):

    await interaction.response.defer()

    if member == interaction.user:

        return await interaction.followup.send(
            "❌ You cannot warn yourself."
        )

    if member == bot.user:

        return await interaction.followup.send(
            "❌ Nice try."
        )

    count = await add_warning(member.id)

    await handle_warning_logic(
        interaction,
        member,
        count,
        reason
    )

@bot.tree.command(
    name="report",
    description="Report a message by its ID for AI review"
)
async def report(
    interaction: discord.Interaction,
    message_id: str
):

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

    verdict, reason = await asyncio.to_thread(
        analyze_message,
        target_msg.content
    )

    if verdict in ["TOXIC", "SPAM"]:

        try:
            await target_msg.delete()
        except:
            pass

        member = interaction.guild.get_member(target_msg.author.id)

        if member:

            if can_warn(member.id):

                warnings = await add_warning(member.id)

                await handle_warning_logic(
                    interaction,
                    member,
                    warnings,
                    f"Reported: {reason}"
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
            f"✅ Report reviewed. Message was deemed **{verdict}** — no action taken.",
            ephemeral=True
        )

        await log_action(
            interaction.guild,
            f"Report by {interaction.user} | Target: {target_msg.author} | Verdict: {verdict} (no action)"
        )


@bot.tree.command(
    name="clear_warnings",
    description="Clear warnings"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def clear_warnings(
    interaction: discord.Interaction,
    member: discord.Member
):

    async with aiosqlite.connect("modbot.db") as db:

        await db.execute(
            "DELETE FROM warnings WHERE user_id=?",
            (member.id,)
        )

        await db.commit()

    await interaction.response.send_message(
        f"✅ Cleared warnings for {member.mention}"
    )

# ================= AUTO MOD =================

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    lowered = message.content.lower()

    # ================= BOT MENTION HANDLING =================

    if bot.user in message.mentions:

        # Reply to a message → report it
        if message.reference and message.reference.message_id:

            try:
                replied_msg = await message.channel.fetch_message(
                    message.reference.message_id
                )
            except:
                replied_msg = None

            if replied_msg and not replied_msg.author.bot:

                verdict, reason = await asyncio.to_thread(
                    analyze_message,
                    replied_msg.content
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
                            message,
                            member,
                            warnings,
                            f"Reported via mention: {reason}"
                        )

                    await log_action(
                        message.guild,
                        f"Mention-report by {message.author} | Target: {replied_msg.author} | Verdict: {verdict} | Reason: {reason}"
                    )

                else:

                    await message.channel.send(
                        f"✅ Message reviewed — deemed **{verdict}**. No action taken."
                    )

            elif replied_msg and replied_msg.author.bot:
                await message.channel.send("❌ Cannot report bot messages.")

        else:

            # Not a reply — generic response
            await message.channel.send(
                "I'm here to help! Use the `/report` command to report a message or ping me in a reply to a message to report :)"
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

            warnings = await add_warning(
                message.author.id
            )

            await handle_warning_logic(
                message,
                message.author,
                warnings,
                "Slur usage"
            )

        return

    # ================= FLOOD SPAM =================

    if check_spam_strict(message.author.id):

        try:
            await message.delete()
        except:
            pass

        if can_warn(message.author.id):

            warnings = await add_warning(
                message.author.id
            )

            await handle_warning_logic(
                message,
                message.author,
                warnings,
                "Rapid spam"
            )

        return

    # ================= SCAM FILTER =================

    for pattern in SCAM_PATTERNS:

        if re.search(pattern, lowered):

            try:
                await message.delete()
            except:
                pass

            if can_warn(message.author.id):

                warnings = await add_warning(
                    message.author.id
                )

                await handle_warning_logic(
                    message,
                    message.author,
                    warnings,
                    "Suspicious links/scam"
                )

            return

    # ================= DIRECT INSULT FILTER =================

    if is_direct_insult(message.content):

        try:
            await message.delete()
        except:
            pass

        if can_warn(message.author.id):

            warnings = await add_warning(
                message.author.id
            )

            await handle_warning_logic(
                message,
                message.author,
                warnings,
                "Personal insult"
            )

        return

    # ================= AI MODERATION =================

    if should_ai_scan(message.content):

        verdict, reason = await asyncio.to_thread(
            analyze_message,
            message.content
        )

        if verdict in ["TOXIC", "SPAM"]:

            try:
                await message.delete()
            except:
                pass

            if can_warn(message.author.id):

                warnings = await add_warning(
                    message.author.id
                )

                await handle_warning_logic(
                    message,
                    message.author,
                    warnings,
                    reason
                )

            return

    await bot.process_commands(message)

# ================= RUN =================

bot.run(TOKEN)