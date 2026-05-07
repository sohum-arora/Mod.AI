import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import time
import re
import datetime
import asyncio
from openai import OpenAI

# ================= CONFIG =================

TOKEN = "MTUwMTIxNTEzMzM0NTY0ODgwMQ.GGDK_a.BHKErNwxlrgZj9MW2iYxdFxEUnul-MXw5_JgGo"
OPENAI_API_KEY = "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"

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

def should_ai_scan(content):

    content = content.lower()

    # IGNORE SHORT MESSAGES
    if len(content) < 12:
        return False

    # CAPS DETECTION
    if len(content) > 20:

        caps = sum(1 for c in content if c.isupper())

        if caps / len(content) > 0.7:
            return True

    # EXCESSIVE PUNCTUATION
    if content.count("!") >= 5:
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