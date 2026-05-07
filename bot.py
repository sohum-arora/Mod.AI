import discord
from discord.ext import commands
import aiosqlite
import time
import re
from openai import OpenAI

# ===== CONFIG =====
TOKEN = "MTUwMTIxNTEzMzM0NTY0ODgwMQ.GCXHjn.o3uykRmzl3lUeQnkhFZ3JPVlUCNs99-1AR_Zq8"
OPENAI_API_KEY = "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"
BASE_URL = "https://api.openai.com/v1"
LOG_CHANNEL_NAME = "mod-logs"

client = OpenAI(api_key=OPENAI_API_KEY, base_url=BASE_URL)

# ===== SPAM TRACKING =====
user_data = {} # Stores {user_id: [last_timestamp, count]}

def check_spam_threshold(user_id):
    now = time.time()
    if user_id not in user_data:
        user_data[user_id] = [now, 1]
        return False
    
    last_time, count = user_data[user_id]
    
    if now - last_time < 2.0:  # If sent within 2 seconds
        user_data[user_id][1] += 1
        user_data[user_id][0] = now
        return user_data[user_id][1] > 3 # Trigger after 3 fast messages
    else:
        user_data[user_id] = [now, 1] # Reset if they slowed down
        return False

# ===== AI ANALYSIS =====
def analyze_message(text):
    if len(text) < 5 or text.startswith("!"): # Don't analyze short texts or commands
        return ("SAFE", "too short")

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Classify: LABEL|REASON. Labels: SAFE, TOXIC, SPAM. Reason: 5 words max."},
                {"role": "user", "content": text}
            ],
            temperature=0
        )
        output = response.choices[0].message.content.strip()
        if "|" not in output: return ("SAFE", "format error")
        
        label, reason = output.split("|", 1)
        return label.strip().upper(), reason.strip()
    except:
        return ("SAFE", "error fallback")

# ===== DISCORD SETUP =====
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ===== DATABASE FUNCTIONS =====
async def init_db():
    async with aiosqlite.connect("modbot.db") as db:
        await db.execute("CREATE TABLE IF NOT EXISTS warnings (user_id INTEGER PRIMARY KEY, count INTEGER)")
        await db.commit()

async def add_warning(user_id):
    async with aiosqlite.connect("modbot.db") as db:
        cursor = await db.execute("SELECT count FROM warnings WHERE user_id=?", (user_id,))
        row = await cursor.fetchone()
        new_count = (row[0] + 1) if row else 1
        await db.execute("INSERT OR REPLACE INTO warnings VALUES (?, ?)", (user_id, new_count))
        await db.commit()
        return new_count

# ===== UTILS =====
async def log_action(guild, msg):
    channel = discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)
    if channel:
        await channel.send(f"**[LOG]** {msg}")

async def punish_with_carl(message, action, duration=None, reason="violation"):
    # Prevents bot from responding to itself or looping
    cmd = f"!{action} {message.author.mention} {duration if duration else ''} {reason}".replace("  ", " ")
    await message.channel.send(cmd)
    await log_action(message.guild, f"Action: {action} | Target: {message.author} | Reason: {reason}")

async def handle_punishment(message, warnings, reason):
    if warnings == 1:
        await message.channel.send(f"{message.author.mention} warned: {reason}")
    elif warnings <= 3:
        await punish_with_carl(message, "mute", "30m" if warnings==2 else "2h", reason)
    elif warnings <= 5:
        await punish_with_carl(message, "mute", "1d", reason)
    else:
        await punish_with_carl(message, "ban", "7d", reason)

# ===== EVENTS =====
@bot.event
async def on_ready():
    await init_db()
    print(f"Logged in as {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # 1. Process commands first
    if message.content.startswith("!"):
        await bot.process_commands(message)
        return

    # 2. Check for Flood Spam
    if check_spam_threshold(message.author.id):
        try: await message.delete() 
        except: pass
        # Only punish if they keep doing it
        if user_data[message.author.id][1] == 5: 
            await punish_with_carl(message, "mute", "10m", "Stop spamming messages")
        return

    # 3. Check for Link/Scam Regex
    if re.search(r"(free money|click here|http[s]?://)", message.content.lower()):
        try: await message.delete()
        except: pass
        await punish_with_carl(message, "mute", "30m", "Suspicious links")
        return

    # 4. AI Analysis for Toxicity
    verdict, reason = analyze_message(message.content)
    if verdict in ["TOXIC", "SPAM"]:
        try: await message.delete()
        except: pass
        
        if verdict == "TOXIC":
            warnings = await add_warning(message.author.id)
            await handle_punishment(message, warnings, reason)
        else:
            await punish_with_carl(message, "mute", "30m", reason)

bot.run(TOKEN)