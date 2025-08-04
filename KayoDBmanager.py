import discord
import subprocess
import os
import asyncio
import random
import psutil
import json
from pathlib import Path
import pygetwindow as gw
import re

# =================== CONFIG ===================
TOKEN = 'enter your discord bot token'
SCRIPTS_DIR = Path(r'Replace with path of account batch files')
STATS_DIR = Path(r'replace with path of kayoflipper stats directory')
MIN_DELAY = 180  # seconds (3 min)
MAX_DELAY = 600  # seconds (10 min)
# ==============================================

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

cancel_event = asyncio.Event()

def get_all_usernames():
    return [f.stem.lower() for f in SCRIPTS_DIR.glob("*.bat")]

def read_stats(username):
    path = STATS_DIR / f"{username}.json"
    if path.exists():
        try:
            with open(path) as f:
                data = json.load(f)
                return int(data.get("profit", 0)), int(data.get("profitPerHour", 0))
        except:
            return 0, 0
    return 0, 0

def get_bot_statuses():
    statuses = {}
    all_usernames = get_all_usernames()

    for username in all_usernames:
        statuses[username] = ("🔴 Not running", None)

    for window_title in gw.getAllTitles():
        if not window_title.lower().startswith("dreambot"):
            continue

        match_full = re.match(r"DreamBot .*? - ([^-]+?) - (.+)", window_title)
        if match_full:
            username = match_full.group(1).strip().lower()
            script = match_full.group(2).strip()
            if username in statuses:
                statuses[username] = ("🟢 Running", script)
            continue

        match_idle = re.match(r"DreamBot .*? - ([^-]+?)$", window_title)
        if match_idle:
            username = match_idle.group(1).strip().lower()
            if username in statuses and statuses[username][0] == "🔴 Not running":
                statuses[username] = ("🟡 Idle", None)

    return statuses

def stop_bot(username):
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['cmdline'] and any(username.lower() in arg.lower() for arg in proc.info['cmdline'] if isinstance(arg, str)):
                proc.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

def start_bot(username):
    bat_path = SCRIPTS_DIR / f"{username}.bat"
    if bat_path.exists():
        subprocess.Popen(
            ["cmd.exe", "/c", "start", "/min", str(bat_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

@client.event
async def on_ready():
    print(f'✅ Logged in as {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    content = message.content.strip().lower()

    if content == '!cancel':
        cancel_event.set()
        await message.channel.send("🛑 Cancel signal sent. Current operation will halt before next action.")

    elif content == '!run all':
        cancel_event.clear()
        all_usernames = get_all_usernames()
        running_set = [u for u, (status, _) in get_bot_statuses().items() if status == "🟢 Running"]

        to_start = [u for u in all_usernames if u not in running_set]
        if not to_start:
            await message.channel.send("✅ All bots are already running.")
            return

        random.shuffle(to_start)
        await message.channel.send(f"🚀 Starting {len(to_start)} bots with staggered delays...")

        for username in to_start:
            if cancel_event.is_set():
                await message.channel.send("⛔ Launching cancelled.")
                return

            start_bot(username)
            await message.channel.send(f"🔼 Started `{username}`")

            delay = random.randint(MIN_DELAY, MAX_DELAY)
            await message.channel.send(f"⏳ Waiting {delay} seconds before next...")
            await asyncio.sleep(delay)

        await message.channel.send("✅ All eligible bots have been launched.")

    elif content == '!status':
        bot_statuses = get_bot_statuses()

        total_profit = 0
        total_profit_hr = 0
        total_running = 0

        lines = ["Username         | Status"]
        lines.append("-----------------|--------------------------------------------------")

        for username, (status, script) in bot_statuses.items():
            profit, profit_per_hr = read_stats(username)
            total_profit += profit
            total_profit_hr += profit_per_hr
            if status == "🟢 Running":
                total_running += 1

            stats_str = f"💰 {profit:,} | ⏱️ {profit_per_hr:,}/hr" if profit > 0 else ""
            if script:
                lines.append(f"{username:<16} | {status} {script} {stats_str}")
            else:
                lines.append(f"{username:<16} | {status} {stats_str}")

        lines.append("\n")
        lines.append(f"Total Bots Running: {total_running}")
        lines.append(f"Total Profit: 💰 {total_profit:,}")
        lines.append(f"Total Profit/Hour: ⏱️ {total_profit_hr:,}/hr")

        await message.channel.send("```\n" + "\n".join(lines) + "\n```")

    elif content == '!stop all':
        cancel_event.clear()
        running = [u for u, (status, _) in get_bot_statuses().items() if status == "🟢 Running"]
        if not running:
            await message.channel.send("✅ No bots are currently running.")
            return

        random.shuffle(running)
        await message.channel.send(f"🛑 Stopping {len(running)} running bots...")

        for username in running:
            if cancel_event.is_set():
                await message.channel.send("⛔ Stop process cancelled.")
                return

            stop_bot(username)
            await message.channel.send(f"🔻 Stopped `{username}`")

            delay = random.randint(MIN_DELAY, MAX_DELAY)
            await message.channel.send(f"⏳ Waiting {delay} seconds before next...")
            await asyncio.sleep(delay)

        await message.channel.send("✅ All running bots have been stopped.")

    elif content.startswith('!run '):
        username = content.replace('!run ', '').strip().lower()
        if username in get_all_usernames():
            current_status, _ = get_bot_statuses().get(username, ("🔴 Not running", None))
            if current_status == "🟢 Running":
                await message.channel.send(f"⚠️ `{username}` is already running.")
            else:
                start_bot(username)
                await message.channel.send(f"✅ Launched `{username}`.")
        else:
            await message.channel.send(f"❌ `{username}` not found in script folder.")

    elif content.startswith('!stop '):
        username = content.replace('!stop ', '').strip().lower()
        current_status, _ = get_bot_statuses().get(username, ("🔴 Not running", None))
        if current_status == "🟢 Running":
            stop_bot(username)
            await message.channel.send(f"🛑 Stopped `{username}`.")
        else:
            await message.channel.send(f"❌ `{username}` is not currently running.")

client.run(TOKEN)
